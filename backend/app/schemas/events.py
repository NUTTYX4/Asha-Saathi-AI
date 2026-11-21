"""Internal browser <-> backend WebSocket contract (NOT the Gnani wire protocol).

Client -> server: binary frames = PCM s16le mono 16 kHz audio; JSON text frames = ClientEvent.
Server -> client: JSON text frames = ServerEvent. Every server event carries `seq`
(monotonic per session) and `turn_id`; clients drop `agent.audio` whose turn_id is
older than the latest `agent.audio.cancel`.
"""

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.visit import VisitRecord


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


ClientEvent = Annotated[SessionStart | RecordConfirm | SessionStop, Field(discriminator="type")]


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


class AgentSpeech(_ServerBase):
    """Agent utterance: text plus base64 WAV from Timbre (audio absent if TTS failed)."""

    type: Literal["agent.audio"] = "agent.audio"
    purpose: Literal["disclosure", "clarification", "readback", "alert", "saved", "info"]
    text: str
    audio_b64: str | None = None
    mime_type: str = "audio/wav"


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


ServerEvent = Annotated[
    SessionStarted | StateChanged | SpeechStarted | TranscriptFinal | RecordUpdated
    | ClarificationRequested | AlertRaised | AgentSpeech | AgentAudioCancel
    | ConfirmationRequested | RecordSaved | SessionError,
    Field(discriminator="type"),
]
