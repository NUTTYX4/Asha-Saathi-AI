# NOVIX — Claude Code Frontend Design Handoff

**Purpose:** Adapt the supplied `healthcare-design-system-DESIGN.md` to ASHA SAATHI AI 2.0 without altering its working authentication, member-bound voice workflows, safety protections or persistence.

## 1. Proven working baseline

- Repository: NOVIX — ASHA SAATHI AI 2.0.
- Working branch reported by the previous agent: `v2/gemini-integration`.
- Last reported local checkpoint: `126fd09` (Gemini integration); earlier checkpoint `6580217` (Phase 5A).
- `main` must remain untouched. Verify the actual Git state before acting; do not assume it is clean.
- Stack: React + TypeScript + Tailwind, FastAPI, PostgreSQL/PostGIS, MapLibre/OpenFreeMap, Gnani Prisma v3.0 STT, Gnani Timbre v3.0 TTS.
- Synthetic demo: 12 households, 50 members, with distinct territorial access.
- Phase 5A full workflow: login → territory map → household confirmation → member confirmation → voice session → transcript-derived draft → complete TTS read-back → correction/version reset → explicit Confirm & Save → per-person Visit History.
- Routine/general visits supported; example confirmed record: H-005 / P-020 / Shantamma Kallur, weight 55 kg, follow-up 28 November 2026. Do not alter this record.
- Gemini provider integrated on the backend but disabled by default. Do not activate it, make test API calls or change its configuration.
- Safety rules remain demo-only pending clinical review; no new medical thresholds, schedules, diagnoses or referral claims.

## 2. Authoritative design source and scope

Read the complete supplied `healthcare-design-system-DESIGN.md` before editing UI. Treat its tokens, accessibility, components, layout, microcopy and privacy standards as the **visual design source**, except where the adaptation rules below explicitly override product-specific assumptions.

**Keep from the source:**
- Light mode; warm neutral canvas `#FAF7F5`, white surfaces, primary Berry `#902C4E`, accent Lime `#D4E990` (with dark text), tokenized CSS/Tailwind mapping.
- Semantic tokens before primitive tokens; accessible contrast, focus states, text + icon status labels.
- Consistent cards, controls, buttons, radius, spacing, shadows, Lucide iconography, understated motion.
- WCAG 2.2 AA intent; keyboard operation, reduced motion, responsive breakpoints, touch targets at least 44×44 px.
- Privacy-first display, unobtrusive notifications, clear error and empty states.

**Explicit NOVIX adaptations:**
- The *product* is an ASHA field-worker app, not a patient portal, obstetrics clinic or appointment-booking site.
- Do not create fake appointments, clinician directories, pregnancy milestones, prescriptions, diagnoses, medical ranges or additional backend features simply because the reference includes examples.
- IA and content must support all member categories (ROUTINE, ANC, PNC, NEWBORN, IMMUNISATION) without assuming the selected member is pregnant, female or a newborn. Use existing backend visit types and labels only.
- Locale: clear Kannada + English. The supplied source mandates Mulish; first verify Kannada glyph coverage and rendering. If Mulish lacks necessary glyphs, use a **documented Kannada-script font fallback**, such as a locally available/licensed Noto Sans Kannada, only for that script; keep Mulish for Latin. Do not ship missing glyphs or illegible Kannada merely to comply with an English-only font rule. Never share or embed unauthorized font files.
- Adapt UK-specific terms, examples, NHS identifiers, phone numbers and emergency wording to neutral, verified India-appropriate ASHA labels. Do **not** invent Indian clinical advice, helpline numbers, schedules or thresholds.
- Keep map and household/member authorization semantics unchanged. Map pins are synthetic and not real residences; attribution must remain visible.
- Do not promise offline save or offline sync: existing map fallback is not equivalent to an offline-capable visit-saving service.
- User-visible clinical alerts must reflect *only* existing approved-in-code rules, clearly marked as demo-only as appropriate. Do not create new clinical logic in the UI.

## 3. Screen design goals, ordered by priority

1. **Worker shell:** accessible header showing current worker role, safe sign out, minimal navigation; preserve login and route guards.
2. **Household discovery:** map + list/search, territorial scope, marker selection, explicit Confirm household, keyboard/GPS-denied/offline fallback, clear attribution.
3. **Member selection:** accessible list and member summary, explicit Confirm/Select member, no implicit selection or cross-member leakage.
4. **Voice workspace (highest interaction priority):** one prominent microphone/action area, unmistakable states (ready, listening, transcribing, interpreting, review, speaking, correcting, saved, error); bilingual copy; readable structured draft; clear visit type; transparent progress without pretending to have spoken or saved.
5. **Safe read-back / save:** show most recent version and full playback status; never enable save before the existing acknowledgement logic allows it; prominent single explicit Confirm & Save action; do not make spoken yes save automatically.
6. **Visit history:** visible beneath selected member details, expandable confirmed structured fields, refresh, empty/loading/error states, member scoping, preservation after reselect/reload.
7. **Responsive presentation:** 320, 360, 375, 412, 768, 1024, 1280, 1536 widths; no horizontal overflow, primary action reachable, safe-area support.
8. **Design consistency:** typography, card density, form labels, buttons, error notices, accessibility and loading skeletons.

Use a restrained Berry/Lime visual vocabulary, not a generic SaaS analytics dashboard or baby-themed landing page. Use data from existing APIs only; no invented counts or fake progress states.

## 4. Implementation guardrails

- **Frontend only** unless a blocking issue absolutely requires a documented small API-contract fix; request approval before backend changes.
- Preserve every existing V2 endpoint, WebSocket message/event shape, session binding, authorization check, state machine, TTS playback acknowledgement, correction sequencing and exact-once save logic.
- Preserve all existing household/member data, backups, access control, Gnani, Gemini adapter/configuration and PostgreSQL migrations.
- Never read, print, stage or commit secrets from `.env`, `frontend/.env.local`, or `data/`.
- Do not call external Gemini or paid Gnani services during UI work; use mock fixtures and synthetic test data.
- Do not replace the working MapLibre/OpenFreeMap setup or remove its offline/error fallback.
- No automatic destructive operations, `git reset --hard`, `docker compose down -v`, database restore, merge, push or changes to `main`.
- Prefer progressive styling/refactoring of existing components over rewriting their logic. Keep React keys, test IDs, ARIA relationships, and selectors used by Playwright stable where practical.
- Avoid new dependencies unless necessary and justified. Any third-party imagery must be properly licensed; unnecessary imagery can be omitted.

## 5. Recommended Claude Code workflow

1. Confirm the current branch, commit, clean/dirty state and any active Vite/Docker services. Do not start coding until the actual baseline is known.
2. Create a separate local `v2/frontend-design` branch from the verified `126fd09` checkpoint (unless newer reviewed work exists; report before branching).
3. Read the entire source DESIGN.md and inspect the current frontend components, route guards, Tailwind/CSS setup and existing browser tests.
4. Produce a concise screen-by-screen implementation plan plus an adaptation note documenting deviations (especially Kannada font fallback and ASHA-specific information architecture).
5. Implement tokens and shared primitives first; then shell, map/member screens, voice panel, history. Keep scope focused on visual/UI improvements.
6. Run and report `npm run typecheck`, `npx vitest run`, `npm run build`, Phase 4 browser E2E and Phase 5 browser E2E. Also run axe-core checks if installed/feasible and manually inspect screenshots at phone and desktop sizes.
7. Verify the key protected flow with mocks: H-005/P-020 routine, weight 52 → correction 55, new read-back, explicit confirm, exactly one saved visit in isolated test DB, correct Visit History and no cross-member leak.
8. Report file changes, before/after screenshots, deviations from the design source, tests, blockers and Git status. **Do not commit, push or merge without approval.**

## 6. Acceptance criteria

The redesign is accepted only when the real product still supports all Phase 5A interaction states and permissions, passes existing tests, and the mobile layout is genuinely easier to use. A visually attractive interface that obscures the confirmed member, drops errors, hides read-back/correction, weakens privacy, invents clinical facts or permits accidental save is a regression.

