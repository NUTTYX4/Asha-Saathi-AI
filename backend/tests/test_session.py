"""Session orchestrator tests with an in-memory DB and a FAKE TTS (mock, isolated test only)."""

import asyncio
from datetime import date

import pytest

from app.db.database import connect
from app.db.repositories import UnconfirmedRecordError, VisitRepository
from app.schemas.visit import RecordStatus, VisitRecord
from app.services.session_service import VoiceSession

TODAY = date(2026, 11, 21)


class Harness:
    def __init__(self, tmp_path):
        self.events: list = []
        self.repo = VisitRepository(connect(tmp_path / "test.db"))

        async def send(event):
            self.events.append(event)

        async def fake_tts(text: str) -> bytes:  # MOCK: no Gnani call in unit tests
            await asyncio.sleep(0)
            return b"RIFF-fake"

        self.session = VoiceSession(send, fake_tts, self.repo, today=lambda: TODAY, respond_delay_s=0)

    async def say(self, text: str):
        await self.session.on_speech_start()
        await self.session.on_transcript(text, "kn-IN")
        await asyncio.sleep(0.05)  # let respond + TTS tasks finish

    def of(self, kind):
        return [e for e in self.events if e.type == kind]


@pytest.fixture
def h(tmp_path):
    return Harness(tmp_path)


async def test_full_flow_correction_and_versioned_confirm(h):
    await h.session.start()
    await asyncio.sleep(0.01)
    assert h.of("agent.audio")[0].purpose == "disclosure"

    await h.say("ಫಲಾನುಭವಿ ಐಡಿ 1 2 3 4. ANC checkup. ತೂಕ 52 ಕಿಲೋ. ಮುಂದಿನ ಭೇಟಿ 28 November.")
    assert h.session.readback_version == h.session.record.record_version
    assert h.of("agent.audio")[-1].purpose == "readback"
    assert h.repo.list_visits() == []  # nothing saved before confirmation

    await h.say("no, weight is 2.8 kilo")
    r = h.session.record
    assert r.weight_kg == 2.8 and r.beneficiary_id == "1234" and r.next_visit_date == date(2026, 11, 28)
    assert h.session.readback_version == r.record_version  # re-read after correction

    await h.say("ಹೌದು")
    saved = h.repo.list_visits()
    assert len(saved) == 1 and saved[0].weight_kg == 2.8
    assert h.of("record.saved")
    assert h.repo.list_followups()[0].due_date == date(2026, 11, 28)


async def test_missing_id_asks_instead_of_guessing(h):
    await h.session.start()
    await h.say("ANC visit, weight 60 kg, next visit 2 December")
    clar = h.of("clarification.requested")
    assert clar and clar[-1].field == "beneficiary_id"
    assert h.session.record.beneficiary_id is None


async def test_stale_confirm_version_rejected(h):
    await h.session.start()
    await h.say("ID 5 6 7 8, newborn visit, next visit 1 December")
    old_version = h.session.readback_version
    await h.say("weight 3.1 kg")  # changes record after read-back
    await h.session.confirm(old_version)
    assert h.repo.list_visits() == []
    assert any(e.code == "CONFIRMATION_REJECTED" for e in h.of("session.error"))


async def test_danger_sign_alerts_immediately_without_confirmation(h):
    await h.session.start()
    await h.session.on_transcript("ಮಗುವಿಗೆ ತುಂಬಾ ಜ್ವರ ಇದೆ", "kn-IN")  # no respond delay needed
    alerts = h.of("alert.raised")
    assert alerts and "NB_FEVER" in alerts[0].rule_ids
    assert h.session.record.requires_phc_referral
    await asyncio.sleep(0.05)
    assert any(e.purpose == "alert" for e in h.of("agent.audio"))


async def test_barge_in_drops_stale_readback(h):
    await h.session.start()
    await h.say("ID 1 1 1 1, ANC, next visit 30 November")
    turn_before = h.session.turn_id
    await h.session.on_speech_start()
    assert h.session.turn_id == turn_before + 1
    assert h.of("agent.audio.cancel")


def test_repository_refuses_unconfirmed(tmp_path):
    repo = VisitRepository(connect(tmp_path / "x.db"))
    with pytest.raises(UnconfirmedRecordError):
        repo.save_confirmed(VisitRecord(beneficiary_id="1", status=RecordStatus.DRAFT))
