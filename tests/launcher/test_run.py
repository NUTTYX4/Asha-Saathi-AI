"""Tests for the root run.py launcher. Every subprocess, HTTP probe and clock is faked.

    py -m unittest discover -s tests/launcher -v
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import run  # noqa: E402

MUTATING = {"start", "up", "stop", "restart", "down", "build", "run", "rm", "kill", "pause", "unpause", "create"}
SECRET = "s3cr3t-postgres-Pa55"
GNANI = "gn-test-key-0123456789"


class FakeProc:
    def __init__(self, lines=(), on_kill=None):
        self.stdout = iter([l + "\n" for l in lines])
        self.returncode = None
        self.pid = 4242
        self.on_kill = on_kill

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode


class World:
    """Scripted machine state plus a fake Runner over it."""

    def __init__(self, services=None, docker=True, daemon=True, node=True, cloudflared=False, demo_proxy=False,
                 vite=False, port_busy=False, alembic="0005 (head)", health_after_polls=0, vite_starts=True,
                 log_lines=(), vite_lines=()):
        self.services = dict(services if services is not None else {"db": ("running", "healthy"),
                                                                     "api": ("running", "healthy")})
        self.docker, self.daemon, self.node = docker, daemon, node
        self.cloudflared, self.demo_proxy = cloudflared, demo_proxy
        self.vite, self.port_busy, self.alembic = vite, port_busy, alembic
        self.health_after_polls = health_after_polls  # ps polls that still report "starting"
        self.vite_starts = vite_starts
        self.log_lines, self.vite_lines = log_lines, vite_lines
        self.calls: list[list[str]] = []
        self.popens: list[list[str]] = []
        self.killed: list[FakeProc] = []
        self.now = 0.0

    # --- Runner interface
    def which(self, name):
        if name == "docker":
            return "/usr/bin/docker" if self.docker else None
        if name in ("node", "npm"):
            return f"/usr/bin/{name}" if self.node else None
        return None

    def run(self, args, timeout=60, cwd=None):
        args = list(args)
        self.calls.append(args)
        ok = lambda out="": subprocess.CompletedProcess(args, 0, out, "")  # noqa: E731
        if args[:2] == ["docker", "info"]:
            return ok("28.1.1") if self.daemon else subprocess.CompletedProcess(args, 1, "", "cannot connect")
        if args[:3] == ["docker", "compose", "version"]:
            return ok("5.7.0")
        if args[0] == "tasklist":
            return ok('"cloudflared.exe","10936"' if self.cloudflared else "INFO: No tasks are running")
        if args[0] == "pgrep":
            return subprocess.CompletedProcess(args, 0 if self.cloudflared else 1, "", "")
        if args[:2] == ["docker", "ps"]:
            return ok("asha-saathi-tunnel-web-1\n" if self.demo_proxy else "")
        if args[:3] == ["docker", "compose", "ps"]:
            return ok(self._ps_json())
        if args[:3] == ["docker", "compose", "exec"]:
            return ok(self.alembic + "\n")
        if args[:2] == ["docker", "compose"] and args[2] in ("start", "up", "unpause"):
            for name in [a for a in args[3:] if not a.startswith("-")]:
                self.services[name] = ("running", "starting" if self.health_after_polls else "healthy")
            return ok()
        if args[:2] == ["docker", "compose"] and args[2] == "run":
            self.alembic = "0005 (head)"
            return ok()
        if args[:2] == ["docker", "compose"] and args[2] == "stop":
            return ok()
        if args[-1] == "--version":
            return ok("v24.0.0" if "node" in args[0] else "11.0.0")
        if args[-1] == "ci":
            return ok()
        return subprocess.CompletedProcess(args, 1, "", f"unexpected command {args}")

    def popen(self, args, cwd=None, env=None):
        args = list(args)
        self.popens.append(args)
        if args[:3] == ["docker", "compose", "logs"]:
            return FakeProc(self.log_lines)
        if self.vite_starts:
            self.vite = True
            return FakeProc(self.vite_lines)
        proc = FakeProc(self.vite_lines)
        proc.returncode = 1
        return proc

    def kill_tree(self, proc):
        self.killed.append(proc)
        proc.returncode = -15

    # --- other fakes
    def _ps_json(self):
        rows = []
        for name, (state, health) in self.services.items():
            if self.health_after_polls and state == "running" and health == "starting":
                self.health_after_polls -= 1
                if self.health_after_polls == 0:
                    self.services[name] = ("running", "healthy")
                    health = "healthy"
            rows.append(json.dumps({"Service": name, "State": state, "Health": health, "Name": f"asha-saathi-{name}-1"}))
        rows.append(json.dumps({"Service": "migrate", "State": "exited", "Health": "", "Name": "asha-saathi-migrate-1"}))
        return "\n".join(rows)

    def http(self, url):
        if url == run.API_HEALTH_URL:
            api = self.services.get("api")
            if api and api == ("running", "healthy"):
                return 200, json.dumps({"status": "ok", "database_ok": True})
            return 0, ""
        if self.vite and url.startswith("https://localhost:5173"):
            return 200, '<!doctype html><div id="root"></div>'
        return 0, ""

    def port_check(self, port):
        return self.port_busy or self.vite

    def sleep(self, seconds):
        self.now += seconds

    def clock(self):
        return self.now

    def mutating_calls(self):
        return [c for c in self.calls if c[:2] == ["docker", "compose"] and len(c) > 2 and c[2] in MUTATING]


class LauncherTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env_file = Path(self.tmp.name) / ".env"
        self.env_file.write_text(
            f"POSTGRES_PASSWORD={SECRET}\nGNANI_API_KEY='{GNANI}'\nV2_VOICE_ENABLED=true\n"
            "GEMINI_EXTRACTION_ENABLED=false\nBACKEND_HOST=127.0.0.1\n# comment\n", encoding="utf-8")
        self.addCleanup(self.tmp.cleanup)

    def launch(self, world, *argv, env_file=None):
        args = run.build_parser().parse_args(list(argv))
        out = io.StringIO()
        launcher = run.Launcher(args, runner=world, http=world.http, port_check=world.port_check,
                                sleep=world.sleep, clock=world.clock, out=out, env_file=env_file or self.env_file)
        code = launcher.main()
        for t in launcher._threads:
            t.join(timeout=2)
        return code, out.getvalue(), launcher


class PrerequisiteTests(LauncherTestCase):
    def test_missing_docker(self):
        code, out, _ = self.launch(World(docker=False), "--status")
        self.assertEqual(code, run.EXIT_PREREQ)
        self.assertIn("Docker is not installed", out)

    def test_docker_daemon_unavailable(self):
        world = World(daemon=False)
        code, out, _ = self.launch(world, "--status")
        self.assertEqual(code, run.EXIT_PREREQ)
        self.assertIn("engine is not running", out)
        self.assertFalse(any(c[:3] == ["docker", "compose", "ps"] for c in world.calls))

    def test_missing_env_file(self):
        world = World()
        code, out, _ = self.launch(world, env_file=Path(self.tmp.name) / "absent.env")
        self.assertEqual(code, run.EXIT_PREREQ)
        self.assertIn("Missing absent.env", out)
        self.assertEqual(world.calls, [], "no command may run without configuration")

    def test_missing_required_value(self):
        self.env_file.write_text("GNANI_API_KEY=x\n", encoding="utf-8")
        code, out, _ = self.launch(World(), "--status")
        self.assertEqual(code, run.EXIT_PREREQ)
        self.assertIn("POSTGRES_PASSWORD", out)

    def test_missing_node_for_frontend(self):
        code, out, _ = self.launch(World(node=False), "--exit-after", "1")
        self.assertEqual(code, run.EXIT_PREREQ)
        self.assertIn("Node.js and npm are required", out)

    def test_secrets_never_printed(self):
        code, out, _ = self.launch(World(), "--status")
        self.assertEqual(code, run.EXIT_OK)
        self.assertNotIn(SECRET, out)
        self.assertNotIn(GNANI, out)
        self.assertIn("POSTGRES_PASSWORD set", out)
        self.assertIn("V2_VOICE_ENABLED=true", out)


class BackendTests(LauncherTestCase):
    def test_existing_healthy_containers_untouched(self):
        world = World()
        code, out, _ = self.launch(world, "--backend-only", "--exit-after", "1")
        self.assertEqual(code, run.EXIT_OK)
        self.assertIn("already healthy", out)
        self.assertEqual(world.mutating_calls(), [])

    def test_stopped_containers_are_started_not_recreated(self):
        world = World(services={"db": ("exited", ""), "api": ("exited", "")})
        code, out, _ = self.launch(world, "--backend-only", "--exit-after", "1")
        self.assertEqual(code, run.EXIT_OK)
        self.assertEqual(world.mutating_calls(), [["docker", "compose", "start", "db", "api"]])
        self.assertIn("Backend    healthy", out)

    def test_missing_containers_created_without_recreate(self):
        world = World(services={})
        code, _, _ = self.launch(world, "--backend-only", "--no-build", "--exit-after", "1")
        self.assertEqual(code, run.EXIT_OK)
        self.assertEqual(world.mutating_calls(),
                         [["docker", "compose", "up", "-d", "--no-recreate", "--no-build", "db", "api"]])

    def test_health_polling_waits_until_healthy(self):
        world = World(services={"db": ("running", "healthy"), "api": ("exited", "")}, health_after_polls=3)
        code, out, _ = self.launch(world, "--backend-only", "--exit-after", "1")
        self.assertEqual(code, run.EXIT_OK)
        self.assertIn("waiting", out)
        self.assertGreaterEqual(world.now, 6, "the launcher should have slept between polls")

    def test_health_timeout_reports_error(self):
        world = World(services={"db": ("running", "healthy"), "api": ("running", "unhealthy")})
        code, out, _ = self.launch(world, "--backend-only")
        self.assertEqual(code, run.EXIT_FAIL)
        self.assertIn("did not become healthy", out)
        self.assertEqual(world.mutating_calls(), [], "an unhealthy running container is waited on, not restarted")

    def test_pending_migration_applied_through_migrate_service(self):
        world = World(alembic="0004")
        code, _, _ = self.launch(world, "--backend-only", "--exit-after", "1")
        self.assertEqual(code, run.EXIT_OK)
        self.assertIn(["docker", "compose", "run", "--rm", "--no-deps", "migrate"], world.calls)


class FrontendTests(LauncherTestCase):
    def test_frontend_started_on_localhost_only(self):
        world = World()
        code, out, _ = self.launch(world, "--exit-after", "1")
        self.assertEqual(code, run.EXIT_OK)
        vite = [p for p in world.popens if "dev" in p]
        self.assertEqual(len(vite), 1)
        self.assertEqual(vite[0][1:], ["run", "dev", "--", "--host", "localhost", "--port", "5173", "--strictPort"])
        self.assertIn("https://localhost:5173/v2", out)

    def test_lan_flag_uses_all_interfaces(self):
        world = World()
        self.launch(world, "--lan", "--exit-after", "1")
        vite = [p for p in world.popens if "dev" in p][0]
        self.assertEqual(vite[vite.index("--host") + 1], "0.0.0.0")

    def test_existing_vite_is_reused(self):
        world = World(vite=True)
        code, out, _ = self.launch(world, "--exit-after", "1")
        self.assertEqual(code, run.EXIT_OK)
        self.assertIn("reusing the dev server", out)
        self.assertFalse([p for p in world.popens if "dev" in p])

    def test_port_taken_by_something_else(self):
        world = World(port_busy=True)
        code, out, _ = self.launch(world, "--exit-after", "1")
        self.assertEqual(code, run.EXIT_FAIL)
        self.assertIn("in use by something", out)

    def test_vite_crash_during_startup(self):
        world = World(vite_starts=False, vite_lines=["Error: boom"])
        code, out, _ = self.launch(world, "--exit-after", "1")
        self.assertEqual(code, run.EXIT_FAIL)
        self.assertIn("exited during startup", out)


class LoggingTests(LauncherTestCase):
    def test_combined_logs_are_labelled_timestamped_filtered_and_redacted(self):
        world = World(
            log_lines=[
                'api-1  | INFO:     172.20.0.3:1 - "GET /api/health HTTP/1.1" 200 OK',
                'api-1  | INFO:     172.20.0.3:1 - "POST /api/v2/auth/login HTTP/1.1" 200 OK',
                f"db-1   | connection to postgresql://asha:{SECRET}@db:5432/asha_saathi",
                "api-1  | Set-Cookie: asha_session=abcdef123456; HttpOnly",
                "api-1  | auth Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.c2lnbmF0dXJlMTIz",
            ],
            vite_lines=["\x1b[32m  VITE v6.3.5  ready in 900 ms\x1b[39m", f"leaked key {GNANI}"],
        )
        code, out, _ = self.launch(world, "--exit-after", "1")
        self.assertEqual(code, run.EXIT_OK)
        self.assertRegex(out, r"\d\d:\d\d:\d\d api \| INFO: .*POST /api/v2/auth/login")
        self.assertRegex(out, r"\d\d:\d\d:\d\d db  \| connection to postgresql://asha:\[redacted\]@db")
        self.assertRegex(out, r"\d\d:\d\d:\d\d web \|   VITE v6\.3\.5  ready")
        self.assertNotIn("GET /api/health", out, "health-check noise is filtered")
        for leaked in (SECRET, GNANI, "abcdef123456", "eyJhbGciOiJIUzI1NiJ9", "\x1b["):
            self.assertNotIn(leaked, out)

    def test_redactor_patterns(self):
        r = run.Redactor(["supersecretvalue"])
        cases = {
            "password=hunter22 next": "password=[redacted] next",
            '{"token": "abc.def"}': '{"token": [redacted]}',
            "cookie: a=b; c=d": "cookie: [redacted]",
            "key AIzaSyA1234567890abcdefghijklmnop": "key [redacted-key]",
            "value supersecretvalue here": "value [redacted] here",
            "plain 127.0.0.1:8000 line": "plain 127.0.0.1:8000 line",
        }
        for raw, expected in cases.items():
            self.assertEqual(r(raw), expected)

    def test_non_secret_env_values_are_not_redacted(self):
        _, _, launcher = self.launch(World(), "--status")
        self.assertEqual(launcher.redact("listening on 127.0.0.1"), "listening on 127.0.0.1")
        self.assertEqual(launcher.redact(f"pw {SECRET}"), "pw [redacted]")


class LifecycleTests(LauncherTestCase):
    def test_ctrl_c_stops_only_launcher_processes(self):
        world = World()
        original_sleep = world.sleep
        calls = {"n": 0}

        def sleep(seconds):
            calls["n"] += 1
            original_sleep(seconds)
            if calls["n"] > 3:
                raise KeyboardInterrupt

        world.sleep = sleep
        code, out, launcher = self.launch(world)
        self.assertEqual(code, run.EXIT_OK)
        self.assertIn("Ctrl+C received", out)
        self.assertEqual(len(world.killed), 2, "Vite and the log follower are stopped")
        self.assertEqual(world.mutating_calls(), [], "no docker stop/down on Ctrl+C")
        self.assertIn("Docker containers were left running", out)

    def test_repeated_execution_is_idempotent(self):
        world = World(vite=True)
        for _ in range(2):
            code, _, _ = self.launch(world, "--exit-after", "1")
            self.assertEqual(code, run.EXIT_OK)
        self.assertEqual(world.mutating_calls(), [])
        self.assertFalse([p for p in world.popens if "dev" in p])

    def test_status_changes_nothing(self):
        world = World(services={"db": ("exited", ""), "api": ("exited", "")})
        code, out, _ = self.launch(world, "--status")
        self.assertEqual(code, run.EXIT_FAIL)
        self.assertEqual(world.mutating_calls(), [])
        self.assertEqual(world.popens, [])
        self.assertIn("db exited", out)

    def test_stop_without_demo_stops_but_never_deletes(self):
        world = World()
        code, _, _ = self.launch(world, "--stop")
        self.assertEqual(code, run.EXIT_OK)
        self.assertEqual(world.mutating_calls(), [["docker", "compose", "stop", "api", "db"]])
        self.assertFalse(any("down" in c or "-v" in c for c in world.calls))


class TunnelProtectionTests(LauncherTestCase):
    def test_stop_refused_while_cloudflared_runs(self):
        for world in (World(cloudflared=True), World(demo_proxy=True)):
            code, out, _ = self.launch(world, "--stop")
            self.assertEqual(code, run.EXIT_REFUSED)
            self.assertIn("Refusing to stop", out)
            self.assertEqual(world.mutating_calls(), [])

    def test_pending_migrations_not_applied_during_demo(self):
        world = World(cloudflared=True, alembic="0004")
        code, out, _ = self.launch(world, "--backend-only", "--exit-after", "1")
        self.assertEqual(code, run.EXIT_OK)
        self.assertIn("NOT applied", out)
        self.assertEqual(world.mutating_calls(), [])

    def test_never_builds_images_during_demo(self):
        world = World(services={}, demo_proxy=True)
        self.launch(world, "--backend-only", "--exit-after", "1")
        up = [c for c in world.mutating_calls() if c[2] == "up"]
        self.assertEqual(len(up), 1)
        self.assertIn("--no-build", up[0])
        self.assertIn("--no-recreate", up[0])

    def test_demo_reported_and_healthy_stack_untouched(self):
        world = World(cloudflared=True, demo_proxy=True, vite=True)
        code, out, _ = self.launch(world, "--exit-after", "1")
        self.assertEqual(code, run.EXIT_OK)
        self.assertIn("Demo       ACTIVE", out)
        self.assertEqual(world.mutating_calls(), [])


class ParsingTests(unittest.TestCase):
    def test_compose_ps_json_lines_and_array(self):
        lines = '{"Service":"db","State":"running","Health":"healthy"}\n{"Service":"api","State":"exited","Health":""}'
        array = json.dumps([{"Service": "db", "State": "running", "Health": "healthy"}])
        self.assertEqual(run.parse_compose_ps(lines)["api"].state, "exited")
        self.assertTrue(run.parse_compose_ps(array)["db"].healthy)
        self.assertEqual(run.parse_compose_ps(""), {})

    def test_env_parser(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / ".env"
            p.write_text('A=1\nB="two words"\nexport C=3 # note\n#D=4\nbad line\n', encoding="utf-8")
            self.assertEqual(run.read_env_file(p), {"A": "1", "B": "two words", "C": "3"})


if __name__ == "__main__":
    unittest.main()
