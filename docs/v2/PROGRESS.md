# ASHA SAATHI AI 2.0: progress log and verification checklist

Briefs:
- Phases 0–3: `ASHA_SAATHI_AI_V2_ENGINEERING_MASTER_PLAN.md` (Section 15).
- Phase 4 onwards: the owner-approved combined handoff, `01_NOVIX_V2_COMBINED_ENGINEERING_HANDOFF.md`. Its reconciled sections 0–7 take precedence.
- Neither brief is committed to the repo.
- Contract mapping: `docs/V2_CONTRACT_DECISIONS.md`.

Branch: `v2/backend-foundation`. Round 1 baseline: `main` at `aba3f2b` (pushed).

## Phase checklist

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Preflight: git baseline, Docker/WSL, toolchain, secrets present | Done |
| 1 | Docker Compose + PostgreSQL/PostGIS + SQLAlchemy/Alembic, Round 1 contracts kept | **Done (gates passed)** |
| 2 | Auth, roles, territories, audit; REST and WebSocket denial tests | **Done (gates passed)** |
| 3 | Households/people/relationships + 12-house/50-person idempotent seed | **Done (gates passed)** |
| 4 | Secure map discovery (list/search/bbox/nearby), household confirmation, member selection, minimal browser UI at `/v2` | **Done, awaiting owner review (not committed)** |
| 5 | Household/person-bound Gnani visit flow saved to PostgreSQL | **Phase 5A GO (Pre-Gemini Checkpoint `2026-11-22 02:35 IST`): `317 passed / 6 skipped` backend Docker, `14/14` Codex QA, `60/60` Vitest + build, `52/52` Phase 4 E2E, `24/24` Phase 5 E2E, OpenFreeMap Liberty PASS, Visit History UI + `ROUTINE` + live Gnani `P-020` verified, dump `asha_saathi_phase5a_checkpoint_20261122_0235.dump`; awaiting commit approval; 5B–5D deferred** |
| 6 | Tasks, referrals, guideline versions, terminology, data quality, KPIs | Not started |
| 7 | Full integrated browser flow (minimal UIs arrive with Phases 4–6) | Not started |
| 8 | Full QA and release report | Not started |
| 9+ | Polished UI, Android (separate approval) | Not in scope |

## Phase 0: preflight (21 Nov 2026)

- Git: `main` = `origin/main` = `aba3f2b`; clean tree. V2 work on branch `v2/backend-foundation`.
- Docker 29.9.2 (client and server), Compose v5.6.1, WSL 2 (`docker-desktop`), hypervisor present.
- Python 3.11.9, Node 24.17.0, npm 11.13.0, uv 0.10.12, RAM 15.7 GB.
- `GNANI_API_KEY` configured (checked through the settings loader; value never printed).

## Phase 1: Docker + PostgreSQL/PostGIS (21 Nov 2026)

**Changes**
- New pinned packages: `sqlalchemy==2.0.58`, `alembic==1.20.1`, `psycopg[binary]==3.3.9`,
  `geoalchemy2==0.21.0`. Round 1 pins unchanged.
- `app/db/models.py` (SQLAlchemy `Visit`, same columns as Round 1);
  `app/db/repositories.py` reimplemented on SQLAlchemy with the **same interface**;
  `app/db/database.py` adds SQLite and PostgreSQL engines.
- `DATABASE_URL` setting (`SecretStr`). Set: PostgreSQL, schema via Alembic only. Unset: Round 1 SQLite.
- Alembic: `backend/alembic.ini`, `backend/migrations/` with revision `0001` (PostGIS extension and
  `visits` table, check constraints, date index).
- `backend/Dockerfile` (non-root uid 10001), `backend/.dockerignore`, `docker-compose.yml`
  (`db`, `migrate`, `api`).
- `/api/health` now also reports `database` and `database_ok`. These fields were added; nothing was
  removed.
- `POSTGRES_PASSWORD` added to `.env.example` (empty) and to the local `.env` (generated, not printed).

**Evidence**

| Check | Command | Result |
| --- | --- | --- |
| Round 1 tests on the new repository layer (host, SQLite) | `.venv\Scripts\python -m pytest -q` | 69 passed, 8 skipped (PostgreSQL-only) |
| Round 1 SQLite file still readable, not modified | `VisitRepository(connect(...)).list_visits()` | 6 visits read |
| Stack starts healthy | `docker compose up --build -d`; `docker compose ps` | db healthy, migrate exit 0, api healthy |
| Migration | `docker compose logs migrate` | `Running upgrade -> 0001` |
| Health | `GET /api/health` | `status ok, database postgresql, database_ok true, gnani_configured true` |
| Round 1 endpoints | `GET /api/visits`, `GET /api/followups` | 200 |
| All tests in the container (PostgreSQL) | `docker compose exec api python -m pytest -q` | **77 passed**, 0 warnings |
| Database port not published | `docker port asha-saathi-db-1` | nothing published |
| API runs as non-root | `docker compose exec api id -u` | 10001 |
| Persistence across full restart | probe visit, then `docker compose down`, then `up -d` | probe visit id 1 still present |
| Backup and restore | `pg_dump -Fc` → `pg_restore` into scratch DB | counts match, alembic `0001`, PostGIS 3.6; scratch DB dropped |
| Downgrade/upgrade on a clean DB | `test_downgrade_and_upgrade_again` | passed |

**Data note:** the PostgreSQL database contains one synthetic probe visit,
`PHASE1-RESTART-PROBE` (id 1), from the restart check.

**Not yet verified in Phase 1:** the browser/phone flow against the container. The proxy target is
unchanged (`127.0.0.1:8000`), but this will be re-checked in Phase 5/7.

Checkpoint commit: `ad5db92`.

## Phase 2: authentication, roles, territories, audit (21 Nov 2026)

**Design**
- **Sessions:** server-side, in the `auth_sessions` table, storing only a SHA-256 hash of the token.
  The cookie `asha_session` is httpOnly, Secure, SameSite=Strict, and lasts 12 h (`SESSION_TTL_HOURS`).
- **Passwords:** Argon2id (`argon2-cffi==25.1.0`), at least 12 characters. When the username doesn't
  exist, a dummy hash is still checked, so response time doesn't reveal valid usernames. Login errors
  are generic.
- **Login rate limit:** 5 failures per username + client in 5 minutes. It's kept in memory, so an
  API restart clears it (acceptable for a single-process prototype).
- **Request forgery:** unsafe requests need the `X-Requested-With: asha-saathi` header. CORS stays
  GET-only, so a cross-site page can't send that header.
- **Roles:** `worker`, `supervisor`, `admin`. Workers and supervisors see only territories with an
  active assignment; admins see all. Access is checked in the service layer
  (`app/auth/service.py: visible_territory_ids / ensure_territory_access`). Another territory's ID
  returns **404**, so IDs can't be probed.
- **Audit:** `audit_events` records action, resource, actor, request ID, and sanitised details
  (codes and field names only). It covers login, failed login, logout, user creation, and assignment
  create/end.
- **WebSocket `/ws/v2/session`:** the handshake is refused (close 4401/4403, HTTP 403) without a valid
  cookie or when the Origin doesn't match the Host. Binding a session to a household or person is
  Phase 5.
- **Round 1 endpoints** (`/api/visits`, `/api/followups`, `/ws/session`) still have **no login**.
  They're kept for the current frontend behind `LEGACY_ROUND1_API_ENABLED` (default true).
  **Open security item:** set it to false once the V2 UI replaces them (Phase 7).
- **First admin:** `docker compose exec api python -m scripts.create_user --username admin --display-name "Admin" --role admin`
  prints a one-time random password. No password is committed.

**New files:** `app/auth/{passwords,service,deps,ratelimit}.py`, `app/api/v2/{auth,territories,admin,ws}.py`,
`app/schemas/auth.py`, `migrations/versions/0002_auth_territories_audit.py`, `scripts/create_user.py`,
`tests/test_auth.py`. `app/main.py` became an app factory (`create_app(engine)`) with a request-ID middleware.

**Evidence**

| Check | Result |
| --- | --- |
| Container suite (`docker compose exec api python -m pytest -q`) | **102 passed** |
| Host suite (SQLite) | 92 passed, 10 skipped (PostgreSQL-only) |
| Migration on the live database | `Running upgrade 0001 -> 0002`; `alembic_version` = 0002 |
| Migrations match the models (`test_migrations_match_models`) | passes. It caught one missing index on its first run, which is now fixed |
| Attack tests (`tests/test_auth.py`, 23) | forged cookie, replayed token after logout, expired session, deactivated user, guessed territory ID (404), ended assignment, non-admin on admin routes, missing CSRF header, rate limit, WebSocket without cookie / forged cookie / cross-site Origin: all refused |
| Live HTTP probes on the Docker API | `/api/v2/auth/me` 401, login without CSRF header 403, bad credentials 401, admin route 401, WebSocket handshakes 403 |
| Live audit row | `auth.login_failed` stored with request ID; 0 rows contain password text |

**Not yet covered:** a forged `person_id` in the WebSocket start message is tested in Phase 5, when
households and people exist.

Checkpoint commit: `e7caeca`.

## Phase 3: households, people, relationships, synthetic seed (21 Nov 2026)

**Decisions (approved: option A, Cubbon Park)**
- **Pins:** the 12 pins sit in public open space inside Cubbon Park (OSM way 22895320). They were
  chosen from OpenStreetMap data and each was then re-checked with `scripts/verify_demo_pins.py`.
  All are labelled "Synthetic demo pin ... not a real residence" with `location_source = synthetic_demo`.
- **Schema (migration `0003`):**
  - `households`: PostGIS `geography(Point,4326)` with a GiST index.
  - `people`.
  - `person_relationships`: explicit `mother_of`, `father_of`, `guardian_of`, `spouse_of` edges.
  - `programme_enrolments`: ANC, PNC, newborn, immunisation and NCD follow-up, recorded **explicitly
    only**, never inferred.
  - `household_surveys`: water source and toilet only (non-medical).
  - `is_demo` renamed to `is_demo_data` on users and territories, so every table uses the same marker.
- **Ownership:** a household belongs to a territory, and a worker's access comes from their territory
  assignment. There's no separate household-assignment table.
- **Deferred:** a household survey create/edit API.
- **Seed (`python -m scripts.seed_demo`):**
  - It only adds missing rows, matched by stable keys, and never modifies or deletes existing ones.
  - UUIDs are deterministic (uuid5).
  - Dates are relative to the fixed demo date 2026-11-21, overridable with `--as-of`.
  - New demo accounts are **inactive with no usable password** until the owner runs
    `python -m scripts.set_password --demo-accounts` (interactive, never echoed or logged).
  - No password is generated for display or printed anywhere. `create_user` now prompts the same way.
- **Round 1 endpoints:** **off by default in V2** (PostgreSQL mode) and on only in the Round 1 SQLite
  mode. `LEGACY_ROUND1_API_ENABLED=true` is an explicit opt-in, and `/api/health` reports
  `legacy_round1_api`. This closes the Phase 2 open item for the V2 default.
- **API:**
  - `GET /api/v2/households` returns map pins: location and member count only, no programmes.
  - `GET /api/v2/households/{H-###|uuid}`, `.../members`, and `GET /api/v2/people/{P-###|uuid}`.
  - `POST /api/v2/households/{id}/members` is for a worker in that territory or an admin, needs the
    CSRF header, and is audited with field names only.
  - Supervisors are read-only. Another territory's household or person returns 404.

**Dataset (all synthetic):** 2 territories × 6 households, 50 people (4+5+4+3+4+5 / 4+4+5+4+4+4),
55 family edges, 10 explicit enrolments (ANC 1, PNC 3, newborn 3, immunisation 2, NCD follow-up 1),
12 surveys, and 4 accounts (`demo_worker_a`, `demo_worker_b`, `demo_supervisor`, `demo_admin`). There
are no phone numbers or identity numbers. Adults have a recorded age, and children have a date of
birth relative to the demo date.

**Evidence**

| Check | Result |
| --- | --- |
| Pin verification against OSM (`python -m scripts.verify_demo_pins`) | **ALL PINS OK**: each inside Cubbon Park, only park and park-woodland areas (`natural=wood` relation 5525499 / way 372060604), 0 buildings within 30 m, minimum separation 80 m |
| Live database migration | `Running upgrade 0002 -> 0003`. Backup taken first (`data/backups/asha_saathi_pre_0003.dump`) |
| Live seed, run 1 | created 2 territories, 4 users, 4 assignments, 12 households, 50 people, 55 relationships, 10 enrolments, 12 surveys. **INVARIANTS: OK** |
| Live seed, run 2 (idempotency) | `created: nothing`, invariants OK |
| Container suite | **133 passed** (incl. 29 in `test_households.py`, 10 in `test_postgres.py`) |
| Host suite (SQLite) | 94 passed, 39 skipped (PostgreSQL-only) |
| Migrations match the models (including PostGIS geography) | passes |
| Authorization (REST, PostgreSQL) | Worker A sees only H-001..006 and Worker B only H-007..012. Supervisor and admin see 12. Requests for Territory B by `H-007`, lowercase `h-007`, UUID, `/members`, `P-###` or person UUID return 404, the same as a missing ID. Adding a member in another territory returns 404, a supervisor adding one gets 403, and a missing CSRF header gets 403. Ending an assignment removes access immediately |
| Integrity | FKs block deleting a household that has members and deleting a territory that has households. CHECKs reject a bad `H-`/`P-` format, unknown relationship type or programme, self-relationship, and a recorded age without a date. Duplicate public IDs are rejected |
| Live defaults | `/api/visits` 404 (Round 1 off), `/api/v2/households` 401 without login, health `legacy_round1_api: false` |
| Voice workflow regression (real Gnani, one run, Round 1 endpoint enabled for that run only, then disabled) | disclosure → read-back 4.9 s → correction delta 3.6 s → "ಹೌದು" saved visit #2 **to PostgreSQL** → newborn fever `NB_FEVER` alert 2.9 s; no session errors |
| Frontend | typecheck and build pass (no frontend changes) |
| Secret scan of the changes | none (only the existing `[ENCRYPTION_KEY]` placeholder in `.env.example`) |

**Data notes:**
- The live database also holds synthetic visit #2 (beneficiary 1234) from the voice regression run,
  plus probe visit #1 from Phase 1.
- The demo accounts are **inactive** until the owner sets a password.

**Remaining risks:**
- **OSM accuracy:** the pins depend on OpenStreetMap; unmapped kiosks or paths aren't covered.
  Re-run `verify_demo_pins` before a public demo.
- **Overpass reliability:** the public Overpass service returned intermittent 502s; the script retries.
- **Extra PostGIS extensions:** the PostGIS image's init script also installs topology and tiger
  extensions in the app database (unused).
- **Surveys:** there's no survey create/edit API yet.
- **Voice not yet bound to a household:** the voice session isn't linked to the selected household or
  person yet (Phase 5).

**Next:** Phase 4 (spatial search APIs, manual-search fallback). Waiting for approval.

## Phase 4: secure map discovery, household confirmation, member selection (21 Nov 2026)

Mapping of the handoff's contracts to the code: `docs/V2_CONTRACT_DECISIONS.md`.

**Scope**
- **No schema change and no seed change.**
- **Backend:**
  - Search (`q`), `bbox`, keyset paging (`after` / `X-Next-After`) and the territory filter on `GET /api/v2/households`.
  - New `GET /api/v2/households/nearby`: PostGIS geography metres, ties broken by ID.
  - New `GET /api/v2/households/{h}/members/{p}`: the server recheck behind "Select member".
  - Uniform, audited 404s (`access.denied`).
  - Relationship names limited to the caller's territories.
  - Per-user read limit (429).
  - Query strings redacted from access logs, and SQL parameters hidden in error text.
- **Browser (`/v2`):**
  - Login and a synthetic-data banner.
  - MapLibre pins: a plain basemap by default; OpenFreeMap is opt-in.
  - Accessible list, search and a one-shot GPS hint that never selects anything.
  - Preview → Confirm household → members → Select member, with a breadcrumb.
  - The selection resets on household change, logout, session loss and grant change.
- **Round 1 at `/` is unchanged.**

**Evidence**

| Check | Result |
| --- | --- |
| Docker suite | **275 passed** (133 baseline + 142 Phase 4) |
| Host suite | 149 passed, 126 skipped (PostgreSQL-only) |
| Frontend | typecheck and build pass. Vitest: **40 passed** (selection state machine, geo helpers, routing) |
| Real browser (Edge 158, `e2e/phase4_browser.py`, disposable `asha_saathi_e2e`) | **52 passed, 0 failed**. Viewports 360, 412 and 1280 px. 19 screenshots in `data/e2e/phase4/`, with no unexpected console errors |
| Live database after all runs | 12 households, 50 people. Demo accounts still inactive. INVARIANTS: OK |
| Independent review (4 lenses + adversarial verifiers) | 12 confirmed findings, all P2, all fixed and covered by tests. No P0/P1 |
| Gnani | Not called in Phase 4. The adapters are unchanged |

**Remaining risks:**
- The rate limiter is in memory.
- Supervisor pins overlap at full zoom-out; zoom in or use the list.
- The dev-only Vite 6.3.5 advisory is pre-existing.
- The OpenFreeMap terms await owner acceptance.
- Kannada UI labels have not been reviewed.

**Next:** Phase 5 needs owner approval.

## Phase 5A: member-linked voice visit (22 Nov 2026)

Full technical handoff and contract map: `docs/v2/PHASE5_HANDOFF.md`.

**Scope**
- **Migration (`0004`):** Additive `v2_visits` table linking confirmed visits to `people`, `households`, `users`, and `territories` with `UNIQUE (worker_id, client_visit_id)` and structured fields only (no audio, raw transcripts, prompts, or drafts).
- **Backend:** `/ws/v2/session` (cookie + same-Origin auth, immutable `VisitBinding`, disclosure-gated mic, per-version read-back ack, spoken "ಹೌದು" blocked from saving, periodic and transactional `FOR SHARE` re-authorisation, mother/newborn separation) and scoped history/receipt endpoints (`/api/v2/people/{key}/visits`, `/api/v2/visits/by-client-key/{client_visit_id}`). Feature-flagged OFF by default (`V2_VOICE_ENABLED=false`).
- **Frontend (`/v2`):** Explicit required visit-type selector (no default), `useV2VoiceSession` + pure `voiceVisitReducer`, `VoiceVisitPanel`, demo-only `V2DangerAlert`, `VisitHistory`, lost-ACK receipt lookup, and `SelectionPanel` integration at 360 px.
- **Deferred (6 AM demo scope):** Phase 5B (Gemini), Phase 5C (IndicTrans2 research), and Phase 5D (unified extraction).

**Codex QA blocker fixes (22 Nov 2026)**
- Cross-person attribution (`session_service.py`): single-population V2 sessions reject observations naming another person or ambiguous subjects (`clarification.requested(field="subject")`) and partition danger alerts strictly between `this_visit` and `other_person` without contaminating the bound person's draft.
- Correction/save race (`session_service.py`, `voice_v2.py`, `voiceVisit.ts`): `_turn_lock` + `_has_pending_speech()` + frontend `speechInProgress` block stale confirmations immediately when speech/correction starts and serialize extraction with confirmation.
- Failed initial read-back (`session_service.py`): `_readback_synthesized` ensures `_full_readback_done` and `_changed_since_readback` only advance after TTS synthesis succeeds (and in V2 after browser playback ack), so a correction after a failed initial read-back reads the complete record.

**Evidence (Pre-Gemini Checkpoint · 22 Nov 2026 ~02:35 IST · zero new paid Gnani calls):**

| Check | Result |
| --- | --- |
| Independent Codex QA (`test_phase5_codex_voice.py` + `test_phase5_codex_postgres.py`, `NOVIX_CODEX_PRIVATE_PG=1` on isolated `novix_codex_e2e`) | **14 passed, 0 failed** (`4.51s`) |
| Docker suite (`docker compose exec -T api python -m pytest -q -p no:cacheprovider`) | **317 passed, 6 skipped** (Codex PG suite skipped without `NOVIX_CODEX_PRIVATE_PG=1`), **0 failed** (`38.06s`) |
| Frontend (`npm run typecheck`, `npx vitest run`, `npm run build`) | Typecheck OK, **60 passed** (5 files incl. `visitHistory.test.ts`), build OK |
| Phase 5 real-browser E2E (`e2e/phase5_browser.py --channel msedge`, `MockVoiceProvider` on `asha_saathi_e2e`, 360/412/1280 px) | **24 passed, 0 failed** (`data/e2e/phase5/report.json`) |
| Phase 4 real-browser regression + offline map fallback (`e2e/phase4_browser.py --channel msedge`) | **52 passed, 0 failed** (`data/e2e/phase4/report.json`) |
| OpenFreeMap Liberty basemap check (`frontend/.env.local`) | **PASS** (`200` style & 6 `.pbf` vector tiles, `0` map/console errors, 6 DEMO-A pins, ODbL + synthetic attribution) |
| Live database & backup (`asha_saathi`) | Alembic `0005` (`routine` visit type), 12 households, 50 people, 55 relationships (`INVARIANTS: OK`), live Gnani `H-005 / P-020` Routine Visit (`55 kg`, `2026-11-28`, `v2`), checkpoint dump `data/backups/asha_saathi_phase5a_checkpoint_20261122_0235.dump` (`53086` bytes, `PGDMP`, `pg_restore --list` OK); `main` unchanged at `aba3f2b` |

**Next:** `PHASE 5A GO` — awaiting owner approval before creating the Phase 5A checkpoint commit and starting Gemini backend planning.
