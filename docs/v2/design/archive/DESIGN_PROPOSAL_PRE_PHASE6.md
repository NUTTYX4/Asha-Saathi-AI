> **ARCHIVED PROPOSAL. Not the implemented design.**
> This audit and proposal was drafted before Phase 6 by an earlier agent, before the design reference
> (`docs/v2/design/healthcare-design-system-DESIGN.md`) was supplied. Several of its choices were not built:
> - the Anek Kannada typeface;
> - the sage canvas;
> - the "SaaS workspace overview" cards;
> - token aliases.
>
> The implemented UI is described in [`docs/v2/DESIGN.md`](../../DESIGN.md) and
> [`PHASE6_DESIGN_NOTES.md`](../PHASE6_DESIGN_NOTES.md). The audit findings in section "Audit Gaps"
> describe the pre-Phase-6 UI and were addressed there. It is kept for history only.

# ASHA SAATHI AI 2.0 (`/v2`) — Phase 6 Frontend Design Specification

**Document status:** Proposed Design Audit & Specification (`docs/v2/DESIGN.md`)  
**Target route:** `/v2` (Round 1 UI at `/` remains untouched per `frontend/src/app/route.ts`)  
**Baseline:** Phase 5A (`6580217`) + Phase 5B Gemini backend (`126fd09`), external Gemini disabled by default (`GEMINI_EXTRACTION_ENABLED=false`)  
**Design direction:** Modern Healthcare + Clean SaaS Dashboard, engineered with Android-first mobile ergonomics (`360px` primary field viewport) and prepared for drop-in visual theme adaptation once the preferred design reference is supplied.

---

## Executive Summary & Current Frontend Audit

### Audited Stack & Architecture
- **Core:** React `18.3.1`, TypeScript `5.8.3`, Vite `6.3.5`, Vitest `4.1.12`, Tailwind CSS `4.1.7` (`@tailwindcss/vite`).
- **Mapping:** `maplibre-gl` `6.16.0` (dynamic chunk with worker, OpenFreeMap Liberty via `VITE_MAP_STYLE_URL` and built-in `#e8eee6` offline `PLAIN_STYLE` fallback).
- **Fonts:** Google Fonts `Anek Kannada` (`500`, `700`) and `Noto Sans Kannada` (`400`, `600`) configured in `frontend/index.html` and `frontend/src/styles/index.css` (`@theme`).
- **Backend contracts & security:** Generated from `contracts/contracts.schema.json` into `frontend/src/types/contracts.ts`; transport via `frontend/src/lib/apiV2.ts` (same-origin `httpOnly` cookie session, `X-Requested-With: asha-saathi` CSRF header, zero `localStorage`/`sessionStorage`/`IndexedDB` caching) and `/ws/v2/session`.

### Verified Functional & Security Strengths (Must Preserve)
1. **Strict identity-binding funnel (`selection.ts`):** Attempt-numbered reducer ensures late responses never leak or apply across household/member switches. Previewing a pin (`household_preview`) leaks zero resident names and triggers zero `/members` calls until explicit confirmation (`Confirm household`).
2. **Offline/failure resilience (`HouseholdMap.tsx`, `NearbyPanel.tsx`, `HouseholdList.tsx`):** Blocked tiles or missing WebGL emit non-blocking `map-problem` guidance while DOM button `.asha-pin` markers and `HouseholdList` remain operable. GPS is one-shot, non-tracking, and suggestion-only (`NearbyPanel`).
3. **Playback-gated clinical safety (`VoiceVisitPanel.tsx`, `voiceVisit.ts`, `V2DangerAlert.tsx`):** Microphone stays off before AI disclosure completes (`disclosurePlayed`); Confirm & Save (`confirm-save`) stays locked until read-back playback completes (`playedReadbackVersion === confirmVersion`) and `missing_fields` is empty; spoken `"ಹೌದು"` never saves; `V2DangerAlert` isolates server danger rules with explicit demo-only disclaimer and `other_person` separation.
4. **Post-save & reload durability (`VisitHistory.tsx`, `useV2VoiceSession.ts`):** `VisitHistory` fetches authoritative PostgreSQL `v2_visits` records via `apiV2.personVisits`, auto-refreshes after `v2.visit.saved`, handles WebSocket mid-save drops via `/api/v2/visits/by-client-key/{clientVisitId}`, and enforces read-only view for `supervisor` / `admin` (`!canRecord`).

### Audit Gaps & UX Friction Found in Current `/v2` UI
1. **Nested card-inside-card density ("box soup") on `360px` mobile:** When a household and member are confirmed, the DOM nests `household-confirmed` (`border-2`) → `member-selected` (`border-2`) → `visit-history` (`border-2`) + `voice-panel` (`border`) → `confirm-save` container (`border-2`) + `RecordCard` (`ring-1`) + `TranscriptPanel` (`ring-1`). At `360px` width, accumulated horizontal padding (`px-4` + `p-4` + `p-3` + `p-3`) shrinks usable content width to `~280px` and causes heavy visual clutter.
2. **Mobile reading & map order (`HouseholdWorkspace.tsx`):** `lg:order-2` sits above `lg:order-1` in DOM source order, so on mobile (`< 1024px`) the right sidebar (status text, search, GPS, `SelectionPanel`) appears *above* `HouseholdMap` and `HouseholdList`. Once a member is selected, the map scrolls off-screen, yet users opening `/v2` see search + empty "Choose a household" prompt before seeing the map pins.
3. **Missing SaaS workspace overview / quick-status strip:** Signed-in ASHA workers only see a raw one-line caption (`Signed in as … Territories: …`) instead of scannable territory/session overview cards and a clear workspace hierarchy.
4. **Understated V2 live audio & playback visual state:** Round 1 (`App.tsx` + `MicButton.tsx`) provides a high-salience animated microphone ring while listening, whereas V2 (`VoiceVisitPanel.tsx`) renders only a static grey text strip (`"Microphone on"` / `"Waiting for the AI disclosure to finish"`) and `StatusPill`, making it harder in bright outdoor light to distinguish disclosure playback, active mic capture, STT transcribing, Gemini/deterministic extraction, and agent read-back playback.
5. **Sub-48px Android hit targets & uneven button sizing:** `VisitHistory` `Refresh` and `Retry` buttons use `min-h-10` (`40px`), and `V2App` `Log out` and `HouseholdWorkspace` `Change household` use `min-h-11` (`44px`), falling below Android's `48dp` (`min-h-12`) minimum touch target recommendation. `Select` / `Confirm` vs `Back` / `Cancel` lack clear visual weight hierarchy in several panels.
6. **Missing tablet (`md:` `768px–1023px`) breakpoint & cramped post-save receipt:** Layout jumps directly from single-column (`< 1024px`) to `lg:grid-cols-[minmax(0,1fr)_26rem]` (`>= 1024px`). In `VoiceVisitPanel`, `visit-saved` compresses all confirmation proof into one dense white-on-green line (`Saved ✓ · version … · visit id …`), without a scannable receipt card or direct scroll link into `VisitHistory`.
7. **Incomplete bilingual parity in V2 chrome:** Round 1 leads with warm Kannada-first bilingual copy, while most V2 controls (`LoginForm`, `HouseholdWorkspace`, `SelectionPanel`, `NearbyPanel`, `VoiceVisitPanel` phase banners) are English-only despite `<html lang="kn">` and the Kannada worker audience.
8. **Design tokens mixed with hardcoded palette/utilities:** `HouseholdMap.tsx` hardcodes `bg-[#e8eee6]`, `index.css` mixes raw `rgb(176 40 95 / …)` shadows/flashes, and several surfaces lack semantic token separation (page canvas vs elevated card vs muted well vs subtle border vs clinical warning/info tones).

---

## 1. Modern ASHA Worker Mobile-First Interface

### Aesthetic & Interaction Philosophy
- **Visual register:** Calm clinical SaaS (`white` / elevated cards on soft cool-neutral sage canvas, restrained structural borders, generous breathing room, crisp semantic status pills) paired with high-contrast field ergonomics suited for sunlit rural/peri-urban Karnataka visits on budget Android phones (`360×780`, `412×915`).
- **Single focal job per fold:** Guide the ASHA worker sequentially through the legally required safety funnel without cognitive overload:
  1. **Verify Territory & Pick Household** (Map / Search / GPS hint → Candidate Preview → Server Confirm)
  2. **Pick Member & Inspect History** (Confirmed Member Sheet → Prior Confirmed Visits + Programmes)
  3. **Conduct Voice Visit & Explicitly Confirm** (Visit Type → Disclosure Gate → Gnani Live Voice + Register Card → Complete Read-back → Explicit Tap Save → Receipt)
- **Android-friendly interaction patterns:**
  - Minimum interactive height **`48px` (`min-h-12`)** and minimum spacing **`8px`** between adjacent tap targets (`Refresh`, `Retry`, `Cancel`, radio pills, history accordions, header logout).
  - **Bottom thumb-zone placement** for primary irreversible/session actions (`Confirm household`, `Select member`, `Confirm and Save`, `Replay read-back`, mobile view switcher) using `env(safe-area-inset-bottom)` padding.
  - **Edge-to-edge mobile section flattening:** Replace stacked nested rounded cards on `< 640px` viewports with hairline dividers, subtle tonal surfaces (`surface-canvas`, `surface-card`, `surface-subtle`), and single-level rounded containers (`rounded-2xl`) so `360px` screens never lose width to repeated inner borders.
  - **Mandatory safety chrome:** Keep `data-testid="synthetic-banner"` persistently anchored above the app header on `/v2`, and keep `/` completely isolated (`!isV2Path(pathname)`).

---

## 2. Dashboard and Daily Visits

Clean SaaS header + compact operational summary cards orient the worker immediately after login without compromising zero-preconfirmation member privacy.

### Phase 6A Summary Capabilities (Zero Backend Changes Required)
Using *only* data already returned by `apiV2.me()`, `apiV2.households()`, `apiV2.household(id)`, `apiV2.members(id)`, and `apiV2.personVisits(personId)`:

| Slot | Data Source (Existing API) | UI Presentation | Privacy / Security Guarantee |
| :--- | :--- | :--- | :--- |
| **Worker & Territory Chip** | `MeOut` (`display_name`, `role`, `territories[]`) | Header user badge (visible on mobile drawer/pill + desktop) + Territory filter/badge strip (`DEMO-A`, etc.) | Shows role (`worker` vs read-only `supervisor`/`admin`); zero PII |
| **Assigned Households KPI** | `pins.length` (from `apiV2.households`) | Stat tile: *Assigned Households / ನಿಯೋಜಿತ ಕುಟುಂಬಗಳು* + count (`6` for Worker A/B, `12` for Supervisor/Admin) | Territory-scoped by server; aggregate pin count only |
| **Active Context Stepper** | `selection.phase` (`Selection` reducer) | 3-step SaaS progress bar: `1 Household` → `2 Member` → `3 Voice Visit` reflecting confirmed vs preview state | Never implies confirmation during `*_preview` |
| **Session Visits Logged** | Local in-memory count of `saved` events in current signed-in React session | Optional non-persistent session counter pill (`Saved this session: N`, reset on logout/reload) | In-memory only; zero browser storage |
| **Household Health Context** | `HouseholdDetail.latest_survey` (`survey_version`, `drinking_water_source`, `has_toilet`, `submitted_on`) | Compact "Sanitation & Water Survey" metadata strip inside the **confirmed** household drawer/panel (currently fetched by `apiV2.household` yet unused in `SelectionPanel`!) | Displayed only **after** `Confirm household` |
| **Member Programme & Visit Summary** | Confirmed `PersonOut` + `V2VisitOut[]` | Shows active programmes (`ANC`, `PNC`, `Newborn`, `Immunisation`, `NCD follow-up`) + total confirmed visits (`count`) + latest follow-up date for the selected member | Loaded only **after** `Select member`; zero cross-member prefetch |

### Deferred Future Dashboard Features (Requires Phase 6B/7 Backend Contracts — Do NOT Fabricate)
- **Today's Daily Visit Queue & Territory Follow-ups Card:** Computing due/overdue follow-ups, scheduled immunisations, or pending PHC referrals *across all households* requires dedicated server-authorized V2 endpoints (e.g., `GET /api/v2/visits/followups` / `GET /api/v2/dashboard/summary` respecting `visible_territory_ids`). UI design allocates a clean dashboard slot for this grid, hidden behind a feature flag until backend Phase 6B/7 supplies those endpoints.
- **No synthetic/mocked metrics on live screens:** Never display hardcoded completion percentages, invented daily visit counts, or placeholder due dates.

---

## 3. Household Map and Territory Selection

### Map & Discovery Architecture
- **Basemap & Fallback:** Preserve `VITE_MAP_STYLE_URL` (OpenFreeMap Liberty when configured) with automatic fallback to `PLAIN_STYLE` (`#e8eee6`) + non-blocking status banner (`data-testid="map-problem"`), plus custom compact attribution (`Synthetic demo pins · not real residences`).
- **Pin Visual States (DOM button markers):**
  - Keep `.asha-pin` (`button[data-household="H-XXX"]`) so all keyboard navigation and Playwright pin selectors remain identical.
  - Enhance states cleanly via CSS custom properties:
    - **Default:** `--color-accent` fill, crisp `2px` white ring, elevation shadow, tabular house number (`1..12`).
    - **Candidate Preview (`highlighted`):** High-contrast `--color-primary` fill + outer pulse/halo ring + crisp border.
    - **Confirmed (`confirmedId`):** Distinct `--color-success` / emerald indicator badge or ring so workers can tell at a glance which household is currently locked vs hovered/previewed.
- **Territory Filter & Search Toolbar:**
  - Unified search & discovery bar (`form[role="search"]`): Search input (`Household ID, e.g. H-003`) with clear (`×`) affordance (`Search` + `All` buttons at `min-h-12`).
  - If `me.territories.length > 1` (e.g., `supervisor` or `admin`), provide a read-only **client-side territory filter pill bar** (`All territories (12)`, `DEMO-A (6)`, `DEMO-B (6)`) filtering already-authorized `pins` (`pin.territory_code`) without extra API calls.
- **GPS Hint Sheet (`NearbyPanel`):**
  - Compact action strip (`Use my location / ನನ್ನ ಸ್ಥಳ ಬಳಸಿ`) displaying accuracy pill (`±Xm`), imprecise/close-households safety callouts, and `48px` clickable suggestion rows (`data-nearby="H-XXX"`).
  - Visual callout clarifying *"GPS hint only — confirm household ID with family"*.
- **Two-Step Security Invariant:**
  - Tapping a pin, list item (`button[data-household]`), search result, or nearby suggestion ONLY enters `household_preview` (showing ID, label, territory code, member count, landmark — **zero resident names**, **zero `/members` API call**).
  - Tapping `Confirm household` triggers parallel `apiV2.household(id)` + `apiV2.members(id)` and transitions to `household_confirmed`, displaying `HouseholdDetail.latest_survey` summary + selectable member list.

---

## 4. Member Information and Visit History

### Flattened Member Profile & Selection Sheet
Eliminate nested boxes by separating the household/member workspace into three clean visual bands inside a single right-hand / detail sheet:
1. **Confirmed Household Band (`data-testid="household-confirmed"`):**
   - Header: `Household H-005` + green `Confirmed` badge + `48px` `Change household` secondary button.
   - Sub-metadata: `{household.label} · {household.territory_code}` + compact single-line `latest_survey` pill (when present: water source & toilet status).
   - Member directory rows (`[data-member="P-XXX"]`): Clean list items (`min-h-14`) showing full name, relationship (`relationship_to_head`), formatted age (`ageLabel`), active programme pills, and right chevron / selected checkmark.
   - **Member Preview Confirmation Bar (`data-testid="member-preview"`):** Crisp summary card + prominent `Select member` (`48px`) primary button + `Back` (`48px`) secondary button.
2. **Selected Member Profile Header (`data-testid="member-selected"`):**
   - Clean clinical identity banner: Name, `P-020` monospace badge, `Selected` pill, relationship, sex, age, active programme pills (or *"Routine / General care eligible"* helper when none enrolled), compact family links (`person.relationships`), and `48px` `Change member` action.
3. **Tabbed or Segmented Member Detail View (Mobile) / Stacked Panels (Desktop):**
   - On `< 768px` mobile, provide clean sub-sections (with anchor pills **"Voice Visit"** and **"Visit History (N)"**) so `VoiceVisitPanel` (`[data-testid="voice-panel"]`) and `VisitHistory` (`[data-testid="visit-history"]`) remain directly mounted in the DOM (preserving all Playwright visibility and auto-refresh expectations!) without feeling cramped inside nested borders.

### Redesigned Visit History (`data-testid="visit-history"`)
- **Header:** `Visit History / ಭೇಟಿ ಇತಿಹಾಸ ({count})` + selected member sub-label + `48px` (`min-h-12`) `Refresh` button with subtle loading spinner state.
- **Empty State:** Structured card (`No confirmed visits yet · ಇನ್ನೂ ದೃಢಪಡಿಸಿದ ಭೇಟಿಗಳಿಲ್ಲ`) explaining that confirmed visits saved for `{person.full_name}` appear here immediately.
- **Timeline Entry Cards (`data-testid="history-item"`):**
  - **Collapsed summary trigger (`data-testid="history-item-toggle"`, full-width `min-h-12` button):**
    - Top row: Bilingual visit-type chip (`ಸಾಮಾನ್ಯ ಭೇಟಿ · Routine / General Visit`, `ANC`, `PNC`, `Newborn`, `Immunisation`) + `data-testid="history-save-status"` green pill (`Saved · Confirmed`).
    - Meta row: Confirmed date/time (`en-IN` medium/short format) + Member name & ID (`Shantamma Kallur (P-020)`).
    - Clinical vitals pill row: `Weight: 55 kg` · `Follow-up: 28 Nov 2026` + amber/red danger pill (`Danger flags (N)`) when present + explicit chevron indicator (`View details` / `Hide details`).
  - **Expanded details drawer (`data-testid="history-item-details"`):**
    - Clean 2-column description list (`grid-cols-[7.5rem_1fr]` on desktop / stacked or compact on 360px) displaying Member, Household, Visit type, Save status (`Saved · Confirmed (vN)`), Confirmed timestamp, Weight (`kg`), Follow-up date, Vaccinations, Danger flags (with `Demo only · pending clinical review` pill), PHC referral flag (in alarm wash if true), Recorded by (`recorded_by`), Extraction source (`deterministic` / `deterministic+assist` when helpful), and truncated Visit ID (`id.slice(0, 8)`).
- **Live Sync Invariants:**
  - `refreshKey` increments automatically when `VoiceVisitPanel` reaches `phase === "saved"`.
  - Guards stale requests via `requestSeqRef` and `filterVisitsForPerson(data, expectedPublicId)`.
  - Persists cleanly across ending a voice session, reselecting the member, or reloading the page (re-fetches authenticated PostgreSQL `/api/v2/people/{id}/visits`).

---

## 5. Gnani Voice Conversation Interface

Dedicated healthcare conversational panel (`data-testid="voice-panel"`) powered exclusively by **Gnani Prisma v3.0 (STT)** + **Gnani Timbre v3.0 (TTS)** with structured extraction (deterministic + optional backend Gemini assist — never Bhashini).

### Structural Zones Inside `VoiceVisitPanel`
1. **Bound Identity & Trust Strip:**
   - Displays `Voice visit for {person.full_name} ({person.public_id}) · Household {household.public_id}`.
   - Server lock badge `data-testid="bound-verified"` (`verified by server` / `ಸರ್ವರ್ ದೃಢೀಕರಿಸಿದೆ`) shown once `v2.session.bound` confirms WebSocket identity match (`boundMatches`).
   - Displays STT badge (`STT prisma-v3.0` / `MOCK` in test) cleanly beside `StatusPill`.
2. **Pre-Start Visit-Type Setup (`state.phase === "idle"`):**
   - Two-column (`sm:grid-cols-2`, single column on `360px`) interactive tile radio cards (`VISIT_TYPE_OPTIONS`) with clear Kannada label + English sub-label (`ANC`, `PNC`, `Newborn`, `Immunisation`, `Routine / General Visit`, `Not sure`).
   - Contextual helper line showing `person`'s active enrolments while reminding the worker *"choose the visit type yourself / ನೀವೇ ಭೇಟಿ ಪ್ರಕಾರ ಆಯ್ಕೆಮಾಡಿ"*.
   - Full-width `min-h-12` primary CTA: `Start voice visit` (`disabled` until visit type is chosen).
   - Clear disclosure note: *"Uses Gnani speech. Nothing is saved until you press Confirm and Save."*
3. **Deterministic Clinical Safety Banner (`V2DangerAlert`, `data-testid="v2-danger-alert"`):**
   - `role="alert"`, `aria-live="assertive"`, sticky at top of active session panel whenever `alerts.length > 0`.
   - High-contrast left alarm accent border (`border-l-8 border-alarm`) on soft alarm wash (`--color-alarm-wash`).
   - Header: `ಅಪಾಯದ ಲಕ್ಷಣ · Danger sign` + mandatory clinical governance pill: `Demo only · rules pending clinical review · not a diagnosis`.
   - When `alert.scope === "other_person"`, renders explicit isolation callout explaining the symptom was heard about another person and excluded from this member's record.
4. **Structured Live Register Card (`RecordCard`, `section[aria-label="Visit record"]`):**
   - High-legibility healthcare register layout with tabular numerals showing `v{record_version}`, draft/pending status in Kannada + English (`ಕರಡು · Draft` / `ದೃಢೀಕರಣ ಬಾಕಿ · Pending confirmation` / `ದೃಢ · Confirmed`), and ruled rows for Beneficiary ID, Visit type, Weight (`kg`), Vaccinations due, Next visit date, and PHC referral alert row.
   - Missing required fields clearly highlighted in accent color (`ಬೇಕು · needed`); newly extracted or corrected fields pulse cleanly via `.field-flash`.
5. **Finalized Conversation Feed (`TranscriptPanel`, `section[aria-label="Conversation"]`):**
   - Clean chat-style bubble list (`max-h-56 overflow-y-auto`), preserving exact selector compatibility (`li.bg-ink` for right-aligned worker utterances; left-aligned light neutral surface for agent/Timbre prompts & read-back scripts).
   - Auto-scrolls to newest finalized turn cleanly without hijacking outer page scroll on initial mount.

---

## 6. Recording, Transcription, Corrections and Playback States

To prevent field workers from speaking prematurely during AI disclosure, mistaking pauses for crashes, or pressing save before corrected read-back completes, every backend `VoicePhase` and `SessionState` maps to an unambiguous multi-sensory cue:

| Lifecycle Moment | State / Condition | Visual & Audio Indicator | Control Availability |
| :--- | :--- | :--- | :--- |
| **Connecting WebSocket** | `phase === "connecting"` | Subtle indeterminate bar + *"Connecting voice session… / ಸಂಪರ್ಕಿಸಲಾಗುತ್ತಿದೆ…"* | `Cancel visit` enabled; `Confirm` hidden |
| **Mandatory AI Disclosure Gate** | `phase === "active"` & `!disclosurePlayed` & `!disclosureFailed` | **Notice banner (amber/navy):** Animated speaker equalizer bars + *"AI ಪ್ರಕಟಣೆ ಓದಲಾಗುತ್ತಿದೆ · Playing AI disclosure — microphone opens after playback"* | Mic stays OFF (`!disclosurePlayed`); `Confirm` disabled |
| **Disclosure Audio Failed** | `disclosureFailed === true` | **Alarm banner (`role="alert"`):** *"Disclosure audio failed; the microphone stays off. Cancel and try again."* | Mic stays OFF; prompt worker to `Cancel visit` & retry |
| **Live Mic Listening** | `sessionState === "listening"` & `!agentSpeaking` & `disclosurePlayed` | **Live green/rose pulse dot** + `.listening-ring` around mic indicator badge + `StatusPill`: `ಕೇಳುತ್ತಿದ್ದೇನೆ · Listening` + *"Microphone on / ಮೈಕ್ ಚಾಲನೆಯಲ್ಲಿದೆ"* | `Cancel visit` enabled; `Confirm` disabled if readback pending |
| **Worker Speaking** | `speechInProgress === true` & `sessionState !== "processing"` | Subtle wave / speech indicator + *"ಮಾತು ಕೇಳಿಸಿಕೊಳ್ಳುತ್ತಿದ್ದೇನೆ · Hearing speech…"* | `Confirm` disabled (`confirmBlockReason`) |
| **Prisma Transcribing & Extracting** | `sessionState === "transcribing"` or `"processing"` | `StatusPill`: `ಬರೆಯುತ್ತಿದ್ದೇನೆ · Transcribing` / `ಪರಿಶೀಲಿಸುತ್ತಿದ್ದೇನೆ · Processing` + compact shimmer on `RecordCard` header | `Confirm` disabled (`"ಮಾತು ಪರಿಶೀಲಿಸುತ್ತಿದ್ದೇನೆ · Processing spoken update…"`) |
| **Clarification Needed** | `clarification !== null` or `sessionState === "clarifying"` | Highlighted prompt callout above `RecordCard`: `ಒಂದು ಪ್ರಶ್ನೆ · Clarification needed` showing exact server `clarification` prompt + agent spoken audio | Worker speaks answer directly; `Confirm` stays blocked until resolved |
| **Timbre Read-Back Playing** | `agentSpeaking` or (`sessionState === "reading_back"` & `playedReadbackVersion !== confirmVersion`) | Speaking waveform pill `ಮಾತನಾಡುತ್ತಿದ್ದೇನೆ · Speaking` / `ಓದುತ್ತಿದ್ದೇನೆ · Reading back` + progress notice *"ಓದುವಿಕೆ ಮುಗಿಯಲಿ · Waiting for read-back to finish"* | `Confirm` locked until complete audio playback fires `clip_ended` (`playedReadbackVersion === confirmVersion`) |
| **Spoken Correction Received** | `record.updated` with newer `record_version` (`v1 -> v2`) | Previous `confirmVersion` & `playedReadbackVersion` invalidated immediately; updated field rows flash (`.field-flash`); version chip updates to `v2`; Timbre automatically reads updated summary aloud | `Confirm` locks immediately until **new** `v2` read-back playback completes |
| **Read-back Audio Failed** | `readbackAudioFailed === true` | Inline amber/alarm alert: *"ಓದು ಕೇಳಿಸಲಿಲ್ಲ · Read-back audio failed — tap Replay read-back."* | `Confirm` locked; `Replay read-back` prominently highlighted |
| **Ready for Explicit Confirmation** | `canConfirm(state) === true` | `StatusPill`: `ದೃಢೀಕರಣಕ್ಕೆ ಕಾಯುತ್ತಿದೆ · Awaiting confirmation`; confirmation dock turns crisp emerald-bordered ready state | `Confirm and Save (version N)` turns solid enabled green (`bg-leaf text-white`), `Replay read-back` & `Cancel visit` enabled |
| **Saving in Flight** | `phase === "saving"` | Button label switches to `"Saving… / ಉಳಿಸಲಾಗುತ್ತಿದೆ…"`, `Confirm`, `Replay`, and `Cancel` disabled (idempotent double-click guard) | All mutation controls disabled |
| **Connection Lost Mid-Save** | `phase === "save_unknown"` | `role="alert"` recovery card checking `visitReceipt(clientVisitId)` + `Check history` action button | Prompts history verification before re-recording |

---

## 7. Clear Confirmation and Saved-Receipt Experience

### Explicit Confirmation Dock (`data-testid="confirm-save"` container)
- **Visual distinction:** Separate from form fields with `border-2 border-leaf/60` when active, strengthening to full-opacity emerald frame (`border-leaf bg-leaf/5`) once `canConfirm(state)` becomes `true`.
- **Two-part instruction copy (Kannada + English):**
  - Explicitly reinforces safety rule: *"ಓದಿದ್ದನ್ನು ಪರಿಶೀಲಿಸಿ. ಬದಲಾವಣೆ ಇದ್ದರೆ ಮಾತನಾಡಿ. 'ಹೌದು' ಎಂದರೆ ಉಳಿಸುವುದಿಲ್ಲ — ಬಟನ್ ಒತ್ತಿ. / Check the read-back. Speak to correct a field. Saying 'ಹೌದು' does not save; press the button."*
- **Primary Action Button:**
  - `data-testid="confirm-save"`, `min-h-12`, full width on mobile: **`Confirm and Save (version {confirmVersion})`** (with Kannada subtext or prefix `ದೃಢೀಕರಿಸಿ ಉಳಿಸಿ` where E2E selector `data-testid="confirm-save"` continues targeting it reliably).
  - Directly underneath when disabled: clear bilingual `confirmBlockReason` text (`Processing spoken update…` / `Read-back audio failed` / `Complete missing fields before saving` / `Waiting for read-back to finish`).
- **Secondary Row (`min-h-12` each, equal `flex-1` split):**
  - `Replay read-back` (shown whenever `readbackAudioFailed || confirmVersion !== null`)
  - `Cancel visit` (safe abort, persists zero rows)

### Structured Post-Save Receipt Card (`data-testid="visit-saved"`)
Replace the current single-line green box with a structured, auditable **Confirmed Visit Receipt Card** (`bg-leaf` header band + crisp white/mint body):
- **Receipt Header:** Checkmark icon + **`Saved · Confirmed (version {record_version}) / ಉಳಿಸಲಾಗಿದೆ`** + timestamp (`en-IN`, e.g., `04:12 AM`).
- **Receipt Body (`dl` grid):**
  - **Member:** `{person.full_name} ({person.public_id})`
  - **Household:** `{household.public_id}`
  - **Visit Type:** Bilingual `VISIT_LABEL[record.visit_type]`
  - **Confirmed Vitals:** `Weight`, `Next visit date`, `Vaccinations due` (from confirmed final `state.record`), plus PHC referral status badge if flagged.
  - **Audit Reference:** `Visit ID {visit_id.slice(0, 8)}` + optional subtle banner when `idempotent_replay === true` (*"Already saved earlier — showing the same visit receipt."*).
- **Post-Save Actions:**
  - Primary/Secondary pair (`min-h-12`): **`Start another visit`** (resets voice panel while keeping `VisitHistory` populated directly above/beside) and **`View in Visit History`** (smooth-scrolls & briefly highlights newest entry in `VisitHistory` below/above).

---

## 8. Kannada-English Typography and Accessibility

### Typography System
- **Font families (`index.css`):**
  - `--font-display`: `"Anek Kannada", "Noto Sans Kannada", system-ui, -apple-system, sans-serif` (weights `500`, `700`) for headings, section titles, KPI numbers, and `StatusPill`.
  - `--font-body`: `"Noto Sans Kannada", system-ui, -apple-system, sans-serif` (weights `400`, `600`) for all body copy, labels, register values, and transcripts.
  - Apply `font-variant-numeric: tabular-nums` on clinical numbers (`weight_kg`, distances in `m`/`km`, household counts, versions, dates, timestamps) and `font-mono` (or crisp spaced sans) on `H-005` / `P-020` / truncated UUIDs.
- **Readable Sizing & Line Heights for Kannada Script:**
  - Kannada vowel signs (*otaksharas* / *ottaksharas*) require taller vertical line boxes (`leading-snug` / `1.45`–`1.6`) so ascenders and subscripts never clip (`h1`, `button`, `dt/dd`, pills).
  - Minimum body size `14px` (`text-sm`) for interactive text and controls; metadata/badges >= `12px` (`text-xs`), avoiding sub-`12px` (`text-[10px]` / `text-[11px]`) text wherever possible (min `11px`–`12px` high contrast for tags).
- **Consistent Bilingual Labeling:**
  - Group Kannada primary + English secondary with explicit visual hierarchy (`font-medium text-ink` Kannada + `text-xs text-ink-soft` English) in navigation, session states, visit types, record rows, confirmation hints, empty history state, and error recovery prompts — without doubling word count unnecessarily on compact controls.

### Accessibility (WCAG 2.2 AA & Android TalkBack)
- **Color & Sunlight Contrast:**
  - Text contrast `>= 4.5:1` across all surface/ink pairs (`#1f2a44` on `#ffffff` = `14.2:1`; `#4a5570` on `#ffffff` = `7.3:1`; `#4a5570` on `#f5f7f4` = `6.8:1`; `#ffffff` on `#b0285f` and `#2f7a4d` verified >= `4.5:1`; `#b3261e` on `#fdecea` >= `6.2:1`).
  - Never communicate state by color alone: pair borders/fills with explicit text badges (`Confirmed`, `Candidate`, `Needs attention`, `Demo only`), checkmarks, and icons.
- **Touch Targets & Keyboard Navigation:**
  - Enforce **`min-h-12` (`48px`)** and **`min-w-12` (`48px`)** on ALL buttons (header `Log out`, `VisitHistory` `Refresh`/`Retry`, `NearbyPanel` `Use my location`/suggestions, `SelectionPanel` `Change household`, map `.asha-pin` hit wrappers/padding, radio cards).
  - Preserve full keyboard navigation verified by `phase4_browser.py`: Map pins remain focusable `<button>` elements with descriptive `aria-label` and `aria-pressed`; `Tab` navigates smoothly from map pin → preview panel → `Confirm household`; focus automatically moves to `panelHeading` (`tabIndex={-1}`) on household preview and confirmation.
- **Live Regions & Reduced Motion:**
  - `aria-live="polite"` on workspace status (`data-testid="status"`), `StatusPill`, `NearbyPanel` feedback, and clarification notice.
  - `role="alert"` + `aria-live="assertive"` exclusively on critical safety/clinical banners (`V2DangerAlert`) and hard failure alerts (`loadError`, `disclosureFailed`, `save_unknown`).
  - Respect `@media (prefers-reduced-motion: reduce)` across all enter/flash/pulse/mic animations (`animation: none; transition-duration: 0.01ms`).

---

## 9. Responsive Desktop, Tablet and 360px Mobile Layouts

Breakpoints intentionally cover **Mobile (`360px–767px`)**, **Tablet (`768px–1023px`)**, and **Desktop (`>= 1024px` / `1280px`)** with zero horizontal scroll (`overflow-x-hidden` guard only as belt-and-braces behind real `min-w-0` + `break-words` flex/grid children):

### A. Mobile Layout (`360px` & `412px` primary field viewports)
Goals: Keep the map visible on initial load, eliminate nested-border squeezing, and keep primary CTAs inside thumb reach.

```text
+--------------------------------------+  <- 360px wide
| DEMO BANNER (full width, sticky opt) |
+--------------------------------------+
| ಆಶಾ ಸಾಥಿ 2.0        [Asha·Worker][Out]|  <- 56px compact header
+--------------------------------------+
| Selected: H-005 / Shantamma Kallur   |  <- Sticky context bar
| Steps: [1 House ✓] [2 Member ✓] [3]  |     + live status
+--------------------------------------+
| [ Search ID...        ] [Search][GPS]|  <- Unified compact toolbar
+--------------------------------------+
| * Phase 1-2 (no member yet):         |
| [ Map Canvas (h-64) · Pins 1..6    ] |  <- Map FIRST before member
| [ Candidate Preview / Confirmed Card]|     selected, then list
| [ Your households (6) list rows    ] |
|                                      |
| * Phase 3 (member selected):         |
| [ Selected Member Profile Header   ] |  <- Compact profile strip
|   [Change household] [Change member] |
| [ Segment: Voice Visit | History(1)] |  <- Quick jump / visible
| +----------------------------------+ |     both sections without
| | Voice Visit · bound verified ✓   | |     3x nested borders
| | [Visit type radios / Active Mic] | |
| | [V2DangerAlert if raised]        | |
| | [RecordCard register rows]       | |
| | [TranscriptPanel]                | |
| | +------------------------------+ | |
| | | Confirm & Save (v2) [48px]   | | |  <- Sticky / anchored dock
| | | [Replay] [Cancel]   [48px]   | | |
| | +------------------------------+ | |
| +----------------------------------+ |
| [ Visit History / ಭೇಟಿ ಇತಿಹಾಸ (1) ] |
+--------------------------------------+
```
*Note on DOM vs visual order:* Keeping `HouseholdList` and `HouseholdMap` easily reachable above/before deep scrolling while preserving `household-preview` focus (`panelHeading.current?.focus()` + `scrollIntoView({ block: "nearest" })`) satisfies both visual first-paint ergonomics on `360px` and keyboard/E2E flow. When `selection.phase === "person_confirmed"`, auto-collapsing/tucking the household directory behind a compact `"Browse households (6)"` accordion (still toggleable anytime, or keeping it below the fold without blocking) prevents kilometers of scrolling on a `360px` phone! *(Note: `phase4_browser.py` and `phase5_browser.py` click `button[data-household="H-004"]` while `selection.phase === "person_confirmed"` or `"household_confirmed"` — so the household list buttons **must remain visible and directly clickable in DOM** during `S1`/`P5-S2` unless toggled via an optional collapse only by explicit user tap! Therefore, keep `HouseholdList` rendered cleanly without hiding `button[data-household]` by default.)*

### B. Tablet Layout (`768px–1023px`, `md:`)
Replaces the current abrupt single-column stretch on iPads/Android tablets with a balanced 2-column split:
- **Container:** `max-w-5xl` (`px-4`), top sticky SaaS bar + compact stat strip (`Territory · Assigned Households · Selection Progress`).
- **Grid:** `md:grid-cols-[minmax(0,1fr)_22rem] lg:grid-cols-[minmax(0,1.1fr)_28rem]` (`gap-4`).
  - Left column (`md:order-1`): `HouseholdMap` (`h-80 md:h-[26rem]`) + `Search & GPS toolbar` + `HouseholdList` (`2`-column compact grid if space allows or crisp `1`-column list).
  - Right column (`md:order-2`): Persistent inspection & workspace column (`SelectionPanel` → `Member Profile` → `VoiceVisitPanel` + `VisitHistory`).

### C. Desktop Layout (`1024px+` / `1280px+`, `lg:` / `xl:`)
Clean clinical SaaS master-detail dashboard (`max-w-7xl` expanded from `max-w-6xl`):
- **Top Header Bar:** App identity (`ಆಶಾ ಸಾಥಿ 2.0`), worker role & territory summary chips (`DEMO-A`, etc.), session check status, and `Log out`.
- **Context & KPI Ribbon:** 3 compact SaaS summary cards/pills (`Assigned Households`, `Active Territory Scope`, `Current Selection Step` breadcrumb + live status).
- **Two-Column Split (`lg:grid-cols-[minmax(0,1.05fr)_30rem]`):**
  - **Left Workspace Rail:** Unified Search + `Use my location` toolbar, OpenFreeMap `HouseholdMap` (`lg:h-[28rem]`) with clear legend pill (Candidate / Confirmed / Territory), and scrollable `HouseholdList` (`Your households (N)`).
  - **Right Clinical Action Pane:** Smooth sticky/independent pane hosting `SelectionPanel`:
    - When `none` / `household_preview`: Crisp empty guidance or candidate inspection sheet.
    - When `household_confirmed` / `person_preview`: Household survey metadata + member directory + preview confirm card.
    - When `person_confirmed`: Member profile strip + **Voice Visit Conversation Console** + **Expandable Visit History** cleanly stacked with clear section dividers (no double/triple enclosing boxes).

---

## 10. Loading, Offline, Permission and API-Error States

Every failure mode currently handled in code receives a consistent, calm, actionable UI treatment:

| Scenario | Trigger / Detection | UI Treatment & Recovery Action | Security / Data Integrity Rule |
| :--- | :--- | :--- | :--- |
| **Initial Session Check** | `auth.status === "checking"` | Centered skeleton/spinner card (`Checking your session… / ಸೆಷನ್ ಪರಿಶೀಲಿಸಲಾಗುತ್ತಿದೆ…`) | Never flashes protected UI before `apiV2.me()` resolves |
| **Session Expired / Revoked** | `401` on `apiV2.me()`, 60s heartbeat, `visibilitychange`, or any REST/WS call | Immediate return to `LoginForm` with status banner (`"Your session has ended. Please sign in again."`) | Full workspace unmount via `key={accessKey(me)}`; zero stale state retained |
| **Login Errors & Lockout** | `LoginForm` `401` / `429` / network `0` | Inline `role="alert"` (`Invalid username or password`, `Too many failed attempts`, or server unreachable); clears `password` input immediately | Never persists credentials |
| **Household / History Loading** | `pins === null` or `visits === null` | Shimmer skeleton placeholder rows matching target card height (prevents layout shift on 360px) | Request sequence guard discards late stale responses |
| **Offline / Server Unreachable** | `ApiError(status=0)` (`fetch` throws) | Non-destructive inline alert banner with explicit `48px` `Retry` button; existing loaded list/history remains readable in memory until retry | Never queues unauthenticated local mutations into `localStorage` |
| **Map Tiles Offline / Blocked** | `map.on("error")` (`tiles`) | Map switches seamlessly to `#e8eee6` `PLAIN_STYLE` canvas; pins stay visible & clickable; `data-testid="map-problem"` banner explains list still works | Zero external tile dependency required to operate |
| **WebGL Unsupported** | `GPUInitializationError` / dynamic import failure | Map container hidden cleanly; `data-testid="map-problem"` directs user to interactive `HouseholdList` directly below | Zero JS crash; list + search cover 100% of selection workflow |
| **GPS Denied / Timeout / Unavailable** | `navigator.geolocation` error codes (`1`, `2`, `3`) or missing API | Calm `role="status"` note inside `NearbyPanel` (`"Location permission was denied. Use search or the list below…"`); zero auto-selection | Coordinates sent at most once on click; never stored |
| **Imprecise / Clustered GPS** | `accuracy > threshold` or `closeTogether(...)` | Explicit warning badge inside `NearbyPanel`: check household ID directly with family before confirming | Never ranks down manual confirmation |
| **Mic Permission Denied / Missing** | `startCapture` promise rejects | `useV2VoiceSession` sets `local_end` (`"ಮೈಕ್ ಸಿಗಲಿಲ್ಲ / Microphone unavailable: …"`), cancels WS, provides `Start again` | No partial/ghost session left open |
| **TTS Disclosure Failure** | `disclosureFailed === true` | `role="alert"` inside `VoiceVisitPanel`; mic remains locked; guides worker to cancel and retry | Legal AI disclosure invariant enforced |
| **TTS Read-back Failure** | `readbackAudioFailed === true` | Prominent warning + highlighted `Replay read-back` (`48px`) button | `Confirm and Save` stays blocked until playback completes |
| **WebSocket Dropped Mid-Save** | `ws.onclose` during `phase === "saving"` | Enters `phase === "save_unknown"` (`"Checking whether the visit was saved…"`), polls `apiV2.visitReceipt(clientVisitId)`; if unknown/5xx, prompts `Check history` button to avoid duplicate recording | Preserves `client_visit_id` idempotency discipline |
| **Grant / Territory Revoked (`404`)** | `404` during `confirmHousehold` or `selectPerson` | Clears stale selection back to `household_confirmed`/`none`, sets `NOT_AVAILABLE` notice (`"That record is not available to your account any more…"`), reloads `loadPins(false)` while keeping explanation visible | Matches `phase4_browser.py` S6 assertion cleanly |
| **Supervisor / Admin Read-Only** | `me.role !== "worker"` (`!canRecord`) | Hides `Start voice visit` & radio form completely; shows clear read-only badge (`"Only ASHA worker accounts record visits."`) while keeping full `VisitHistory` inspection enabled | Matches `phase5_browser.py` P5-S5 assertion cleanly |

---

## 11. Component Structure, Design Tokens and Navigation

### Proposed Frontend Directory & Component Organization
Keeps existing pure logic/reducers (`selection.ts`, `voiceVisit.ts`, `visitHistory.ts`, `geo.ts`, `apiV2.ts`) and hooks (`useV2VoiceSession.ts`) completely intact while introducing clean SaaS primitives:

```text
frontend/src/
  app/
    App.tsx                         # Round 1 (/) — UNCHANGED
    V2App.tsx                       # /v2 Auth shell, synthetic demo banner, SaaS top bar
    route.ts                        # / vs /v2 splitter — UNCHANGED
  shared/ui/                        # NEW presentational primitives (no business state)
    Button.tsx                      # Variants: primary, secondary, ghost, danger, success (all min-h-12)
    Card.tsx                        # Flat/elevated surface container variants (avoiding double borders)
    Badge.tsx                       # Semantic status pills (success, warning, danger, info, neutral)
    AlertBanner.tsx                 # Unified inline status/error/clinical banner with optional action
    StepProgress.tsx                # 3-step selection progress indicator (no false confirmation cues)
  features/
    auth/
      LoginForm.tsx                 # Clean centered clinical sign-in card
    households/
      HouseholdWorkspace.tsx        # Top KPI/context strip + Search/GPS bar + responsive 2-col layout
      selection.ts / geo.ts / labels.ts  # Domain logic & labels — UNCHANGED behavior
      components/
        TerritoryOverview.tsx       # NEW Phase 6A SaaS summary strip (count, role, territory pills, step)
        HouseholdMap.tsx            # MapLibre container + pin legend + fallback banner
        HouseholdList.tsx           # High-contrast household rows + optional territory chip filter
        NearbyPanel.tsx             # Compact GPS hint drawer/card
        SelectionPanel.tsx          # Flattened inspection sheet: Preview / Household / Member Profile
    visits/
      visitHistory.ts               # Domain helpers — UNCHANGED
      components/
        RecordCard.tsx              # Structured medical register card with tabular nums + flash highlights
        VisitHistory.tsx            # Timeline accordion cards + expanded audit <dl>
    voice/
      hooks/useV2VoiceSession.ts    # Hook & WS lifecycle — UNCHANGED protocol
      v2/
        voiceVisit.ts               # Reducer & canConfirm / confirmBlockReason — UNCHANGED safety rules
        V2DangerAlert.tsx           # Assertive deterministic safety banner
        VoiceStageHeader.tsx        # NEW unified Gnani disclosure/listening/speaking/playback strip
        ConfirmDock.tsx             # NEW focused explicit confirm & save bar + replay/cancel controls
        SavedReceiptCard.tsx        # NEW rich structured post-save receipt + history link
        VoiceVisitPanel.tsx         # Orchestrates V2 voice subcomponents cleanly
```

### Semantic Design Tokens (`frontend/src/styles/index.css` `@theme`)
Preserve all existing token names as aliases so zero existing classes break (`bg-ink`, `bg-paper`, `bg-sheet`, `bg-rose`, `bg-leaf`, `bg-alarm`, `bg-alarm-wash`, `text-ink-soft`, `border-rule`), while introducing clean semantic SaaS tokens ready for rapid theme swapping when the design reference arrives:

| Token Category | Proposed CSS Variables | Current Mapped Default | Purpose |
| :--- | :--- | :--- | :--- |
| **Surfaces** | `--color-surface-canvas` (`--color-paper`), `--color-surface-card` (`--color-sheet`), `--color-surface-subtle`, `--color-surface-header` (`--color-ink`) | `#f5f7f4`, `#ffffff`, `#eef2ed`, `#1f2a44` | Clean SaaS background separation without heavy borders |
| **Borders & Dividers** | `--color-border-subtle` (`--color-rule`), `--color-border-strong` | `#d5dbd3`, `#9aa6b2` | Hairline cards and high-contrast inputs |
| **Ink Hierarchy** | `--color-text-primary` (`--color-ink`), `--color-text-muted` (`--color-ink-soft`) | `#1f2a44`, `#4a5570` | `>= 7:1` contrast in outdoor lighting |
| **Brand / Accent** | `--color-brand-primary`, `--color-brand-accent` (`--color-rose`), `--color-brand-accent-deep` (`--color-rose-deep`) | `#1f2a44`, `#b0285f`, `#8c1d4a` | Header, active selection, primary focus CTAs, map pins |
| **Clinical States** | `--color-status-success` (`--color-leaf`), `--color-status-success-wash`, `--color-status-warning`, `--color-status-warning-wash`, `--color-status-danger` (`--color-alarm`), `--color-status-danger-wash` (`--color-alarm-wash`) | `#2f7a4d`, `#e9f4ee`, `#b45309`, `#fef3c7`, `#b3261e`, `#fdecea` | Saved receipts, clarifications/TTS retry, clinical danger signs |
| **Typography & Numerics** | `--font-display`, `--font-body`, `--font-mono` | Anek Kannada, Noto Sans Kannada, ui-monospace | Kannada script legibility + `tabular-nums` vitals & IDs |
| **Radius & Elevation** | `--radius-card`, `--radius-control`, `--radius-pill`, `--shadow-card`, `--shadow-dock` | `1rem`, `0.75rem`, `9999px`, soft hairline shadows | Cohesive modern SaaS depth |
| **Motion Budget** | `--duration-micro: 120ms`, `--duration-ui: 170ms`, `--duration-modal: 240ms`, `--ease-enter`, `--ease-exit`, `--ease-tactile` | Preserved verbatim from `index.css` | Transform/opacity transitions only; `prefers-reduced-motion` safe |

### Design Reference Adaptation Slots
Once the preferred design reference is shared, styling maps cleanly into `DESIGN.md` with **zero structural rewrite**:
1. **Palette & Brand Tokens:** Swap `--color-surface-*`, `--color-brand-*`, `--color-border-*`, and status washes inside `@theme` while preserving `>= 4.5:1` WCAG AA contrast and `.bg-ink` utility contrast (`white` text on dark worker chat bubble).
2. **Shell Chrome:** Adjust header height, user chip layout, badge geometry (`rounded-full` vs `rounded-lg`), and shadow intensity inside `V2App.tsx`, `TerritoryOverview.tsx`, and `shared/ui/Card.tsx`.
3. **Typography Scale & Weights:** Optionally introduce a companion clean Latin UI font (e.g., `Plus Jakarta Sans` or `Inter`) alongside `Anek Kannada` / `Noto Sans Kannada` in `index.html` and `--font-display` / `--font-body` for crisp bilingual SaaS tables & KPIs.
4. **Data Card Density:** Adjust card padding (`p-3`/`p-4`/`p-5`), border radius (`rounded-xl` vs `rounded-2xl`), and table/timeline layout in `HouseholdList`, `RecordCard`, `VisitHistory`, and `SavedReceiptCard`.

### Navigation Architecture
- **No additional client router required:** Keep `/v2` single-route SPA state driven cleanly by `Auth` (`checking` / `signed_out` / `signed_in`) and `selection` (`Selection` reducer). Switching routes via URL would risk breaking active WebSocket / mic streams or creating history-state mismatches on mobile back button.
- **Sticky Navigation & Context Continuity:**
  - Persistent synthetic demo ribbon + app bar (`Log out` button always accessible).
  - Sticky context ribbon (`SelectionBreadcrumb` + 3-step visual progress + live `data-testid="status"` line) remains pinned under scroll on both mobile and desktop.
  - In `HouseholdWorkspace`, picking a new household when a voice session is active continues to unmount `SelectedMemberSection` cleanly and close the WebSocket with `session.cancel` (`phase5_browser.py` P5-S2).

---

## 12. Migration Plan That Preserves All Current V2 Functionality

### Non-Negotiable Selector, Behavioural & Security Contracts
Every refactor step **must preserve** every contract exercised by `frontend` Vitest (`60 tests`), `e2e/phase4_browser.py` (`52 checks`), `e2e/phase5_browser.py` (`24 checks`), and backend `apiV2`:

| Contract / Selector | Source File(s) Relying on It | Migration Rule |
| :--- | :--- | :--- |
| `data-testid="synthetic-banner"` | `phase4_browser.py` | Keep visible on login + signed-in `/v2`, absent on `/` |
| `h1`/`heading` matching `Your households (\d+)` | `phase4_browser.py` | Preserve exact heading text `Your households ({pins.length})` |
| `ul[aria-label="Households"] button[data-household="H-XXX"]` | `phase4_browser.py`, `phase5_browser.py` | Keep list items directly rendered & clickable cleanly (`min-h-12`/`min-h-14`) |
| `.asha-pin` with `dataset.household` & `.asha-pin--active` | `phase4_browser.py` | Keep class name, `<button>` element, `data-household`, `aria-label`, `aria-pressed` |
| `data-testid="map-problem"` | `phase4_browser.py` | Emit cleanly only on map style/tile/WebGL error; zero emission on healthy style |
| `data-testid="selection-breadcrumb"` | `phase4_browser.py` | Keep exact text pattern showing `(not confirmed)` / `(not selected)` / confirmed names |
| `data-testid="household-preview"`, `Confirm household` | `phase4_browser.py`, `phase5_browser.py` | Keep preview isolation (zero resident names, zero pre-confirm `/members` fetch) |
| `data-testid="household-confirmed"`, `[data-member]` | `phase4_browser.py`, `phase5_browser.py` | Keep `[data-member="P-XXX"]` interactive member buttons starting with `full_name` |
| `data-testid="member-preview"`, `Select member`, `data-testid="member-selected"` | `phase4_browser.py`, `phase5_browser.py` | Preserve server member recheck (`apiV2.member`) before rendering `VisitHistory` & `VoiceVisitPanel` |
| `data-nearby="H-XXX"` | `phase4_browser.py` | Preserve GPS suggestion buttons & denied/timeout fallback copy |
| `data-testid="voice-panel"`, `data-testid="bound-verified"` | `phase5_browser.py` | Keep panel mounted for both worker & read-only supervisor (`Start voice visit` hidden when `!canRecord`) |
| `role="radio"` matching `Newborn`, `PNC`, `Routine / General Visit`, etc. + `Start voice visit` button | `phase5_browser.py` | Keep native accessible `<input type="radio">` labels & disabled state before choice |
| `section[aria-label="Conversation"] li.bg-ink` | `phase5_browser.py` (`line 90`) | **CRITICAL:** Worker bubbles inside `TranscriptPanel` must keep `li.bg-ink` class (or ensure `--color-ink` adapts visually while keeping `bg-ink`) |
| `section[aria-label="Visit record"]` | `phase5_browser.py` | Keep exact `<section aria-label="Visit record">` Landmark + `weight kg` / `next_visit_date` values |
| `data-testid="v2-danger-alert"` | `phase5_browser.py` | Keep assertive alert containing `Demo only` disclaimer & server labels |
| `data-testid="confirm-save"`, `data-testid="visit-saved"` | `phase5_browser.py` | Keep exact `testId` hooks, playback-ack gate, and single-write double-click guard |
| `data-testid="visit-history"`, `history-item`, `history-item-toggle`, `history-save-status`, `history-item-details` | `phase5_browser.py`, `visitHistory.test.ts` | Keep all 5 history `data-testid` attributes + `No confirmed visits yet` empty state text + `Saved · Confirmed` pill |
| Zero persistent browser storage & auth/CSRF rules | `phase5_browser.py`, `apiV2.ts` | Never introduce `localStorage`, `sessionStorage`, or `IndexedDB`; keep `credentials: "same-origin"`, `cache: "no-store"`, and CSRF header |
| Round 1 isolation (`/`) | `route.ts`, `phase4_browser.py` | Do not modify `App.tsx`, `FollowUpsPage.tsx`, `ConfirmBar.tsx`, `DangerAlert.tsx`, `useVoiceSession.ts`, or `api.ts` |

### 6-Step Incremental Implementation Sequence (After Design Reference Approval)
1. **Step 1 — Design Tokens & Shared UI Primitives:** Extend `index.css` `@theme` (incorporating the user's design reference palette/type tokens) and add `shared/ui/{Button,Card,Badge,AlertBanner,StepProgress}.tsx`. *Verify:* `npm run typecheck`, `npx vitest run`.
2. **Step 2 — Application Shell, Login & Tablet/Desktop Grid:** Refine `V2App.tsx`, `LoginForm.tsx`, and `HouseholdWorkspace.tsx` responsive layout (`360px` map-first discovery ordering, `md:` tablet 2-col, `lg:` desktop 2-col, `TerritoryOverview`, unified search+GPS bar). *Verify:* `npm run build` + `e2e/phase4_browser.py --channel msedge` (`52/52`).
3. **Step 3 — Map Polish, Territory Pills & Nearby Sheet:** Upgrade `HouseholdMap.tsx` (status legend, clear active vs confirmed pin distinction), `HouseholdList.tsx`, and `NearbyPanel.tsx` (`48px` targets, clear GPS guidance). *Verify:* `e2e/phase4_browser.py --channel msedge` (`52/52`).
4. **Step 4 — Flattened Selection Sheet, Member Profile & Visit History:** Refactor `SelectionPanel.tsx` (surface `HouseholdDetail.latest_survey`, remove nested box clutter) and `VisitHistory.tsx` (`48px` refresh/retry buttons, cleaner timeline cards & expanded details grid). *Verify:* `npx vitest run` + `e2e/phase5_browser.py --channel msedge` (`24/24`).
5. **Step 5 — Gnani Voice Stage Header, Confirmation Dock & Saved Receipt Card:** Extract `VoiceStageHeader`, `ConfirmDock`, and `SavedReceiptCard` inside `features/voice/v2/`, preserving `voiceVisit.ts` & `useV2VoiceSession.ts` untouched. Keep `TranscriptPanel`'s `li.bg-ink` contract intact. *Verify:* `e2e/phase5_browser.py --channel msedge` (`24/24`) + manual live Gnani Prisma/Timbre Routine Visit check (`H-005 / P-020`).
6. **Step 6 — Kannada-English & Accessibility Pass + Final Full Verification:** Audit all `360px`, `412px`, `768px`, and `1280px` viewports for zero horizontal overflow, `>= 48px` touch targets, `prefers-reduced-motion`, WCAG AA contrast, full `vitest`, `tsc --noEmit`, `vite build`, `phase4_browser.py`, `phase5_browser.py`, and backend regression checks.
