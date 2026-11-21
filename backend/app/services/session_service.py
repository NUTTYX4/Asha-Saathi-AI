"""Voice-session orchestrator: state machine, extraction merge, read-back,
confirmation, danger alerts and barge-in. Transport-agnostic: it emits events
through `send` and synthesizes speech through `tts`, so tests can inject fakes.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import date

from pydantic import BaseModel

from app.db.repositories import VisitRepository
from app.safety import danger_signs
from app.schemas.events import (
    AgentAudioCancel,
    AgentSpeech,
    AlertRaised,
    ClarificationRequested,
    ConfirmationRequested,
    RecordSaved,
    RecordUpdated,
    SessionError,
    SessionStarted,
    SessionState,
    SpeechStarted,
    StateChanged,
    TranscriptFinal,
)
from app.schemas.visit import RecordStatus, VisitRecord, VisitType
from app.services import prompts
from app.services.extraction import Extraction, Intent, extract, find_visit_type

log = logging.getLogger(__name__)

# Agent speech a barge-in must not cut off: the AI disclosure (compliance) and
# danger-sign referrals (safety).
NON_INTERRUPTIBLE = frozenset({"disclosure", "alert"})
STILL_TALKING_FALLBACK_S = 3.0
FORM_FIELDS = frozenset({"beneficiary_id", "visit_type", "weight_kg", "vaccinations_due", "next_visit_date"})

SendFn = Callable[[BaseModel], Awaitable[None]]
TtsFn = Callable[[str], Awaitable[bytes]]


class VoiceSession:
    def __init__(
        self,
        send: SendFn,
        tts: TtsFn,
        repo: VisitRepository,
        today: Callable[[], date] = date.today,
        respond_delay_s: float = 0.6,
        stt_model: str | None = None,
    ) -> None:
        self.session_id = uuid.uuid4().hex[:12]
        self._send = send
        self._tts = tts
        self._repo = repo
        self._today = today
        self._respond_delay_s = respond_delay_s
        self._stt_model = stt_model
        self.state = SessionState.IDLE
        self.record = VisitRecord()
        self.seq = 0
        self.turn_id = 0
        self.readback_version: int | None = None
        self._pending: list[str] = []
        self._last_language: str | None = None
        self._asked_field: str | None = None
        self._speaking_purpose: str | None = None
        self._respond_task: asyncio.Task | None = None
        self._tasks: set[asyncio.Task] = set()
        # Prisma VAD: speech_start events seen since the last transcript. Two or more
        # means the worker resumed talking before the previous segment's transcript.
        self._starts_since_transcript = 0
        # Danger flags raised while the patient category was uncertain, grouped by the
        # spoken phrase that triggered them (see danger_signs.evidence_groups).
        self._uncertain_groups: list[set[str]] = []
        self._full_readback_done = False
        self._changed_since_readback: set[str] = set()

    # ---------- plumbing ----------
    async def emit(self, event: BaseModel, turn_id: int | None = None) -> None:
        self.seq += 1
        event.seq = self.seq  # type: ignore[attr-defined]
        event.turn_id = self.turn_id if turn_id is None else turn_id  # type: ignore[attr-defined]
        await self._send(event)

    async def set_state(self, state: SessionState) -> None:
        if state != self.state:
            self.state = state
            await self.emit(StateChanged(state=state))

    def _spawn(self, coro: Awaitable) -> asyncio.Task:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def close(self) -> None:
        for task in list(self._tasks):
            task.cancel()

    async def speak(self, text: str, purpose: str) -> None:
        """Synthesize in the background; drop the audio if a barge-in superseded it."""
        turn = self.turn_id
        self._speaking_purpose = purpose

        async def run() -> None:
            audio_b64: str | None = None
            try:
                audio_b64 = base64.b64encode(await self._tts(text)).decode("ascii")
            except Exception as exc:  # report, keep the text visible
                log.warning("TTS failed: %s", exc)
                await self.emit(SessionError(code="TTS_FAILED", message=str(exc), retryable=True))
            if purpose not in NON_INTERRUPTIBLE and turn != self.turn_id:
                return  # stale: the worker interrupted
            await self.emit(AgentSpeech(purpose=purpose, text=text, audio_b64=audio_b64), turn_id=turn)

        self._spawn(run())

    # ---------- lifecycle ----------
    async def start(self) -> None:
        await self.emit(SessionStarted(session_id=self.session_id, stt_model=self._stt_model))
        await self.emit(RecordUpdated(record=self.record))
        await self.speak(prompts.DISCLOSURE, "disclosure")
        await self.set_state(SessionState.LISTENING)

    async def on_speech_start(self) -> None:
        if self._respond_task and not self._respond_task.done():
            self._respond_task.cancel()  # worker is still talking; wait for the full note
        self._starts_since_transcript += 1
        await self.emit(SpeechStarted())
        if self._speaking_purpose is not None and self._speaking_purpose not in NON_INTERRUPTIBLE:
            self.turn_id += 1  # barge-in: stale agent audio is dropped
            self._speaking_purpose = None
            await self.emit(AgentAudioCancel())
        await self.set_state(SessionState.TRANSCRIBING)

    async def on_transcript(self, text: str, language: str | None) -> None:
        if not text:
            return
        self._last_language = language or self._last_language
        await self.emit(TranscriptFinal(text=text, language=language))
        # Escalation never waits for confirmation. Visit type named in this same
        # utterance counts ("ನವಜಾತ ಶಿಶು ಭೇಟಿ, ಮಗುವಿಗೆ ಜ್ವರ").
        context = find_visit_type(text) or self.record.visit_type
        await self._check_danger(text, context)
        self._pending.append(text)
        still_talking = self._starts_since_transcript >= 2
        self._starts_since_transcript = 1 if still_talking else 0
        if self._respond_task and not self._respond_task.done():
            self._respond_task.cancel()
        # If the worker already resumed speaking, wait for the rest of the note; the
        # long fallback still answers if that speech_start was noise with no transcript.
        delay = STILL_TALKING_FALLBACK_S if still_talking else self._respond_delay_s
        self._respond_task = self._spawn(self._respond_after_delay(delay))

    async def confirm(self, record_version: int) -> None:
        """Explicit confirmation (voice or tap). Version must match what was read back."""
        if (
            self.readback_version is None
            or record_version != self.readback_version
            or record_version != self.record.record_version
        ):
            await self.emit(SessionError(
                code="CONFIRMATION_REJECTED",
                message="Record changed or was not read back yet; reading back again.",
                retryable=True,
            ))
            await self.speak(prompts.RECORD_CHANGED, "info")
            await self._readback()
            return
        self.record.status = RecordStatus.CONFIRMED
        await self.set_state(SessionState.CONFIRMED)
        try:
            visit_id = self._repo.save_confirmed(self.record)
        except Exception as exc:
            self.record.status = RecordStatus.PENDING_CONFIRMATION
            await self.emit(SessionError(code="SAVE_FAILED", message=str(exc)))
            await self.set_state(SessionState.ERROR)
            return
        await self.emit(RecordSaved(visit_id=visit_id, record=self.record))
        await self.set_state(SessionState.SAVED)
        await self.speak(prompts.SAVED, "saved")
        # Fresh record for the next visit.
        self.record = VisitRecord()
        self.readback_version = None
        self._asked_field = None
        self._uncertain_groups = []
        self._full_readback_done = False
        self._changed_since_readback = set()
        await self.emit(RecordUpdated(record=self.record))
        await self.set_state(SessionState.LISTENING)

    # ---------- internals ----------
    async def _respond_after_delay(self, delay_s: float) -> None:
        await asyncio.sleep(delay_s)
        await self._respond()

    async def _respond(self) -> None:
        text = " ".join(self._pending)
        self._pending.clear()
        await self.set_state(SessionState.PROCESSING)
        ext = extract(text, self._today(), expecting_date=self._asked_field == "next_visit_date")

        if ext.intent == Intent.CONFIRM and self.state_is_awaiting():
            await self.confirm(self.readback_version or -1)
            return
        if ext.intent == Intent.REJECT:
            self.readback_version = None
            await self.speak(prompts.ASK_WHAT_TO_CHANGE, "clarification")
            await self.set_state(SessionState.LISTENING)
            return
        if ext.has_fields:
            await self._apply(ext)
        elif self.readback_version is not None:
            await self.speak(prompts.NOT_UNDERSTOOD_CONFIRM, "clarification")
            await self.set_state(SessionState.AWAITING_CONFIRMATION)
            return
        await self._next_step()

    def state_is_awaiting(self) -> bool:
        return self.readback_version is not None

    async def _apply(self, ext: Extraction) -> None:
        r = self.record
        changed: list[str] = []
        if ext.beneficiary_id is not None and ext.beneficiary_id != r.beneficiary_id:
            r.beneficiary_id = ext.beneficiary_id
            changed.append("beneficiary_id")
        if ext.visit_type is not None and ext.visit_type != r.visit_type:
            keeps_specific = (
                ext.visit_type == VisitType.IMMUNISATION
                and r.visit_type != VisitType.UNKNOWN
                and not ext.is_correction
            )
            if not keeps_specific:
                r.visit_type = ext.visit_type
                changed.append("visit_type")
        if ext.weight_kg is not None and ext.weight_kg != r.weight_kg:
            r.weight_kg = ext.weight_kg
            changed.append("weight_kg")
        if ext.vaccinations_due is not None:
            if ext.is_correction or not ext.vaccinations_due or r.vaccinations_due is None:
                merged = list(ext.vaccinations_due)
            else:
                merged = r.vaccinations_due + [v for v in ext.vaccinations_due if v not in r.vaccinations_due]
            if merged != r.vaccinations_due:
                r.vaccinations_due = merged
                changed.append("vaccinations_due")
        if ext.next_visit_date is not None and ext.next_visit_date != r.next_visit_date:
            r.next_visit_date = ext.next_visit_date
            changed.append("next_visit_date")
        if "visit_type" in changed:
            changed += self._rescope_uncertain_flags()
        if changed:
            await self._bump(changed)

    async def _bump(self, changed: list[str]) -> None:
        r = self.record
        r.record_version += 1
        r.status = RecordStatus.DRAFT
        r.language = self._last_language or r.language
        r.missing_fields = r.compute_missing()
        self.readback_version = None  # any change invalidates an earlier read-back
        self._changed_since_readback.update(changed)
        await self.emit(RecordUpdated(record=r, changed_fields=changed))

    async def _check_danger(self, text: str, context: VisitType) -> None:
        assessment = danger_signs.assess(text, context)
        new = [m for m in assessment.matches if m.rule_id not in self.record.danger_signs]
        if not new:
            return
        self.record.danger_signs.extend(m.rule_id for m in new)
        self.record.requires_phc_referral = True
        await self._bump(["danger_signs", "requires_phc_referral"])

        if assessment.context_certain:
            spoken = [m.label["kn-IN"] for m in new]
            shown = [m.label["en-IN"] for m in new]
        else:
            # Patient category unknown: repeat the worker's own words rather than
            # asserting "mother" or "newborn". Both rule sets stay flagged until the
            # visit type is known.
            spoken, shown = [], []
            for group in danger_signs.evidence_groups(new):
                phrase = text[min(m.start for m in group): max(m.end for m in group)]
                populations = {m.population for m in group}
                spoken.append(phrase)
                shown.append(
                    f"{phrase} (mother or newborn not specified)" if len(populations) > 1 else group[0].label["en-IN"]
                )
                if len(populations) > 1:
                    self._uncertain_groups.append({m.rule_id for m in group})
        message = danger_signs.referral_message(spoken, "kn-IN")
        await self.emit(AlertRaised(rule_ids=[m.rule_id for m in new], labels=shown, message=message))
        await self.speak(message, "alert")

    def _rescope_uncertain_flags(self) -> list[str]:
        """Once the visit type is known, drop the wrong-population copy of a flag raised
        under uncertainty, but only if the right-population copy of the same spoken
        evidence remains. A referral is never removed outright."""
        target = danger_signs.POPULATIONS_BY_VISIT[self.record.visit_type]
        if len(target) != 1:
            return []
        removed: set[str] = set()
        remaining_groups: list[set[str]] = []
        for group in self._uncertain_groups:
            keep = {rid for rid in group if danger_signs.rule_population(rid) in target}
            if keep and keep != group:
                removed |= group - keep
            elif not keep:
                remaining_groups.append(group)
        self._uncertain_groups = remaining_groups
        if not removed:
            return []
        self.record.danger_signs = [rid for rid in self.record.danger_signs if rid not in removed]
        self.record.requires_phc_referral = bool(self.record.danger_signs)
        return ["danger_signs"]

    async def _next_step(self) -> None:
        missing = self.record.compute_missing()
        if missing:
            field = missing[0]
            self._asked_field = field
            await self.set_state(SessionState.CLARIFYING)
            await self.emit(ClarificationRequested(field=field, prompt=prompts.ASK_FIELD[field]))
            await self.speak(prompts.ASK_FIELD[field], "clarification")
            await self.set_state(SessionState.LISTENING)
            return
        await self._readback()

    async def _readback(self) -> None:
        self._asked_field = None
        await self.set_state(SessionState.READING_BACK)
        labels = self._danger_labels()
        self.record.status = RecordStatus.PENDING_CONFIRMATION
        self.readback_version = self.record.record_version
        await self.emit(RecordUpdated(record=self.record))
        await self.emit(ConfirmationRequested(record_version=self.readback_version))
        # After one full read-back, a correction re-reads only the changed form fields
        # (the full record stays on screen). Danger-sign changes force a full read-back.
        delta = self._changed_since_readback
        if self._full_readback_done and delta and delta <= FORM_FIELDS:
            text = prompts.readback_changes(self.record, sorted(delta))
        else:
            text = prompts.readback(self.record, labels)
            self._full_readback_done = True
        self._changed_since_readback = set()
        await self.speak(text, "readback")
        await self.set_state(SessionState.AWAITING_CONFIRMATION)

    def _danger_labels(self) -> list[str]:
        rules, _ = danger_signs.load_rules()
        by_id = {r.id: r for r in rules}
        return [by_id[i].label["kn-IN"] for i in self.record.danger_signs if i in by_id]
