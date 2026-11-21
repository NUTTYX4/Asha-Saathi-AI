# V2 backend operations (Docker)

The V2 backend runs only in Docker. Round 1 (SQLite, local uvicorn) is preserved on the
`main` branch and still works there unchanged.

## Services (`docker-compose.yml`)

| Service | Image | Role | Network exposure |
| --- | --- | --- | --- |
| `db` | `postgis/postgis:17-3.6` | PostgreSQL 17 + PostGIS 3.6, data in the `pgdata` volume | None: internal Docker network only |
| `migrate` | built from `backend/Dockerfile` | One-off `alembic upgrade head`, runs before the API | Internal only |
| `api` | built from `backend/Dockerfile` | FastAPI, non-root user (uid 10001) | `127.0.0.1:8000` only (Vite proxies `/api` and `/ws`) |

Secrets come from the git-ignored repository-root `.env`: `GNANI_API_KEY` and `POSTGRES_PASSWORD`.

## Everyday commands (repository root)

```powershell
docker compose up --build -d                     # start db -> migrate -> api
docker compose ps                                # both services should say (healthy)
docker compose logs -f api                       # backend log
docker compose exec api python -m pytest -q      # all tests, including PostgreSQL ones
docker compose run --rm migrate                  # apply migrations manually
docker compose down                              # stop; data stays in the pgdata volume
```

**Never run `docker compose down -v` on real data:** `-v` deletes the database volume.

The frontend is unchanged: in `frontend\`, run `npm run dev`. It proxies to `127.0.0.1:8000`, so
the browser and phone flow works the same against the container.

## Synthetic demo data and accounts

```powershell
docker compose exec api python -m scripts.seed_demo            # add anything missing (safe to repeat), then check
docker compose exec api python -m scripts.seed_demo --check    # read-only invariant report
docker compose exec api python -m scripts.set_password --demo-accounts   # interactive; activates the 4 demo accounts
docker compose exec api python -m scripts.set_password --username demo_worker_a
docker compose exec api python -m scripts.create_user --username admin --display-name "Admin" --role admin
backend\.venv\Scripts\python -m scripts.verify_demo_pins       # from backend\, needs internet (OpenStreetMap)
```

- **Passwords:** they're typed interactively, never shown, and never logged. The seed never changes
  existing rows, accounts or passwords.
- **Demo accounts:** `demo_worker_a` (Territory A, H-001..006), `demo_worker_b` (Territory B,
  H-007..012), `demo_supervisor` (both, read-only), and `demo_admin`.

## Round 1 endpoints in V2

`/api/visits`, `/api/followups` and `/ws/session` have no login, so they're **off by default** in
Docker. For a temporary Round 1-UI demo only:

```powershell
$env:LEGACY_ROUND1_API_ENABLED = "true"; docker compose up -d api      # on
Remove-Item Env:LEGACY_ROUND1_API_ENABLED; docker compose up -d api    # off again
```

`GET /api/health` shows the current state in `legacy_round1_api`.

## Backup and restore

```powershell
# Backup (custom format), copied out with docker cp: PowerShell pipes corrupt binary data
docker compose exec -T db pg_dump -U asha -d asha_saathi -Fc -f /tmp/asha_saathi.dump
docker cp asha-saathi-db-1:/tmp/asha_saathi.dump data\backups\asha_saathi.dump

# Restore into a new database (does not touch the live one)
docker cp data\backups\asha_saathi.dump asha-saathi-db-1:/tmp/asha_saathi.dump
docker compose exec -T db createdb -U asha asha_restore
docker compose exec -T db pg_restore -U asha -d asha_restore /tmp/asha_saathi.dump
```

`data/` is git-ignored, so backups never enter git.

## Rollback

| To undo | Do this |
| --- | --- |
| The latest migration | `docker compose run --rm migrate alembic downgrade -1`. The `0001` downgrade drops `visits`, so take a backup first |
| V2 entirely | `docker compose down`, then `git switch main` and run Round 1 as in the README. The `pgdata` volume is kept |
| A bad data change | Restore the latest backup into a new database and compare before switching |

The Round 1 SQLite file `data/asha_saathi.db` is never opened by the Docker stack.
