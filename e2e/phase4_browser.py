"""Phase 4 real-browser QA: household map, confirmation and member selection (synthetic data only).

Run from the repository root with the Docker stack up (`docker compose up -d`):

    uv run --no-project --with playwright==1.64.1 python -I e2e/phase4_browser.py [--channel msedge] [--headed]

What it does
  1. Builds the api-e2e image and creates the disposable database asha_saathi_e2e (the 12-household /
     50-person synthetic seed plus the e2e-only account e2e_supervisor_a). The demo accounts of that
     database get one-time random passwords, sent over stdin and kept only in this process.
  2. Starts api-e2e (http://127.0.0.1:8001, compose profile "e2e") and a Vite dev server on
     http://localhost:5174 (plain HTTP on localhost, a secure context) proxying to it.
  3. Drives an installed Chromium-based browser (Playwright channel: msedge or chrome) through the
     Phase 4 scenarios at 360, 412 and 1280 px. Screenshots and report.json go to data/e2e/phase4/
     (git-ignored). No traces or videos are recorded, so typed passwords are never saved.
     Hermetic: the page may only reach the local app. The configured basemap style URL (OpenFreeMap,
     as an owner would enable it) is answered locally by the test with a plain style, or refused
     to simulate a tile outage; no request ever reaches OpenFreeMap (its terms forbid automated
     collection) or any other external host.
  4. Always stops Vite and api-e2e and drops the e2e database, whatever happened.

The app database, its accounts and the live API on :8000 are not touched.
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
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "e2e" / "phase4"
API = "http://127.0.0.1:8001"
WEB = "http://localhost:5174"
E2E_DB = "asha_saathi_e2e"
ACCOUNTS = ["demo_worker_a", "demo_worker_b", "demo_supervisor", "demo_admin", "e2e_supervisor_a"]
A_HOUSES = [f"H-{n:03d}" for n in range(1, 7)]
B_HOUSES = [f"H-{n:03d}" for n in range(7, 13)]
H003 = {"lat": 12.977466, "lon": 77.594572}  # synthetic Cubbon Park pin (app/seed/demo_data.py)
H003_NAMES = ["Prakash Halli", "Kavya Halli", "Baby of Kavya Halli", "Nagamma Halli"]
EVERY_NAME_RE = re.compile(
    r"Hosamane|Kerekatte|Halli|Doddamane|Kallur|Hebbar|Gowda|Patil|Naik|Shetty|Bhat|\bRao\b"
)
CSRF = {"X-Requested-With": "asha-saathi"}
STYLE_URL = "https://tiles.openfreemap.org/styles/liberty"  # configured for the test, never contacted
MOCK_STYLE = {"version": 8, "sources": {},
              "layers": [{"id": "background", "type": "background", "paint": {"background-color": "#dfe9dc"}}]}

expect.set_options(timeout=15_000)


# ------------------------------------------------------------------ infrastructure
def compose(*args: str, stdin: str | None = None, check: bool = True) -> str:
    result = subprocess.run(["docker", "compose", *args], cwd=ROOT, input=stdin, capture_output=True,
                            text=True, encoding="utf-8")
    if check and result.returncode != 0:
        raise RuntimeError(f"docker compose {' '.join(args[:3])} failed:\n{result.stderr[-1500:]}")
    return result.stdout


def e2e_sql(sql: str) -> str:
    """Run SQL on the disposable e2e database only (explicit database name)."""
    return compose("exec", "-T", "db", "psql", "-U", "asha", "-d", E2E_DB, "-v", "ON_ERROR_STOP=1",
                   "-tAc", sql)


def wait_http(url: str, timeout_s: float = 120) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status < 500:
                    return
        except urllib.error.HTTPError as e:
            if e.code < 500:
                return
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError(f"{url} did not come up within {timeout_s:.0f}s")


class Report:
    def __init__(self) -> None:
        self.checks: list[dict] = []
        self.screens: list[str] = []
        self.console: dict[str, list[str]] = {}
        self.info: dict[str, object] = {}

    def check(self, scenario: str, name: str, ok: bool, detail: object = "") -> bool:
        self.checks.append({"scenario": scenario, "check": name, "ok": bool(ok), "detail": detail})
        print(f"  [{'PASS' if ok else 'FAIL'}] {scenario}: {name}" + (f" — {detail}" if detail and not ok else ""))
        return bool(ok)

    def shot(self, page: Page, name: str) -> None:
        path = OUT / f"{name}.png"
        page.evaluate("window.scrollTo(0, 0)")  # keep the sticky breadcrumb at the top of the capture
        page.wait_for_timeout(150)
        page.screenshot(path=str(path), full_page=True)
        self.screens.append(path.name)

    @property
    def failed(self) -> list[dict]:
        return [c for c in self.checks if not c["ok"]]


def watch(page: Page, report: Report, scenario: str) -> list[str]:
    """Collect console errors, uncaught errors and every API URL the page requests."""
    errors = report.console.setdefault(scenario, [])
    page.on("console", lambda m: errors.append(m.text[:300]) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {str(e)[:300]}"))
    api_calls: list[str] = []
    page.on("request", lambda r: api_calls.append(r.url.replace(WEB, "")) if "/api/" in r.url else None)
    return api_calls


# ------------------------------------------------------------------ page helpers
def login(page: Page, username: str, password: str, field_view: bool = True) -> None:
    """Sign in. Admins land on the admin dashboard (Phase 7); field_view=True switches them to the
    household map so the map/selection scenarios run unchanged."""
    page.goto(f"{WEB}/v2")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()
    # The count appears only once the pins have loaded ("Your households" while loading).
    households = page.get_by_role("heading", name=re.compile(r"Your households \(\d+\)"))
    dashboard = page.get_by_test_id("admin-dashboard")
    expect(households.or_(dashboard)).to_be_visible()
    if dashboard.is_visible() and field_view:
        page.get_by_role("navigation", name="Admin views").get_by_role("button", name="Field view").click()
    if field_view:
        expect(households).to_be_visible()
    expect(page.get_by_test_id("synthetic-banner")).to_be_visible()


def list_ids(page: Page) -> list[str]:
    return page.locator('ul[aria-label="Households"] button[data-household]').evaluate_all(
        "els => els.map(e => e.dataset.household)")


def marker_ids(page: Page) -> list[str]:
    return page.locator(".asha-pin").evaluate_all("els => els.map(e => e.dataset.household)")


def wait_markers(page: Page, n: int) -> bool:
    try:
        expect(page.locator(".asha-pin")).to_have_count(n, timeout=20_000)
        return True
    except AssertionError:
        return False


def show_households(page: Page, end_visit: bool = False) -> None:
    """Open the household list. On phones it sits behind the journey's Households step once a
    household is confirmed; leaving a live voice visit first asks to end it."""
    lst = page.locator('ul[aria-label="Households"]')
    if lst.count() and lst.first.is_visible():
        return
    page.get_by_role("navigation", name="Visit journey").get_by_role("button", name=re.compile("^Households")).click()
    if end_visit:
        page.get_by_role("dialog").get_by_role("button", name="End visit").click()
    expect(lst).to_be_visible()


def breadcrumb(page: Page) -> str:
    return page.get_by_test_id("selection-breadcrumb").inner_text().strip()


def body_text(page: Page) -> str:
    return page.locator("body").inner_text()


def fetch_status(page: Page, path: str) -> int:
    return page.evaluate("async (p) => (await fetch(p, {credentials: 'same-origin'})).status", path)


def fetch_json(page: Page, path: str):
    return page.evaluate("async (p) => (await fetch(p, {credentials: 'same-origin'})).json()", path)


def no_horizontal_scroll(page: Page) -> bool:
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def context(browser: Browser, width: int, height: int, tiles: str = "mock", **kw) -> BrowserContext:
    """A fresh browser profile that can only reach the local app.

    tiles="mock": the basemap style request is answered locally with a plain style.
    tiles="blocked": the style request fails, as when the tile provider is offline or blocked."""
    ctx = browser.new_context(viewport={"width": width, "height": height}, locale="en-IN", **kw)

    def route(r):
        url = r.request.url
        if url.startswith(WEB):
            r.continue_()
        elif url.startswith(STYLE_URL) and tiles == "mock":
            r.fulfill(json=MOCK_STYLE, headers={"Access-Control-Allow-Origin": "*"})  # as the real CDN sends
        else:  # tile provider in "blocked" mode, fonts, anything external
            EXTERNAL.add(url.split("/")[2])
            r.abort()

    ctx.route("**/*", route)
    return ctx


EXTERNAL: set[str] = set()  # external hosts the app tried to reach (all refused locally)


# ------------------------------------------------------------------ scenarios
def s0_round1_screen_unchanged(browser: Browser, pw: dict[str, str], r: Report) -> None:
    """P4-12: / still shows the Round 1 voice screen, not the V2 app."""
    sc = "S0 Round 1 screen at /"
    ctx = context(browser, 360, 800)
    page = ctx.new_page()
    watch(page, r, sc)
    page.goto(f"{WEB}/")
    expect(page.get_by_text("AI \u0cb8\u0cb9\u0cbe\u0caf\u0c95")).to_be_visible()
    r.check(sc, "Round 1 header and visit/follow-up tabs render",
            page.get_by_role("navigation", name="Sections").is_visible())
    r.check(sc, "no V2 banner or sign-in form on /",
            page.get_by_test_id("synthetic-banner").count() == 0 and page.get_by_role("button", name="Sign in").count() == 0)
    r.shot(page, "s0_round1_root_360")
    ctx.close()


def s1_worker_a_flow(browser: Browser, pw: dict[str, str], r: Report) -> None:
    """P4-01/03/04/05/09/11 at 360 px: pin preview leaks no identity, explicit confirm, member, reset."""
    sc = "S1 worker A 360px"
    ctx = context(browser, 360, 800)
    page = ctx.new_page()
    calls = watch(page, r, sc)
    page.goto(f"{WEB}/v2")
    expect(page.get_by_role("button", name="Sign in")).to_be_visible()
    r.check(sc, "synthetic banner on the login page", page.get_by_test_id("synthetic-banner").is_visible())
    r.shot(page, "s1_01_login_360")
    login(page, "demo_worker_a", pw["demo_worker_a"])
    r.check(sc, "list shows exactly H-001..H-006", list_ids(page) == A_HOUSES, list_ids(page))
    markers_ok = wait_markers(page, 6)
    r.check(sc, "map shows exactly six pins", markers_ok and sorted(marker_ids(page)) == A_HOUSES, marker_ids(page))
    page.wait_for_timeout(1500)  # give the (mocked) style request time to settle
    r.check(sc, "configured basemap style loads without a map error", page.get_by_test_id("map-problem").count() == 0)
    r.check(sc, "no person name anywhere before confirmation", not EVERY_NAME_RE.search(body_text(page)))
    r.check(sc, "no horizontal scroll at 360px", no_horizontal_scroll(page))
    r.shot(page, "s1_02_six_pins_360")

    if markers_ok:
        page.locator('.asha-pin[data-household="H-003"]').click()
    else:
        page.locator('ul[aria-label="Households"] button[data-household="H-003"]').click()
    expect(page.get_by_test_id("household-preview")).to_be_visible()
    preview = page.get_by_test_id("household-preview").inner_text()
    r.check(sc, "pin opens a preview with ID and member count", "H-003" in preview and "4" in preview)
    r.check(sc, "preview is not a selection (breadcrumb)", breadcrumb(page) == "Selected: H-003 (not confirmed) / No member",
            breadcrumb(page))
    r.check(sc, "preview shows no member names", not any(n in body_text(page) for n in H003_NAMES))
    r.check(sc, "no members request before confirmation", not any("/members" in c for c in calls),
            [c for c in calls if "/members" in c])
    r.shot(page, "s1_03_preview_h003_360")

    page.get_by_role("button", name="Confirm household").click()
    expect(page.get_by_test_id("household-confirmed")).to_be_visible()
    member_buttons = page.locator("[data-member]")
    names = member_buttons.evaluate_all("els => els.map(e => e.querySelector('span span').textContent)")
    r.check(sc, "confirmed household lists its 4 real members", sorted(names) == sorted(H003_NAMES), names)
    r.check(sc, "breadcrumb: household confirmed, no member", breadcrumb(page) == "Selected: H-003 / No member",
            breadcrumb(page))
    r.shot(page, "s1_04_confirmed_members_360")

    page.locator("[data-member]", has_text=re.compile(r"^Kavya Halli")).click()
    expect(page.get_by_test_id("member-preview")).to_be_visible()
    r.check(sc, "member preview is not a selection",
            breadcrumb(page) == "Selected: H-003 / Kavya Halli (not selected)", breadcrumb(page))
    page.get_by_role("button", name="Select member").click()
    expect(page.get_by_test_id("member-selected")).to_be_visible()
    r.check(sc, "breadcrumb shows H-003 / Kavya Halli", breadcrumb(page) == "Selected: H-003 / Kavya Halli",
            breadcrumb(page))
    member_checks = [c for c in calls if re.search(r"/households/[^/]+/members/[^/?]+$", c)]
    r.check(sc, "member selection was rechecked by the server", len(member_checks) == 1, member_checks)
    r.check(sc, "no horizontal scroll with members open", no_horizontal_scroll(page))
    r.shot(page, "s1_05_member_selected_360")

    show_households(page)
    page.locator('ul[aria-label="Households"] button[data-household="H-004"]').click()
    expect(page.get_by_test_id("household-preview")).to_be_visible()
    r.check(sc, "choosing another household clears the member",
            breadcrumb(page) == "Selected: H-004 (not confirmed) / No member", breadcrumb(page))
    r.check(sc, "previous members are gone from the page", not any(n in body_text(page) for n in H003_NAMES))
    r.shot(page, "s1_06_switch_clears_360")

    page.get_by_role("button", name="Log out").click()
    expect(page.get_by_role("button", name="Sign in")).to_be_visible()
    r.check(sc, "logout returns to sign-in with no household data", not EVERY_NAME_RE.search(body_text(page))
            and "H-00" not in body_text(page))
    page.reload()
    expect(page.get_by_role("button", name="Sign in")).to_be_visible()
    r.check(sc, "after reload the old session is gone", fetch_status(page, "/api/v2/households") == 401)
    r.shot(page, "s1_07_logged_out_360")
    ctx.close()


def s2_worker_b_scope(browser: Browser, pw: dict[str, str], r: Report) -> None:
    """P4-01/06 at 412 px: Worker B sees B only; direct URLs for A's records are refused."""
    sc = "S2 worker B 412px"
    ctx = context(browser, 412, 915)
    page = ctx.new_page()
    watch(page, r, sc)
    login(page, "demo_worker_b", pw["demo_worker_b"])
    r.check(sc, "list shows exactly H-007..H-012", list_ids(page) == B_HOUSES, list_ids(page))
    r.check(sc, "map shows exactly six pins", wait_markers(page, 6) and sorted(marker_ids(page)) == B_HOUSES)
    r.check(sc, "no horizontal scroll at 412px", no_horizontal_scroll(page))
    r.shot(page, "s2_01_worker_b_412")
    statuses = {p: fetch_status(page, p) for p in (
        "/api/v2/households/H-003", "/api/v2/households/h-003", "/api/v2/households/H-003/members",
        "/api/v2/people/P-011", "/api/v2/households/H-007/members/P-011")}
    r.check(sc, "direct requests for Territory A records all return 404", set(statuses.values()) == {404}, statuses)
    near_a = fetch_json(page, f"/api/v2/households/nearby?lat={H003['lat']}&lon={H003['lon']}&radius_m=5000")
    r.check(sc, "nearby around an A pin returns only B households",
            sorted(x["public_id"] for x in near_a) == B_HOUSES, [x["public_id"] for x in near_a])
    page.get_by_label("Search by household ID or label").fill("H-003")
    page.get_by_role("button", name="Search").click()
    expect(page.get_by_test_id("status")).to_contain_text("No household in your area matches")
    r.check(sc, "searching for an A household finds nothing", list_ids(page) == [])
    r.shot(page, "s2_02_search_a_household_412")
    ctx.close()


def s3_no_tiles_no_gps(browser: Browser, pw: dict[str, str], r: Report) -> None:
    """P4-08: map tiles blocked and location denied: search/list still reach a member."""
    sc = "S3 tiles blocked + GPS denied 360px"
    ctx = context(browser, 360, 800, tiles="blocked")
    page = ctx.new_page()
    watch(page, r, sc)
    login(page, "demo_worker_a", pw["demo_worker_a"])
    expect(page.get_by_test_id("map-problem")).to_be_visible(timeout=20_000)
    r.check(sc, "tile failure is reported to the worker", True)
    r.check(sc, "pins still drawn without a basemap", wait_markers(page, 6))
    r.check(sc, "list still has six households", list_ids(page) == A_HOUSES)
    page.get_by_role("button", name="Use my location").click()
    status = page.locator("section[aria-labelledby='nearby-heading'] [role=status]")
    expect(status).to_be_visible(timeout=15_000)
    r.check(sc, "denied location gives a message, not a selection",
            breadcrumb(page) == "Selected: No household / No member", status.inner_text())
    r.shot(page, "s3_01_tiles_and_gps_unavailable_360")
    page.get_by_label("Search by household ID or label").fill("h-003")
    page.get_by_role("button", name="Search").click()
    expect(page.get_by_role("heading", name="Search results (1)")).to_be_visible()
    page.locator('ul[aria-label="Households"] button[data-household="H-003"]').click()
    page.get_by_role("button", name="Confirm household").click()
    page.locator("[data-member]", has_text=re.compile(r"^Baby of Kavya Halli")).click()
    page.get_by_role("button", name="Select member").click()
    expect(page.get_by_test_id("member-selected")).to_be_visible()
    r.check(sc, "manual search reached the member",
            breadcrumb(page) == "Selected: H-003 / Baby of Kavya Halli", breadcrumb(page))
    r.shot(page, "s3_02_manual_selection_360")
    ctx.close()


def s4_gps_hint(browser: Browser, pw: dict[str, str], r: Report) -> None:
    """GPS granted at H-003: suggestions only, nothing auto-selected."""
    sc = "S4 GPS hint 412px"
    ctx = context(browser, 412, 915, geolocation={"latitude": H003["lat"], "longitude": H003["lon"], "accuracy": 15},
                  permissions=["geolocation"])
    page = ctx.new_page()
    calls = watch(page, r, sc)
    login(page, "demo_worker_a", pw["demo_worker_a"])
    page.get_by_role("button", name="Use my location").click()
    suggestions = page.locator("[data-nearby]")
    expect(suggestions.first).to_be_visible()
    order = suggestions.evaluate_all("els => els.map(e => e.dataset.nearby)")
    r.check(sc, "nearest suggestion is H-003 and all are Territory A",
            order[:1] == ["H-003"] and set(order) <= set(A_HOUSES), order)
    r.check(sc, "a GPS fix selects nothing", breadcrumb(page) == "Selected: No household / No member", breadcrumb(page))
    r.check(sc, "no household detail or members fetched from GPS alone",
            not any(re.search(r"/households/(?!nearby)[^?]+", c) for c in calls))
    r.shot(page, "s4_01_gps_suggestions_412")
    suggestions.first.click()
    r.check(sc, "a suggestion becomes only a candidate",
            breadcrumb(page) == "Selected: H-003 (not confirmed) / No member", breadcrumb(page))
    r.shot(page, "s4_02_suggestion_preview_412")
    ctx.close()


def s5_supervisors(browser: Browser, pw: dict[str, str], r: Report) -> None:
    """P4-02 at desktop width: supervisors see exactly their grants."""
    sc = "S5 supervisors 1280px"
    for user, expected in (("demo_supervisor", A_HOUSES + B_HOUSES), ("e2e_supervisor_a", A_HOUSES),
                           ("demo_admin", A_HOUSES + B_HOUSES)):
        ctx = context(browser, 1280, 800)
        page = ctx.new_page()
        watch(page, r, sc)
        login(page, user, pw[user])
        r.check(sc, f"{user} sees exactly {len(expected)} households", list_ids(page) == expected, list_ids(page))
        r.check(sc, f"{user} map has {len(expected)} pins", wait_markers(page, len(expected)))
        r.shot(page, f"s5_{user}_1280")
        ctx.close()


def s6_keyboard_and_revocation(browser: Browser, pw: dict[str, str], r: Report) -> None:
    """Keyboard-only selection, then a grant revoked mid-selection is refused at confirmation."""
    sc = "S6 keyboard + revoked grant 412px"
    ctx = context(browser, 412, 915)
    page = ctx.new_page()
    watch(page, r, sc)
    login(page, "demo_worker_a", pw["demo_worker_a"])
    if wait_markers(page, 6):
        page.locator('.asha-pin[data-household="H-002"]').focus()
        page.keyboard.press("Enter")
        r.check(sc, "map pin works from the keyboard",
                breadcrumb(page) == "Selected: H-002 (not confirmed) / No member", breadcrumb(page))
    page.locator('ul[aria-label="Households"] button[data-household="H-005"]').focus()
    page.keyboard.press("Enter")
    expect(page.get_by_test_id("household-preview")).to_be_visible()
    expect(page.locator("#selection-heading")).to_be_focused()  # focus moves to the preview
    page.keyboard.press("Tab")  # next stop after the heading is Confirm
    focused = page.evaluate("document.activeElement && document.activeElement.textContent")
    r.check(sc, "Tab from the preview reaches Confirm household", focused == "Confirm household", focused)
    page.keyboard.press("Enter")
    expect(page.get_by_test_id("household-confirmed")).to_be_visible()
    r.check(sc, "keyboard confirmed H-005", breadcrumb(page) == "Selected: H-005 / No member", breadcrumb(page))

    show_households(page)
    page.locator('ul[aria-label="Households"] button[data-household="H-006"]').click()
    e2e_sql("UPDATE territory_assignments SET ends_at = now() WHERE ends_at IS NULL AND user_id = "
            "(SELECT id FROM users WHERE username = 'demo_worker_a')")
    try:
        page.get_by_role("button", name="Confirm household").click()
        expect(page.get_by_test_id("status")).to_contain_text("not available to your account")
        r.check(sc, "revoked grant: confirmation refused and selection cleared",
                breadcrumb(page) == "Selected: No household / No member", breadcrumb(page))
        expect(page.get_by_role("heading", name="Your households (0)")).to_be_visible()
        r.check(sc, "list reloads empty after revocation", list_ids(page) == [])
        r.check(sc, "the explanation stays on screen after the reload",
                "not available to your account" in page.get_by_test_id("status").inner_text())
        r.shot(page, "s6_revoked_grant_412")
    finally:
        e2e_sql("INSERT INTO territory_assignments (id, user_id, territory_id, starts_at) SELECT gen_random_uuid(), "
                "u.id, t.id, now() FROM users u, territories t WHERE u.username = 'demo_worker_a' AND t.code = 'DEMO-A'")
    ctx.close()


def s7_session_ends_mid_selection(browser: Browser, pw: dict[str, str], r: Report) -> None:
    """A session revoked elsewhere: the next action returns to sign-in with everything cleared."""
    sc = "S7 session revoked mid-selection 360px"
    ctx = context(browser, 360, 800)
    page = ctx.new_page()
    watch(page, r, sc)
    login(page, "demo_worker_a", pw["demo_worker_a"])
    page.locator('ul[aria-label="Households"] button[data-household="H-003"]').click()
    page.get_by_role("button", name="Confirm household").click()
    page.locator("[data-member]", has_text=re.compile(r"^Kavya Halli")).click()
    other = ctx.new_page()  # same browser session, second tab: log out there
    other.goto(f"{WEB}/v2")
    status = other.evaluate("async (h) => (await fetch('/api/v2/auth/logout', {method: 'POST', headers: h})).status",
                            CSRF)
    other.close()
    r.check(sc, "logout in another tab succeeded", status == 204, status)
    page.get_by_role("button", name="Select member").click()
    expect(page.get_by_role("button", name="Sign in")).to_be_visible()
    r.check(sc, "returned to sign-in with an explanation", "session has ended" in body_text(page))
    r.check(sc, "no member names left on screen", not EVERY_NAME_RE.search(body_text(page)))
    r.shot(page, "s7_session_ended_360")
    ctx.close()


SCENARIOS = [s0_round1_screen_unchanged, s1_worker_a_flow, s2_worker_b_scope, s3_no_tiles_no_gps, s4_gps_hint, s5_supervisors,
             s6_keyboard_and_revocation, s7_session_ends_mid_selection]


# ------------------------------------------------------------------ main
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--channel", default="msedge", help="Playwright browser channel (msedge, chrome)")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    report = Report()
    passwords = {u: secrets.token_urlsafe(18) for u in ACCOUNTS}  # one-time, this process only
    vite: subprocess.Popen | None = None
    vite_log = open(OUT / "vite.log", "w", encoding="utf-8")
    started = time.monotonic()
    try:
        print("Building api-e2e and creating the disposable e2e database ...")
        compose("--profile", "e2e", "build", "api-e2e")
        setup = compose("--profile", "e2e", "run", "--rm", "-T", "api-e2e", "python", "-m", "tests.e2e_bootstrap",
                        "setup", stdin=json.dumps(passwords))
        report.info["e2e_database"] = json.loads(setup.strip().splitlines()[-1])
        compose("--profile", "e2e", "up", "-d", "api-e2e")
        wait_http(f"{API}/api/health")
        with urllib.request.urlopen(f"{API}/api/health") as h:
            report.info["e2e_api_health"] = json.loads(h.read())
        env = {**os.environ, "ASHA_BACKEND_URL": API, "ASHA_DEV_HTTP": "1", "VITE_MAP_STYLE_URL": STYLE_URL}
        vite = subprocess.Popen(["node", "node_modules/vite/bin/vite.js", "--host", "localhost", "--port", "5174",
                                 "--strictPort"], cwd=ROOT / "frontend", env=env, stdout=vite_log,
                                stderr=subprocess.STDOUT)
        wait_http(f"{WEB}/v2")

        with sync_playwright() as p:
            browser = p.chromium.launch(channel=args.channel, headless=not args.headed)
            report.info["browser"] = f"{args.channel} {browser.version}"
            print(f"Browser: {report.info['browser']}")
            for scenario in SCENARIOS:
                print(scenario.__doc__.strip().splitlines()[0])
                try:
                    scenario(browser, passwords, report)
                except Exception as exc:  # record and continue with the next scenario
                    report.check(scenario.__name__, "scenario completed", False,
                                 f"{type(exc).__name__}: {str(exc)[:500]}")
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
        compose("--profile", "e2e", "stop", "api-e2e", check=False)
        compose("--profile", "e2e", "rm", "-f", "api-e2e", check=False)
        teardown = compose("--profile", "e2e", "run", "--rm", "-T", "api-e2e", "python", "-m",
                           "tests.e2e_bootstrap", "teardown", check=False)
        report.info["teardown"] = teardown.strip().splitlines()[-1] if teardown.strip() else "teardown failed"
        report.info["duration_s"] = round(time.monotonic() - started, 1)
        report.info["external_hosts_refused"] = sorted(EXTERNAL)
        summary = {"passed": sum(c["ok"] for c in report.checks), "failed": len(report.failed),
                   "checks": report.checks, "screenshots": report.screens, "console_errors": report.console,
                   "info": report.info}
        (OUT / "report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"\n{summary['passed']} passed, {summary['failed']} failed · report: {OUT / 'report.json'}")
    return 1 if report.failed or not report.checks else 0


if __name__ == "__main__":
    sys.exit(main())
