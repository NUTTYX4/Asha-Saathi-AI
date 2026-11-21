# ASHA SAATHI AI — notes for Claude Code

Voice-first field register for ASHA workers (Gnani PS1). Hackathon prototype; synthetic data only.

## Stable decisions
- Monorepo: `backend/` (FastAPI, Python 3.11, SQLite), `frontend/` (React + TS + Vite + Tailwind v4),
  `contracts/`, `docs/`. See README for layout and setup.
- STT is Gnani Prisma v3.0 and TTS is Gnani Timbre v3.0, both via the backend only. Never expose
  `GNANI_API_KEY` to the browser, logs, or chat.
- Pydantic schemas in `backend/app/schemas/` are canonical. After changing them, run
  `python -m scripts.export_contracts` (in backend/) and then `npm run gen:types` (in frontend/).
  Never hand-edit `frontend/src/types/contracts.ts`.
- Extraction is deterministic (`services/extraction.py`). Null means unknown; never guess values.
- Saving requires explicit confirmation of the read-back `record_version`.
- Danger signs come only from `safety/rules.json`, with a cited source. Never add diagnosis, treatment,
  or dosage text.
- Do not store raw audio or transcripts.

## Commands
- Backend tests: `cd backend && .venv\Scripts\python -m pytest -q`
- Live Gnani smoke test (spends credits): `.venv\Scripts\python -m scripts.smoke_gnani`
- Frontend check: `cd frontend && npm run typecheck && npm run build`
- The user runs the dev servers in their own terminals (see README "Run"). Backend log: `data/backend.log`.
  In Windows PowerShell 5.1, never pipe uvicorn through `2>&1 | Tee-Object`: the server exits. Use the
  `cmd /c "... > ..\data\backend.log 2>&1"` form instead.

## V2 (branch `v2/backend-foundation`)
- Brief: `ASHA_SAATHI_AI_V2_ENGINEERING_MASTER_PLAN.md` §15. Progress and evidence: `docs/v2/PROGRESS.md`.
- The backend runs in Docker (`docker compose up --build -d`); runbook in `docs/v2/operations.md`.
- Container tests (PostgreSQL included): `docker compose exec api python -m pytest -q`.
- PostgreSQL schema changes go only through Alembic (`backend/migrations/versions`). Never
  `docker compose down -v`. The Round 1 SQLite file `data/asha_saathi.db` must stay untouched.

## Rules
- Do not push to GitHub. A guardrail hook blocks dangerous git commands.
- Report features as mocked, real-API-tested, or end-to-end verified, with evidence.
