# Final QA report: ASHA Saathi AI 2.0

- **Date:** 22 Nov 2026
- **Branch:** `v2/final-qa-admin`. The feature commits are already on `origin/main` at `56787a7`; this release adds documentation, deployment files and one test assertion on top.
- **Environment:**
  - Every integration test used **disposable** databases: PostgreSQL/PostGIS databases that the tests create and drop, the disposable `asha_saathi_e2e` database for browser suites, and a throwaway private PostGIS container for the Codex suite, removed afterwards.
  - Browser suites ran against `api-e2e` with **simulated speech** and a hermetic browser that refuses every external host.
  - Gnani and Gemini keys were blanked in every test container, and **no live Gnani or Gemini call was made**.
- **Live demo:** the live demo, tunnel, live database and live passwords were **not** changed (§9).

## 1. Route inventory

| | Count |
| --- | --- |
| HTTP routes, total | **28** (20 GET + 8 POST) |
| Existing V2 routes | 21 |
| Admin dashboard routes added in this release | 7 (`/admin/overview`, `/workers`, `/visits`, `/coverage`, `/users`, `/assignments` and `POST /admin/assignments/{id}/reassign`) |
| WebSocket | 1 (`/ws/v2/session`) |
| Round 1 routes | 3. They are not registered while `LEGACY_ROUND1_API_ENABLED=false` |

## 2. Endpoint and role coverage (exact)

- **GET routes, as every role.** `test_endpoint_role_matrix` checks **all 20 GET routes** as **5 roles** (signed out, worker A, worker B, supervisor, admin).
  - That is **21 request rows × 5 = 105 requests, and 105/105 returned the expected status**. `/territories/{id}` is checked twice: in scope, and with an unknown ID.
  - Every error body is also checked for tracebacks, the word "password" and SQLAlchemy text.
- **The 8 POST routes, by targeted tests.** Writes need valid bodies and cleanup, so they are not in the matrix:

  | POST route(s) | Checks |
  | --- | --- |
  | login, logout | missing CSRF 403; wrong password 401 (generic message); access after logout 401 |
  | `/admin/users`, `/admin/territories`, `/admin/assignments`, `/admin/assignments/{id}/end` | 4 cases × (signed out 401, worker A 403, supervisor 403, admin without CSRF 403) = **16 checks**; plus bad role 422, missing field 422, unknown IDs 404 |
  | `/admin/assignments/{id}/reassign` | signed out 401; worker A, worker B and supervisor 403; admin without CSRF 403; extra field 422; same territory 409; unknown territory or assignment 404; already ended 409; success 201 with an audit row; visits keep their recorder |
  | `/households/{key}/members` | own-territory worker 201; foreign territory 404; supervisor 403; future date of birth 422 (`test_households.py`) |

- **Correction.** An earlier version of this report said all 28 routes were checked as 5 roles with "105/105". That was inconsistent: 28 × 5 = 140. The 105 applies to the **20 GET routes (21 rows)**. The 8 POST routes are covered by the targeted tests above. No 140-request product was run, and none is claimed.

## 3. Results of the final run

| Suite | Result |
| --- | --- |
| Backend, full suite (one-off container built from the branch source; disposable DBs) | **360 passed, 6 skipped**, 0 failed |
| The 6 skipped: `test_phase5_codex_postgres.py`, which needs `NOVIX_CODEX_PRIVATE_PG=1` and a private empty PostGIS server | Run separately (next row). **Not** counted as passing in the full-suite figure |
| Independent Codex QA (`test_phase5_codex_postgres.py` + `test_phase5_codex_voice.py`) on a throwaway private PostGIS container, no published ports | **14 passed**, 0 failed |
| Admin dashboard and matrix (`test_admin_dashboard.py`, after adding the signed-out reassign check) | **15 passed** |
| Gemini provider (`test_gemini_extraction.py`, mocked SDK and responses) | all pass in the container run (20 cases on the host plus 6 PostgreSQL cases in the container) |
| Frontend typecheck | clean |
| Frontend unit tests (Vitest) | **60 passed** |
| Production build (written to a scratch folder, not the live `frontend/dist`) | builds |
| Phase 4 browser: map, selection, territory isolation | **52 passed**, 0 failed |
| Phase 5 browser: voice visit, simulated speech, new greeting | **24 passed**, 0 failed |
| Phase 6 browser: responsive layout, axe, leave-visit dialog | **52 passed**, 0 failed |
| Phase 7 browser: admin dashboard | **75 passed**, 0 failed |
| Tunnel proxy suite (Phase 5 scenarios through the Caddy demo proxy) | **24 passed**, 0 failed |
| Launcher (`tests/launcher`) | **30 passed** |

## 4. Browser flows

**Worker** (Phase 4 + Phase 5):

- **Selection:** sign in; territory-scoped map and list; confirm a household; confirm a member; explicit visit type.
- **Voice visit:** bound voice session, with the microphone ignored until the disclosure has played; simulated transcript; extraction; a demo-only newborn danger alert; full read-back; spoken correction, which creates a new version and needs a new read-back acknowledgement; Confirm and Save.
- **Saving:** **exactly one row** even after a double-click; history before and after reload.
- **Cancelling:** switching household (Phase 5 S2) or ending the visit (Phase 6 D3) cancels it, with 0 rows saved.
- **Isolation:** worker B is refused on worker A's members and on the WebSocket; supervisors are read-only.

**Admin** (Phase 7):

- **Access:** workers and supervisors see no dashboard; every admin GET and the reassign POST return 403; signed out returns 401.
- **Metrics:** match the disposable register (12 households, 2 workers, 0 visits); worker detail; territory coverage; visit-list empty state.
- **Moving a worker:** Cancel changes nothing; Confirm moves worker B to DEMO-A, with the DB and the audit actor checked; moving back works, and history keeps both ended rows.
- **Dialog:** sizes to its content (regression check).

## 5. Responsive layout and accessibility

- **Worker screens:** no horizontal scroll at 320, 360, 375, 412, 768, 1024, 1280 and 1536 px. Primary targets on phones are 44 px or more.
- **Admin dashboard:** no horizontal scroll at 320, 360, 390, 768, 1024 and 1280 px (overview plus 5 tabs at each width).
- **axe-core WCAG 2.2 A/AA, 0 serious or critical violations on:**
  - login, households, household preview, confirmed household, member setup and live voice visit;
  - admin overview, worker detail, coverage and the reassign dialog.

## 6. Voice, Gemini and clinical scope

- **V2 greeting:** "ನಮಸ್ಕಾರ. ನಾನು AI ಸಹಾಯಕ, ಮನುಷ್ಯರಲ್ಲ. ಭೇಟಿಯ ವಿವರ ಹೇಳಿ."
  - The AI disclosure comes first, and microphone input is ignored until the disclosure clip has played.
  - The Round 1 greeting is unchanged.
  - Native-speaker review is **pending**.
  - Tests: one opening clip; the greeting is not repeated; the disclosure is present; no product name; the gate still works.
- **Simulated speech only.** Every automated voice test used simulated speech. **This does not establish real Gnani recognition quality on a phone.**
- **Gemini:** live calls disabled (`EXTRACTION_PROVIDER_MODE=deterministic`, `GEMINI_EXTRACTION_ENABLED=false`). All Gemini scenarios used a mocked SDK. The configured model ID `gemini-3.8-flash` was **not** validated against the live provider.
- **Clinical scope:** the danger rules are **demo-only** and need clinical sign-off. The app gives no diagnosis, treatment or medication advice.

## 7. Bugs found and fixed in this release

| Severity | Issue | Fix |
| --- | --- | --- |
| P3 (UI) | Confirmation dialogs (the Phase 6 leave-visit dialog and the reassign dialog) stretched to the full viewport height | `.v2:not(dialog)` (`0a77ce2`), plus a Phase 7 regression check |
| Test gap | The signed-out reassign attempt was not asserted | added to `test_workers_cannot_reassign_themselves` |
| Documentation | Coverage claim of "28 routes × 5 roles = 105" | corrected (§2) |

No P0 or P1 defect was found.

## 8. Known limitations

| Severity | Limitation |
| --- | --- |
| High (operational) | The live demo is served from a laptop through a quick tunnel owned by one terminal session; the tunnel URL cannot be recovered if it dies (`DEMO_READINESS.md`) |
| Medium | This release is **not deployed** to the live demo: no admin dashboard and no short greeting there yet |
| Medium | Demo-only clinical rules; Kannada pending review; real-device Gnani quality untested |
| Low | Shared sign-in rate limit behind the demo proxy |
| Low | The Territories tab has no map (household chips instead) |
| Low | The Codex PostgreSQL suite needs its own private server, so it is skipped inside the normal full-suite run |

Not production-ready. It still needs:

- clinical review;
- language review;
- real-device testing;
- stable hosting with access control;
- per-client rate limiting;
- password rotation;
- backups and monitoring;
- a data-protection review.

## 9. Live environment confirmation

| Item | State at the end of the session |
| --- | --- |
| `cloudflared` | still PID 10936, not restarted |
| `api`, `db` and the tunnel proxy | the same container start times as before the session |
| Live data | 1 visit, 12 households, 50 people, 4 active assignments; unchanged |
| Test databases or containers | none left |
| `frontend/dist` (what the demo serves) | not rebuilt |
| Live passwords | not read, not changed |
