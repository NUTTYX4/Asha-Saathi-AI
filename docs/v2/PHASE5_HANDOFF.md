# ASHA SAATHI AI 2.0 — Phase 5A Handoff & Verification Report

**Timestamp:** 22 November 2026 02:36 IST  
**Scope completed:** Phase 5A — Member-linked Gnani Prisma/Timbre visit workflow + Codex QA blocker fixes + `ROUTINE` visit & clarification/intent fixes + Visit History UI + OpenFreeMap Liberty basemap + Pre-Gemini Verification & Backup Checkpoint  
**Status:** **PHASE 5A GO — All regression & safety gates passed (`317 passed / 6 skipped` Docker backend, `14/14` Codex QA in isolated PostGIS, `60/60` Vitest + `tsc` + `vite build`, `52/52` Phase 4 E2E + offline fallback, `24/24` Phase 5 E2E, live OpenFreeMap Liberty verification, live Gnani `H-005 / P-020` Routine Visit persisted & serialized); checkpoint dump `data/backups/asha_saathi_phase5a_checkpoint_20261122_0235.dump` verified; NOT committed, pushed, or merged (awaiting owner approval before Phase 5A checkpoint commit / Gemini planning)**

---

## 1. Repository & Database State

- **Current branch:** `v2/backend-foundation`
- **HEAD commit (Phase 4):** `62f44e2` (`feat(v2): secure household map discovery, confirmation and member selection`)
- **Round 1 baseline (`main`):** `aba3f2b` (untouched)
- **Live PostgreSQL database (`asha_saathi`):**
  - Alembic revision: `0005` (`0005_add_routine_visit_type`, adding `routine` to `ck_v2_visits_visit_type`)
  - Seed invariants: `12` households (`DEMO-A: 6`, `DEMO-B: 6`), `50` people, `55` relationships, `min_pin_separation_m: 80.0`, all 4 demo accounts active (`INVARIANTS: OK`)
  - Pre-Phase-5 dump: `data/backups/asha_saathi_pre_phase5.dump` (`46952` bytes)
  - **Phase 5A Checkpoint dump:** `data/backups/asha_saathi_phase5a_checkpoint_20261122_0235.dump` (`53086` bytes, `PGDMP` custom format, `107` TOC entries verified via `pg_restore --list`, `SHA256: 7AC85FF6F2645C08081C9BA2EC0EE74896F00C5B63CC1A42365717189BAFC7C2`)
- **Live API (`:8000`) & Vite (`:5173`):** `V2_VOICE_ENABLED=true` active in local `.env`; Gemini and IndicTrans2 disabled/absent; `VITE_MAP_STYLE_URL=https://tiles.openfreemap.org/styles/liberty` active in git-ignored `frontend/.env.local`.
- **Excluded from future commits (`.gitignore`-verified):** `.env` (secrets/DB URL/Gnani key), `frontend/.env.local` (OpenFreeMap local opt-in), `data/` (`data/backups/*.dump`, `data/e2e/**`).

### Uncommitted Phase 5 Files

**Modified (`M`):**
- `.env.example` (added commented `# V2_VOICE_ENABLED=false`)
- `docker-compose.yml` (added `V2_VOICE_ENABLED` default `false` on `api`; `V2_VOICE_ENABLED=true`, `VOICE_PROVIDER_MODE=mock`, `MOCK_VOICE_SCRIPT` on `api-e2e`)
- `backend/app/api/v2/ws.py`
- `backend/app/api/websocket.py`
- `backend/app/core/config.py`
- `backend/app/db/models.py`
- `backend/app/integrations/gnani/prisma.py`
- `backend/app/main.py`
- `backend/app/safety/danger_signs.py`
- `backend/app/schemas/events.py`
- `backend/app/schemas/visit.py`
- `backend/app/services/extraction.py`
- `backend/app/services/prompts.py`
- `backend/app/services/session_service.py`
- `backend/scripts/export_contracts.py`
- `backend/tests/conftest.py`
- `backend/tests/test_extraction.py`
- `contracts/contracts.schema.json`
- `docs/v2/PROGRESS.md`
- `frontend/src/app/V2App.tsx`
- `frontend/src/features/households/HouseholdWorkspace.tsx`
- `frontend/src/features/households/components/SelectionPanel.tsx`
- `frontend/src/features/voice/services/audioPlayer.ts`
- `frontend/src/lib/apiV2.ts`
- `frontend/src/lib/labels.ts`
- `frontend/src/types/contracts.ts`
- `frontend/vite.config.ts`

**Untracked (`??`):**
- `backend/app/api/v2/visits.py`
- `backend/app/db/visits_v2.py`
- `backend/app/integrations/voice_provider.py`
- `backend/app/schemas/visits_v2.py`
- `backend/app/services/voice_v2.py`
- `backend/migrations/versions/0004_person_linked_visits.py`
- `backend/migrations/versions/0005_add_routine_visit_type.py`
- `backend/tests/test_phase5_codex_postgres.py`
- `backend/tests/test_phase5_codex_voice.py`
- `backend/tests/test_voice_v2.py`
- `docs/v2/PHASE5_CODEX_QA.txt`
- `docs/v2/PHASE5_HANDOFF.md`
- `e2e/phase5_browser.py`
- `frontend/src/features/visits/visitHistory.ts`
- `frontend/src/features/visits/visitHistory.test.ts`
- `frontend/src/features/visits/components/VisitHistory.tsx`
- `frontend/src/features/voice/hooks/useV2VoiceSession.ts`
- `frontend/src/features/voice/v2/V2DangerAlert.tsx`
- `frontend/src/features/voice/v2/VoiceVisitPanel.tsx`
- `frontend/src/features/voice/v2/voiceVisit.ts`
- `frontend/src/features/voice/v2/voiceVisit.test.ts`

---

## 2. Codex QA Blocker Fixes & Backend Gate Checklist (`MOCK_GNANI`)

### Confirmed Blockers Fixed (from `docs/v2/PHASE5_CODEX_QA.txt`)
1. **Cross-person contamination (`session_service.py`):** Added subject attribution in `_subject_conflict` and replaced `_alert_other_person` with `_check_danger_bound`. In a single-population bound V2 visit, utterances naming another person or ambiguous subjects are rejected with `clarification.requested(field="subject")` and never write measurements or danger flags to the bound person's draft; `other_person` alerts surface separately.
2. **Correction / save race (`session_service.py`, `voice_v2.py`, `voiceVisit.ts`):** Added `_turn_lock`, `_speech_pending`, `_speech_seq`, and `_has_pending_speech()` on the backend, plus `speechInProgress` on the frontend reducer. Any `on_speech_start` / `on_transcript` blocks `confirm()` immediately and serializes draft extraction with confirmation so a stale save can never win during debounce/extraction.
3. **Failed initial read-back (`session_service.py`):** Added `_readback_synthesized` tracking so `_full_readback_done` and `_changed_since_readback` only advance after TTS actually produces audio (and in V2 after browser playback acknowledgement). A correction after a failed initial read-back now reads the complete current record.

### Routine / General Visit (`ROUTINE`) & Clarification-Loop / Intent Fixes
1. **`ROUTINE` visit type (`visit.py`, `models.py`, `0005_add_routine_visit_type.py`, `danger_signs.py`, `voice_v2.py`, `labels.ts`, `voiceVisit.ts`, regenerated contracts):** Added `VisitType.ROUTINE = "routine"` ("Routine / General Visit" / "ಸಾಮಾನ್ಯ ಭೇಟಿ") selectable regardless of enrolment; updated `ck_v2_visits_visit_type` via additive Alembic migration `0005`; scoped `POPULATIONS_BY_VISIT[VisitType.ROUTINE] = frozenset()` so `ROUTINE` visits never apply or invent maternal/newborn clinical rules while still supporting `weight_kg` and `next_visit_date`.
2. **Clarification loop & conversational intent fixes (`extraction.py`, `session_service.py`, `prompts.py`, `voice_v2.py`):**
   - Added `Intent.NO_CHANGE` and `Intent.GREETING` plus `Extraction.wants_correction` and `is_negative_answer`, distinguishing visit-type answers (`"Normal visit."`), greetings (`"Hello."`), no-change replies (`"ಯಾವುದೂ ಇಲ್ಲ."`, `"ಯಾವುದೂ ಬದಲಾವಣೆ ಇಲ್ಲ."`), negative answers (`"ಯಾವುದೂ ಅಲ್ಲ."`), and standalone negations (`"ಇಲ್ಲ."`, `"no"`) from explicit correction requests.
   - `ASK_WHAT_TO_CHANGE` is now emitted only on explicit correction requests (`wants_correction`) or explicit `REJECT` while awaiting confirmation.
   - Tracked `_asked_routine_confirm`, `_routine_prompt_shown`, and `_clarified_once` so unresolved `"unknown"` visits offer one focused `ASK_ROUTINE_VISIT` confirmation instead of repeating identical `visit_type` prompts.

| Gate Requirement | Verified By | Result |
| --- | --- | --- |
| All 14 independent Codex QA tests pass | `tests/test_phase5_codex_voice.py` + `tests/test_phase5_codex_postgres.py` (`NOVIX_CODEX_PRIVATE_PG=1` on isolated `novix_codex_e2e`) | **PASS** (14 passed, 0 failed) |
| Full Docker backend tests pass | `docker compose exec -T api python -m pytest -q -p no:cacheprovider` | **PASS** (317 passed, 6 Codex PG skipped without private DB flag, 0 failed) |
| Migrations `0004`–`0005` valid & PostgreSQL healthy | `alembic_version = 0005`; `db` healthy; `test_postgres.py` | **PASS** |
| Synthetic dataset invariants | `households` (`12`: `DEMO-A: 6`, `DEMO-B: 6`), `people` (`50`), `relationships` (`55`), `v2_visits` (`1` prior test row for `P-020`; `0` transcript/Kannada rows) | **PASS** |
| Mocked Gnani WebSocket flow completes | `test_voice_v2.py::test_ws_full_visit_saves_once_and_identity_cannot_change`; `e2e/phase5_browser.py` (`P5-S1`) | **PASS** |
| One confirmed visit under exact person | `test_voice_v2.py::test_full_flow_saves_exactly_one_person_linked_visit`; `P5-S1` DB check | **PASS** |
| Duplicate confirm creates exactly one visit | `test_voice_v2.py::test_concurrent_identical_confirms_insert_one_row`; `P5-S1` double-click confirm | **PASS** |
| Correction requires fresh read-back & ack | `test_voice_v2.py::test_correction_invalidates_earlier_readback_and_its_acknowledgement`; `voiceVisit.test.ts`; `P5-S1` | **PASS** |
| Spoken "ಹೌದು" alone never saves | `test_voice_v2.py::test_spoken_yes_never_saves` | **PASS** |
| Territory revocation / logout / move blocks save | `test_voice_v2.py` + `test_phase5_codex_postgres.py::test_read_back_over_socket_then_finish[revoke]` | **PASS** |
| Mother/newborn isolated & immunisation unresolved | `test_voice_v2.py`; `test_phase5_codex_voice.py`; `test_phase5_codex_postgres.py::test_confirmed_maternal_history_excludes_babys_note` | **PASS** |
| Cancellation / disconnect creates no visit | `test_voice_v2.py`; `test_phase5_codex_postgres.py::test_read_back_over_socket_then_finish[cancel]`; `P5-S2` | **PASS** |
| Round 1 isolation & regression green | `test_voice_v2.py::test_round1_store_and_routes_stay_isolated`; `e2e/phase4_browser.py` `S0` | **PASS** |
| No audio / raw transcript / draft persisted | `test_voice_v2.py::test_no_transcript_text_is_persisted`; `test_phase5_codex_postgres.py`; `P5-S1` DB & browser checks | **PASS** |

---

## 3. Contract Map (Spec Proposal vs. Implemented Code)

- **WebSocket Authentication (`/ws/v2/session`):** Uses the Phase 2 `asha_session` `httpOnly` cookie + strict same-`Origin` (`Origin` host == `Host` or `CORS_ORIGINS`) handshake validation *before* `accept()`. The spec's separate `/api/v2/voice-sessions/bootstrap` capability endpoint was intentionally omitted to avoid introducing a parallel token mechanism.
- **First Client Frame:** `v2.session.start` (`{ household_id, person_id, client_visit_id, visit_type }`). Server re-authorises the pair, fixes `VisitBinding`, and emits `v2.session.bound`.
- **Client → Server Events (`V2ClientEvent`):** `v2.session.start`, `playback.completed` (`purpose: "disclosure" | "readback"`, `record_version`), `record.confirm` (`record_version`), `readback.request`, `session.cancel`, `session.stop`.
- **Server → Client Events (`ServerEvent`):** `session.started`, `v2.session.bound`, `state.changed`, `speech.started`, `transcript.final`, `record.updated`, `clarification.requested`, `alert.raised` (`scope: "this_visit" | "other_person"`, `rule_status: "demo_only_pending_clinical_review"`), `agent.audio` (`purpose`, `audio_b64`, `record_version`), `agent.audio.cancel`, `record.confirmation_requested` (`record_version`), `v2.visit.saved` (`visit_id`, `person_public_id`, `record_version`, `confirmed_at`, `idempotent_replay`), `session.error`, `session.ended` (`reason`, `message`).
- **REST Endpoints:**
  - `GET /api/v2/people/{key}/visits` (newest-first confirmed history, territory-scoped)
  - `GET /api/v2/people/{key}/visits/{visit_id}`
  - `GET /api/v2/visits/by-client-key/{client_visit_id}` (lost-ACK idempotent receipt reconciliation)
- **Error Codes:** `NOT_AVAILABLE`, `ROLE_FORBIDDEN`, `AUTH_EXPIRED`, `AUTH_REVOKED`, `MEMBERSHIP_CHANGED`, `READBACK_NOT_FINISHED`, `CONFIRMATION_REJECTED`, `IDEMPOTENCY_KEY_CONFLICT`, `PERSISTENCE_UNKNOWN`, `SUBJECT_IMMUTABLE`, `TOO_MANY_SESSIONS`, `NOT_READY`, `GNANI_NOT_CONFIGURED`, `STT_CONNECT_FAILED`, `STT_ERROR`, `AUDIO_FRAME_TOO_LARGE`, `BAD_CLIENT_EVENT`.

---

## 4. Frontend Implementation Summary

- **Audio Player (`frontend/src/features/voice/services/audioPlayer.ts`):** Additive `onClipEnded(purpose, recordVersion)` callback and `closed` guard while keeping Round 1 `enqueue(b64, turn, purpose)` compatible.
- **API Client (`frontend/src/lib/apiV2.ts`):** Added `personVisits`, `visitReceipt`, `v2SessionSocketUrl()`, and `V2ClientEvent`.
- **State Machine (`frontend/src/features/voice/v2/voiceVisit.ts` + `voiceVisit.test.ts`):** Pure reducer tracking `idle → connecting → active → saving → saved | ended | save_unknown`, per-version read-back completion (`playedReadbackVersion === confirmVersion`), invalidation on correction, and lost-ACK reconciliation.
- **Session Hook (`frontend/src/features/voice/hooks/useV2VoiceSession.ts`):** Manages `/ws/v2/session`, mic capture (`audioCapture.ts`), `AgentAudioPlayer` playback acks, server-bound identity verification (`boundMatches`), post-save 4 s audio drain before WS close, `ws.onclose` lost-ACK lookup via `apiV2.visitReceipt`, and unmount `session.cancel` cleanup.
- **UI (`VoiceVisitPanel.tsx`, `V2DangerAlert.tsx`, `VisitHistory.tsx`, `SelectionPanel.tsx`, `HouseholdWorkspace.tsx`):**
  - Explicit required visit-type radio selection (`ANC`, `PNC`, `newborn`, `immunisation`, `routine`, `unknown` "Not sure") with **no default** and no auto-fill from enrolments (recorded programmes shown only as a hint).
  - Disclosure-gated microphone indicator, live transcript, `RecordCard`, demo-only `V2DangerAlert` (including `other_person` separation notice), `Confirm and Save (version N)` disabled until latest read-back audio completes, `Replay read-back`, `Cancel visit`, saved receipt card, and per-person `VisitHistory`.
  - Mobile-first at 360 px with zero horizontal overflow; switching household or member unmounts and cancels the session without saving.

---

## 5. Test Evidence & Checkpoint Record

**Latest Pre-Gemini Verification (22 November 2026, ~02:35 IST · zero new paid Gnani calls):**

| Suite | Command | Result |
| --- | --- | --- |
| Independent Codex QA (isolated `novix_codex_e2e` PG) | `python -B -m pytest -p no:cacheprovider -v tests/test_phase5_codex_voice.py tests/test_phase5_codex_postgres.py` (`NOVIX_CODEX_PRIVATE_PG=1`) | **14 passed, 0 failed** (`4.51s`) |
| Backend (Docker + PostgreSQL) | `docker compose exec -T api python -m pytest -q -p no:cacheprovider` | **317 passed, 6 skipped** (Codex PG suite skipped without `NOVIX_CODEX_PRIVATE_PG=1`), **0 failed** (`38.06s`) |
| Frontend Typecheck + Unit + Build | `cd frontend; npm run typecheck; npx vitest run; npm run build` | Typecheck OK; **60 passed** (5 files, incl. `visitHistory.test.ts`); build OK |
| Phase 5 Browser E2E (`MOCK_GNANI`, Edge 158, 360/412/1280 px, disposable `asha_saathi_e2e`) | `uv run --no-project --with playwright==1.64.1 python -I e2e/phase5_browser.py --channel msedge` | **24 passed, 0 failed** (`data/e2e/phase5/report.json`) |
| Phase 4 Browser Regression + Offline Map Fallback (Edge 158) | `uv run --no-project --with playwright==1.64.1 python -I e2e/phase4_browser.py --channel msedge` | **52 passed, 0 failed** (`data/e2e/phase4/report.json`) |
| OpenFreeMap Liberty Live Tile Verification (Edge 158) | Playwright real-tile check reading `frontend/.env.local` | **PASS** (`STYLE_STATUS: [200]`, 6 `.pbf` tiles `200`, `MAP_PROBLEM_COUNT: 0`, 6 pins `H-001`..`H-006`, ODbL + synthetic attribution visible) |

### Key Phase 5A File SHA-256 Hashes (Checkpoint `2026-11-22 02:35 IST`)
- `backend/app/schemas/visit.py`: `BA66524C1F7C2A6C1C354C9550B9C86CBA16896F3627E583F6E69C5BCC31C6CE`
- `backend/app/schemas/visits_v2.py`: `69B8480DEA890B83D2DE193D36666E490C10BCD9F45D88726A0AB4C1B2444371`
- `backend/app/schemas/events.py`: `EAA3011B8C87132DBC2C69B2C2C3DAD10F58B62CA2720CA49CC17D1A42DBC987`
- `backend/app/db/models.py`: `6310C585B3D57992BC5E633888D52CDD0ED590A5118824D754BBC339C4EDC9D4`
- `backend/app/db/visits_v2.py`: `61CCF53D386F1AAE9E4356B520BB973E072625FA843C19DFF806253F65E8C1C9`
- `backend/app/api/v2/visits.py`: `FFAB6A5E779638E51777D258B2BF09F6C7980D1A6364172F1C90CBE91CD20B68`
- `backend/app/api/v2/ws.py`: `33FCB4F57C0118690B5055F5C6C368AD8A8318B6786D7C1DB4389DB9625D647E`
- `backend/app/safety/danger_signs.py`: `2AC13F4ED1CE8A8FA156C5213D25F8939FFCA48508FD7F35CA2176D4B3B00A8A`
- `backend/app/safety/rules.json`: `7443654795B1A0088A4C25D86EE99F97F953BF9CDCF4A7BCBEF99962C0E70179`
- `backend/app/services/extraction.py`: `5230E3BEFCBD8985A70E220C10D963E22E4D6228D521B8D1D5D23E73A76F6E9D`
- `backend/app/services/prompts.py`: `2D6F5534D2BB8C4966BD729125F9D813BC99EAD976FAD87A86AFA6D7834DB386`
- `backend/app/services/session_service.py`: `7DF175B9E5D3454EF041213C0CBF86254B6BB42226CD26A7B1A775ACCDDF61BD`
- `backend/app/services/voice_v2.py`: `E67571BF25B1164266515A416883DDF1BA8A6232AC413610962F91EC493BF4F7`
- `backend/migrations/versions/0004_person_linked_visits.py`: `B7773999ACE232B5B506CAC1DC1275D0C1CE1BD93DD995BC95E808A429335CE9`
- `backend/migrations/versions/0005_add_routine_visit_type.py`: `ECF812E17F50C83A72568AC0A5015BC7498D5847ECD7EBA9BE4160453F394FF2`
- `contracts/contracts.schema.json`: `030C2A01A169A6887386398C9D3C891E64593DF7C5DDF237917891E89BFC24CE`
- `frontend/src/types/contracts.ts`: `6D820D2377724D936044FD006B3CEFF45C817D9B228E0027D8913057F4887B23`
- `frontend/src/lib/apiV2.ts`: `D1D76CA1DFE99400A881D93DB7AFB84615D87CDBF859411EC82898875E887193`
- `frontend/src/lib/labels.ts`: `D9C884C3C68AA33A11F9AB7F8A1DA7F54389D7BEB3E38D16B83A0360DADB1CB0`
- `frontend/src/features/households/components/HouseholdMap.tsx`: `BA46DE0C7FE4CE95E08CFDB92D3B966E0827AAEAA488882220D0A2DDA510E2AF`
- `frontend/src/features/households/components/SelectionPanel.tsx`: `D563BE7F199F27C06148157B49425633AA1725B5F26976BD2135DFA7E59F00BA`
- `frontend/src/features/visits/visitHistory.ts`: `9BEB4DA9B5310C275A8B53A63EFA0DA216CEC88D6203F2B5D5C8BFCC67C87447`
- `frontend/src/features/visits/components/VisitHistory.tsx`: `2AFC6756F512C445F0193886C5CD5ABCBBC8A8E0D09C002600ECAE9FF345D0D3`
- `frontend/src/features/voice/hooks/useV2VoiceSession.ts`: `63493AFE55F9EBB3B692CD779EF4760E58C8D9A3FE1F148E7FDAB285983968A9`
- `frontend/src/features/voice/v2/VoiceVisitPanel.tsx`: `26AB4E51DEBF6ED32212B1A486756A113AA067DD85842BF0CCBEFD2381573791`
- `frontend/src/features/voice/v2/voiceVisit.ts`: `FAF44CBD37CC2CCC985E717E9509BAA52F29A52989987A7B9A12E958FB4FB6B5`

---

## 6. Live Environment Status (`V2_VOICE_ENABLED=true`)

1. `.env` has `V2_VOICE_ENABLED=true`, Gemini and IndicTrans2 disabled, `api` (`:8000`) healthy (`alembic_version = 0005`, `stt_model: prisma-v3.0`, `tts_model: timbre-v3.0`), `db` healthy.
2. `frontend/.env.local` has `VITE_MAP_STYLE_URL=https://tiles.openfreemap.org/styles/liberty`, and Vite dev server is serving `https://localhost:5173/v2` (`200`).
3. `H-005 / P-020` (`Shantamma Kallur`) holds `1` confirmed `routine` visit row (`weight_kg=55`, `next_visit_date=2026-11-28`, `danger_signs=[]`, `record_version=2`) serialized cleanly by `/api/v2/people/{key}/visits`; `0` visits exist for other members (`H-003` clean).

---

## 7. Known Gaps & Risks

- **Single-process `SessionRegistry`:** Lives in API process memory (suitable for the single-worker Uvicorn prototype).
- **Client playback acknowledgement:** `playback.completed` attests `AudioBufferSourceNode.onended` fired, not acoustic proof that audio was heard.
- **Kannada UI & prompts:** Pending native-speaker review.
- **Clinical rules:** All 13 danger-sign rules remain `demo_only_pending_clinical_review` (`rules.json` cites `WHO_PCPNC_2015` pending section verification; `ROUTINE` visits apply no clinical alert rules).
- **External map tile availability:** OpenFreeMap Liberty loads external tiles from `tiles.openfreemap.org`; offline/blocked fallback (`map-problem` banner + working markers & list) verified via `phase4_browser.py` (`S3`).
- **Hermetic E2E console filter:** `e2e/phase5_browser.py` filters expected `net::ERR_FAILED` (aborted external font requests) and initial unauthenticated `401` on `/api/v2/auth/me`.

---

## 8. Exact Next Step (Awaiting Owner Approval)

- **PHASE 5A STATUS: GO** — ready to create a clean Phase 5A checkpoint commit (staging only tracked/intended files, keeping `.env`, `frontend/.env.local`, and `data/` excluded) and proceed to Phase 5B Gemini backend planning once approved by the owner.
