# ASHA SAATHI AI 2.0: progress log and verification checklist

Brief: `ASHA_SAATHI_AI_V2_ENGINEERING_MASTER_PLAN.md` (Section 15 is authoritative).
Branch: `v2/backend-foundation`. Round 1 baseline: `main` at `aba3f2b` (pushed).

## Phase checklist

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Preflight: git baseline, Docker/WSL, toolchain, secrets present | Done |
| 1 | Docker Compose + PostgreSQL/PostGIS + SQLAlchemy/Alembic, Round 1 contracts kept | **Done (gates passed)** |
| 2 | Auth, roles, territories, audit; REST and WebSocket denial tests | Not started |
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

**Next:** Phase 2 (authentication, roles, territories, audit).
