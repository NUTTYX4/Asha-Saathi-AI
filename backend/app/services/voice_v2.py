"""Person-bound V2 voice visit (Phase 5).

A `V2VisitSession` is the Round 1 `VoiceSession` (same Gnani adapters, disclosure, extraction,
danger checks, read-back and correction logic) bound to one server-verified subject:

- identity (worker, household, person, territory, logical visit key) is fixed at start from the
  explicit Phase 4 selection *re-authorised by the server*; speech can never change it;
- nothing is heard before the AI disclosure has played; a correction invalidates the earlier
  read-back and its playback acknowledgement;
- only the explicit Confirm-and-Save action of the latest, fully played read-back saves
  (a spoken "ಹೌದು" never does), exactly once, in one PostgreSQL transaction that re-checks
  authorisation under row locks (app/db/visits_v2.py);
- authorisation is re-checked periodically, before read-back and at confirmation; losing it
  ends the session and discards the draft. Nothing is persisted before confirmation.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import date

from pydantic import BaseModel
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.auth.service import AccessDenied, _token_hash, load_principal, user_for_token
from app.db.models import Household
from app.db.visits_v2 import VisitBinding, VisitReceipt, VisitSaveRefused, check_binding, confirm_visit
from app.integrations.extraction_provider import ExtractionProvider
from app.schemas.events import (
    RecordUpdated,
    SessionEnded,
    SessionStarted,
    SessionState,
    V2SessionBound,
    V2SessionStart,
    V2VisitSaved,
)
from app.schemas.visit import VisitRecord, VisitType
from app.services import prompts
from app.services.households import get_household_member
from app.services.session_service import SaveRefused, TtsFn, VoiceSession

log = logging.getLogger(__name__)

ENDING_CODES = frozenset({"AUTH_EXPIRED", "AUTH_REVOKED", "MEMBERSHIP_CHANGED"})

# Danger-sign population for a person-bound V2 visit, from the worker's explicit visit type.
# PNC in V2 is the mother's postnatal visit (a newborn check is its own "newborn" visit for the
# baby's record). Immunisation and unknown stay unresolved: never mapped to newborn automatically.
DANGER_SCOPE: dict[VisitType, VisitType] = {
    VisitType.ANC: VisitType.ANC,            # maternal
    VisitType.PNC: VisitType.ANC,            # maternal
    VisitType.NEWBORN: VisitType.NEWBORN,    # newborn
    VisitType.IMMUNISATION: VisitType.UNKNOWN,
    VisitType.ROUTINE: VisitType.ROUTINE,    # routine/general: no maternal/newborn danger rules
    VisitType.UNKNOWN: VisitType.UNKNOWN,
}


class StartRefused(Exception):
    """The session cannot start. `code`/`message` are safe to show: an unavailable household or
    person is reported the same way whether it is missing or outside the worker's scope."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


NOT_AVAILABLE = StartRefused("NOT_AVAILABLE", "That household member is not available to your account.")


def authorize_start(engine: Engine, token: str | None, start: V2SessionStart,
                    request_id: str | None = None) -> tuple[VisitBinding, str]:
    """Re-authorise the browser's selection. Returns the immutable binding and display name."""
    with Session(engine) as db:
        user = user_for_token(db, token)
        if user is None:
            raise StartRefused("AUTH_EXPIRED", "Your login session has ended. Sign in again.")
        principal = load_principal(db, user)
        if principal.role != "worker":
            raise StartRefused("ROLE_FORBIDDEN", "Only an ASHA worker account can record a visit.")
        try:
            person = get_household_member(db, principal, start.household_id, start.person_id,
                                          request_id=request_id)
        except AccessDenied:
            raise NOT_AVAILABLE from None
        household = db.scalar(select(Household).where(Household.id == person.household_id))
        if household is None or household.territory_id not in principal.territory_ids:
            raise NOT_AVAILABLE
        binding = VisitBinding(
            worker_id=principal.user_id, session_token_hash=_token_hash(token or ""),
            household_id=household.id, person_id=person.id, territory_id=household.territory_id,
            client_visit_id=start.client_visit_id, session_ref=uuid.uuid4().hex[:12],
            household_public_id=household.public_id, person_public_id=person.public_id,
        )
        return binding, person.full_name


class V2VisitSession(VoiceSession):
    def __init__(
        self,
        *,
        send: Callable[[BaseModel], Awaitable[None]],
        tts: TtsFn,
        engine: Engine,
        binding: VisitBinding,
        visit_type: VisitType,
        person_display_name: str,
        stt_model: str | None,
        on_end: Callable[[str], Awaitable[None]] | None = None,
        today: Callable[[], date] = date.today,
        respond_delay_s: float = 0.6,
        extraction_source: str = "deterministic",
        extraction_provider: ExtractionProvider | None = None,
    ) -> None:
        super().__init__(
            send, tts, repo=None, today=today, respond_delay_s=respond_delay_s,  # type: ignore[arg-type]
            stt_model=stt_model, require_playback_ack=True, spoken_confirm_saves=False,
            locked_beneficiary_id=binding.person_public_id, locked_visit_type=visit_type,
            danger_scope=DANGER_SCOPE[visit_type], gate_until_disclosure=True,
            extraction_provider=extraction_provider,
        )
        self.session_id = binding.session_ref
        self.binding = binding
        self.visit_type = visit_type
        self._engine = engine
        self._person_display_name = person_display_name
        self._on_end = on_end
        self._base_extraction_source = extraction_source
        self._extraction_source = extraction_source
        self.saved: VisitReceipt | None = None
        self.ended_reason: str | None = None

    # ---------- lifecycle ----------
    async def start(self) -> None:
        await self.emit(SessionStarted(session_id=self.session_id, stt_model=self._stt_model))
        await self.emit(V2SessionBound(
            household_public_id=self.binding.household_public_id, person_public_id=self.binding.person_public_id,
            person_display_name=self._person_display_name, visit_type=self.visit_type,
            client_visit_id=self.binding.client_visit_id,
        ))
        await self.emit(RecordUpdated(record=self.record))
        if not self._greeting_sent:
            self._greeting_sent = True
            await self.speak(prompts.V2_DISCLOSURE, "disclosure")
        await self.set_state(SessionState.LISTENING)

    @property
    def active(self) -> bool:
        return self.ended_reason is None and self.saved is None

    async def end(self, reason: str, message: str) -> None:
        """Stop without saving: discard the draft and tell the browser why (idempotent)."""
        if self.ended_reason is not None:
            return
        self.ended_reason = reason
        if self._respond_task and not self._respond_task.done():
            self._respond_task.cancel()
        if self.saved is None:
            self._discard_draft()
        await self.emit(SessionEnded(reason=reason, message=message))
        if self._on_end is not None:
            await self._on_end(reason)

    def _on_assist_used(self) -> None:
        self._extraction_source = "deterministic+assist"

    def _discard_draft(self) -> None:
        self.record = VisitRecord()
        self._extraction_source = self._base_extraction_source
        self._pending.clear()
        self.readback_version = None
        self.playback_ack_version = None
        self._readback_synthesized.clear()
        self._full_readback_done = False
        self._speech_pending = False
        self._asked_routine_confirm = False
        self._routine_prompt_shown = False
        self._clarified_once.clear()

    async def revalidate(self) -> bool:
        """Re-check login session, role, assignment and membership; end the session if lost."""
        if self.ended_reason is not None:
            return False
        try:
            await asyncio.to_thread(self._check)
        except VisitSaveRefused as exc:
            await self.end("revoked", exc.message)
            return False
        return True

    def _check(self) -> None:
        with Session(self._engine) as db:
            check_binding(db, self.binding, lock=False)

    # ---------- speech (nothing new once saved or ended) ----------
    async def on_speech_start(self) -> None:
        if self.active:
            await super().on_speech_start()

    async def on_transcript(self, text: str, language: str | None) -> None:
        if self.active:
            await super().on_transcript(text, language)

    async def request_readback(self) -> None:
        """Read the current version again (e.g. the previous read-back audio failed)."""
        async with self._turn_lock:
            if not self._pending and not (self._respond_task and not self._respond_task.done()):
                self._speech_pending = False
            if self.active and self.readback_version is not None and not self.record.compute_missing():
                self._full_readback_done = False
                await self._readback()

    async def _readback(self) -> None:
        if not await self.revalidate():
            return
        await super()._readback()

    # ---------- confirmation and save ----------
    async def confirm(self, record_version: int) -> None:
        if self.ended_reason is not None:
            return
        if self.saved is not None:  # repeated confirmation of the same logical visit: same receipt
            await self._emit_saved(self.saved, replay=True)
            return
        if not await self.revalidate():
            return
        await super().confirm(record_version)

    async def _confirm_locked(self, record_version: int) -> None:
        if self.ended_reason is not None:
            return
        if self.saved is not None:
            await self._emit_saved(self.saved, replay=True)
            return
        await super()._confirm_locked(record_version)

    async def _persist(self, record: VisitRecord) -> VisitReceipt:
        try:
            return await asyncio.to_thread(confirm_visit, self._engine, self.binding, record, self._extraction_source)
        except VisitSaveRefused as exc:
            raise SaveRefused(exc.code, exc.message) from None

    async def _on_save_refused(self, exc: SaveRefused) -> None:
        if exc.code in ENDING_CODES:
            await self.end("revoked", exc.message)

    async def _on_saved(self, receipt: VisitReceipt) -> None:
        self.saved = receipt
        await self._emit_saved(receipt, replay=receipt.idempotent_replay)
        await self.set_state(SessionState.SAVED)
        await self.speak(prompts.V2_SAVED, "saved")

    async def _emit_saved(self, receipt: VisitReceipt, replay: bool) -> None:
        await self.emit(V2VisitSaved(visit_id=receipt.visit_id, person_public_id=receipt.person_public_id,
                                     record_version=receipt.record_version, confirmed_at=receipt.confirmed_at,
                                     idempotent_replay=replay))


class SessionRegistry:
    """Live V2 sessions in this API process (single-process deployment, documented).

    One live session per (worker, logical visit key): a newer connection with the same key
    supersedes the older one, which can then no longer confirm. A worker may hold at most
    `max_per_worker` live sessions."""

    def __init__(self, max_per_worker: int) -> None:
        self._max = max_per_worker
        self._by_key: dict[tuple[uuid.UUID, uuid.UUID], V2VisitSession] = {}

    def claim(self, session: V2VisitSession) -> V2VisitSession | None:
        b = session.binding
        key = (b.worker_id, b.client_visit_id)
        previous = self._by_key.get(key)
        others = [s for k, s in self._by_key.items() if k[0] == b.worker_id and k != key]
        if len(others) >= self._max:
            raise StartRefused("TOO_MANY_SESSIONS", "Close your other open voice visit first.")
        self._by_key[key] = session
        return previous

    def release(self, session: V2VisitSession) -> None:
        key = (session.binding.worker_id, session.binding.client_visit_id)
        if self._by_key.get(key) is session:
            del self._by_key[key]

    def live_count(self) -> int:
        return len(self._by_key)
