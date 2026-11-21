# Phase 6: frontend design implementation notes

Branch `v2/frontend-design` (from `126fd09`). Frontend only: the backend, database, Gnani and Gemini adapters, clinical rules, session binding, read-back/confirm logic and exactly-once save are untouched.

## What changed

**Navigation.** The phone gets a journey of three screens: Households, then Household, then Member and visit.
- A journey rail under the app bar shows what is confirmed and lets the worker step back.
- Decisions sit at the bottom of the screen: the household candidate, the member candidate, and Confirm and Save.
- From 1024 px the households stay on the left and the current step is shown on the right.

**Voice workspace.**
- A large orb shows what the worker should do now: listen to the disclosure, speak, wait, hear the read-back, or confirm.
- Under it, a four-step track follows the real safety sequence: Disclosure, Speak, Read-back, Confirm.
- The visit record is a register with version and status badges.
- The conversation feed is kept, and a sticky confirmation dock holds the save controls.

**Leaving a live visit.** A native-dialog confirmation appears ("End this voice visit? Nothing has been saved."). Leaving ends the session and nothing is saved, as before.

**Visit history.** A dated timeline in one container, with expandable confirmed fields.

**Design system.**
- Berry/Lime tokens from the design system, scoped to the `.v2` root in `frontend/src/styles/index.css`.
- New Tailwind token names only; the Round 1 tokens are unchanged.
- A small UI kit in `frontend/src/features/ui/`: Button, Badge, Sheet, Notice, ConfirmDialog and BrandMark.

## Deviations from the source design system (`healthcare-design-system-DESIGN.md`)

| Source rule | What we did and why |
| --- | --- |
| Mulish is the only typeface | Mulish has no Kannada glyphs. The stack is `"Mulish Variable", "Noto Sans Kannada Variable"`, so Kannada characters fall through to Noto Sans Kannada and Latin stays in Mulish. Both are self-hosted from `@fontsource-variable` (OFL), loaded only in the V2 chunk, with no Google requests. |
| Patient-portal IA (appointments, pregnancy progress, prescriptions) | Not used. This is an ASHA field-worker app, so the screens are household, member, voice visit and history. Nothing assumes the member is pregnant, female or a newborn. |
| Bottom navigation on mobile | Replaced by the journey rail at the top. The flow is a sequence, and the bottom of the screen is kept for the decision and confirmation actions. |
| Emergency signposting card with phone numbers | Not added. We have no verified Indian helpline or clinical wording; danger alerts show only the server's rule text, marked demo-only. |
| UK examples, NHS identifiers | Not used. IDs are the synthetic H-/P- codes in tabular Mulish. |

## Kannada copy

Headings and labels are bilingual: Kannada first, English underneath. Button labels stay English for brevity. New navigation strings (for example ಸದಸ್ಯರು, ಮಾತುಕತೆ, ಮೊದಲು ಕೇಳಿ) are **pending native-speaker review**. No clinical Kannada was added.

## Test-harness changes (intent unchanged)

| Change | Where | Why |
| --- | --- | --- |
| New `show_households()` helper | `e2e/phase4_browser.py`, used by Phase 5 | On phones, after a household is confirmed, the household list sits behind the journey's Households step. During a live visit it first confirms "End visit". |
| Worker lines found by `li[data-who="worker"]` | Phase 5 suite | Replaces the Round 1 colour class `li.bg-ink`. |
| History heading checked as "ಭೇಟಿ ಇತಿಹಾಸ" and "Visit history" | Phase 5 suite | The heading is now on two lines. |

**New `e2e/phase6_design.py`:**
- No horizontal scroll at 320, 360, 375, 412, 768, 1024, 1280 and 1536 px.
- 44 px+ primary targets on phones.
- axe-core WCAG 2.2 A/AA scans of six screens.
- The leave-visit dialog.
- Round 1 at `/` unchanged.

## Dependencies added

| Package | Version | Licence | Scope |
| --- | --- | --- | --- |
| `lucide-react` | 1.70.0 | ISC | runtime |
| `@fontsource-variable/mulish` | 5.3.0 | OFL-1.1 | runtime |
| `@fontsource-variable/noto-sans-kannada` | 5.3.0 | OFL-1.1 | runtime |
| `axe-core` | 4.14.0 | MPL-2.0 | dev only |
