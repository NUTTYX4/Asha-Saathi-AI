# Local development

How to run ASHA Saathi AI 2.0 (`/v2`) on your own machine with one command, read its logs, and stop it safely.

The launcher is for **local development only**. It is not a way to host the app publicly. The public demo is a separate setup, described under [The public demo is separate](#the-public-demo-is-separate).

## One-command start

From the repository root:

```powershell
py run.py            # Windows (Python launcher)
python3 run.py       # macOS / Linux
```

Then open **https://localhost:5173/v2**. Accept the self-signed certificate once, then sign in with a demo account.

You need:

- **Docker Desktop**, running.
- **Node.js 20+** with npm.
- **Python 3.9+**. The launcher uses only the standard library, so there is nothing to `pip install`.
- **A `.env` file** at the repository root. Copy it from `.env.example`. `POSTGRES_PASSWORD` is required, and `GNANI_API_KEY` is needed for voice visits.

| Command | What it does |
| --- | --- |
| `py run.py` | Checks tools and `.env`, makes sure `db` and `api` are healthy, starts the Vite dev server (or reuses one already running), then streams logs |
| `py run.py --status` | Shows tools, configuration, container health, migration state and the frontend. Changes nothing |
| `py run.py --backend-only` | Makes sure `db` and `api` are healthy and streams their logs. No frontend |
| `py run.py --no-build` | Never builds Docker images. If one is missing, it fails instead |
| `py run.py --lan` | Serves the dev frontend on all interfaces, so a phone on the same Wi-Fi can open `https://<laptop-IP>:5173/v2` |
| `py run.py --stop` | Stops the `api` and `db` containers. Data is kept. Refused while the public demo is running |
| `py run.py --help` | All options |

Exit codes:

- `0` OK
- `1` a service failed
- `2` a prerequisite is missing (Docker, Node, `.env`)
- `3` refused to protect the running demo

## What the launcher will and won't do

**It will:**

- **Leave healthy containers alone.** If `db` and `api` are already healthy, it leaves them exactly as they are: no restart, no recreate, no rebuild.
- **Start stopped containers in place.** It uses `docker compose start` on the existing containers.
- **Create missing services from the existing Compose file.** It runs `docker compose up -d --no-recreate`, which builds an image only if it does not exist yet. Add `--no-build` to forbid even that.
- **Apply pending migrations only through the existing mechanism.** That is the `migrate` service (`alembic upgrade head`), and only when the public demo is not running.
- **Reuse a running dev server.** If the Vite dev server already answers on `https://localhost:5173`, it reuses it instead of starting a second one.
- **Keep the dev server on this machine.** It binds Vite to `localhost`. Pass `--lan` to open it to other devices.
- **Clean up only its own processes on Ctrl+C.** It stops the Vite server it started and its log followers. Docker keeps running.

**It never:**

- resets, reseeds or replaces the database;
- runs `docker compose down`, and never `-v`;
- rebuilds a running image;
- prints a value from `.env`.

## Architecture

```
Browser ──HTTPS──▶ Vite dev server  localhost:5173  (frontend/, self-signed certificate)
                     │  /api  and  /ws  are proxied
                     ▼
                  api container  127.0.0.1:8000   (FastAPI, backend/)
                     │  internal Docker network only
                     ▼
                  db container  (PostgreSQL 17 + PostGIS; data in the pgdata volume; no host port)
```

- `docker-compose.yml` defines three services:
  - `db`;
  - `migrate`, a one-off `alembic upgrade head`;
  - `api`.

  It also defines `api-e2e`, for browser tests only (profile `e2e`).
- The Vite proxy keeps the browser's Host header for `/ws`, so the backend's same-origin WebSocket check works. It also lets a phone use the app over one HTTPS origin.
- Operations reference: [docs/v2/operations.md](v2/operations.md).

## Development frontend vs production frontend

| | Development (this launcher) | Production build (demo) |
| --- | --- | --- |
| Served by | Vite dev server, hot reload | Caddy, serving `frontend/dist` (`deploy/tunnel/`) |
| URL | `https://localhost:5173/v2` | The demo link (see below) |
| Build step | None | `npm run build` |
| Backend | Same `api` container | Same `api` container |

Rebuilding `frontend/dist` changes what demo visitors see immediately. Do not run `npm run build` while the demo is live.

## Logs

The launcher prints one combined, timestamped stream:

```
14:02:11 web | VITE v6.3.5  ready in 676 ms
14:02:15 api | INFO: 172.20.0.3:44812 - "POST /api/v2/auth/login HTTP/1.1" 200 OK
14:02:15 db  | LOG:  checkpoint complete ...
```

- Docker health-check requests (`GET /api/health`) are hidden as noise.
- Cookies, `Authorization` headers, bearer tokens, JWTs, API keys, `password=`/`token=` values, database URL passwords and every secret value from `.env` are replaced with `[redacted]`.
- If the launcher reused an existing dev server, that server's log stays in the window that started it.

For logs without the launcher:

```powershell
docker compose logs -f api
```

## Health

`py run.py --status` prints, for example:

```
Demo       not running
Services   db running (healthy) | api running (healthy) | API health ok
Migrations 0005 (head)
Frontend   running at https://localhost:5173/v2
```

The API health endpoint is `http://127.0.0.1:8000/api/health`.

## Troubleshooting

| Message | Fix |
| --- | --- |
| `Docker is installed but its engine is not running` | Start Docker Desktop, wait for "Engine running", and run again |
| `Missing .env` | `Copy-Item .env.example .env` (PowerShell) or `cp .env.example .env`, then fill it in |
| `.env is missing required values: POSTGRES_PASSWORD` | Set it in `.env`. It must match the password the database volume was created with |
| `Port 5173 is in use by something that is not the ASHA Saathi dev server` | Close the other program, or find it with `netstat -ano \| findstr :5173` |
| `Backend did not become healthy` | `docker compose logs api db`. A common cause is a changed `POSTGRES_PASSWORD` |
| `Migrations PENDING ... NOT applied` | The demo is running. After the demo, run `docker compose run --rm migrate` |
| Browser warns about the certificate | Expected: the dev server uses a self-signed certificate (HTTPS is needed for the microphone) |
| `npm ci failed` | Delete `frontend/node_modules` and run again. Check Node is 20+ |

## Windows PowerShell notes

- Use `py run.py`. The Windows Python launcher picks the newest installed Python.
- Ctrl+C is safe. The launcher runs its children in their own process group and stops the whole npm → node tree with `taskkill /T`.
- If scripts are blocked by execution policy, that does not affect `run.py`, because it is run by Python, not PowerShell.

## The public demo is separate

The public demo has its own pieces, and the launcher only reads their state:

- the permanent link **https://novix-asha-saathi-demo.vercel.app** (`deploy/vercel-redirect/`);
- a Cloudflare tunnel (`cloudflared`);
- the Caddy proxy (`deploy/tunnel/`, port 8080).

When it sees `cloudflared` or the demo proxy running, it switches to protective mode:

- `--stop` is refused;
- pending migrations are reported but not applied;
- images are never built;
- healthy containers are never touched.

Starting a stopped `db` or `api` container is still allowed, because that only restores service.

## Safe shutdown

1. Press **Ctrl+C** in the launcher window. This stops Vite and the log stream; containers keep running.
2. When the demo is **not** running and you want the backend off:

   ```powershell
   py run.py --stop
   ```

   This runs `docker compose stop api db`. The database volume is kept.
3. Never run `docker compose down -v`: `-v` deletes the database volume.

## Launcher tests

```powershell
py -m unittest discover -s tests/launcher -v
```

The tests fake every Docker, Node, HTTP and clock call. They cover:

- missing Docker or `.env`;
- healthy, stopped and missing containers;
- health polling;
- frontend start and reuse;
- log labelling and redaction;
- Ctrl+C cleanup;
- repeat runs;
- demo protection.
