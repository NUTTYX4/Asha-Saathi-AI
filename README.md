# ASHA SAATHI AI

**Voice-first digital field register for ASHA workers**

- **Team:** NOVIX
- **Event:** Build Bengaluru 2.0 (24-hour hackathon)
- **Problem statement:** Gnani PS1. Healthcare: voice field register for ASHA workers
- **Language:** Kannada with English medical terms (code-mixed)

> Hackathon prototype. Synthetic data only. Not a medical device. It does not diagnose, treat or
> recommend doses.

---

## What it does

An ASHA worker records a home visit (ANC, PNC, newborn or immunisation) by speaking instead of typing.

1. **AI disclosure.** The assistant says it is an AI helper. This prompt cannot be interrupted.
2. **Speech to text.** The browser streams microphone audio to the backend, which forwards it to
   **Gnani Prisma v3.0** (realtime WebSocket STT).
3. **Field extraction.** Deterministic Kannada–English rules extract the beneficiary ID, visit type,
   weight, vaccinations due and next visit date. Anything not said stays empty: values are never guessed.
4. **Danger signs.** Fixed rules from a cited WHO guideline raise an immediate "refer to PHC now" alert.
   Rules are scoped to the patient (mother or newborn). If it is unclear who the sign belongs to, the
   alert repeats the worker's own words instead of naming a patient.
5. **Spoken read-back.** **Gnani Timbre v3.0** reads back the captured fields. After a correction, only
   the changed field is re-read.
6. **Correction and confirmation.** The worker corrects by voice ("ಇಲ್ಲ, ತೂಕ ಅರವತ್ತೆರಡು ಕಿಲೋ"). The record is
   saved only after an explicit "ಹೌದು" (yes) that matches the version just read back.
7. **Follow-up list.** Saved visits appear in a follow-up list, with referrals listed first.

## Architecture

```text
Phone browser (React + TypeScript + Vite + Tailwind, HTTPS)
  │  mic PCM 16 kHz ─►  /ws/session  ◄─ events + agent audio (WAV)
  ▼
FastAPI backend (127.0.0.1:8000, reached only through the Vite HTTPS proxy)
  ├─ Gnani Prisma v3.0  (wss, realtime STT)
  ├─ Deterministic extraction + danger-sign rules (rules.json, cited)
  ├─ Gnani Timbre v3.0  (REST TTS)
  └─ SQLite: confirmed visits only
```

- The Gnani API key stays on the backend. The browser never receives it.
- Neither audio nor transcripts are stored. The database holds confirmed structured fields only.

## Gnani services used

| Service | Configuration | Used for |
| --- | --- | --- |
| [Prisma v3.0 realtime STT](https://docs.gnani.ai/api/STT/stt-websocket) | `wss://api.vachana.ai/stt/v3/stream`, `model: prisma-v3.0`, `language_code: kn-IN`, `format: codemix`, 16 kHz PCM, 1,024-byte frames | Transcribing the worker's speech, with server-side end-of-speech detection |
| [Timbre v3.0 TTS](https://docs.gnani.ai/api/TTS/tts-inference) | `POST https://api.vachana.ai/api/v1/tts/inference`, `model: timbre-v3.0`, voice `Shruthi`, `language: kn-IN`, 24 kHz WAV | Disclosure, questions, read-back, danger-sign referral prompts |

No telephony, no voice cloning and no hosted voice-agent product: the orchestration is our own code.

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | React 18, TypeScript, Vite 6 (HTTPS dev server), Tailwind CSS 4, AudioWorklet mic capture |
| Backend | Python 3.11, FastAPI, Pydantic v2, websockets, httpx, SQLite |
| Voice | Gnani Prisma v3.0 (STT), Gnani Timbre v3.0 (TTS) |
| Logic | Deterministic extraction, Kannada number parsing and rule-based danger signs (no LLM) |

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

The rest of this section describes the original Round 1 app (SQLite, run by hand).

## Setup (Windows PowerShell)

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

## Repository layout

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

## Verification status (21 Nov 2026)

| Level | What was checked | Result |
| --- | --- | --- |
| Unit and session tests | Extraction, Kannada numbers, danger signs (negation, mother/newborn scoping), correction, version-safe confirmation, barge-in, confirmed-only storage, Timbre WAV fix and retry (Gnani mocked) | 69 passed |
| Live Gnani API | Prisma v3.0 transcription and Timbre v3.0 synthesis (smoke script) | Pass |
| Scripted end-to-end | WebSocket client streaming synthetic Timbre speech through the full flow | Pass |
| Browser end-to-end | Headless Edge, phone viewport, emulated microphone | Pass |
| Physical Android phone | Connectivity, mic, playback; ANC note → read-back → confirm → save → follow-up; newborn fever → alert and PHC referral | Pass |
| Physical phone: spoken correction | Verified in an earlier phone run; not repeated in the latest run | Pass (earlier run) |

## Known limitations

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
