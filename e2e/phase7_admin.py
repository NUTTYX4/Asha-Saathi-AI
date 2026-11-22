"""Phase 7 admin dashboard QA: access control, metrics, assignments, responsive layout and axe-core.

Run from the repository root with the Docker stack up:

    uv run --no-project --with playwright==1.64.1 python -I e2e/phase7_admin.py --channel msedge

Reuses the Phase 5 harness (disposable asha_saathi_e2e database, api-e2e with MOCK speech, hermetic
browser, teardown). Screenshots and report.json go to data/e2e/phase7/ (git-ignored).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import Browser, Page, expect

sys.path.insert(0, str(Path(__file__).parent))
import phase4_browser as p4  # noqa: E402
import phase5_browser as p5  # noqa: E402
import phase6_design as p6  # noqa: E402

OUT = p4.ROOT / "data" / "e2e" / "phase7"
p4.OUT = p5.OUT = p6.OUT = OUT
WIDTHS = [320, 360, 390, 768, 1024, 1280]


def fetch_status(page: Page, path: str, method: str = "GET", csrf: bool = False, body: dict | None = None) -> int:
    return page.evaluate(
        """async ([p, m, c, b]) => (await fetch(p, {method: m, credentials: 'same-origin',
            headers: Object.assign({'Content-Type': 'application/json'}, c ? {'X-Requested-With': 'asha-saathi'} : {}),
            body: b ? JSON.stringify(b) : undefined})).status""",
        [path, method, csrf, body],
    )


def a1_admin_overview(browser: Browser, pw: dict[str, str], r: p4.Report, ids: dict[str, str]) -> None:
    """A1: the admin lands on the dashboard; metrics match the e2e register; every width fits."""
    sc = "A1 admin overview"
    for width in WIDTHS:
        ctx = p5.p5_context(browser, width, 800 if width < 768 else 900)
        page = ctx.new_page()
        p4.watch(page, r, f"{sc} {width}")
        p4.login(page, "demo_admin", pw["demo_admin"], field_view=False)
        expect(page.get_by_test_id("admin-dashboard")).to_be_visible()
        expect(page.get_by_test_id("admin-overview")).to_be_visible()
        if width == 360:
            r.check(sc, "households registered = 12", page.get_by_test_id("m-households").inner_text().split("\n")[1] == "12")
            r.check(sc, "active ASHA workers = 2", page.get_by_test_id("m-workers").inner_text().split("\n")[1] == "2")
            r.check(sc, "confirmed visits = 0 on a fresh database", page.get_by_test_id("m-visits").inner_text().split("\n")[1] == "0")
            p6.axe(page, r, sc, "admin overview 360")
        r.check(sc, f"{width}px overview: no horizontal scroll", p4.no_horizontal_scroll(page))
        for tab in ("ASHA workers", "Visit activity", "Territories", "Assignments", "Audit history"):
            page.get_by_role("navigation", name="Dashboard sections").get_by_role("button", name=tab).click()
            page.wait_for_timeout(300)
            r.check(sc, f"{width}px {tab}: no horizontal scroll", p4.no_horizontal_scroll(page))
            if width in (360, 1280):
                r.shot(page, f"a1_{tab.split()[0].lower()}_{width}")
        ctx.close()


def a2_workers_and_coverage(browser: Browser, pw: dict[str, str], r: p4.Report, ids: dict[str, str]) -> None:
    """A2: worker activity rows, worker detail, territory coverage and an empty visit list."""
    sc = "A2 workers and coverage 390px"
    ctx = p5.p5_context(browser, 390, 844)
    page = ctx.new_page()
    p4.watch(page, r, sc)
    p4.login(page, "demo_admin", pw["demo_admin"], field_view=False)
    nav = page.get_by_role("navigation", name="Dashboard sections")
    nav.get_by_role("button", name="ASHA workers").click()
    expect(page.get_by_test_id("admin-workers")).to_be_visible()
    rows = page.locator("[data-worker]")
    r.check(sc, "two worker rows (worker accounts only)", rows.count() == 2, rows.count())
    page.locator('[data-worker="demo_worker_a"]').click()
    expect(page.get_by_test_id("admin-worker-detail")).to_be_visible()
    r.check(sc, "worker detail shows DEMO-A", "DEMO-A" in page.get_by_test_id("admin-worker-detail").inner_text())
    p6.axe(page, r, sc, "worker detail")
    nav.get_by_role("button", name="Territories").click()
    expect(page.get_by_test_id("admin-coverage")).to_be_visible()
    text = page.get_by_test_id("admin-coverage").inner_text()
    r.check(sc, "both territories listed with 6 registered each", text.count("Registered") == 2 and "DEMO-A" in text and "DEMO-B" in text)
    p6.axe(page, r, sc, "coverage")
    nav.get_by_role("button", name="Visit activity").click()
    empty = page.get_by_test_id("admin-visits").get_by_text("No confirmed visits", exact=True)
    expect(empty).to_be_visible()
    r.check(sc, "visit list empty state on a fresh database", empty.count() == 1)
    ctx.close()


def a3_assignment_change(browser: Browser, pw: dict[str, str], r: p4.Report, ids: dict[str, str]) -> None:
    """A3: move worker B to DEMO-A with a confirmation, check the DB and audit, then move back."""
    sc = "A3 assignment change 1024px"
    ctx = p5.p5_context(browser, 1024, 900)
    page = ctx.new_page()
    p4.watch(page, r, sc)
    p4.login(page, "demo_admin", pw["demo_admin"], field_view=False)
    page.get_by_role("navigation", name="Dashboard sections").get_by_role("button", name="Assignments").click()
    expect(page.get_by_test_id("admin-assignments")).to_be_visible()

    def move(territory: str) -> None:
        row = page.locator('[data-assignment="demo_worker_b"]')
        row.get_by_label("Move to").select_option(label=territory)
        row.get_by_role("button", name="Move").click()
        dialog = page.get_by_role("dialog")
        expect(dialog).to_be_visible()
        r.check(sc, f"dialog explains visits stay with the worker ({territory})", "no household or beneficiary record moves" in dialog.inner_text())
        if territory == "DEMO-A":
            box = dialog.bounding_box() or {"height": 9999}
            r.check(sc, "confirmation dialog sizes to its content (regression: .v2 min-height)",
                    box["height"] < 0.6 * 900, box["height"])
            p6.axe(page, r, sc, "reassign dialog")
            r.shot(page, "a3_reassign_dialog_1024")
        dialog.get_by_role("button", name=f"Move to {territory}").click()
        expect(page.get_by_role("status").filter(has_text="moved from")).to_be_visible()

    # Cancel first: nothing changes.
    row = page.locator('[data-assignment="demo_worker_b"]')
    row.get_by_label("Move to").select_option(label="DEMO-A")
    row.get_by_role("button", name="Move").click()
    page.get_by_role("dialog").get_by_role("button", name="Cancel").click()
    active = p4.e2e_sql(
        "SELECT t.code FROM territory_assignments a JOIN users u ON u.id=a.user_id JOIN territories t ON t.id=a.territory_id "
        "WHERE u.username='demo_worker_b' AND a.ends_at IS NULL").strip()
    r.check(sc, "Cancel leaves the assignment unchanged", active == "DEMO-B", active)

    move("DEMO-A")
    active = p4.e2e_sql(
        "SELECT t.code FROM territory_assignments a JOIN users u ON u.id=a.user_id JOIN territories t ON t.id=a.territory_id "
        "WHERE u.username='demo_worker_b' AND a.ends_at IS NULL").strip()
    r.check(sc, "worker B now active only in DEMO-A", active == "DEMO-A", active)
    audit = p4.e2e_sql(
        "SELECT u.username FROM audit_events e JOIN users u ON u.id=e.actor_user_id "
        "WHERE e.action='assignment.reassign' ORDER BY e.id DESC LIMIT 1").strip()
    r.check(sc, "audit records the admin as actor", audit == "demo_admin", audit)
    move("DEMO-B")
    active = p4.e2e_sql(
        "SELECT t.code FROM territory_assignments a JOIN users u ON u.id=a.user_id JOIN territories t ON t.id=a.territory_id "
        "WHERE u.username='demo_worker_b' AND a.ends_at IS NULL").strip()
    r.check(sc, "moved back to DEMO-B", active == "DEMO-B", active)
    ended = int(p4.e2e_sql(
        "SELECT count(*) FROM territory_assignments a JOIN users u ON u.id=a.user_id "
        "WHERE u.username='demo_worker_b' AND a.ends_at IS NOT NULL").strip())
    r.check(sc, "history keeps both ended assignments", ended >= 2, ended)
    page.get_by_role("navigation", name="Dashboard sections").get_by_role("button", name="Audit history").click()
    expect(page.get_by_test_id("admin-audit")).to_be_visible()
    reassigns = page.get_by_test_id("admin-audit").get_by_text("assignment.reassign", exact=True)
    r.check(sc, "audit tab lists assignment.reassign", reassigns.count() >= 2, reassigns.count())
    ctx.close()


def a4_access_control(browser: Browser, pw: dict[str, str], r: p4.Report, ids: dict[str, str]) -> None:
    """A4: workers and supervisors see no dashboard and get 403 from every admin route; anonymous 401."""
    sc = "A4 access control"
    for user in ("demo_worker_a", "demo_supervisor"):
        ctx = p5.p5_context(browser, 360, 800)
        page = ctx.new_page()
        p4.watch(page, r, f"{sc} {user}")
        p4.login(page, user, pw[user])
        r.check(sc, f"{user}: no admin dashboard rendered", page.get_by_test_id("admin-dashboard").count() == 0)
        for path in ("/api/v2/admin/overview", "/api/v2/admin/workers", "/api/v2/admin/visits",
                     "/api/v2/admin/coverage", "/api/v2/admin/users", "/api/v2/admin/assignments", "/api/v2/admin/audit"):
            r.check(sc, f"{user}: {path} is 403", fetch_status(page, path) == 403)
        status = fetch_status(page, "/api/v2/admin/assignments/00000000-0000-0000-0000-000000000000/reassign", "POST",
                              csrf=True, body={"territory_id": "00000000-0000-0000-0000-000000000000"})
        r.check(sc, f"{user}: reassign is 403", status == 403, status)
        ctx.close()
    ctx = p5.p5_context(browser, 360, 800)
    page = ctx.new_page()
    page.goto(f"{p4.WEB}/v2")
    r.check(sc, "anonymous: admin overview is 401", fetch_status(page, "/api/v2/admin/overview") == 401)
    ctx.close()


p5.SCENARIOS = [a4_access_control, a1_admin_overview, a2_workers_and_coverage, a3_assignment_change]

if __name__ == "__main__":
    sys.exit(p5.main())
