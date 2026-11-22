# Demo readiness

## Live demo, as checked at the end of the QA session (read-only)

| Item | State |
| --- | --- |
| Submitted URL | **https://novix-asha-saathi-demo.vercel.app** gives a 307 redirect to `https://households-definitions-facilities-comfortable.trycloudflare.com/v2`, which returns 200 |
| Tunnel | `cloudflared` PID 10936, the same process since 05:30 IST, not restarted |
| Proxy | `asha-saathi-tunnel-web-1` running, the same start time as before the session |
| API | `asha-saathi-api-1` healthy, the same start time; `/api/health` reports ok with database ok |
| Database | `asha-saathi-db-1` healthy, the same start time; live data unchanged (12 households, 50 people, 1 confirmed visit) |
| Served frontend | `frontend/dist` not rebuilt (the production smoke build was written to a scratch folder) |
| Live passwords | not read, not changed |

## What the live demo shows today

The live demo runs the **pre-session** image and build. The work on `v2/final-qa-admin` is **not deployed**:

- the admin dashboard;
- the shorter greeting;
- the dialog fix.

Deploying it would mean rebuilding the `api` image, recreating the container and rebuilding `frontend/dist`. That briefly interrupts the demo, so it needs your decision and a quiet window.

When you choose to deploy, from the repository root:

```powershell
docker compose build api; docker compose up -d --no-deps api      # restarts the API (seconds)
cd frontend; $env:VITE_MAP_STYLE_URL="https://tiles.openfreemap.org/styles/liberty"; npm run build; Remove-Item Env:VITE_MAP_STYLE_URL
```

- No migration is needed: the database stays at `0005`.
- The tunnel and the Vercel link are unaffected.

## Risks to the demo

1. **The tunnel belongs to the Claude Code session.** It ends if this session closes or the laptop sleeps, restarts or loses its connection for long. The URL cannot be recovered. Re-pointing the Vercel link to a new tunnel takes one command: `deploy/vercel-redirect/set-demo-link.ps1`.
2. **Shared login rate limit.** Repeated wrong passwords through the proxy lock that account for everyone for the limiter window.
3. **Voice spends real credits.** Voice visits on the live stack use real Gnani credits.

## Before production use

- Clinical review of the danger-sign rules. They are still **demo-only**, with page citations unverified.
- Native-speaker review of the Kannada prompts, including the new greeting.
- Live Gnani speech-quality testing on real phones. All automated voice tests use **mock** speech, which says nothing about real recognition quality.
- A stable hosting setup instead of a quick tunnel: a named Cloudflare Tunnel with Access, or real hosting.
- Per-user client addresses for rate limiting behind the proxy.
- Strong unique passwords, rotated after the demo.
- Backups, monitoring and a data-protection review.
- Review and merge of the V2 branch.
