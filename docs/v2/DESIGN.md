# ASHA Saathi AI 2.0: implemented UI design

This describes the UI that ships at `/v2`. The source design system is [`design/healthcare-design-system-DESIGN.md`](design/healthcare-design-system-DESIGN.md), and the Phase 6 decisions and deviations are in [`design/PHASE6_DESIGN_NOTES.md`](design/PHASE6_DESIGN_NOTES.md). An older pre-Phase-6 proposal is kept in [`design/archive/`](design/archive/DESIGN_PROPOSAL_PRE_PHASE6.md) for history only.

## Visual system

- **Tokens.** Berry `#902C4E` is the primary colour. Lime `#D4E990` is the accent, with `#2F3B12` text on it. The canvas is `#FAF7F5`, and success, warning, error and info each have a family.
  - The tokens are defined in `frontend/src/styles/index.css`, scoped to the `.v2` root. Round 1 at `/` keeps its own tokens.
  - The page-height rule applies to `.v2:not(dialog)`, so dialogs size to their content.
- **Type.** Mulish Variable for Latin text and Noto Sans Kannada Variable for Kannada. Both are self-hosted with `@fontsource-variable` and loaded only in the V2 chunk.
- **Icons.** `lucide-react`.
- **UI kit.** `frontend/src/features/ui/primitives.tsx` provides `Button`, `Badge`, `Sheet`, `ConfirmDialog` (native `<dialog>`) and `Notice`. `BrandMark` is in the same folder.

## Screens

| Who | Screen | Notes |
| --- | --- | --- |
| Everyone | Login | Brand block plus the sign-in card. The synthetic-data banner is always visible |
| Worker, supervisor | Households → Household → Member and visit | On phones, a journey rail of three screens: decisions sit in bottom sheets, and the household and member must each be confirmed. From 1024 px, a two-pane layout. Supervisors see everything but cannot record |
| Worker | Voice visit | The orb shows what to do now, above a four-step track: Disclosure → Speak → Read-back → Confirm. Below that are the versioned visit record, the conversation and a sticky **Confirm and Save** dock. Leaving a live visit asks first |
| Worker, supervisor | Visit history | Dated timeline of confirmed visits with expandable fields |
| Admin | **Admin dashboard** (Phase 7) | Overview, ASHA workers (plus a worker detail view), Visit activity, Territories, Assignments and Audit history. Date, territory and worker filters. A switch moves between **Dashboard** and **Field view**. See `docs/qa/ADMIN_DASHBOARD_QA.md` |

## Voice copy

- **V2 opening:** "ನಮಸ್ಕಾರ. ನಾನು AI ಸಹಾಯಕ, ಮನುಷ್ಯರಲ್ಲ. ಭೇಟಿಯ ವಿವರ ಹೇಳಿ." It is a greeting, then the AI disclosure, then the prompt. The microphone stays gated until this clip has played.
- **Prompts:** fixed Kannada prompts in `backend/app/services/prompts.py`.
- **Review:** all Kannada copy is pending native-speaker review.

## Quality bar (tested)

- **Layout:** no horizontal scroll from 320 to 1536 px on the worker screens, and from 320 to 1280 px on the admin dashboard.
- **Touch targets:** 44 px or more on phones.
- **Accessibility:** zero serious or critical axe-core WCAG 2.2 A/AA violations on the scanned screens.
- **Behaviour:** visible keyboard focus; reduced motion is respected.

Evidence: `e2e/phase6_design.py` and `e2e/phase7_admin.py`.
