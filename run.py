#!/usr/bin/env python3
"""NOVIX - ASHA SAATHI AI 2.0: safe one-command launcher for LOCAL DEVELOPMENT.

    py run.py                 start whatever is missing, then stream logs (Ctrl+C to leave)
    py run.py --status        show health only; changes nothing
    py run.py --backend-only  make sure db + api are up, stream their logs, no frontend
    py run.py --no-build      never build Docker images (fail instead if one is missing)
    py run.py --lan           serve the dev frontend on all interfaces (phone on the same Wi-Fi)
    py run.py --stop          stop the db and api containers (refused while the demo tunnel is up)

Safety rules this launcher follows:
  * Healthy containers are never restarted, recreated or rebuilt. Stopped ones are only started.
  * The database is never reset, reseeded or replaced; migrations run only through the existing
    `migrate` service (alembic upgrade head) and never while the public demo is active.
  * Ctrl+C stops only what this launcher started (the Vite dev server and log followers).
    Docker containers keep running.
  * Secrets from .env, cookies, tokens and passwords are redacted from everything it prints.
  * When the Cloudflare demo (cloudflared, or the deploy/tunnel proxy) is running, anything that
    could interrupt it is refused.

Standard library only. Not for public hosting: see docs/LOCAL_DEVELOPMENT.md.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence, TextIO

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"

API_HEALTH_URL = "http://127.0.0.1:8000/api/health"
VITE_PORT = 5173
CORE_SERVICES = ("db", "api")  # start order
REQUIRED_ENV = ("POSTGRES_PASSWORD",)
RECOMMENDED_ENV = {"GNANI_API_KEY": "voice visits (Gnani speech) will not work"}
SHOWN_FLAGS = ("V2_VOICE_ENABLED", "GEMINI_EXTRACTION_ENABLED", "LEGACY_ROUND1_API_ENABLED")
DEMO_PROXY_PROJECT = "asha-saathi-tunnel"
SECRET_KEY_PATTERN = re.compile(r"(?i)(KEY|PASSWORD|PASSWD|SECRET|TOKEN|DSN|DATABASE_URL|CREDENTIAL)")
ANSI = re.compile(r"\[[0-9;?]*[A-Za-z]")
HEALTH_TIMEOUT_S = 180
VITE_TIMEOUT_S = 90

EXIT_OK, EXIT_FAIL, EXIT_PREREQ, EXIT_REFUSED = 0, 1, 2, 3


# ----------------------------------------------------------------------------- redaction
class Redactor:
    """Masks secrets in any text before it is printed."""

    PATTERNS: Sequence[tuple[re.Pattern[str], str]] = (
        (re.compile(r"(?i)\b(cookie|set-cookie|authorization|proxy-authorization|x-api-key|api-key)\s*:\s*.+"),
         r"\1: [redacted]"),
        (re.compile(r"(?i)\b(asha_session|session|sessionid|csrftoken|cf_authorization)=([^;\s&]+)"),
         r"\1=[redacted]"),
        (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [redacted]"),
        (re.compile(r"\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}"), "[redacted-jwt]"),
        (re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"), "[redacted-key]"),
        (re.compile(r"\b(sk|pk|rk|ghp|gho|xox[abp])[-_][A-Za-z0-9_-]{16,}"), "[redacted-key]"),
        (re.compile(r"([a-z][a-z0-9+.-]*://[^:/\s@]+:)([^@\s]+)(@)", re.I), r"\1[redacted]\3"),
        (re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|private[_-]?key)\b(\"?\s*[=:]\s*)"
                    r"(\"[^\"]*\"|'[^']*'|[^\s,;&]+)"), r"\1\2[redacted]"),
    )

    def __init__(self, secret_values: Iterable[str] = ()) -> None:
        self.secret_values = sorted({v for v in secret_values if v and len(v) >= 6}, key=len, reverse=True)

    def __call__(self, text: str) -> str:
        for value in self.secret_values:
            text = text.replace(value, "[redacted]")
        for pattern, replacement in self.PATTERNS:
            text = pattern.sub(replacement, text)
        return text


# ----------------------------------------------------------------------------- helpers
def read_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines. Values are returned for checks and redaction only, never printed."""
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[key] = value
    return values


def http_get(url: str, timeout: float = 3.0) -> tuple[int, str]:
    """GET url; returns (status, start of body). Certificate checks are skipped only for localhost."""
    context = None
    if url.startswith("https://"):
        context = ssl.create_default_context()
        if re.match(r"https://(localhost|127\.0\.0\.1)(:|/)", url):
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=timeout, context=context) as resp:
            return resp.status, resp.read(8192).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception:
        return 0, ""


def port_in_use(port: int) -> bool:
    """True if anything listens on localhost:port (IPv4 or IPv6)."""
    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                if sock.connect_ex((host, port)) == 0:
                    return True
        except OSError:
            continue
    return False


@dataclass(frozen=True)
class Service:
    state: str  # running, exited, created, paused, restarting, dead
    health: str  # healthy, unhealthy, starting, or "" when there is no healthcheck
    name: str = ""

    @property
    def healthy(self) -> bool:
        return self.state == "running" and self.health in ("healthy", "")


def parse_compose_ps(text: str) -> dict[str, Service]:
    """`docker compose ps --format json` prints a JSON array (older) or one object per line (newer)."""
    text = text.strip()
    if not text:
        return {}
    items = json.loads(text) if text.startswith("[") else [json.loads(l) for l in text.splitlines() if l.strip()]
    return {
        i["Service"]: Service(str(i.get("State", "")).lower(), str(i.get("Health") or "").lower(), i.get("Name", ""))
        for i in items
        if i.get("Service")
    }


class Runner:
    """Thin subprocess wrapper; replaced by a fake in tests."""

    def which(self, name: str) -> Optional[str]:
        return shutil.which(name)

    def run(self, args: Sequence[str], timeout: float = 60, cwd: Path = ROOT) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=timeout)
        except FileNotFoundError:
            return subprocess.CompletedProcess(list(args), 127, "", f"{args[0]}: not found")
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(list(args), 124, "", f"{args[0]}: timed out after {timeout}s")

    def popen(self, args: Sequence[str], cwd: Path = ROOT, env: Optional[dict[str, str]] = None) -> subprocess.Popen:
        kwargs: dict = {}
        if os.name == "nt":  # Ctrl+C must reach only this launcher; it then stops its own children
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        return subprocess.Popen(list(args), cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                                bufsize=1, **kwargs)

    def kill_tree(self, proc: subprocess.Popen) -> None:
        """Stop a child and everything it started (npm -> node on Windows)."""
        if proc.poll() is not None:
            return
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=15)
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


# ----------------------------------------------------------------------------- launcher
class LauncherError(Exception):
    def __init__(self, message: str, code: int = EXIT_FAIL) -> None:
        super().__init__(message)
        self.code = code


class Launcher:
    def __init__(self, args: argparse.Namespace, runner: Optional[Runner] = None,
                 http: Callable[[str], tuple[int, str]] = http_get,
                 port_check: Callable[[int], bool] = port_in_use,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 out: TextIO = sys.stdout, env_file: Path = ENV_FILE) -> None:
        self.args = args
        self.runner = runner or Runner()
        self.http = http
        self.port_check = port_check
        self.sleep = sleep
        self.clock = clock
        self.out = out
        self.env_file = env_file
        self.redact = Redactor()
        self.env: dict[str, str] = {}
        self.children: list[subprocess.Popen] = []
        self.vite: Optional[subprocess.Popen] = None
        self.demo_reasons: list[str] = []
        self._lock = threading.Lock()
        self._threads: list[threading.Thread] = []

    # -- output
    def say(self, text: str = "") -> None:
        with self._lock:
            print(self.redact(text), file=self.out, flush=True)

    def log_line(self, label: str, line: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.say(f"{stamp} {label:<4}| {ANSI.sub('', line).rstrip()}")

    # -- checks
    def check_python(self) -> None:
        if sys.version_info < (3, 9):
            raise LauncherError("Python 3.9 or newer is required.", EXIT_PREREQ)

    def check_config(self) -> None:
        if not self.env_file.exists():
            hint = "Copy-Item .env.example .env" if os.name == "nt" else "cp .env.example .env"
            raise LauncherError(f"Missing {self.env_file.name} at the repository root. Create it with `{hint}` "
                                "and fill in the values (never commit it).", EXIT_PREREQ)
        self.env = read_env_file(self.env_file)
        self.redact = Redactor(v for k, v in self.env.items() if SECRET_KEY_PATTERN.search(k))
        missing = [k for k in REQUIRED_ENV if not self.env.get(k)]
        if missing:
            raise LauncherError(f".env is missing required values: {', '.join(missing)}", EXIT_PREREQ)
        parts = [f"{k} set" for k in REQUIRED_ENV]
        for key, effect in RECOMMENDED_ENV.items():
            parts.append(f"{key} set" if self.env.get(key) else f"{key} MISSING ({effect})")
        for flag in SHOWN_FLAGS:
            value = self.env.get(flag, "").lower()
            if value in ("true", "false"):
                parts.append(f"{flag}={value}")
        self.say(f"Config     .env found: {'; '.join(parts)}")

    def check_docker(self) -> None:
        if not self.runner.which("docker"):
            raise LauncherError("Docker is not installed or not on PATH. Install Docker Desktop.", EXIT_PREREQ)
        info = self.runner.run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=30)
        if info.returncode != 0:
            raise LauncherError("Docker is installed but its engine is not running. Start Docker Desktop, wait "
                                "until it says 'Engine running', then try again.", EXIT_PREREQ)
        compose = self.runner.run(["docker", "compose", "version", "--short"], timeout=30)
        if compose.returncode != 0:
            raise LauncherError("Docker Compose v2 is missing (`docker compose`). Update Docker Desktop.", EXIT_PREREQ)
        self._docker_versions = (info.stdout.strip(), compose.stdout.strip())

    def check_node(self) -> tuple[str, str]:
        node, npm = self.runner.which("node"), self.runner.which("npm")
        if not node or not npm:
            raise LauncherError("Node.js and npm are required for the frontend (Node 20+). Install Node.js LTS, "
                                "or use --backend-only.", EXIT_PREREQ)
        node_v = self.runner.run([node, "--version"], timeout=30).stdout.strip()
        npm_v = self.runner.run([npm, "--version"], timeout=30).stdout.strip()
        return node_v, npm_v

    def detect_demo(self) -> list[str]:
        reasons: list[str] = []
        if os.name == "nt":
            res = self.runner.run(["tasklist", "/FI", "IMAGENAME eq cloudflared.exe", "/FO", "CSV", "/NH"], timeout=30)
            running = "cloudflared.exe" in res.stdout.lower()
        else:
            running = self.runner.run(["pgrep", "-x", "cloudflared"], timeout=30).returncode == 0
        if running:
            reasons.append("cloudflared is running")
        res = self.runner.run(["docker", "ps", "--filter", f"label=com.docker.compose.project={DEMO_PROXY_PROJECT}",
                               "--format", "{{.Names}}"], timeout=30)
        if res.returncode == 0 and res.stdout.strip():
            reasons.append("the deploy/tunnel demo proxy is running")
        self.demo_reasons = reasons
        return reasons

    @property
    def demo_active(self) -> bool:
        return bool(self.demo_reasons)

    # -- docker state
    def compose(self, *args: str, timeout: float = 300) -> subprocess.CompletedProcess:
        return self.runner.run(["docker", "compose", *args], timeout=timeout)

    def services(self) -> dict[str, Service]:
        res = self.compose("ps", "-a", "--format", "json", timeout=60)
        if res.returncode != 0:
            raise LauncherError("`docker compose ps` failed: " + self.redact(res.stderr.strip()[:300]))
        return parse_compose_ps(res.stdout)

    def api_ok(self) -> bool:
        status, body = self.http(API_HEALTH_URL)
        if status != 200:
            return False
        try:
            data = json.loads(body)
        except ValueError:
            return False
        return data.get("status") == "ok" and data.get("database_ok", True) is not False

    def describe_services(self, svcs: dict[str, Service]) -> str:
        parts = []
        for name in CORE_SERVICES:
            svc = svcs.get(name)
            if not svc:
                parts.append(f"{name} not created")
            else:
                parts.append(f"{name} {svc.state}" + (f" ({svc.health})" if svc.health else ""))
        parts.append("API health ok" if self.api_ok() else "API health not answering")
        return " | ".join(parts)

    # -- backend
    def ensure_backend(self) -> None:
        svcs = self.services()
        if all(svcs.get(s) and svcs[s].healthy for s in CORE_SERVICES) and self.api_ok():
            self.say("Backend    db and api are already healthy: not restarting or rebuilding them.")
        else:
            stopped = [s for s in CORE_SERVICES if svcs.get(s) and svcs[s].state in ("exited", "created", "dead")]
            paused = [s for s in CORE_SERVICES if svcs.get(s) and svcs[s].state == "paused"]
            missing = [s for s in CORE_SERVICES if s not in svcs]
            if paused:
                self.say(f"Backend    unpausing: {', '.join(paused)}")
                self._must(self.compose("unpause", *paused), "unpause")
            if stopped:
                self.say(f"Backend    starting stopped containers (no rebuild, no recreate): {', '.join(stopped)}")
                self._must(self.compose("start", *stopped), "start")
            if missing:
                cmd = ["up", "-d", "--no-recreate"]
                if self.args.no_build or self.demo_active:
                    cmd.append("--no-build")
                self.say(f"Backend    creating missing services with the existing Compose file: {', '.join(missing)}"
                         + ("" if "--no-build" in cmd else " (images are built only if absent)"))
                self._must(self.compose(*cmd, *missing, timeout=900), "up")
            if not (stopped or paused or missing):
                self.say("Backend    containers are running but not healthy yet: waiting.")
            self.wait_backend()
        self.check_migrations()

    def _must(self, res: subprocess.CompletedProcess, what: str) -> None:
        if res.returncode != 0:
            detail = self.redact((res.stderr or res.stdout).strip()[-600:])
            raise LauncherError(f"`docker compose {what}` failed:\n{detail}\nSee: docker compose logs api db")

    def wait_backend(self, timeout: float = HEALTH_TIMEOUT_S) -> None:
        deadline = self.clock() + timeout
        last = ""
        while True:
            svcs = self.services()
            if all(svcs.get(s) and svcs[s].healthy for s in CORE_SERVICES) and self.api_ok():
                self.say("Backend    healthy: " + self.describe_services(svcs))
                return
            dead = [s for s in CORE_SERVICES if svcs.get(s) and svcs[s].state in ("exited", "dead")]
            if dead:
                raise LauncherError(f"{', '.join(dead)} stopped while starting. Check: docker compose logs {' '.join(dead)}")
            summary = self.describe_services(svcs)
            if summary != last:
                self.say("Backend    waiting: " + summary)
                last = summary
            if self.clock() >= deadline:
                raise LauncherError(f"Backend did not become healthy within {int(timeout)}s ({summary}). "
                                    "Check: docker compose logs api db")
            self.sleep(3)

    def migration_state(self) -> tuple[Optional[bool], str]:
        res = self.compose("exec", "-T", "api", "alembic", "current", timeout=60)
        text = res.stdout.strip().splitlines()
        current = text[-1].strip() if text else ""
        if res.returncode != 0 or not current:
            return None, "could not read the migration state"
        return "(head)" in current, current

    def check_migrations(self) -> None:
        at_head, current = self.migration_state()
        if at_head is None:
            self.say(f"Migrations {current} (continuing)")
        elif at_head:
            self.say(f"Migrations up to date: {current}")
        elif self.demo_active:
            self.say(f"Migrations PENDING ({current}), NOT applied: the public demo is running. "
                     "Apply later with: docker compose run --rm migrate")
        else:
            self.say(f"Migrations pending ({current}): applying with the existing migrate service ...")
            self._must(self.compose("run", "--rm", "--no-deps", "migrate", timeout=600), "run --rm migrate")
            _, current = self.migration_state()
            self.say(f"Migrations now at: {current}")

    # -- frontend
    def frontend_urls(self) -> list[str]:
        return [f"https://localhost:{VITE_PORT}/v2", f"http://localhost:{VITE_PORT}/v2"]

    def vite_running(self) -> Optional[str]:
        for url in self.frontend_urls():
            status, body = self.http(url)
            if status == 200 and 'id="root"' in body:
                return url
        return None

    def ensure_frontend(self) -> str:
        existing = self.vite_running()
        if existing:
            self.say(f"Frontend   reusing the dev server that is already running at {existing}")
            self.say("           (its log stays in the window that started it)")
            return existing
        if self.port_check(VITE_PORT):
            raise LauncherError(f"Port {VITE_PORT} is in use by something that is not the ASHA Saathi dev server. "
                                "Close it, then run the launcher again.")
        node_v, npm_v = self.check_node()
        npm = self.runner.which("npm") or "npm"
        if not (FRONTEND / "node_modules").exists():
            self.say(f"Frontend   installing dependencies once (npm ci, Node {node_v}, npm {npm_v}) ...")
            res = self.runner.run([npm, "ci"], timeout=900, cwd=FRONTEND)
            if res.returncode != 0:
                raise LauncherError("npm ci failed:\n" + self.redact(res.stdout[-800:] + res.stderr[-800:]))
        host = "0.0.0.0" if self.args.lan else "localhost"
        self.say(f"Frontend   starting the Vite HTTPS dev server on {host}:{VITE_PORT} (Node {node_v}) ...")
        env = {k: v for k, v in os.environ.items() if k not in ("ASHA_DEV_HTTP", "ASHA_BACKEND_URL")}
        self.vite = self.runner.popen([npm, "run", "dev", "--", "--host", host, "--port", str(VITE_PORT),
                                       "--strictPort"], cwd=FRONTEND, env=env)
        self.children.append(self.vite)
        self.follow(self.vite, lambda line: ("web", line))
        deadline = self.clock() + VITE_TIMEOUT_S
        while True:
            url = self.vite_running()
            if url:
                return url
            if self.vite.poll() is not None:
                raise LauncherError("The Vite dev server exited during startup; see the 'web' lines above.")
            if self.clock() >= deadline:
                raise LauncherError(f"The Vite dev server did not answer within {VITE_TIMEOUT_S}s.")
            self.sleep(1)

    # -- logs
    _COMPOSE_PREFIX = re.compile(r"^([A-Za-z0-9_.-]+?)(?:-\d+)?\s+\|\s?(.*)$")
    _NOISE = (re.compile(r'"GET /api/health HTTP/1\.[01]" 200'),)

    def classify_compose_line(self, line: str) -> Optional[tuple[str, str]]:
        match = self._COMPOSE_PREFIX.match(line)
        label, text = (match.group(1), match.group(2)) if match else ("dock", line)
        if any(p.search(text) for p in self._NOISE):
            return None
        return label, text

    def follow(self, proc: subprocess.Popen, classify: Callable[[str], Optional[tuple[str, str]]]) -> threading.Thread:
        def pump() -> None:
            assert proc.stdout is not None
            for raw in proc.stdout:
                item = classify(raw.rstrip("\r\n"))
                if item and item[1].strip():
                    self.log_line(*item)

        thread = threading.Thread(target=pump, daemon=True)
        thread.start()
        self._threads.append(thread)
        return thread

    def stream_backend_logs(self) -> None:
        proc = self.runner.popen(["docker", "compose", "logs", "-f", "--tail", "15", *CORE_SERVICES], cwd=ROOT)
        self.children.append(proc)
        self.follow(proc, self.classify_compose_line)

    # -- lifecycle
    def wait_until_interrupted(self) -> int:
        started = self.clock()
        try:
            while True:
                if self.vite is not None and self.vite.poll() is not None:
                    self.say("The Vite dev server stopped unexpectedly.")
                    return EXIT_FAIL
                if self.args.exit_after and self.clock() - started >= self.args.exit_after:
                    self.say(f"--exit-after {self.args.exit_after}s reached.")
                    return EXIT_OK
                self.sleep(0.5)
        except KeyboardInterrupt:
            self.say("")
            self.say("Ctrl+C received.")
            return EXIT_OK

    def cleanup(self) -> None:
        for proc in reversed(self.children):
            self.runner.kill_tree(proc)
        self.children.clear()
        self.say("Stopped the launcher's own processes. Docker containers were left running "
                 "(py run.py --status to check, py run.py --stop to stop them).")

    # -- commands
    def preflight(self, need_node: bool) -> None:
        self.say(f"NOVIX local launcher  ({platform.system()} {platform.release()}, Python {platform.python_version()})")
        self.check_python()
        self.check_config()
        self.check_docker()
        tools = f"docker {self._docker_versions[0]} | compose {self._docker_versions[1]}"
        if need_node:
            node_v, npm_v = self.check_node()
            tools += f" | node {node_v} | npm {npm_v}"
        self.say(f"Tools      {tools}")
        reasons = self.detect_demo()
        if reasons:
            self.say(f"Demo       ACTIVE ({'; '.join(reasons)}): protective mode, nothing that could interrupt "
                     "it will be done.")
        else:
            self.say("Demo       not running")

    def status(self) -> int:
        self.preflight(need_node=False)
        svcs = self.services()
        self.say("Services   " + self.describe_services(svcs))
        at_head, current = self.migration_state() if svcs.get("api") and svcs["api"].state == "running" else (None, "api not running")
        self.say(f"Migrations {current}")
        url = self.vite_running()
        self.say(f"Frontend   {'running at ' + url if url else 'not running (py run.py starts it)'}")
        healthy = all(svcs.get(s) and svcs[s].healthy for s in CORE_SERVICES) and self.api_ok()
        return EXIT_OK if healthy else EXIT_FAIL

    def stop(self) -> int:
        self.preflight(need_node=False)
        if self.demo_active:
            raise LauncherError("Refusing to stop services: the public demo is running ("
                                + "; ".join(self.demo_reasons) + "). Stopping db/api would take it offline.",
                                EXIT_REFUSED)
        self.say("Stopping the api and db containers (data is kept; nothing is deleted) ...")
        self._must(self.compose("stop", "api", "db", timeout=120), "stop")
        self.say("Stopped. Start again with: py run.py")
        return EXIT_OK

    def start(self) -> int:
        self.preflight(need_node=not self.args.backend_only)
        self.ensure_backend()
        frontend_url = None if self.args.backend_only else self.ensure_frontend()
        self.say("")
        self.say("Ready:")
        if frontend_url:
            self.say(f"  App (V2)        https://localhost:{VITE_PORT}/v2   (accept the self-signed certificate once)")
            if self.args.lan:
                self.say(f"  Phone (LAN)     https://<this-laptop-IP>:{VITE_PORT}/v2")
        self.say("  API health      " + API_HEALTH_URL)
        self.say("  Status          py run.py --status")
        self.say("Streaming logs (secrets redacted). Ctrl+C leaves the launcher; containers keep running.")
        self.say("")
        self.stream_backend_logs()
        try:
            return self.wait_until_interrupted()
        finally:
            self.cleanup()

    def main(self) -> int:
        try:
            if self.args.status:
                return self.status()
            if self.args.stop:
                return self.stop()
            return self.start()
        except LauncherError as exc:
            self.say(f"ERROR: {exc}")
            return exc.code
        except KeyboardInterrupt:
            self.say("Interrupted.")
            self.cleanup()
            return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="py run.py",
        description="Safely start the NOVIX / ASHA Saathi AI 2.0 stack for local development.",
        epilog="Healthy containers are never restarted or rebuilt, the database is never reset, and Ctrl+C leaves "
               "Docker running. See docs/LOCAL_DEVELOPMENT.md.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="show tools, services, migrations and frontend; change nothing")
    mode.add_argument("--stop", action="store_true",
                      help="stop the api and db containers (never deletes data; refused while the demo is running)")
    parser.add_argument("--backend-only", action="store_true", help="make sure db + api are healthy; no frontend")
    parser.add_argument("--no-build", action="store_true", help="never build Docker images, even if one is missing")
    parser.add_argument("--lan", action="store_true",
                        help="serve the dev frontend on all interfaces (0.0.0.0) for a phone on the same Wi-Fi")
    parser.add_argument("--exit-after", type=float, default=0, metavar="SECONDS",
                        help="leave automatically after SECONDS (for automated checks)")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    args = build_parser().parse_args(argv)
    return Launcher(args).main()


if __name__ == "__main__":
    sys.exit(main())
