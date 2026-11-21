# ASHA SAATHI AI

**Voice-First Digital Field Register for ASHA Healthcare Workers**

- **Team:** NOVIX
- **Event:** Build Bengaluru 2.0 (24-Hour Hackathon)
- **Problem Statement:** Gnani PS1 — Healthcare: Voice Field Register for ASHA Workers
- **Primary Language Focus:** Kannada with English medical terms (code-mixed), expandable to other supported Indic languages

---

## Overview

**ASHA SAATHI AI** is a mobile-first, voice-driven digital field register that enables Accredited Social Health Activist (ASHA) workers to record home visits (ANC, PNC, newborn, and immunisation) through natural speech instead of manual typing.

### Core Voice Workflow

1. **AI Disclosure:** On launch, the assistant discloses that it is an AI helper in the worker's language.
2. **Voice Capture & Streaming STT:** The worker dictates home-visit notes; **Gnani Prisma v3.0** transcribes speech in real time over WebSockets.
3. **Structured Extraction:** The backend extracts required visit fields without inventing unknown data.
4. **Validation & Danger-Sign Escalation:** Deterministic validation checks numerical measurements, and guideline-backed rules flag danger signs with immediate Primary Health Centre (PHC) referral instructions (no diagnosis or treatment advice).
5. **Spoken Read-Back & Correction:** **Gnani Timbre v3.0** reads the extracted record aloud; the worker can interrupt and correct any field by voice.
6. **Explicit Confirmation & Persistence:** Records are saved only after explicit confirmation, updating the saved visit log and follow-up list.

---

## Core Architecture

```text
Mobile Web App (React + TypeScript + Vite + Tailwind)
  -> FastAPI Session Gateway (WebSocket + REST)
  -> Gnani Prisma v3.0 (Streaming Speech-to-Text)
  -> Structured Extraction (LLM) + Deterministic Validation & Danger-Sign Rules
  -> Gnani Timbre v3.0 (Text-to-Speech Read-Back)
  -> Voice Correction & Explicit Confirmation Loop
  -> SQLite Persistence & Follow-Up List
```

> **Security Principle:** The browser never receives or exposes Gnani or LLM API keys. All speech and AI calls are proxied through the FastAPI backend.

---

## Gnani Services Used

- **Gnani Prisma v3.0:** Real-time WebSocket streaming Speech-to-Text (Kannada–English code-mixed support).
- **Gnani Timbre v3.0:** Natural Text-to-Speech for spoken read-back, clarification prompts, and danger-sign alerts.
- Custom orchestration over WebSockets (no telephony, no voice cloning, no hosted end-to-end voice-agent black box).

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| **Frontend** | React, TypeScript, Vite, Tailwind CSS |
| **Backend** | Python 3.11+, FastAPI, Pydantic, SQLite |
| **Voice** | Gnani Prisma v3.0 (STT), Gnani Timbre v3.0 (TTS), WebSockets |
| **Intelligence** | LLM structured extraction (e.g., Gemini Flash) + deterministic validators + rule-based danger-sign engine |

---

## Safety & Responsible AI

- **Synthetic Data Only:** All demonstrations use synthetic beneficiaries — no real patient data or recordings.
- **No Clinical Diagnosis/Treatment:** Never diagnoses conditions, prescribes medications, or recommends dosages.
- **Guideline-Backed Escalation:** Predefined danger signs map strictly to cited public-health guidelines and advise immediate PHC referral.
- **Human-in-the-Loop:** Explicit worker confirmation is required before saving any record.
- **Data Hygiene:** Demonstration transcripts/audio are protected and deleted after judging.

---

## Setup Instructions

*(To be finalized once folder layout and dependencies are scaffolded.)*

1. Copy `.env.example` to `.env` at the repository root and populate your API credentials.
2. Backend setup (Python / FastAPI) — *coming next*.
3. Frontend setup (Vite / React) — *coming next*.

---

## Team Ownership (NOVIX)

- **Agent 1:** Backend infrastructure, database, session gateway & integration
- **Agent 2:** Speech (Gnani Prisma v3.0 / Timbre v3.0) & intelligence services (extraction, validation, danger signs)
- **Agent 3:** Frontend mobile-first UX, end-to-end flow & presentation deliverables
