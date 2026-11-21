# Browser ↔ backend WebSocket protocol (`/ws/session`)

This is the app's internal contract, **not** the Gnani wire protocol. Canonical types:
`backend/app/schemas/events.py` → `contracts/contracts.schema.json` → `frontend/src/types/contracts.ts`.

## Client → server
| Frame | Meaning |
| --- | --- |
| binary | PCM s16le, mono, 16 kHz (the browser sends 1,024-byte frames; the backend re-frames to exactly 1,024 bytes for Prisma) |
| `{"type":"session.start"}` | Must be the first text frame. The server opens Prisma and speaks the AI disclosure. |
| `{"type":"record.confirm","record_version":N}` | Tap fallback for confirmation. Rejected unless `N` equals both the read-back version and the current version. |
| `{"type":"session.stop"}` | End the session. |

## Server → client
Every event has `seq` (monotonic per session) and `turn_id`.

| `type` | Payload | Notes |
| --- | --- | --- |
| `session.started` | `session_id`, `stt_model` | `stt_model` says whether the Prisma v3.0 fields were present in `connected` |
| `state.changed` | `state` | idle, listening, transcribing, processing, clarifying, reading_back, awaiting_confirmation, confirmed, saved, error |
| `speech.started` | | Prisma VAD detected voice |
| `transcript.final` | `text`, `language` | Prisma sends only final segments (no partials) |
| `record.updated` | `record`, `changed_fields` | Any change bumps `record.record_version` and invalidates an earlier read-back |
| `clarification.requested` | `field`, `prompt` | A required field is missing (never guessed) |
| `alert.raised` | `rule_ids`, `labels`, `message` | Danger sign: sent immediately and never waits for confirmation |
| `agent.audio` | `purpose`, `text`, `audio_b64` (WAV) | `audio_b64` is null if TTS failed; the text is still shown |
| `agent.audio.cancel` | | Barge-in: drop agent audio with an older `turn_id` (disclosure and alert audio are never dropped) |
| `record.confirmation_requested` | `record_version` | The version that was just read back |
| `record.saved` | `visit_id`, `record` | Persisted after explicit confirmation |
| `session.error` | `code`, `message`, `retryable` | e.g. `GNANI_NOT_CONFIGURED`, `STT_CONNECT_FAILED`, `TTS_FAILED`, `CONFIRMATION_REJECTED` |

## Confirmation rule
A record is saved only when the worker confirms (the voice word "ಹೌದು"/"yes", or a tap) **and** the
confirmed `record_version` equals the version that was read back. Any later change, including a new
danger sign, requires a fresh read-back.
