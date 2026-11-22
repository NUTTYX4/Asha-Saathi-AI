# Final system QA report

- **Date:** 22 Nov 2026
- **Branch:** `v2/final-qa-admin`, from `9c52782`. Not pushed, not merged; `main` is unchanged.
- **Environment:** every write test ran on disposable PostgreSQL/PostGIS databases, created and dropped by the tests or harness. Every browser test used the disposable `asha_saathi_e2e` database, the `api-e2e` container with **mock** speech, and a hermetic browser that refuses external hosts.
- **Paid services:** no live Gnani or Gemini call was made. The test containers had their Gnani and Gemini keys blanked.

## Commits in this session

| SHA | Concern |
| --- | --- |
| `d77959d` | Voice: shorter V2 opening (greeting plus AI disclosure) |
| `0a77ce2` | UI fix: confirmation dialogs sized to their content |
| `7212f6d` | Admin dashboard API, reassignment, contracts, backend tests |
| `69d09bb` | Admin dashboard UI, Phase 7 browser suite, login helper |
| (docs commit) | `docs/qa/*` |

## Results by suite

| | Suite | Result |
| --- | --- | --- |
| A | Launcher (`tests/launcher`) | **30/30** |
| B+C | Backend unit and PostgreSQL integration (disposable container from the branch source) | **360 passed, 6 skipped** |
| D | Independent Codex QA | voice part passes inside B+C; the 6 skipped are `test_phase5_codex_postgres.py`, which needs its own network-isolated PostGIS server. **Not run** this session |
| E | Gemini provider (`test_gemini_extraction.py`) | 20 passed on the host (6 PostgreSQL cases skipped there); all pass in the container run |
| F | Frontend unit (Vitest) | **60/60**; typecheck clean |
| G | Phase 4 browser (map, selection, territory isolation) | **52/52** |
| H | Phase 5 browser (voice visit, mock Gnani, includes the new greeting) | **24/24** |
| I | Phase 6 design (responsive, axe, leave dialog), rerun after the dialog fix | **52/52** |
| J | Admin dashboard: pytest 15/15; browser `phase7_admin.py` | **75/75** |
| K | Endpoint × role matrix | **105/105** requests as expected |
| L | WebSocket security (`test_voice_v2.py` WS cases, Codex voice, Phase 5 S3) | pass |
| M | Production build smoke (to a scratch folder, not the live `dist`) | pass; the V2 chunk is 122 kB (93 kB before the dashboard) |
| N | Live demo health (read-only) | pass (see `DEMO_READINESS.md`) |

**API surface:** 28 HTTP routes on the branch (21 live plus 7 new admin routes), plus 1 WebSocket. See `API_ENDPOINT_COVERAGE.md`. Roles: see `ROLE_SECURITY_MATRIX.md`.

## Worker end-to-end flow

Phase 5 S1 runs at 360 px with mock speech. The disposable-PostGIS backend tests run on top of it. The table maps each step of the brief to its evidence.

| Step | Evidence |
| --- | --- |
| A–H: login, territory, map, household candidate, confirm, members, select, identity | Phase 4 (52), Phase 5 S1 |
| I: bound voice session | S1 "bound identity shows baby public id"; `test_start_binds_the_exact_selected_person` |
| J–K: speech and extraction | mock transcripts only; deterministic extraction (`test_extraction.py`, `test_voice_v2.py`) |
| L: visit type | explicit choice required (S1: Start is disabled until a type is picked); never inferred from enrolment |
| M: danger signs | existing demo-only rules (S1 NB_FEVER alert with the "Demo only" badge; mother/newborn separation test) |
| N–Q: read-back, correction, invalidation, new acknowledgement | `test_correction_invalidates_earlier_readback_and_its_acknowledgement`; S1 corrected weight 3 kg |
| R–S: Confirm and Save, exactly once | S1 "exactly one DB row after double-click confirm"; concurrent-confirm tests; spoken "ಹೌದು" never saves |
| T–U: history and reload | S1 history before and after reload |
| V: follow-up | next-visit date in history; admin follow-up counts |
| W: cancel without saving | Phase 5 S2 (household switch), Phase 6 D3 (End visit): 0 rows |
| Programmes | newborn (S1), routine (H-005/P-020 flow tests), ANC/PNC (`test_voice_v2.py` mother/newborn); immunisation is a supported type, never auto-mapped |

Mock speech says nothing about live Gnani recognition quality. That still needs real-phone testing.

## Voice greeting

- **Before** (shared with Round 1): "ನಮಸ್ಕಾರ! ನಾನು ಆಶಾ ಸಾಥಿ, ಒಂದು AI ಸಹಾಯಕ. ನಾನು ಮನುಷ್ಯರಲ್ಲ. ಮನೆ ಭೇಟಿಯ ವಿವರಗಳನ್ನು ಹೇಳಿ."
- **After** (V2 only): "ನಮಸ್ಕಾರ. ನಾನು AI ಸಹಾಯಕ, ಮನುಷ್ಯರಲ್ಲ. ಭೇಟಿಯ ವಿವರ ಹೇಳಿ." That is the greeting, the required AI disclosure, then straight to the visit.
- **Unchanged:** the same clip purpose (`disclosure`), so the microphone gate is unchanged; Round 1 keeps its original text.
- **Tests:**
  - there is exactly one opening clip;
  - the greeting appears once;
  - the disclosure is present;
  - there is no product name;
  - speech before the disclosure ack is ignored;
  - the full flow still works (Phase 5 24/24).
- **Pending:** native-speaker review of the Kannada.

## Gemini

- **Configuration:** `EXTRACTION_PROVIDER_MODE=deterministic` on the live stack; `GEMINI_EXTRACTION_ENABLED` defaults to false.
- **Configured model:** `gemini-3.8-flash` (`GEMINI_MODEL`). Whether that model is still available was **not** checked: no external call was made.
- **Mocked tests verify:**
  - deterministic default;
  - mock mode;
  - schema validation and invalid-JSON fallback;
  - invented-field rejection;
  - no hallucinated measurements;
  - fallback on a missing key, a timeout and SDK errors;
  - latency bounds;
  - the LLM can't trigger or suppress referrals;
  - correction with a new read-back;
  - wrong-person references can't rebind;
  - late responses after a cancel are ignored;
  - no prompt or transcript in logs or the database;
  - no clarification loop.

## PostgreSQL

- **Migration:** at `0005` live and in the tests; no migration added.
- **Seed invariants:** 12/50, verified live with `seed_demo --check` before the session.
- **Constraints:** foreign keys and check constraints are exercised in `test_households.py` and `test_postgres.py`.
- **Visit integrity:** visits are bound to people with a worker owner and are unique per `(worker, client_visit_id)`.
- **Audit:** the reassign audit is asserted.
- **Isolation:** no cross-member or cross-territory leakage (matrix plus WebSocket tests).
- **Live data:** unchanged (1 visit). No test database remains afterwards.

## Bugs found and fixed

| Severity | Bug | Fix |
| --- | --- | --- |
| P3 (UI) | Confirmation dialogs stretched to the full viewport height (Phase 6 leave-visit dialog and the new reassign dialog) | `.v2:not(dialog)` for the page-height rule (`0a77ce2`), plus a regression check |
| Test harness | `p4.login` assumed every role lands on the household list; admins now land on the dashboard | `field_view` option. No assertion was changed |
| Test harness | Two Phase 7 checks read the UI before it had loaded | wait for visible content |

No P0 or P1 defect was found. Authentication, CSRF and territory isolation passed every check.

## Unresolved

| Severity | Issue |
| --- | --- |
| High (operational) | The live demo depends on a quick tunnel owned by the Claude Code session (see `DEMO_READINESS.md`) |
| Medium | The branch work is not deployed to the live demo; deploying needs a short API restart and a `dist` rebuild |
| Medium | Clinical rules are demo-only and unvalidated; the Kannada prompts are unreviewed |
| Medium | Live Gnani speech quality is untested on real devices |
| Low | The login limiter shares one client address behind the proxy |
| Low | Codex PostgreSQL QA (6 tests) was not run (it needs an isolated server) |
| Low | The territory view lists household chips instead of a map |
