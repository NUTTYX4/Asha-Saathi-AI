"""Phase 5 service-level regressions. Speech, authorization I/O and storage are isolated."""

import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.db.visits_v2 import VisitBinding, VisitReceipt
from app.schemas.visit import VisitType
from app.services import prompts
from app.services.voice_v2 import SessionRegistry, V2VisitSession


NOTE = "weight 52 kg. next visit 28 November."


class Visit:
    def __init__(self, binding, visit_type, monkeypatch):
        self.events = []
        self.writes = []
        self.tts = AsyncMock(return_value=b"mock clip")

        async def send(event):
            self.events.append(event.model_copy(deep=True))

        async def save(record):
            self.writes.append(record.model_copy(deep=True))
            return VisitReceipt(uuid4(), binding.person_public_id, record.record_version,
                                datetime.now(UTC), False)

        self.session = V2VisitSession(
            send=send, tts=self.tts, engine=None, binding=binding, visit_type=visit_type,
            person_display_name="Synthetic member", stt_model="mock",
            today=lambda: date(2026, 11, 22), respond_delay_s=0,
        )
        monkeypatch.setattr(self.session, "_check", Mock(return_value=None))
        monkeypatch.setattr(self.session, "_persist", save)

    async def settle(self):
        # The response task can itself schedule audio. Drain both without timing guesses.
        while tasks := [task for task in self.session._tasks if not task.done()]:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=3)

    async def say(self, text):
        await self.session.on_speech_start()
        await self.session.on_transcript(text, "en-IN")
        await self.settle()

    def clips(self, purpose):
        return [e for e in self.events if e.type == "agent.audio" and e.purpose == purpose]

    def acknowledge(self, clip):
        assert clip.audio_b64, "Only successfully synthesized audio can be played"
        self.session.on_playback_completed(clip.purpose, clip.record_version)


@pytest.fixture
async def open_visit(monkeypatch):
    visits = []

    async def create(visit_type=VisitType.PNC, binding=None):
        if binding is None:
            binding = VisitBinding(
                worker_id=uuid4(), session_token_hash="synthetic", household_id=uuid4(),
                person_id=uuid4(), territory_id=uuid4(), client_visit_id=uuid4(),
                session_ref="qa-only", household_public_id="H-003",
                person_public_id="P-011" if visit_type == VisitType.PNC else "P-012",
            )
        visit = Visit(binding, visit_type, monkeypatch)
        visits.append(visit)
        await visit.session.start()
        await visit.settle()
        visit.acknowledge(visit.clips("disclosure")[-1])
        return visit

    yield create
    for visit in visits:
        await visit.session.close()


@pytest.mark.parametrize(("visit_type", "note"), [
    (VisitType.PNC, "The baby's weight is 3 kg."),
    (VisitType.NEWBORN, "The mother's weight is 52 kg."),
])
async def test_other_person_weight_stays_off_selected_record(open_visit, visit_type, note):
    visit = await open_visit(visit_type)
    await visit.say(note)
    assert visit.session.record.weight_kg is None


@pytest.mark.parametrize(("visit_type", "note", "other_rule"), [
    (VisitType.PNC, "The baby had a seizure.", "NB_CONVULSIONS"),
    (VisitType.NEWBORN, "The mother had a seizure.", "MAT_CONVULSIONS"),
])
async def test_shared_danger_keyword_follows_explicit_subject(open_visit, visit_type, note, other_rule):
    visit = await open_visit(visit_type)
    await visit.say(note)
    alerts = [e for e in visit.events if e.type == "alert.raised"]
    assert not visit.session.record.danger_signs
    assert any(a.scope == "other_person" and other_rule in a.rule_ids for a in alerts)
    assert all(a.scope != "this_visit" for a in alerts)


async def test_received_correction_prevents_old_save_during_debounce(open_visit, monkeypatch):
    visit = await open_visit()
    await visit.say(NOTE)
    old = visit.clips("readback")[-1]
    visit.acknowledge(old)

    # Hold only the normal transcript debounce. The worker clicks after the corrected
    # transcript arrives but before extraction issues its next record.updated event.
    resume = asyncio.Event()
    original = visit.session._respond_after_delay

    async def wait_for_worker_click(delay):
        await resume.wait()
        await original(delay)

    monkeypatch.setattr(visit.session, "_respond_after_delay", wait_for_worker_click)
    await visit.session.on_speech_start()
    await visit.session.on_transcript("No, weight is 55 kg.", "en-IN")
    try:
        await visit.session.confirm(old.record_version)
        assert [r.weight_kg for r in visit.writes] == []
    finally:
        resume.set()
        await visit.settle()
    corrected = visit.clips("readback")[-1]
    assert corrected.record_version > old.record_version
    visit.acknowledge(corrected)
    await visit.session.confirm(corrected.record_version)
    assert [r.weight_kg for r in visit.writes] == [55]


async def test_correction_after_first_readback_tts_failure_reads_complete_record(open_visit):
    visit = await open_visit()
    visit.tts.side_effect = RuntimeError("offline synthetic TTS")
    await visit.say(NOTE)
    assert any(e.type == "session.error" and e.code == "TTS_FAILED" for e in visit.events)
    assert not any(c.audio_b64 for c in visit.clips("readback"))

    visit.tts.side_effect = None
    await visit.say("No, weight is 55 kg.")
    recovered = visit.clips("readback")[-1]
    assert recovered.audio_b64
    # The original identity and date have never played. A delta-only clip omits them.
    assert recovered.text == prompts.readback(visit.session.record, [])


async def test_failed_readback_blocks_save_until_successful_replay(open_visit):
    visit = await open_visit()
    visit.tts.side_effect = RuntimeError("offline synthetic TTS")
    await visit.say(NOTE)
    assert any(e.type == "session.error" and e.code == "TTS_FAILED" for e in visit.events)
    version = visit.session.record.record_version
    await visit.session.confirm(version)
    assert visit.writes == []

    visit.tts.side_effect = None
    await visit.session.request_readback()
    await visit.settle()
    visit.acknowledge(visit.clips("readback")[-1])
    await visit.session.confirm(version)
    assert [r.weight_kg for r in visit.writes] == [52]


async def test_replacement_session_requires_new_note_and_confirmation(open_visit):
    registry = SessionRegistry(max_per_worker=1)
    first = await open_visit()
    registry.claim(first.session)
    await first.say(NOTE)
    old = first.clips("readback")[-1]
    first.acknowledge(old)
    fresh = await open_visit(binding=replace(first.session.binding, session_ref="qa-reconnect"))
    previous = registry.claim(fresh.session)
    assert previous is first.session
    await previous.end("superseded", "Another tab opened this visit")
    registry.release(previous)
    assert registry.live_count() == 1
    await previous.confirm(old.record_version)
    assert first.writes == [] and fresh.writes == []
    assert fresh.session.record.weight_kg is None
    assert fresh.session.playback_ack_version is None
    await fresh.say(NOTE)
    new = fresh.clips("readback")[-1]
    await fresh.session.confirm(new.record_version)
    assert fresh.writes == []
    fresh.acknowledge(new)
    await fresh.session.confirm(new.record_version)
    assert len(fresh.writes) == 1
