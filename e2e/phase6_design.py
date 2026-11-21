"""Phase 6 design QA: responsive layout, accessibility (axe-core) and the leave-visit dialog.

Run from the repository root with the Docker stack up (`docker compose up -d`):

    uv run --no-project --with playwright==1.64.1 python -I e2e/phase6_design.py --channel msedge

Reuses the Phase 5 harness (disposable asha_saathi_e2e database, api-e2e with MOCK speech,
hermetic browser, teardown). Screenshots and report.json go to data/e2e/phase6/ (git-ignored).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import Browser, Page, expect

sys.path.insert(0, str(Path(__file__).parent))
import phase4_browser as p4  # noqa: E402
import phase5_browser as p5  # noqa: E402

OUT = p4.ROOT / "data" / "e2e" / "phase6"
p4.OUT = OUT
p5.OUT = OUT
AXE = p4.ROOT / "frontend" / "node_modules" / "axe-core" / "axe.min.js"
WIDTHS = [320, 360, 375, 412, 768, 1024, 1280, 1536]
AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]


def axe(page: Page, r: p4.Report, sc: str, where: str) -> None:
    """Run axe-core on the current page. Serious or critical WCAG A/AA violations fail the check."""
    # Let entrance animations and colour transitions finish (looping ones are excluded).
    page.evaluate(
        """() => Promise.all(document.getAnimations()
            .filter(a => a.effect && a.effect.getTiming().iterations !== Infinity)
            .map(a => a.finished.catch(() => null)))"""
    )
    page.wait_for_timeout(250)
    page.add_script_tag(path=str(AXE))
    violations = page.evaluate(
        """async (tags) => (await axe.run(document, {runOnly: {type: 'tag', values: tags}})).violations
            .map(v => ({id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help,
                        targets: v.nodes.slice(0, 3).map(n => n.target.join(' '))}))""",
        AXE_TAGS,
    )
    blocking = [v for v in violations if v["impact"] in ("serious", "critical")]
    r.info.setdefault("axe", {})[where] = violations
    r.check(sc, f"axe: no serious/critical WCAG A/AA violations on {where}", not blocking, blocking)


def min_height(page: Page, name: str) -> float:
    box = page.get_by_role("button", name=name).first.bounding_box()
    return box["height"] if box else 0.0


def d1_responsive(browser: Browser, pw: dict[str, str], r: p4.Report, ids: dict[str, str]) -> None:
    """D1: every screen fits 320-1536 px without horizontal scrolling; touch targets >= 44 px."""
    sc = "D1 responsive"
    for width in WIDTHS:
        height = 800 if width < 768 else 900
        ctx = p5.p5_context(browser, width, height)
        page = ctx.new_page()
        p4.watch(page, r, f"{sc} {width}")
        p4.login(page, "demo_worker_a", pw["demo_worker_a"])
        r.check(sc, f"{width}px households: no horizontal scroll", p4.no_horizontal_scroll(page))
        if width in (320, 360, 412, 1280):
            r.shot(page, f"d1_households_{width}")
        page.locator('ul[aria-label="Households"] button[data-household="H-003"]').click()
        expect(page.get_by_test_id("household-preview")).to_be_visible()
        r.check(sc, f"{width}px preview: no horizontal scroll", p4.no_horizontal_scroll(page))
        if width < 768:
            r.check(sc, f"{width}px Confirm household is a 44 px+ target", min_height(page, "Confirm household") >= 44)
        if width in (360, 1280):
            r.shot(page, f"d1_preview_{width}")
        page.get_by_role("button", name="Confirm household").click()
        expect(page.get_by_test_id("household-confirmed")).to_be_visible()
        page.locator("[data-member]", has_text=re.compile(r"^Kavya Halli")).click()
        expect(page.get_by_test_id("member-preview")).to_be_visible()
        r.check(sc, f"{width}px member preview: no horizontal scroll", p4.no_horizontal_scroll(page))
        if width in (360, 1280):
            r.shot(page, f"d1_member_preview_{width}")
        page.get_by_role("button", name="Select member").click()
        expect(page.get_by_test_id("member-selected")).to_be_visible()
        expect(page.get_by_test_id("voice-panel")).to_be_visible()
        r.check(sc, f"{width}px member and voice: no horizontal scroll", p4.no_horizontal_scroll(page))
        if width < 768:
            r.check(sc, f"{width}px Start voice visit is a 44 px+ target", min_height(page, "Start voice visit") >= 44)
        if width in (320, 360, 768, 1280, 1536):
            r.shot(page, f"d1_member_{width}")
        ctx.close()


def d2_accessibility(browser: Browser, pw: dict[str, str], r: p4.Report, ids: dict[str, str]) -> None:
    """D2: axe-core WCAG 2.2 A/AA scan of login, households, preview, household, member, live visit."""
    sc = "D2 accessibility 360px"
    ctx = p5.p5_context(browser, 360, 800)
    page = ctx.new_page()
    p4.watch(page, r, sc)
    page.goto(f"{p4.WEB}/v2")
    expect(page.get_by_role("button", name="Sign in")).to_be_visible()
    axe(page, r, sc, "login")
    p4.login(page, "demo_worker_a", pw["demo_worker_a"])
    p4.wait_markers(page, 6)
    axe(page, r, sc, "households")
    page.locator('ul[aria-label="Households"] button[data-household="H-006"]').click()
    expect(page.get_by_test_id("household-preview")).to_be_visible()
    axe(page, r, sc, "household preview")
    page.get_by_role("button", name="Confirm household").click()
    expect(page.get_by_test_id("household-confirmed")).to_be_visible()
    axe(page, r, sc, "confirmed household")
    page.locator("[data-member]", has_text=re.compile(r"^Sowmya Hebbar")).click()
    page.get_by_role("button", name="Select member").click()
    expect(page.get_by_test_id("member-selected")).to_be_visible()
    axe(page, r, sc, "member and visit setup")
    page.get_by_role("radio", name=re.compile("Routine")).check()
    page.get_by_role("button", name="Start voice visit").click()
    expect(page.locator('section[aria-label="Visit record"]')).to_be_visible(timeout=45_000)
    axe(page, r, sc, "live voice visit")
    r.shot(page, "d2_live_visit_360")
    page.get_by_role("button", name="Cancel visit").click()
    ctx.close()


def d3_leave_dialog(browser: Browser, pw: dict[str, str], r: p4.Report, ids: dict[str, str]) -> None:
    """D3: leaving a live visit asks first; Keep recording keeps it, End visit ends it unsaved."""
    sc = "D3 leave-visit dialog 412px"
    ctx = p5.p5_context(browser, 412, 915)
    page = ctx.new_page()
    p4.watch(page, r, sc)
    p4.login(page, "demo_worker_a", pw["demo_worker_a"])
    p5.select_member(page, "H-004", "Rekha Doddamane")
    page.get_by_role("radio", name=re.compile("Routine")).check()
    page.get_by_role("button", name="Start voice visit").click()
    expect(page.get_by_test_id("bound-verified")).to_be_visible(timeout=20_000)
    journey = page.get_by_role("navigation", name="Visit journey")
    journey.get_by_role("button", name=re.compile("^Households")).click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()
    r.check(sc, "dialog explains nothing is saved", "Nothing has been saved" in dialog.inner_text())
    r.shot(page, "d3_leave_dialog_412")
    dialog.get_by_role("button", name="Keep recording").click()
    expect(dialog).to_be_hidden()
    r.check(sc, "Keep recording keeps the visit open", page.get_by_test_id("voice-panel").is_visible())
    journey.get_by_role("button", name=re.compile("^Households")).click()
    page.get_by_role("dialog").get_by_role("button", name="End visit").click()
    expect(page.locator('ul[aria-label="Households"]')).to_be_visible()
    r.check(sc, "End visit closes the voice panel", page.get_by_test_id("voice-panel").count() == 0)
    rows = p4.e2e_sql(
        "SELECT count(*) FROM v2_visits v JOIN people p ON p.id = v.person_id WHERE p.full_name = 'Rekha Doddamane'"
    ).strip()
    r.check(sc, "nothing saved for the abandoned visit", rows == "0", rows)
    ctx.close()


def d4_round1_unchanged(browser: Browser, pw: dict[str, str], r: p4.Report, ids: dict[str, str]) -> None:
    """D4: / still renders the Round 1 screen without the V2 design system."""
    sc = "D4 Round 1 at /"
    ctx = p4.context(browser, 360, 800)
    page = ctx.new_page()
    page.goto(f"{p4.WEB}/")
    expect(page.get_by_role("navigation", name="Sections")).to_be_visible()
    r.check(sc, "no V2 root on /", page.locator(".v2").count() == 0)
    family = page.evaluate("getComputedStyle(document.body).fontFamily")
    r.check(sc, "Round 1 body font unchanged (no Mulish)", "Mulish" not in family, family)
    r.shot(page, "d4_round1_360")
    ctx.close()


p5.SCENARIOS = [d4_round1_unchanged, d1_responsive, d2_accessibility, d3_leave_dialog]

if __name__ == "__main__":
    sys.exit(p5.main())
