# ASHA SAATHI AI 2.0: progress log and verification checklist

Brief: `ASHA_SAATHI_AI_V2_ENGINEERING_MASTER_PLAN.md` (Section 15 is authoritative).
Branch: `v2/backend-foundation`. Round 1 baseline: `main` at `aba3f2b` (pushed).

## Phase checklist

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Preflight: git baseline, Docker/WSL, toolchain, secrets present | Done |
| 1 | Docker Compose + PostgreSQL/PostGIS + SQLAlchemy/Alembic, Round 1 contracts kept | **Done (gates passed)** |
| 2 | Auth, roles, territories, audit; REST and WebSocket denial tests | **Done (gates passed)** |
| 3 | Households/people/relationships + 12-house/50-person idempotent seed | Not started |
| 4 | PostGIS spatial APIs, manual search fallback | Not started |
| 5 | Household/person-bound Gnani visit flow saved to PostgreSQL | Not started |
| 6 | Tasks, referrals, guideline versions, terminology, data quality, KPIs | Not started |
| 7 | Minimal browser UI | Not started |
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

**Next:** Phase 3 (households, people, relationships, 12/50 seed).
