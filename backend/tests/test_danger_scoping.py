"""Danger-sign population scoping (fix for: newborn fever note raised a maternal rule)."""

import asyncio
from datetime import date

import pytest

from app.db.database import connect
from app.db.repositories import VisitRepository
from app.safety.danger_signs import assess
from app.schemas.visit import VisitType
from app.services.session_service import VoiceSession


def ids(text, visit):
    return sorted(m.rule_id for m in assess(text, visit).matches)


@pytest.mark.parametrize(
    ("text", "visit", "expected", "certain"),
    [
        # ANC: maternal rules only
        ("ಗರ್ಭಿಣಿಗೆ ತುಂಬಾ ಜ್ವರ ಇದೆ", VisitType.ANC, ["MAT_HIGH_FEVER"], True),
        # Newborn: newborn rules only
        ("ಮಗುವಿಗೆ ತುಂಬಾ ಜ್ವರ ಇದೆ", VisitType.NEWBORN, ["NB_FEVER"], True),
        # PNC covers both; the named subject decides
        ("ಮಗುವಿಗೆ ತುಂಬಾ ಜ್ವರ ಇದೆ", VisitType.PNC, ["NB_FEVER"], True),
        ("ತಾಯಿಗೆ ತುಂಬಾ ಜ್ವರ ಇದೆ", VisitType.PNC, ["MAT_HIGH_FEVER"], True),
        # PNC without a named subject: conservative, both, marked uncertain
        ("ತುಂಬಾ ಜ್ವರ ಇದೆ", VisitType.PNC, ["MAT_HIGH_FEVER", "NB_FEVER"], False),
        # Unknown visit but the baby is named
        ("baby has high fever", VisitType.UNKNOWN, ["NB_FEVER"], True),
        # Unknown visit, nobody named: conservative, both, uncertain
        ("high fever since yesterday", VisitType.UNKNOWN, ["MAT_HIGH_FEVER", "NB_FEVER"], False),
        # Both named ("baby's mother"): ambiguous, keep both
        ("ಮಗುವಿನ ತಾಯಿಗೆ ತುಂಬಾ ಜ್ವರ", VisitType.PNC, ["MAT_HIGH_FEVER", "NB_FEVER"], False),
    ],
)
def test_scoping(text, visit, expected, certain):
    result = assess(text, visit)
    assert sorted(m.rule_id for m in result.matches) == expected
    assert result.context_certain is certain


@pytest.mark.parametrize(
    ("text", "visit"),
    [
        ("ಮಗುವಿಗೆ ಜ್ವರ ಇಲ್ಲ", VisitType.NEWBORN),
        ("no fever", VisitType.PNC),
        ("ರಕ್ತಸ್ರಾವ ಇಲ್ಲ", VisitType.ANC),
        ("no bleeding, no fever", VisitType.UNKNOWN),
    ],
)
def test_negation_across_contexts(text, visit):
    assert ids(text, visit) == []


def test_maternal_sign_not_checked_for_newborn_visit():
    assert ids("bleeding", VisitType.NEWBORN) == []


def test_named_baby_never_hides_a_maternal_only_sign():
    """Regression: an earlier version dropped bleeding when 'baby' was named."""
    result = assess("bleeding and baby fever", VisitType.UNKNOWN)
    assert sorted(m.rule_id for m in result.matches) == ["MAT_VAGINAL_BLEEDING", "NB_FEVER"]
    assert result.context_certain is False


# ---------- session-level behaviour (FAKE TTS: isolated test, no Gnani call) ----------
class _H:
    def __init__(self, tmp_path):
        self.events = []

        async def send(e):
            self.events.append(e)

        async def fake_tts(_text):
            return b"RIFF"

        self.s = VoiceSession(send, fake_tts, VisitRepository(connect(tmp_path / "t.db")),
                              today=lambda: date(2026, 11, 21), respond_delay_s=0)

    async def say(self, text):
        await self.s.on_speech_start()
        await self.s.on_transcript(text, "kn-IN")
        await asyncio.sleep(0.05)

    def alerts(self):
        return [e for e in self.events if e.type == "alert.raised"]


@pytest.fixture
def h(tmp_path):
    return _H(tmp_path)


async def test_same_utterance_newborn_context_is_used(h):
    """The exact failing case from the live run."""
    await h.s.start()
    await h.say("ನವಜಾತ ಶಿಶು ಭೇಟಿ. ಮಗುವಿಗೆ ತುಂಬಾ ಜ್ವರ ಇದೆ.")
    assert h.s.record.danger_signs == ["NB_FEVER"]
    assert h.alerts()[0].rule_ids == ["NB_FEVER"]


async def test_uncertain_context_uses_worker_words_then_rescopes(h):
    await h.s.start()
    await h.say("ತುಂಬಾ ಜ್ವರ ಇದೆ")
    alert = h.alerts()[0]
    assert sorted(alert.rule_ids) == ["MAT_HIGH_FEVER", "NB_FEVER"]
    assert "ತುಂಬಾ ಜ್ವರ" in alert.message
    assert "ಮಗು" not in alert.message and "not specified" in alert.labels[0]
    await h.say("newborn visit")
    assert h.s.record.danger_signs == ["NB_FEVER"]
    assert h.s.record.requires_phc_referral


async def test_rescope_never_drops_a_referral_without_counterpart(h):
    await h.s.start()
    await h.say("bleeding since morning")  # maternal-only rule, unknown visit
    await h.say("newborn visit")
    assert "MAT_VAGINAL_BLEEDING" in h.s.record.danger_signs
    assert h.s.record.requires_phc_referral


async def test_disclosure_is_not_interruptible(h):
    await h.s.start()
    turn = h.s.turn_id
    await h.s.on_speech_start()
    assert h.s.turn_id == turn
    assert not [e for e in h.events if e.type == "agent.audio.cancel"]


async def test_resumed_speech_does_not_trigger_premature_reply(h):
    """Live run: worker paused mid-note; agent asked a question while she kept talking."""
    await h.s.start()
    await h.s.on_speech_start()
    await h.s.on_speech_start()  # resumed before the first segment's transcript arrived
    await h.s.on_transcript("ಫಲಾನುಭವಿ ID 1 2 3 4.", "kn-IN")
    await asyncio.sleep(0.1)
    assert not [e for e in h.events if e.type == "clarification.requested"]
    await h.s.on_transcript("ANC checkup, ಮುಂದಿನ ಭೇಟಿ 28 November", "kn-IN")
    await asyncio.sleep(0.1)
    assert h.s.readback_version is not None  # one combined response: straight to read-back
    assert not [e for e in h.events if e.type == "clarification.requested"]


async def test_correction_rereads_only_changed_field(h):
    await h.s.start()
    await h.say("ID 1 2 3 4, ANC, weight 52 kg, next visit 28 November")
    full = [e for e in h.events if e.type == "agent.audio" and e.purpose == "readback"][-1].text
    await h.say("ಇಲ್ಲ, ತೂಕ 55 ಕಿಲೋ")
    short = [e for e in h.events if e.type == "agent.audio" and e.purpose == "readback"][-1].text
    assert "ಐಡಿ" in full and "ಮುಂದಿನ ಭೇಟಿ" in full
    assert "ಐವತ್ತೈದು" in short and "ಐಡಿ" not in short and "ಸರಿಯೇ" in short
    assert h.s.readback_version == h.s.record.record_version
