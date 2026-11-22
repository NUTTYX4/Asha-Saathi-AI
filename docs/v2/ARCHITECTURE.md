# ASHA Saathi AI 2.0: architecture

A voice-first field register for ASHA workers. It is a prototype with synthetic data only. It provides no diagnosis, treatment or medication advice. Its danger-sign rules are **demo-only**, pending clinical review.

## Components

```
Browser (React 18 + TS + Vite + Tailwind 4, /v2)
   │  same origin: /api/* (REST, httpOnly session cookie + anti-CSRF header), /ws/v2/session (voice)
   ▼
FastAPI (backend/app, Docker service "api", 127.0.0.1:8000)
   ├── PostgreSQL 17 + PostGIS 3.6 (service "db", internal network only, volume pgdata)
   ├── Gnani Prisma v3.0 (speech-to-text) and Timbre v3.0 (text-to-speech), from the backend only
   └── Gemini extraction assist: optional, off by default (EXTRACTION_PROVIDER_MODE=deterministic)
```

- **Local development:** the Vite dev server proxies `/api` and `/ws`. Start everything with `py run.py` (see [`../LOCAL_DEVELOPMENT.md`](../LOCAL_DEVELOPMENT.md)).
- **Demo hosting:** Caddy serves the production build and forwards only `/api/v2/*`, `/api/health` and `/ws/v2/session`, through a Cloudflare quick tunnel (`deploy/tunnel/`). The permanent link `novix-asha-saathi-demo.vercel.app` redirects to the current tunnel (`deploy/vercel-redirect/`).
- **Schema:** changes go only through Alembic (`backend/migrations`). The current head is `0005`.

## Roles

There are three roles, enforced on the server (`users.role` CHECK; `require_roles`):

| Role | Can do |
| --- | --- |
| `worker` | Read and record in assigned territories only. Other territories return 404 |
| `supervisor` | Read every territory it is assigned to. Never records |
| `admin` | Global read, user/territory/assignment management, and the admin dashboard |

Territory scope comes from active `territory_assignments` rows. Ending or moving an assignment takes effect on the next request, and live voice sessions are revalidated.

## API route groups

There are 28 HTTP routes and 1 WebSocket. The full matrix is in `docs/qa/API_ENDPOINT_COVERAGE.md`.

| Group | Routes | Access |
| --- | --- | --- |
| Health | `GET /api/health` | public |
| Auth | `POST /api/v2/auth/login`, `POST /api/v2/auth/logout`, `GET /api/v2/auth/me` | login/logout need the anti-CSRF header |
| Territories | `GET /api/v2/territories`, `GET /api/v2/territories/{id}` | signed in, scoped |
| Households and people | `GET /api/v2/households`, `/households/nearby`, `/households/{key}`, `/households/{key}/members`, `/households/{key}/members/{person}`, `POST /households/{key}/members`, `GET /api/v2/people/{key}` | scoped. Writes: worker (own territory) or admin, plus CSRF. Reads have a per-user request budget |
| Visits | `GET /api/v2/people/{key}/visits`, `/people/{key}/visits/{visit_id}`, `/visits/by-client-key/{id}` | scoped. The receipt lookup returns only the caller's own visits |
| Admin management | `POST /api/v2/admin/users`, `/admin/territories`, `/admin/assignments`, `/admin/assignments/{id}/end`, `/admin/assignments/{id}/reassign`; `GET /api/v2/admin/audit` | admin only. Writes need CSRF and are audited |
| Admin dashboard | `GET /api/v2/admin/overview`, `/admin/workers`, `/admin/visits`, `/admin/coverage`, `/admin/users`, `/admin/assignments` | admin only, read-only |
| Voice | `WS /ws/v2/session` | cookie plus same Origin; worker in scope; flag `V2_VOICE_ENABLED` |

The Round 1 routes (`/api/visits`, `/api/followups`, `/ws/session`) are not registered unless `LEGACY_ROUND1_API_ENABLED=true`.

## Voice visit data flow

1. **Choose the person.** The worker confirms a household, then a member, then picks the visit type explicitly. Nothing is inferred from enrolment.
2. **Bind the session.** The browser opens `/ws/v2/session` and sends `v2.session.start`. The server authorizes it and binds it to `(worker, household, person, territory, client_visit_id)`. The binding cannot change.
3. **Disclose first.** One short greeting with the AI disclosure is spoken, once per session ("ನಮಸ್ಕಾರ, ನಾನು AI ಸಹಾಯಕ.", "Namaskara, I am an AI assistant."). Audio is ignored until the browser reports that the disclosure finished playing.
4. **Speech in.** Speech goes through Prisma to a transcript, then deterministic extraction (the optional Gemini assist is validated, and can never set identity or alerts). The result is a versioned draft. The demo-only danger rules are checked against the right population (mother or newborn).
5. **Read back.** Timbre reads the full record back. A correction bumps the version and invalidates the earlier read-back acknowledgement.
6. **Explicit save.** **Confirm and Save** for the latest acknowledged version writes exactly one `v2_visits` row. One transaction holds `FOR SHARE` locks, enforces unique `(worker_id, client_visit_id)` and revalidates access. Saying "ಹೌದು" never saves.
7. **What is kept.** No audio, transcript or draft is stored. History reads confirmed rows only.

## Admin data

- **Source:** every dashboard count comes from `users`, `territories`, `territory_assignments`, `households`, `people`, `v2_visits` and `audit_events`.
- **Definitions:** see `backend/app/schemas/admin.py`. Briefly:
  - "registered" vs "visited", where visited means at least one confirmed visit in range;
  - follow-ups come from each person's latest confirmed visit;
  - dates are IST.
- **Reassignment:** ends the old assignment and starts the new one in one transaction, audited. Visits stay with their recorder.
