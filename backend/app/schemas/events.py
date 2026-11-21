"""Internal browser <-> backend WebSocket contract (NOT the Gnani wire protocol).

Client -> server: binary frames = PCM s16le mono 16 kHz audio; JSON text frames = ClientEvent.
Server -> client: JSON text frames = ServerEvent. Every server event carries `seq`
(monotonic per session) and `turn_id`; clients drop `agent.audio` whose turn_id is
older than the latest `agent.audio.cancel`.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.visit import VisitRecord, VisitType


class _Event(BaseModel):
    # Defaults are always serialized, so the exported schema marks them required.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class SessionState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    PROCESSING = "processing"
    CLARIFYING = "clarifying"
    READING_BACK = "reading_back"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    SAVED = "saved"
    ERROR = "error"


# ---------- client -> server ----------
class SessionStart(_Event):
    type: Literal["session.start"] = "session.start"


class RecordConfirm(_Event):
    """Tap fallback for confirmation; must name the version that was read back."""

    type: Literal["record.confirm"] = "record.confirm"
    record_version: int


class SessionStop(_Event):
    type: Literal["session.stop"] = "session.stop"


# ---------- client -> server, V2 only (/ws/v2/session) ----------
class V2SessionStart(_Event):
    """First frame of a V2 voice visit. IDs come from the explicit Phase 4 selection and are
    re-authorised by the server; visit_type is the worker's explicit choice (may be unknown)."""

    type: Literal["v2.session.start"] = "v2.session.start"
    household_id: str = Field(min_length=1, max_length=64)
    person_id: str = Field(min_length=1, max_length=64)
    client_visit_id: uuid.UUID
    visit_type: VisitType = VisitType.UNKNOWN


class PlaybackCompleted(_Event):
    """The browser finished playing an agent clip. For a read-back it names the version read."""

    type: Literal["playback.completed"] = "playback.completed"
    purpose: Literal["disclosure", "readback"]
    record_version: int | None = None


class ReadbackRequest(_Event):
    """Ask for the read-back of the current version again (e.g. after a TTS failure)."""

    type: Literal["readback.request"] = "readback.request"


class SessionCancel(_Event):
    type: Literal["session.cancel"] = "session.cancel"


ClientEvent = Annotated[SessionStart | RecordConfirm | SessionStop, Field(discriminator="type")]
V2ClientEvent = Annotated[
    V2SessionStart | RecordConfirm | SessionStop | PlaybackCompleted | ReadbackRequest | SessionCancel,
    Field(discriminator="type"),
]


# ---------- server -> client ----------
class _ServerBase(_Event):
    seq: int = 0
    turn_id: int = 0


class SessionStarted(_ServerBase):
    type: Literal["session.started"] = "session.started"
    session_id: str
    stt_model: str | None = None


class StateChanged(_ServerBase):
    type: Literal["state.changed"] = "state.changed"
    state: SessionState


class SpeechStarted(_ServerBase):
    type: Literal["speech.started"] = "speech.started"


class TranscriptFinal(_ServerBase):
    type: Literal["transcript.final"] = "transcript.final"
    text: str
    language: str | None = None


class RecordUpdated(_ServerBase):
    type: Literal["record.updated"] = "record.updated"
    record: VisitRecord
    changed_fields: list[str] = Field(default_factory=list)


class ClarificationRequested(_ServerBase):
    type: Literal["clarification.requested"] = "clarification.requested"
    field: str
    prompt: str


class AlertRaised(_ServerBase):
    type: Literal["alert.raised"] = "alert.raised"
    rule_ids: list[str]
    labels: list[str]
    message: str
    # "this_visit": recorded on the current draft. "other_person" (V2 only): heard about someone
    # other than the bound person; shown and spoken immediately, never written to this record.
    scope: Literal["this_visit", "other_person"] = "this_visit"
    # The 13 existing rules await per-rule clinical source review.
    rule_status: str = "demo_only_pending_clinical_review"


class AgentSpeech(_ServerBase):
    """Agent utterance: text plus base64 WAV from Timbre (audio absent if TTS failed)."""

    type: Literal["agent.audio"] = "agent.audio"
    purpose: Literal["disclosure", "clarification", "readback", "alert", "saved", "info"]
    text: str
    audio_b64: str | None = None
    mime_type: str = "audio/wav"
    # For a read-back: the record_version it reads, so playback can be acknowledged per version.
    record_version: int | None = None


class AgentAudioCancel(_ServerBase):
    type: Literal["agent.audio.cancel"] = "agent.audio.cancel"


class ConfirmationRequested(_ServerBase):
    type: Literal["record.confirmation_requested"] = "record.confirmation_requested"
    record_version: int


class RecordSaved(_ServerBase):
    type: Literal["record.saved"] = "record.saved"
    visit_id: int
    record: VisitRecord


class SessionError(_ServerBase):
    type: Literal["session.error"] = "session.error"
    code: str
    message: str
    retryable: bool = False


class V2SessionBound(_ServerBase):
    """V2: the server-verified, immutable subject of this voice session (display fields only)."""

    type: Literal["v2.session.bound"] = "v2.session.bound"
    household_public_id: str
    person_public_id: str
    person_display_name: str
    visit_type: VisitType
    client_visit_id: uuid.UUID


class V2VisitSaved(_ServerBase):
    """V2: the one confirmed visit for this logical visit key (repeat confirms replay it)."""

    type: Literal["v2.visit.saved"] = "v2.visit.saved"
    visit_id: uuid.UUID
    person_public_id: str
    record_version: int
    confirmed_at: datetime
    idempotent_replay: bool = False


class SessionEnded(_ServerBase):
    """V2: the session stopped without saving (revoked, superseded, expired or cancelled)."""

    type: Literal["session.ended"] = "session.ended"
    reason: Literal["revoked", "superseded", "expired", "idle", "cancelled", "provider_unavailable"]
    message: str


ServerEvent = Annotated[
    SessionStarted | StateChanged | SpeechStarted | TranscriptFinal | RecordUpdated
    | ClarificationRequested | AlertRaised | AgentSpeech | AgentAudioCancel
    | ConfirmationRequested | RecordSaved | SessionError
    | V2SessionBound | V2VisitSaved | SessionEnded,
    Field(discriminator="type"),
]
