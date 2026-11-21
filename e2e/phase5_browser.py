"""Phase 5 real-browser QA: member-linked voice visit (MOCK Gnani, synthetic data only).

Run from the repository root with the Docker stack up (`docker compose up -d`):

    uv run --no-project --with playwright==1.64.1 python -I e2e/phase5_browser.py --channel msedge

Uses the disposable database `asha_saathi_e2e` and `MockVoiceProvider` (no live Gnani call,
no credits). Never touches the live `asha_saathi` database or :8000 API.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, expect, sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
import phase4_browser as p4  # noqa: E402

ROOT = p4.ROOT
OUT = ROOT / "data" / "e2e" / "phase5"
p4.OUT = OUT

API = p4.API
WEB = p4.WEB
ACCOUNTS = p4.ACCOUNTS
STYLE_URL = p4.STYLE_URL

# Synthetic scripted utterances (no real patient). Second line corrects weight; third raises NB_FEVER.
SCRIPT = [
    "ತೂಕ ಎರಡು ಪಾಯಿಂಟ್ ಐದು ಕಿಲೋ, ಮುಂದಿನ ಭೇಟಿ ನವೆಂಬರ್ ಇಪ್ಪತ್ತೆಂಟು",
    "ಇಲ್ಲ, ತೂಕ ಮೂರು ಕಿಲೋ",
    "ಮಗುವಿಗೆ ತುಂಬಾ ಜ್ವರ ಇದೆ",
]


def p5_context(browser: Browser, width: int, height: int, **kw) -> BrowserContext:
    return p4.context(browser, width, height, permissions=["microphone"], **kw)


def select_member(page: Page, household_id: str, member_name: str) -> None:
    p4.show_households(page)
    page.locator(f'ul[aria-label="Households"] button[data-household="{household_id}"]').click()
    expect(page.get_by_test_id("household-preview")).to_be_visible()
    page.get_by_role("button", name="Confirm household").click()
    expect(page.get_by_test_id("household-confirmed")).to_be_visible()
    page.locator("[data-member]", has_text=re.compile(rf"^{re.escape(member_name)}")).click()
    expect(page.get_by_test_id("member-preview")).to_be_visible()
    page.get_by_role("button", name="Select member").click()
    expect(page.get_by_test_id("member-selected")).to_be_visible()
    expect(page.get_by_test_id("voice-panel")).to_be_visible()


def p5_s1_worker_a_full_visit(browser: Browser, pw: dict[str, str], r: p4.Report, ids: dict[str, str]) -> None:
    """P5-S1 at 360 px: bound newborn visit -> correction -> NB_FEVER alert -> confirm -> DB + reload."""
    sc = "P5-S1 worker A newborn visit 360px"
    ctx = p5_context(browser, 360, 800)
    page = ctx.new_page()
    p4.watch(page, r, sc)
    p4.login(page, "demo_worker_a", pw["demo_worker_a"])

    baby_pid = ids["baby_pid"]
    select_member(page, "H-003", "Baby of Kavya Halli")

    start_btn = page.get_by_role("button", name="Start voice visit")
    r.check(sc, "Start is disabled before picking a visit type", start_btn.is_disabled())
    page.get_by_role("radio", name=re.compile(r"Newborn")).check()
    r.check(sc, "Start is enabled after picking Newborn", start_btn.is_enabled())
    r.shot(page, "p5_s1_01_ready_360")
    start_btn.click()

    expect(page.get_by_test_id("bound-verified")).to_be_visible(timeout=20_000)
    panel_text = page.get_by_test_id("voice-panel").inner_text()
    r.check(sc, "bound identity shows baby public id", baby_pid in panel_text, panel_text)

    confirm_btn = page.get_by_test_id("confirm-save")
    expect(confirm_btn).to_be_visible()
    r.check(sc, "confirm-save is disabled right after start", confirm_btn.is_disabled())

    # Wait for all three scripted utterances (transcript -> weight 3 kg correction -> NB_FEVER alert).
    worker_lines = page.locator('section[aria-label="Conversation"] li[data-who="worker"]')
    expect(worker_lines.first).to_be_visible(timeout=45_000)
    record_card = page.locator('section[aria-label="Visit record"]')
    expect(record_card).to_contain_text("3 kg", timeout=45_000)
    danger = page.get_by_test_id("v2-danger-alert")
    expect(danger).to_be_visible(timeout=45_000)
    r.check(sc, "danger alert shows Demo only badge", "Demo only" in danger.inner_text(), danger.inner_text())

    pre_count = p4.e2e_sql("SELECT count(*) FROM v2_visits").strip()
    r.check(sc, "zero DB rows before explicit confirmation", pre_count == "0", pre_count)

    expect(confirm_btn).to_be_enabled(timeout=45_000)
    r.shot(page, "p5_s1_02_awaiting_confirm_360")
    confirm_btn.dblclick()

    saved = page.get_by_test_id("visit-saved")
    expect(saved).to_be_visible(timeout=20_000)

    db_count = p4.e2e_sql("SELECT count(*) FROM v2_visits").strip()
    row_info = p4.e2e_sql(
        "SELECT p.public_id || '|' || v.weight_kg || '|' || v.visit_type || '|' || v.subject_population "
        "FROM v2_visits v JOIN people p ON p.id = v.person_id"
    ).strip()
    kannada_count = p4.e2e_sql(
        r"SELECT count(*) FROM v2_visits v WHERE to_jsonb(v)::text ~ U&'[\0C80-\0CFF]'"
    ).strip()
    r.check(sc, "exactly one DB row after double-click confirm", db_count == "1", db_count)
    r.check(
        sc,
        "DB row bound to baby with corrected weight 3 and newborn scope",
        row_info == f"{baby_pid}|3|newborn|newborn",
        row_info,
    )
    r.check(sc, "no Kannada transcript text persisted in v2_visits", kannada_count == "0", kannada_count)

    storage_empty = page.evaluate(
        """async () => {
            const dbs = indexedDB.databases ? await indexedDB.databases() : [];
            return localStorage.length === 0 && sessionStorage.length === 0 && dbs.length === 0;
        }"""
    )
    r.check(sc, "browser persistent storage is empty", bool(storage_empty), storage_empty)

    history = page.get_by_test_id("visit-history")
    expect(history).to_contain_text("ಭೇಟಿ ಇತಿಹಾಸ")
    expect(history).to_contain_text("Visit history")
    history_item = page.get_by_test_id("history-item")
    expect(history_item).to_have_count(1, timeout=15_000)
    expect(history_item).to_contain_text("Baby of Kavya Halli")
    expect(history_item).to_contain_text(baby_pid)
    expect(history_item).to_contain_text("Saved")
    expect(history_item).to_contain_text("3 kg")
    page.get_by_test_id("history-item-toggle").click()
    details = page.get_by_test_id("history-item-details")
    expect(details).to_be_visible()
    expect(details).to_contain_text("H-003")
    expect(details).to_contain_text("3 kg")
    r.check(sc, "visit history displays expandable saved visit details at 360px", True)
    r.check(sc, "no horizontal scroll at 360px", p4.no_horizontal_scroll(page))
    r.shot(page, "p5_s1_03_saved_history_360")

    page.reload()
    expect(page.get_by_role("heading", name=re.compile(r"Your households \(\d+\)"))).to_be_visible()
    select_member(page, "H-003", "Baby of Kavya Halli")
    expect(page.get_by_test_id("history-item")).to_have_count(1, timeout=15_000)
    page.get_by_test_id("history-item-toggle").click()
    reloaded_details = page.get_by_test_id("history-item-details")
    expect(reloaded_details).to_be_visible()
    expect(reloaded_details).to_contain_text("3 kg")
    expect(reloaded_details).to_contain_text("H-003")
    r.check(sc, "no horizontal scroll after reload at 360px", p4.no_horizontal_scroll(page))
    r.check(sc, "history still shows 1 expandable item after page reload", True)
    unexpected = [
        e
        for e in r.console.get(sc, [])
        if e
        not in (
            "Failed to load resource: net::ERR_FAILED",
            "Failed to load resource: the server responded with a status of 401 (Unauthorized)",
        )
    ]
    r.check(sc, "no unexpected console errors in P5-S1", not unexpected, unexpected)
    ctx.close()


def p5_s2_switch_household_cancels(browser: Browser, pw: dict[str, str], r: p4.Report, ids: dict[str, str]) -> None:
    """P5-S2 at 412 px: switching household mid-visit cancels session and writes nothing."""
    sc = "P5-S2 household switch cancels 412px"
    ctx = p5_context(browser, 412, 915)
    page = ctx.new_page()
    p4.watch(page, r, sc)
    p4.login(page, "demo_worker_a", pw["demo_worker_a"])

    select_member(page, "H-003", "Kavya Halli")
    page.get_by_role("radio", name=re.compile(r"PNC")).check()
    page.get_by_role("button", name="Start voice visit").click()
    expect(page.locator('section[aria-label="Visit record"]')).to_contain_text("2.5 kg", timeout=45_000)
    r.shot(page, "p5_s2_01_kavya_recording_412")

    p4.show_households(page, end_visit=True)  # leaving a live visit asks first, then ends it
    page.locator('ul[aria-label="Households"] button[data-household="H-004"]').click()
    expect(page.get_by_test_id("voice-panel")).to_have_count(0)
    r.check(
        sc,
        "switching household cleared member and closed voice panel",
        p4.breadcrumb(page) == "Selected: H-004 (not confirmed) / No member",
        p4.breadcrumb(page),
    )

    kavya_rows = p4.e2e_sql(
        "SELECT count(*) FROM v2_visits v JOIN people p ON p.id = v.person_id WHERE p.public_id = '"
        + ids["kavya_pid"]
        + "'"
    ).strip()
    r.check(sc, "zero DB rows saved for Kavya", kavya_rows == "0", kavya_rows)

    select_member(page, "H-003", "Kavya Halli")
    expect(page.get_by_test_id("visit-history")).to_contain_text("No confirmed visits yet")
    r.check(sc, "Kavya history shows No confirmed visits yet", True)
    r.check(sc, "no horizontal scroll at 412px", p4.no_horizontal_scroll(page))
    r.shot(page, "p5_s2_02_kavya_empty_history_412")
    ctx.close()


def p5_s3_worker_b_isolated(browser: Browser, pw: dict[str, str], r: p4.Report, ids: dict[str, str]) -> None:
    """P5-S3: Worker B gets 404 on Worker A's member history and NOT_AVAILABLE over WebSocket."""
    sc = "P5-S3 worker B scope"
    ctx = p5_context(browser, 360, 800)
    page = ctx.new_page()
    p4.watch(page, r, sc)
    p4.login(page, "demo_worker_b", pw["demo_worker_b"])

    baby_pid = ids["baby_pid"]
    hist_status = p4.fetch_status(page, f"/api/v2/people/{baby_pid}/visits")
    r.check(sc, "Worker B gets 404 on Territory A member history", hist_status == 404, hist_status)

    ws_result = page.evaluate(
        """async ({ householdId, personId, clientVisitId }) => {
            const scheme = location.protocol === "https:" ? "wss" : "ws";
            const ws = new WebSocket(`${scheme}://${location.host}/ws/v2/session`);
            const messages = [];
            return await new Promise((resolve) => {
                const timer = setTimeout(() => resolve({ messages, closed: false, code: null }), 10000);
                ws.onopen = () => {
                    ws.send(JSON.stringify({
                        type: "v2.session.start",
                        household_id: householdId,
                        person_id: personId,
                        client_visit_id: clientVisitId,
                        visit_type: "newborn",
                    }));
                };
                ws.onmessage = (e) => {
                    try { messages.push(JSON.parse(e.data)); } catch {}
                };
                ws.onclose = (e) => {
                    clearTimeout(timer);
                    resolve({ messages, closed: true, code: e.code });
                };
            });
        }""",
        {"householdId": "H-003", "personId": baby_pid, "clientVisitId": "11111111-1111-4111-8111-111111111111"},
    )
    codes = [m.get("code") for m in ws_result["messages"] if m.get("type") == "session.error"]
    r.check(
        sc,
        "WS refuses foreign person with NOT_AVAILABLE and closes",
        ws_result["closed"] and "NOT_AVAILABLE" in codes,
        ws_result,
    )
    db_count = p4.e2e_sql("SELECT count(*) FROM v2_visits").strip()
    r.check(sc, "DB count unchanged after foreign WS attempt", db_count == "1", db_count)
    ctx.close()


def p5_s4_anonymous_blocked(browser: Browser, _pw: dict[str, str], r: p4.Report, ids: dict[str, str]) -> None:
    """P5-S4: Anonymous caller gets 401 on V2 visit history."""
    sc = "P5-S4 anonymous blocked"
    ctx = p5_context(browser, 360, 800)
    page = ctx.new_page()
    p4.watch(page, r, sc)
    page.goto(f"{WEB}/v2")
    expect(page.get_by_role("button", name="Sign in")).to_be_visible()
    status = p4.fetch_status(page, f"/api/v2/people/{ids['baby_pid']}/visits")
    r.check(sc, "anonymous history GET returns 401", status == 401, status)
    ctx.close()


def p5_s5_supervisor_read_only(browser: Browser, pw: dict[str, str], r: p4.Report, _ids: dict[str, str]) -> None:
    """P5-S5 at 1280 px: supervisor can view history but cannot start a voice visit."""
    sc = "P5-S5 supervisor read-only 1280px"
    ctx = p5_context(browser, 1280, 800)
    page = ctx.new_page()
    p4.watch(page, r, sc)
    p4.login(page, "demo_supervisor", pw["demo_supervisor"])
    select_member(page, "H-003", "Baby of Kavya Halli")
    panel = page.get_by_test_id("voice-panel")
    expect(panel).to_contain_text("Only ASHA worker accounts record visits.")
    expect(page.get_by_test_id("history-item")).to_have_count(1, timeout=15_000)
    r.check(
        sc,
        "supervisor sees read-only message and history with no Start button",
        page.get_by_role("button", name="Start voice visit").count() == 0,
    )
    r.shot(page, "p5_s5_supervisor_1280")
    ctx.close()


SCENARIOS = [
    p5_s1_worker_a_full_visit,
    p5_s2_switch_household_cancels,
    p5_s3_worker_b_isolated,
    p5_s4_anonymous_blocked,
    p5_s5_supervisor_read_only,
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--channel", default="msedge", help="Playwright browser channel (msedge, chrome)")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    report = p4.Report()
    passwords = {u: secrets.token_urlsafe(18) for u in ACCOUNTS}
    vite: subprocess.Popen | None = None
    vite_log = open(OUT / "vite.log", "w", encoding="utf-8")
    started = time.monotonic()
    os.environ["MOCK_VOICE_SCRIPT"] = json.dumps(SCRIPT)
    try:
        print("Building api-e2e and creating the disposable e2e database ...")
        p4.compose("--profile", "e2e", "build", "api-e2e")
        setup = p4.compose(
            "--profile", "e2e", "run", "--rm", "-T", "api-e2e",
            "python", "-m", "tests.e2e_bootstrap", "setup",
            stdin=json.dumps(passwords),
        )
        report.info["e2e_database"] = json.loads(setup.strip().splitlines()[-1])
        p4.compose("--profile", "e2e", "up", "-d", "api-e2e")
        p4.wait_http(f"{API}/api/health")
        with urllib.request.urlopen(f"{API}/api/health") as h:
            report.info["e2e_api_health"] = json.loads(h.read())

        ids = {
            "baby_pid": p4.e2e_sql("SELECT public_id FROM people WHERE full_name = 'Baby of Kavya Halli'").strip(),
            "kavya_pid": p4.e2e_sql("SELECT public_id FROM people WHERE full_name = 'Kavya Halli'").strip(),
        }

        env = {**os.environ, "ASHA_BACKEND_URL": API, "ASHA_DEV_HTTP": "1", "VITE_MAP_STYLE_URL": STYLE_URL}
        vite = subprocess.Popen(
            ["node", "node_modules/vite/bin/vite.js", "--host", "localhost", "--port", "5174", "--strictPort"],
            cwd=ROOT / "frontend",
            env=env,
            stdout=vite_log,
            stderr=subprocess.STDOUT,
        )
        p4.wait_http(f"{WEB}/v2")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                channel=args.channel,
                headless=not args.headed,
                args=[
                    "--use-fake-device-for-media-stream",
                    "--use-fake-ui-for-media-stream",
                    "--autoplay-policy=no-user-gesture-required",
                ],
            )
            report.info["browser"] = f"{args.channel} {browser.version}"
            print(f"Browser: {report.info['browser']}")
            for scenario in SCENARIOS:
                print(scenario.__doc__.strip().splitlines()[0])
                try:
                    scenario(browser, passwords, report, ids)
                except Exception as exc:
                    report.check(scenario.__name__, "scenario completed", False, f"{type(exc).__name__}: {str(exc)[:500]}")
                    traceback.print_exc()
            browser.close()
    finally:
        if vite:
            vite.terminate()
            try:
                vite.wait(timeout=15)
            except subprocess.TimeoutExpired:
                vite.kill()
        vite_log.close()
        p4.compose("--profile", "e2e", "stop", "api-e2e", check=False)
        p4.compose("--profile", "e2e", "rm", "-f", "api-e2e", check=False)
        teardown = p4.compose(
            "--profile", "e2e", "run", "--rm", "-T", "api-e2e",
            "python", "-m", "tests.e2e_bootstrap", "teardown",
            check=False,
        )
        report.info["teardown"] = teardown.strip().splitlines()[-1] if teardown.strip() else "teardown failed"
        report.info["duration_s"] = round(time.monotonic() - started, 1)
        report.info["external_hosts_refused"] = sorted(p4.EXTERNAL)
        summary = {
            "passed": sum(c["ok"] for c in report.checks),
            "failed": len(report.failed),
            "checks": report.checks,
            "screenshots": report.screens,
            "console_errors": report.console,
            "info": report.info,
        }
        (OUT / "report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"\n{summary['passed']} passed, {summary['failed']} failed · report: {OUT / 'report.json'}")
    return 1 if report.failed or not report.checks else 0


if __name__ == "__main__":
    sys.exit(main())
