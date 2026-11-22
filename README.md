# ASHA SAATHI AI

**Voice-first digital field register for ASHA workers**

- **Team:** NOVIX
- **Event:** Build Bengaluru 2.0 (24-hour hackathon)
- **Problem statement:** Gnani PS1. Healthcare: voice field register for ASHA workers
- **Language:** Kannada with English medical terms (code-mixed)

> Hackathon prototype. Synthetic data only. Not a medical device and not production-ready. It does not
> diagnose, treat or recommend medication. The danger-sign rules are **demo-only** and need clinical
> sign-off before any real use.

## Status

| App | Path | State |
| --- | --- | --- |
| **ASHA Saathi AI 2.0** | `/v2` | The current app. Docker (FastAPI + PostgreSQL/PostGIS), accounts and roles, territories, household map, person-linked voice visits, visit history, admin dashboard |
| Round 1 | `/` | The original single-screen voice register (SQLite, no login). It is kept unchanged, and its API is **off** in V2 unless `LEGACY_ROUND1_API_ENABLED=true` |

## What V2 does

**ASHA worker** (signed in, scoped to their assigned territory):

1. Opens the household map or list, picks a household, and **confirms** it.
2. Picks a member, **confirms** the person, and chooses the visit type explicitly: routine, ANC, PNC, newborn or immunisation.
3. Starts the voice visit. The agent says "ನಮಸ್ಕಾರ. ನಾನು AI ಸಹಾಯಕ, ಮನುಷ್ಯರಲ್ಲ. ಭೇಟಿಯ ವಿವರ ಹೇಳಿ." The microphone only listens after this disclosure has played.
4. Speaks the visit in Kannada and English. **Gnani Prisma v3.0** transcribes it, and deterministic extraction fills a versioned draft. Missing values stay empty. Demo-only danger rules are checked for the right person.
5. Listens to the full read-back from **Gnani Timbre v3.0**. A spoken correction creates a new version and needs a new read-back.
6. Presses **Confirm and Save**, which saves exactly once. Saying "ಹೌದು" never saves. The visit appears in the person's **Visit history**.

**Supervisor:** reads every territory it is assigned to and never records.

**Admin:**

- the **admin dashboard**: Overview, ASHA workers with a detail view, Visit activity, Territories (registered vs visited households), Assignments (assign, move with confirmation, end; all audited) and Audit history;
- the same field view as workers, across all territories.

All authorization is enforced on the server. Other territories' records return 404.

## Architecture (V2)

```text
Browser /v2 (React 18 + TS + Vite + Tailwind 4) ── same origin: /api/* (session cookie + anti-CSRF header), /ws/v2/session
  ▼
FastAPI (Docker "api", 127.0.0.1:8000) ── Gnani Prisma v3.0 STT / Timbre v3.0 TTS (backend only)
  ▼                                    └─ Gemini extraction assist: optional, OFF by default
PostgreSQL 17 + PostGIS (Docker "db", internal network only)
```

- The API keys stay on the backend.
- No audio, transcript or draft is stored; only explicitly confirmed visits are.
- Details: [docs/v2/ARCHITECTURE.md](docs/v2/ARCHITECTURE.md). UI: [docs/v2/DESIGN.md](docs/v2/DESIGN.md). Operations: [docs/v2/operations.md](docs/v2/operations.md).

## Gnani services used

| Service | Configuration | Used for |
| --- | --- | --- |
| [Prisma v3.0 realtime STT](https://docs.gnani.ai/api/STT/stt-websocket) | `wss://api.vachana.ai/stt/v3/stream`, `model: prisma-v3.0`, `language_code: kn-IN`, `format: codemix`, 16 kHz PCM, 1,024-byte frames | Transcribing the worker's speech, with server-side end-of-speech detection |
| [Timbre v3.0 TTS](https://docs.gnani.ai/api/TTS/tts-inference) | `POST https://api.vachana.ai/api/v1/tts/inference`, `model: timbre-v3.0`, voice `Shruthi`, `language: kn-IN`, 24 kHz WAV | Disclosure, questions, read-back, danger-sign referral prompts |

No telephony, no voice cloning and no hosted voice-agent product: the orchestration is our own code.

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | React 18, TypeScript, Vite 6, Tailwind CSS 4, MapLibre (OpenFreeMap), lucide-react, Mulish + Noto Sans Kannada |
| Backend | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy, Alembic, PostgreSQL 17 + PostGIS 3.6 (Docker) |
| Voice | Gnani Prisma v3.0 (STT), Gnani Timbre v3.0 (TTS) |
| Logic | Deterministic extraction and Kannada number parsing; rule-based, demo-only danger signs; optional validated Gemini assist (off) |

## Tests

| Suite | Command | Last result (see [docs/qa/FINAL_QA_REPORT.md](docs/qa/FINAL_QA_REPORT.md)) |
| --- | --- | --- |
| Backend (PostgreSQL, disposable DBs) | see [docs/v2/operations.md](docs/v2/operations.md) | in the QA report |
| Frontend | `cd frontend; npm run typecheck; npx vitest run` | in the QA report |
| Browser e2e (mock speech) | `e2e/phase4_browser.py` … `e2e/phase7_admin.py` | in the QA report |
| Launcher | `py -m unittest discover -s tests/launcher` | in the QA report |

All voice tests use **simulated speech**, so they do not measure real Gnani recognition quality on a phone. Live Gemini calls are disabled in tests.

## Known limitations (V2)

- Danger rules are demo-only, pending clinical review. The Kannada prompts are pending native-speaker review.
- Live speech quality on real devices is not yet tested.
- The hackathon demo runs from a laptop through a Cloudflare quick tunnel ([docs/qa/DEMO_READINESS.md](docs/qa/DEMO_READINESS.md)). Merging code does not update it.
- All visitors share one sign-in rate limit behind the demo proxy.
- The Territories tab lists households but has no map.
- An independent database QA set needs its own isolated server.

---

## Quick start: ASHA Saathi AI 2.0 (one command)

You need:

- Docker Desktop, running
- Node.js 20+
- Python 3.9+
- a repository-root `.env` copied from `.env.example`, with `POSTGRES_PASSWORD` and `GNANI_API_KEY` set

```powershell
py run.py              # start what is missing, then stream logs; Ctrl+C leaves Docker running
py run.py --status     # health only, changes nothing
```

Open **https://localhost:5173/v2**.

The launcher never restarts or rebuilds healthy containers and never resets the database. It refuses anything disruptive while the public demo tunnel is running.

Details, logs, troubleshooting and safe shutdown: [docs/LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md). Docker operations: [docs/v2/operations.md](docs/v2/operations.md).

### V2 repository map

| Path | Purpose |
| --- | --- |
| `backend/app/api/v2/` | Auth, territories, households, visits, admin management, admin dashboard, voice WebSocket |
| `backend/app/services/` | Territory-scoped access (`households.py`), voice session (`voice_v2.py`), extraction, prompts |
| `backend/migrations/` | Alembic migrations (head `0005`) |
| `backend/tests/` | Backend tests, including disposable-PostgreSQL integration tests |
| `frontend/src/features/` | Households/map, voice visit, visit history, admin dashboard, UI kit |
| `e2e/` | Playwright browser suites (Phase 4–7, tunnel proxy) |
| `deploy/tunnel/`, `deploy/vercel-redirect/` | Demo proxy and tunnel; permanent demo link |
| `run.py`, `tests/launcher/` | One-command local launcher and its tests |
| `docs/v2/`, `docs/qa/` | Architecture, design, operations; QA reports and demo runbook |

The rest of this section describes the original Round 1 app (SQLite, run by hand).

## Round 1 setup (original app, Windows PowerShell)

Prerequisites: Python 3.11, Node.js 20+, a Gnani API Platform key from
[app.gnani.ai/voice](https://app.gnani.ai/voice).

**1. Configure (once).** At the repository root:

```powershell
Copy-Item .env.example .env
notepad .env        # set GNANI_API_KEY=... (never commit .env)
```

**2. Install (once).**

```powershell
cd backend
python -m venv .venv                      # or: uv venv -p 3.11 .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m pytest -q         # unit tests, no Gnani calls
cd ..\frontend
npm install
```

**3. Run (three windows, each opened at the repository root).**

```powershell
# Window 1: backend (logs go to data\backend.log)
cd backend
cmd /c "set PYTHONUNBUFFERED=1 && .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > ..\data\backend.log 2>&1"

# Window 2: follow the backend log
Get-Content data\backend.log -Wait -Tail 30

# Window 3: frontend (HTTPS on :5173, proxies /api and /ws to the backend)
cd frontend
npm run dev
```

- **Window 1 shows no output.** That's expected: the log goes to the file, and Window 2 shows it.
- **Don't use `2>&1 | Tee-Object` in Windows PowerShell 5.1:** it wraps uvicorn's log lines as errors and
  the server exits.
- **To run without a log file**, use
  `.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` from `backend\` instead.

Check that the backend is up: `Invoke-RestMethod http://127.0.0.1:8000/api/health` should show
`status: ok`, `gnani_configured: True`, `prisma-v3.0`, `timbre-v3.0`.

Optional live check, which spends a few Gnani credits: from `backend\`, run
`.venv\Scripts\python -m scripts.smoke_gnani`.

### Using it on an Android phone

1. Put the phone on the same Wi-Fi as the laptop. If the venue Wi-Fi blocks devices from reaching each
   other, use the phone's hotspot instead.
2. Open the `Network: https://<laptop-IP>:5173` address that `npm run dev` prints, in Chrome.
3. If the page does not load, allow the port on the laptop. In an **administrator** PowerShell, this
   opens it on private networks, local subnet only:
   ```powershell
   New-NetFirewallRule -DisplayName "ASHA Saathi Vite dev (LAN only)" -Direction Inbound -Protocol TCP -LocalPort 5173 -Profile Private -RemoteAddress LocalSubnet -Action Allow
   ```
   Remove it afterwards with `Remove-NetFirewallRule -DisplayName "ASHA Saathi Vite dev (LAN only)"`.
4. The dev server uses a self-signed certificate, so Chrome shows a warning. HTTPS is required for
   microphone access. For a trusted certificate, either:
   - install a local CA with [mkcert](https://github.com/FiloSottile/mkcert) on the phone and point Vite at
     the generated certificate, or
   - use a temporary HTTPS tunnel. This makes the app reachable to anyone with the link while the tunnel
     is up.
5. Tap the mic button, allow the microphone, and listen for the AI disclosure.

The backend listens on `127.0.0.1` only. The phone reaches it through the Vite proxy, never directly.

## Round 1 repository layout

| Path | Purpose |
| --- | --- |
| `backend/app/api/` | REST routes (`/api/health`, `/api/visits`, `/api/followups`) and the `/ws/session` voice gateway |
| `backend/app/services/` | Session state machine, extraction, Kannada number handling, spoken prompts |
| `backend/app/integrations/gnani/` | Prisma v3.0 (STT) and Timbre v3.0 (TTS) adapters |
| `backend/app/safety/` | Danger-sign rules (`rules.json`) and patient scoping |
| `backend/app/db/` | SQLite storage of confirmed visits only |
| `backend/app/schemas/` | Canonical Pydantic contracts |
| `backend/scripts/` | `export_contracts` (schema export), `smoke_gnani` (live API check) |
| `backend/tests/` | Unit and session tests (Gnani mocked) |
| `frontend/src/features/` | Voice session, record card, confirmation, alerts, follow-ups |
| `frontend/public/pcm-worklet.js` | Mic capture: downsampling to 16 kHz 16-bit PCM |
| `frontend/src/types/contracts.ts` | Generated from the backend schema. Do not edit by hand |
| `contracts/` | JSON schema and the browser ↔ backend WebSocket protocol |
| `docs/` | Danger-sign sources |

To regenerate the contracts after changing the schemas: in `backend\`, run
`.venv\Scripts\python -m scripts.export_contracts`; then in `frontend\`, run `npm run gen:types`.

---

## Round 1 verification status (21 Nov 2026)

| Level | What was checked | Result |
| --- | --- | --- |
| Unit and session tests | Extraction, Kannada numbers, danger signs (negation, mother/newborn scoping), correction, version-safe confirmation, barge-in, confirmed-only storage, Timbre WAV fix and retry (Gnani mocked) | 69 passed |
| Live Gnani API | Prisma v3.0 transcription and Timbre v3.0 synthesis (smoke script) | Pass |
| Scripted end-to-end | WebSocket client streaming synthetic Timbre speech through the full flow | Pass |
| Browser end-to-end | Headless Edge, phone viewport, emulated microphone | Pass |
| Physical Android phone | Connectivity, mic, playback; ANC note → read-back → confirm → save → follow-up; newborn fever → alert and PHC referral | Pass |
| Physical phone: spoken correction | Verified in an earlier phone run; not repeated in the latest run | Pass (earlier run) |

## Round 1 known limitations

- **Extraction is rule-based.** Unusual phrasing can be missed; missing required fields are asked for,
  never guessed. No LLM is used.
- **Single STT locale.** The live Prisma API accepts exactly one `language_code`, so we use `kn-IN`.
  English terms still come back in Latin script with `format: codemix`.
- **Response time.** Each reply waits for the full Timbre REST response, typically 2–4 s and slower when
  the service is busy. Timbre's streaming API returned a first chunk in about 0.4 s in a probe, but it is
  not integrated yet.
- **Danger-sign citations.** The source is confirmed, but the section and page numbers for each rule are
  not verified yet. The Kannada keyword lists need native-speaker review. See
  [docs/danger-sign-sources.md](docs/danger-sign-sources.md).
- **Development certificate.** The dev certificate is self-signed and untrusted on phones (see above).
- **Log noise.** A client that disconnects before starting a session leaves a harmless traceback in the
  backend log.
- **Single-user prototype.** No login or multi-worker data separation.

## Safety and data handling

- **Synthetic data only.** Demonstrations use synthetic beneficiaries only; no real patient data.
- **No clinical advice.** No diagnosis, treatment or dosage advice. A danger sign produces only a fixed
  referral instruction.
- **Explicit confirmation.** Nothing is saved without the worker confirming the read-back.
- **No stored speech.** No audio or transcripts are stored. `data/` (the SQLite database and backend log)
  is git-ignored. Delete it after judging.
- **Key stays server-side.** `GNANI_API_KEY` lives only in the backend `.env` and is never logged.

## Hackathon development tools

These tools were used to **build** the project. None of them is a runtime dependency: the running app
uses only the stack listed above and the Gnani APIs.

| Tool | Role |
| --- | --- |
| Claude Code | Primary coding agent: backend, voice pipeline, frontend, tests and documentation |
| Google Antigravity | Used in the team's hackathon workflow. *Specific usage: pending team confirmation.* |
| Qwen AI Studio | Used in the team's hackathon workflow. *Specific usage: pending team confirmation.* |

## Team (NOVIX)

- **Lead + Claude Code:** core engineering (backend, voice pipeline, frontend, integration)
- **Member 2:** research and QA (danger-sign sources, Kannada review, phone testing)
- **Member 3:** pitch and documentation
