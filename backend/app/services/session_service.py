"""Voice-session orchestrator: state machine, extraction merge, read-back,
confirmation, danger alerts and barge-in. Transport-agnostic: it emits events
through `send` and synthesizes speech through `tts`, so tests can inject fakes.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
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


class SaveRefused(Exception):
    """A save the server must refuse (e.g. authorisation lost). `code` is safe to show."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class VoiceSession:
    def __init__(
        self,
        send: SendFn,
        tts: TtsFn,
        repo: VisitRepository,
        today: Callable[[], date] = date.today,
        respond_delay_s: float = 0.6,
        stt_model: str | None = None,
        *,
        require_playback_ack: bool = False,
        spoken_confirm_saves: bool = True,
        locked_beneficiary_id: str | None = None,
        locked_visit_type: VisitType | None = None,
        danger_scope: VisitType | None = None,
        gate_until_disclosure: bool = False,
    ) -> None:
        """The keyword options are V2 (Phase 5) behaviour; their defaults are Round 1's.

        require_playback_ack: confirmation also needs the browser to report that the read-back
            of exactly this record_version finished playing.
        spoken_confirm_saves: a spoken "ಹೌದು" saves (Round 1). V2 sets False: only the explicit
            Confirm-and-Save action saves.
        locked_beneficiary_id / locked_visit_type: the server-verified subject and the worker's
            explicit visit type. Speech can never change them; a conflict asks to reselect.
        danger_scope: (V2) the visit type whose population scopes danger signs for the bound
            person: ANC = maternal, NEWBORN = newborn, UNKNOWN = unresolved. A sign for the other
            population is alerted immediately but never written to this person's record.
        gate_until_disclosure: ignore speech until the AI disclosure has finished playing.
        """
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
        self._readback_synthesized: dict[int, tuple[bool, set[str]]] = {}
        self._asked_routine_confirm = False
        self._routine_prompt_shown = False
        self._clarified_once: set[str] = set()
        self._turn_lock = asyncio.Lock()
        self._speech_pending = False
        self._speech_seq = 0
        self._speech_started_at = 0.0
        self._require_playback_ack = require_playback_ack
        self._spoken_confirm_saves = spoken_confirm_saves
        self._locked_beneficiary_id = locked_beneficiary_id
        self._locked_visit_type = locked_visit_type if locked_visit_type not in (None, VisitType.UNKNOWN) else None
        self._danger_scope = danger_scope
        self._disclosure_done = not gate_until_disclosure
        self.playback_ack_version: int | None = None
        if locked_beneficiary_id is not None:
            self.record.beneficiary_id = locked_beneficiary_id
        if self._locked_visit_type is not None:
            self.record.visit_type = self._locked_visit_type
        self.record.missing_fields = self.record.compute_missing()

    @property
    def active(self) -> bool:
        return True

    def _has_pending_speech(self) -> bool:
        if self._pending:
            return True
        if self._respond_task is not None and not self._respond_task.done():
            return True
        return self._speech_pending and (time.monotonic() - self._speech_started_at) < 5.0

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

    async def speak(
        self,
        text: str,
        purpose: str,
        record_version: int | None = None,
        *,
        is_full_readback: bool = False,
        covered_fields: set[str] | None = None,
    ) -> None:
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
            if purpose == "readback" and audio_b64 is not None and record_version is not None:
                if self._require_playback_ack:
                    self._readback_synthesized[record_version] = (is_full_readback, set(covered_fields or ()))
                else:
                    if is_full_readback:
                        self._full_readback_done = True
                    if covered_fields:
                        self._changed_since_readback.difference_update(covered_fields)
            await self.emit(AgentSpeech(purpose=purpose, text=text, audio_b64=audio_b64,
                                        record_version=record_version), turn_id=turn)

        self._spawn(run())

    # ---------- lifecycle ----------
    async def start(self) -> None:
        await self.emit(SessionStarted(session_id=self.session_id, stt_model=self._stt_model))
        await self.emit(RecordUpdated(record=self.record))
        await self.speak(prompts.DISCLOSURE, "disclosure")
        await self.set_state(SessionState.LISTENING)

    def on_playback_completed(self, purpose: str, record_version: int | None) -> None:
        """Browser report that a clip finished playing (V2). A read-back ack counts only for
        the version that is still current, successfully synthesized, and read back."""
        if purpose == "disclosure":
            self._disclosure_done = True
        elif (purpose == "readback" and record_version is not None
              and record_version == self.readback_version == self.record.record_version
              and record_version in self._readback_synthesized):
            self.playback_ack_version = record_version
            is_full, covered = self._readback_synthesized[record_version]
            if is_full:
                self._full_readback_done = True
            self._changed_since_readback.difference_update(covered)

    @property
    def accepting_speech(self) -> bool:
        return self._disclosure_done

    async def on_speech_start(self) -> None:
        if not self._disclosure_done:
            return  # nothing is heard before the AI disclosure has played
        self._speech_seq += 1
        self._speech_pending = True
        self._speech_started_at = time.monotonic()
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
        if not text or not self._disclosure_done:
            return
        self._speech_seq += 1
        self._speech_pending = True
        self._speech_started_at = time.monotonic()
        self._last_language = language or self._last_language
        await self.emit(TranscriptFinal(text=text, language=language))
        # Escalation never waits for confirmation. Visit type named in this same
        # utterance counts ("ನವಜಾತ ಶಿಶು ಭೇಟಿ, ಮಗುವಿಗೆ ಜ್ವರ").
        context = self._danger_scope or self._locked_visit_type or find_visit_type(text) or self.record.visit_type
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
        """Explicit confirmation (voice or tap). Blocks if speech/extraction is in flight."""
        if self._has_pending_speech():
            await self.emit(SessionError(
                code="CONFIRMATION_REJECTED",
                message="Processing your spoken update; wait for the new read-back before saving.",
                retryable=True,
            ))
            return
        async with self._turn_lock:
            if self._has_pending_speech():
                await self.emit(SessionError(
                    code="CONFIRMATION_REJECTED",
                    message="Processing your spoken update; wait for the new read-back before saving.",
                    retryable=True,
                ))
                return
            await self._confirm_locked(record_version)

    async def _confirm_locked(self, record_version: int) -> None:
        """Version-checked persistence under `_turn_lock`."""
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
        if self._require_playback_ack and self.playback_ack_version != record_version:
            await self.emit(SessionError(
                code="READBACK_NOT_FINISHED",
                message="The read-back of this version has not finished playing yet.",
                retryable=True,
            ))
            return
        self.record.status = RecordStatus.CONFIRMED
        await self.set_state(SessionState.CONFIRMED)
        try:
            receipt = await self._persist(self.record)
        except SaveRefused as exc:
            self.record.status = RecordStatus.PENDING_CONFIRMATION
            await self.emit(SessionError(code=exc.code, message=exc.message))
            await self.set_state(SessionState.ERROR)
            await self._on_save_refused(exc)
            return
        except Exception as exc:
            self.record.status = RecordStatus.PENDING_CONFIRMATION
            await self.emit(SessionError(code="SAVE_FAILED", message=str(exc)))
            await self.set_state(SessionState.ERROR)
            return
        await self._on_saved(receipt)

    # ---------- persistence hooks (V2 overrides) ----------
    async def _persist(self, record: VisitRecord):
        """Save the confirmed record; returns a receipt. Round 1: the SQLite/PostgreSQL visits table."""
        return self._repo.save_confirmed(record)

    async def _on_save_refused(self, exc: SaveRefused) -> None:
        """Called after a refused save has been reported (V2 ends the session)."""

    async def _on_saved(self, visit_id) -> None:
        await self.emit(RecordSaved(visit_id=visit_id, record=self.record))
        await self.set_state(SessionState.SAVED)
        await self.speak(prompts.SAVED, "saved")
        # Fresh record for the next visit.
        self.record = VisitRecord()
        self.readback_version = None
        self.playback_ack_version = None
        self._asked_field = None
        self._uncertain_groups = []
        self._full_readback_done = False
        self._changed_since_readback = set()
        self._readback_synthesized.clear()
        self._speech_pending = False
        self._asked_routine_confirm = False
        self._routine_prompt_shown = False
        self._clarified_once.clear()
        await self.emit(RecordUpdated(record=self.record))
        await self.set_state(SessionState.LISTENING)

    # ---------- internals ----------
    async def _respond_after_delay(self, delay_s: float) -> None:
        await asyncio.sleep(delay_s)
        await self._respond()

    async def _respond(self) -> None:
        async with self._turn_lock:
            if not self.active or not self._pending:
                if not self._pending:
                    self._speech_pending = False
                return
            seq = self._speech_seq
            text = " ".join(self._pending)
            self._pending.clear()
            try:
                await self.set_state(SessionState.PROCESSING)
                ext = extract(
                    text,
                    self._today(),
                    expecting_date=self._asked_field == "next_visit_date",
                    expecting_visit_type=self._asked_field == "visit_type",
                )

                if ext.intent == Intent.GREETING:
                    await self.set_state(
                        SessionState.AWAITING_CONFIRMATION if self.state_is_awaiting() else SessionState.LISTENING
                    )
                    return

                if ext.has_fields:
                    if not await self._apply(ext, text):
                        await self.set_state(SessionState.LISTENING)  # waiting for the worker (V2 subject check)
                        return
                    self._asked_routine_confirm = False
                    self._routine_prompt_shown = False
                    self._clarified_once.clear()
                    await self._next_step()
                    return

                if self._asked_routine_confirm and self.record.visit_type == VisitType.UNKNOWN:
                    self._asked_routine_confirm = False
                    if ext.intent == Intent.CONFIRM:
                        self.record.visit_type = VisitType.ROUTINE
                        await self._bump(["visit_type"])
                        await self._next_step()
                        return
                    await self.set_state(SessionState.LISTENING)
                    return

                if (
                    self._asked_field == "visit_type"
                    and self.record.visit_type == VisitType.UNKNOWN
                    and not self.state_is_awaiting()
                    and (ext.intent in (Intent.REJECT, Intent.NO_CHANGE) or ext.is_negative_answer)
                ):
                    if not self._routine_prompt_shown:
                        self._routine_prompt_shown = True
                        self._asked_routine_confirm = True
                        await self.set_state(SessionState.CLARIFYING)
                        await self.emit(ClarificationRequested(field="visit_type", prompt=prompts.ASK_ROUTINE_VISIT))
                        await self.speak(prompts.ASK_ROUTINE_VISIT, "clarification")
                    await self.set_state(SessionState.LISTENING)
                    return

                if ext.intent == Intent.NO_CHANGE:
                    await self.set_state(
                        SessionState.AWAITING_CONFIRMATION if self.state_is_awaiting() else SessionState.LISTENING
                    )
                    return

                if ext.intent == Intent.CONFIRM and self.state_is_awaiting():
                    if self._spoken_confirm_saves:
                        await self._confirm_locked(self.readback_version or -1)
                    else:
                        # V2: saving needs the explicit Confirm-and-Save action, never speech alone.
                        await self.speak(prompts.PRESS_TO_SAVE, "info")
                        await self.set_state(SessionState.AWAITING_CONFIRMATION)
                    return

                if ext.intent == Intent.REJECT:
                    if self.state_is_awaiting():
                        if ext.wants_correction or self._spoken_confirm_saves:
                            self.readback_version = None
                            self.playback_ack_version = None
                            await self.speak(prompts.ASK_WHAT_TO_CHANGE, "clarification")
                            await self.set_state(SessionState.LISTENING)
                        else:
                            await self.set_state(SessionState.AWAITING_CONFIRMATION)
                    else:
                        await self.set_state(SessionState.LISTENING)
                    return

                if self.readback_version is not None:
                    await self.speak(prompts.NOT_UNDERSTOOD_CONFIRM, "clarification")
                    await self.set_state(SessionState.AWAITING_CONFIRMATION)
                    return

                await self._next_step()
            finally:
                if self._speech_seq == seq and not self._pending:
                    self._speech_pending = False

    def state_is_awaiting(self) -> bool:
        return self.readback_version is not None

    def _subject_conflict(self, ext: Extraction, text: str = "") -> bool:
        """V2: speech naming another beneficiary, a different visit type, or another person/ambiguous subject."""
        if (self._locked_beneficiary_id is not None and ext.beneficiary_id is not None
                and ext.beneficiary_id != self._locked_beneficiary_id):
            return True
        if self._danger_scope is not None and text:
            target = danger_signs.POPULATIONS_BY_VISIT[self._danger_scope]
            named = danger_signs.named_subjects(text, frozenset({"maternal", "newborn"}))
            if len(named) > 1 or (len(target) == 1 and bool(named - target)):
                return True
        if self._locked_visit_type is None or ext.visit_type is None or ext.visit_type == self._locked_visit_type:
            return False
        # "immunisation" mentioned during a specific visit is not a different subject (Round 1 rule).
        return not (ext.visit_type == VisitType.IMMUNISATION and not ext.is_correction)

    async def _apply(self, ext: Extraction, text: str = "") -> bool:
        """Merge extracted fields. False if nothing may be applied (V2 subject conflict)."""
        if self._subject_conflict(ext, text):
            # Never move the record to someone else: nothing from this utterance is applied.
            await self.emit(ClarificationRequested(field="subject", prompt=prompts.SUBJECT_MISMATCH))
            await self.speak(prompts.SUBJECT_MISMATCH, "clarification")
            return False
        if self._locked_visit_type is not None:
            ext.visit_type = None  # the explicit visit type stays as chosen
        if self._locked_beneficiary_id is not None:
            ext.beneficiary_id = None
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
        return True

    async def _bump(self, changed: list[str]) -> None:
        r = self.record
        r.record_version += 1
        r.status = RecordStatus.DRAFT
        r.language = self._last_language or r.language
        r.missing_fields = r.compute_missing()
        self.readback_version = None  # any change invalidates an earlier read-back
        self.playback_ack_version = None  # ...and any acknowledgement of its playback
        self._readback_synthesized.clear()
        self._asked_routine_confirm = False
        self._routine_prompt_shown = False
        self._clarified_once.clear()
        self._changed_since_readback.update(changed)
        await self.emit(RecordUpdated(record=r, changed_fields=changed))

    async def _check_danger(self, text: str, context: VisitType) -> None:
        if self._danger_scope is not None and len(danger_signs.POPULATIONS_BY_VISIT[self._danger_scope]) == 1:
            await self._check_danger_bound(text)
            return
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

    async def _check_danger_bound(self, text: str) -> None:
        """V2 with an explicit single-population visit type: only findings attributed to the bound
        person (or unnamed findings matching their population) enter `this_visit`; findings naming
        another person or ambiguous multi-person statements are surfaced as `other_person` alerts
        immediately without contaminating this record."""
        target = danger_signs.POPULATIONS_BY_VISIT[self._danger_scope]
        named = danger_signs.named_subjects(text, frozenset({"maternal", "newborn"}))
        assessment = danger_signs.assess(text, VisitType.UNKNOWN)
        own_matches: list[danger_signs.DangerMatch] = []
        other_matches: list[danger_signs.DangerMatch] = []
        for group in danger_signs.evidence_groups(assessment.matches):
            in_target = [m for m in group if m.population in target]
            out_target = [m for m in group if m.population not in target]
            if len(named) > 1:
                other_matches.extend(group)
            elif named and not (named <= target):
                other_matches.extend(out_target or group)
            elif in_target:
                own_matches.extend(in_target)
            else:
                other_matches.extend(out_target)

        if other_matches:
            msg = danger_signs.referral_message([m.label["kn-IN"] for m in other_matches], "kn-IN")
            await self.emit(AlertRaised(
                rule_ids=[m.rule_id for m in other_matches],
                labels=[f"{m.label['en-IN']} (not the selected person: record separately)" for m in other_matches],
                message=msg,
                scope="other_person",
            ))
            await self.speak(msg, "alert")

        new = [m for m in own_matches if m.rule_id not in self.record.danger_signs]
        if not new:
            return
        self.record.danger_signs.extend(m.rule_id for m in new)
        self.record.requires_phc_referral = True
        await self._bump(["danger_signs", "requires_phc_referral"])
        message = danger_signs.referral_message([m.label["kn-IN"] for m in new], "kn-IN")
        await self.emit(AlertRaised(
            rule_ids=[m.rule_id for m in new],
            labels=[m.label["en-IN"] for m in new],
            message=message,
        ))
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
            if field in self._clarified_once:
                await self.set_state(SessionState.LISTENING)
                return
            self._clarified_once.add(field)
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
        # After one completed full read-back, a correction re-reads only the changed form
        # fields (the full record stays on screen). Until a full read-back succeeds (or when
        # danger signs change), synthesize the complete record.
        delta = set(self._changed_since_readback)
        is_full = not (self._full_readback_done and delta and delta <= FORM_FIELDS)
        if is_full:
            text = prompts.readback(self.record, labels)
        else:
            text = prompts.readback_changes(self.record, sorted(delta))
        await self.speak(
            text,
            "readback",
            record_version=self.readback_version,
            is_full_readback=is_full,
            covered_fields=delta,
        )
        await self.set_state(SessionState.AWAITING_CONFIRMATION)

    def _danger_labels(self) -> list[str]:
        rules, _ = danger_signs.load_rules()
        by_id = {r.id: r for r in rules}
        return [by_id[i].label["kn-IN"] for i in self.record.danger_signs if i in by_id]
