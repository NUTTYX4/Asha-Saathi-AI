# Demo readiness: hackathon runbook

> **Pushing or merging code does not update the live demo.** The demo runs from a Docker image, a frontend build and a tunnel process on the presenter's laptop. They change only when someone deliberately rebuilds and restarts them, as described in [Deploying a new build later](#deploying-a-new-build-later).

## 1. What is live and what is only on the branch

| | Live demo (as checked on 22 Nov 2026) | `main` / `v2/final-qa-admin` |
| --- | --- | --- |
| Worker flow: households, member, voice visit, history | yes | yes |
| Admin dashboard (Overview, workers, visits, territories, assignments, audit) | **no** | yes |
| Short V2 greeting ("ನಮಸ್ಕಾರ. ನಾನು AI ಸಹಾಯಕ, ಮನುಷ್ಯರಲ್ಲ. ಭೇಟಿಯ ವಿವರ ಹೇಳಿ.") | **no** (the live API still speaks the older introduction) | yes |
| Confirmation dialogs sized to their content | **no** | yes |
| Database schema | `0005` | `0005` (this release adds no migration) |

## 2. How the demo is served

```
Visitor ──▶ https://novix-asha-saathi-demo.vercel.app          (Vercel project novix-asha-saathi-demo: a 307 redirect only)
        ──▶ https://households-definitions-facilities-comfortable.trycloudflare.com   (Cloudflare quick tunnel)
        ──▶ cloudflared on the laptop ──▶ Caddy 127.0.0.1:8080  (deploy/tunnel: serves frontend/dist, forwards /api/v2/*, /api/health, /ws/v2/session)
        ──▶ api container 127.0.0.1:8000 (FastAPI, baked image) ──▶ db container (PostgreSQL/PostGIS, internal network only)
```

- **Why the tunnel is session-bound.** `cloudflared` was started from the Claude Code session, so it is a child of that session's shell. Closing that session, sleeping or restarting the laptop, or a long network loss can end the process.
- **What happens if it dies.** A quick-tunnel hostname cannot be recovered. A new tunnel gets a new random address.
- **The permanent link survives this.** The Vercel link exists so it can be re-pointed (see §4).

## 3. Health checks (read-only, safe at any time)

From the repository root in PowerShell:

```powershell
py run.py --status                                           # tools, containers, migration, demo detection
curl.exe -s -o NUL -w "%{http_code} %{redirect_url}`n" https://novix-asha-saathi-demo.vercel.app/
curl.exe -s https://households-definitions-facilities-comfortable.trycloudflare.com/api/health
Get-Process cloudflared                                      # the tunnel process exists
docker compose ps; docker compose -f deploy/tunnel/compose.yaml ps
```

**Healthy looks like this:**

- the Vercel link returns `307` to the tunnel;
- `/api/health` reports `"status":"ok"` and `"database_ok":true`;
- `db` and `api` show `(healthy)`;
- the tunnel proxy `web` is running.

## 4. Safe recovery

| Symptom | Safe action | Changes the URL? |
| --- | --- | --- |
| Tunnel URL shows Cloudflare error 1033 or 530, and `cloudflared` is gone | Start a new tunnel: `cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8080`. Then re-point the permanent link: `powershell -ExecutionPolicy Bypass -File .\deploy\vercel-redirect\set-demo-link.ps1 https://NEW.trycloudflare.com` | The tunnel URL changes; the **Vercel link stays the same** |
| Tunnel answers 502 (Caddy is down, for example after a Docker Desktop restart) | `docker compose -f deploy/tunnel/compose.yaml up -d` | No |
| `api` or `db` stopped | `py run.py --backend-only` (it starts stopped containers in place and never rebuilds) | No |
| A demo account is locked after wrong passwords | Wait for the limiter window to pass (all visitors share one address behind the proxy) | No |

## 5. Do not do these during judging

- **Don't touch the tunnel.** Don't close the Claude Code session or terminal that owns `cloudflared`, and don't let the laptop sleep or restart. Set the laptop to never sleep, set lid close to do nothing, and pause Windows Update.
- **Don't change what Caddy serves.** Don't run `npm run build`: Caddy serves `frontend/dist` directly, so a rebuild changes the live site immediately.
- **Don't stop or reset containers.** Don't run `docker compose down`. Never use `-v`, because it deletes the database. Don't restart Docker Desktop. Don't run `docker compose build api` or `up` with recreate.
- **Don't run the browser suites.** They share the database server, so don't run them on the demo machine during judging.
- **Don't change passwords.** Judges may have the submitted sign-in details.

## 6. Deploying a new build later

Do this only after judging, or in an agreed quiet window.

**Preconditions:**

- `main` is pushed and its checks passed;
- a database backup has been taken (`docs/v2/operations.md`, "Backup and restore");
- nobody is using the demo.

**Steps:**

```powershell
git switch main; git pull --ff-only
docker compose build api                     # new image from main
docker compose up -d --no-deps api           # recreates only the api container (a few seconds offline)
py run.py --status                           # wait for api (healthy) and "Migrations 0005 (head)"
cd frontend
$env:VITE_MAP_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty"
npm run build                                # Caddy picks up the new dist immediately
Remove-Item Env:VITE_MAP_STYLE_URL
```

- The tunnel, the Caddy container and the Vercel link are **not** restarted.
- No migration is needed for this release.

**Rollback:**

1. Check out the previous commit: `git switch --detach 9c52782`. Its backend code is identical to the `126fd09` image the live API runs, and its frontend matches the live build.
2. Run the same build and `up -d --no-deps api` steps.
3. Rebuild `frontend/dist` the same way.

The database is unaffected, because this release adds no migration.

## 7. After judging

- **Rotate every demo account password**, giving each account its own strong password. Type them interactively and never put them in files:

  ```powershell
  docker compose exec api python -m scripts.set_password --username demo_worker_a
  ```

  Repeat for `demo_worker_b`, `demo_supervisor` and `demo_admin`.
- **Close the public link.** Stop the tunnel (Ctrl+C in its window), then stop the proxy with `docker compose -f deploy/tunnel/compose.yaml down`. That command touches only the proxy.
- **Disable the redirect** if the link should not stay public: pause or remove the `novix-asha-saathi-demo` Vercel project.

## 8. Limits of this demo

- **Synthetic data only.** It is not production-ready and gives no diagnosis, treatment or medication advice.
- **Danger rules are demo-only**, pending clinical sign-off.
- **Kannada prompts**, including the new greeting, are pending native-speaker review.
- **Voice quality is unproven.** Automated voice tests use simulated speech, so they do not establish real Gnani recognition quality on a phone. Live voice visits spend real Gnani credits.
- **Gemini assist is off.**
