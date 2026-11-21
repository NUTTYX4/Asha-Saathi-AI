"""Phase 5B tests: optional Gemini structured extraction, strict schema validation, grounding & fail-safe fallback.

All tests run cleanly without making live external network calls (offline mocks / SQLite + Docker PostgreSQL).
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from alembic import command
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from fastapi.testclient import TestClient

from app.auth.deps import CSRF_HEADER, CSRF_VALUE
from app.auth.service import set_user_password
from app.core.config import Settings, get_settings
from app.db.database import connect
from app.db.models import Person, User, V2Visit
from app.db.repositories import VisitRepository
from app.integrations.extraction_provider import (
    DeterministicExtractionProvider,
    ExtractionContext,
    GeminiExtractionProvider,
    MockGeminiExtractionProvider,
    build_extraction_provider,
)
from app.integrations.voice_provider import MockVoiceProvider
from app.main import create_app
from app.schemas.gemini_extraction import GeminiCandidate, candidate_to_extraction
from app.schemas.visit import VisitType
from app.seed.demo import seed_demo
from app.services import prompts
from app.services.extraction import Intent, extract as deterministic_extract
from app.services.session_service import VoiceSession
from app.services.voice_v2 import V2VisitSession
from tests.conftest import alembic_config, disposable_pg_database, requires_postgres
from tests.test_voice_v2 import PW, V2Harness, person, v2_rows

TODAY = date(2026, 11, 21)


def _sqlite_session(tmp_path, extraction_provider=None):
    events: list = []
    repo = VisitRepository(connect(tmp_path / "phase5b.db"))

    async def send(ev):
        events.append(ev)

    async def fake_tts(_text: str) -> bytes:
        await asyncio.sleep(0)
        return b"RIFF-fake"

    sess = VoiceSession(
        send,
        fake_tts,
        repo,
        today=lambda: TODAY,
        respond_delay_s=0,
        require_playback_ack=True,
        spoken_confirm_saves=False,
        locked_beneficiary_id="P-020",
        locked_visit_type=VisitType.ROUTINE,
        danger_scope=VisitType.ROUTINE,
        gate_until_disclosure=True,
        extraction_provider=extraction_provider,
    )
    return sess, events


async def _drive_say(session: VoiceSession, text_val: str) -> None:
    await session.on_speech_start()
    await session.on_transcript(text_val, "kn-IN")
    await asyncio.sleep(0.08)


# ------------------------------------------------------------------ 1. Deterministic default unchanged
def test_deterministic_default_off_and_unchanged(monkeypatch):
    monkeypatch.delenv("GEMINI_EXTRACTION_ENABLED", raising=False)
    monkeypatch.delenv("EXTRACTION_PROVIDER_MODE", raising=False)
    get_settings.cache_clear()
    settings = Settings(_env_file=None)
    assert settings.gemini_extraction_enabled is False
    assert settings.extraction_provider_mode == "deterministic"
    provider = build_extraction_provider(settings)
    assert isinstance(provider, DeterministicExtractionProvider)

    # Even if provider_mode="gemini", disabled flag keeps deterministic.
    disabled = Settings(_env_file=None, gemini_extraction_enabled=False, extraction_provider_mode="gemini")
    assert isinstance(build_extraction_provider(disabled), DeterministicExtractionProvider)


# ------------------------------------------------------------------ 2-6. Schema validation, grounding & conversational cases
async def test_mock_gemini_shantamma_phrases_and_edge_cases():
    provider = MockGeminiExtractionProvider()

    # Exact live phrase pair
    out1 = await provider.extract(
        ExtractionContext(text="Weight 52 kg, ಮುಂದಿನ ಭೇಟಿ ನವೆಂಬರ್ ಇಪ್ಪತ್ತೆಂಟು.", today=TODAY, current_visit_type=VisitType.ROUTINE)
    )
    assert out1.used_assist is True
    assert out1.extraction.weight_kg == 52
    assert out1.extraction.next_visit_date == date(2026, 11, 28)

    out2 = await provider.extract(
        ExtractionContext(text="ಇಲ್ಲ, ತೂಕ ಐವತ್ತೈದು ಕಿಲೋ.", today=TODAY, current_visit_type=VisitType.ROUTINE)
    )
    assert out2.used_assist is True
    assert out2.extraction.weight_kg == 55 and out2.extraction.is_correction is True

    # Conversational & ambiguous phrases
    normal = await provider.extract(ExtractionContext(text="Normal visit", today=TODAY))
    assert normal.extraction.visit_type == VisitType.ROUTINE

    for nc_text in ("ಯಾವುದೂ ಇಲ್ಲ", "Nothing to change"):
        nc = await provider.extract(ExtractionContext(text=nc_text, today=TODAY))
        assert nc.extraction.intent == Intent.NO_CHANGE and not nc.extraction.wants_correction

    hi = await provider.extract(ExtractionContext(text="Hello", today=TODAY))
    assert hi.extraction.intent == Intent.GREETING

    unclear_date = await provider.extract(ExtractionContext(text="next visit soon", today=TODAY))
    assert unclear_date.extraction.next_visit_date is None

    unclear_wt = await provider.extract(ExtractionContext(text="weight around normal", today=TODAY))
    assert unclear_wt.extraction.weight_kg is None

    contra_wt = await provider.extract(ExtractionContext(text="Weight 52 kg and 60 kg.", today=TODAY))
    assert contra_wt.extraction.weight_kg is None

    contra_dt = await provider.extract(
        ExtractionContext(text="Next visit 28 November and 5 December.", today=TODAY)
    )
    assert contra_dt.extraction.next_visit_date is None

    other = await provider.extract(ExtractionContext(text="Her husband weight is 70 kg", today=TODAY))
    assert other.extraction.subject_conflict is True and other.extraction.weight_kg is None


async def test_wrong_person_reference_cannot_rebind_or_mutate(tmp_path):
    provider = MockGeminiExtractionProvider(
        responder=lambda _ctx: json.dumps({
            "mentions_other_person": True,
            "referred_beneficiary_id": "P-999",
            "visit_type": "ANC",
            "weight": {"value": 64, "unit": "kg"},
            "next_visit_date": "2026-12-01",
            "clarification_field": "subject",
        })
    )
    sess, events = _sqlite_session(tmp_path, extraction_provider=provider)
    await sess.start()
    await asyncio.sleep(0.01)
    sess.on_playback_completed("disclosure", None)
    await _drive_say(sess, "sister weight 64 kg, next visit 1 December")

    assert sess.record.beneficiary_id == "P-020"
    assert sess.record.visit_type == VisitType.ROUTINE
    assert sess.record.weight_kg is None
    assert sess.record.next_visit_date is None
    assert any(e.type == "clarification.requested" and e.field == "subject" for e in events)


async def test_invalid_json_rejected_and_falls_back():
    for bad in ("{not valid json", "[]", "", "null", '{"weight": "heavy"}'):
        provider = MockGeminiExtractionProvider(responder=lambda _ctx, b=bad: b)
        out = await provider.extract(
            ExtractionContext(text="Weight 52 kg, next visit 28 November.", today=TODAY)
        )
        assert out.used_assist is False
        assert out.fallback_reason == "invalid_output"
        assert out.extraction.weight_kg == 52
        assert out.extraction.next_visit_date == date(2026, 11, 28)


@pytest.mark.parametrize(
    "payload",
    [
        {"diagnosis": "anemia", "weight": {"value": 52, "unit": "kg"}},
        {"clinical_advice": "Take iron tablets"},
        {"danger_signs": ["MAT_HIGH_FEVER"], "requires_phc_referral": False},
        {"confirmed": True, "person_id": "P-999"},
        {"assigned_programme": "ANC"},
        {"visit_type": "malaria"},
        {"vaccinations_due": ["COVID_UNKNOWN"]},
        {"weight": {"value": -5, "unit": "kg"}},
        {"weight": {"value": 300, "unit": "kg"}},
    ],
)
async def test_invented_unsupported_fields_rejected(payload):
    provider = MockGeminiExtractionProvider(responder=lambda _ctx, p=payload: json.dumps(p))
    out = await provider.extract(
        ExtractionContext(text="Weight 52 kg, next visit 28 November.", today=TODAY)
    )
    assert out.used_assist is False
    assert out.fallback_reason == "invalid_output"
    # Safe deterministic extraction remains intact.
    assert out.extraction.weight_kg == 52 and out.extraction.next_visit_date == date(2026, 11, 28)


async def test_missing_measurements_not_hallucinated():
    # No weight digit and no vaccine cue in utterance: LLM hallucinations must be stripped.
    provider = MockGeminiExtractionProvider(
        responder=lambda _ctx: json.dumps({
            "visit_type": "routine",
            "weight": {"value": 54, "unit": "kg"},
            "vaccinations_due": ["BCG"],
            "next_visit_date": "2026-11-28",
        })
    )
    out = await provider.extract(
        ExtractionContext(text="Routine visit, patient doing well, next visit 28 November.", today=TODAY)
    )
    assert out.extraction.weight_kg is None
    assert out.extraction.vaccinations_due is None
    assert out.extraction.next_visit_date == date(2026, 11, 28)

    # Weight only, LLM hallucinates a follow-up date without any date cue.
    provider_date = MockGeminiExtractionProvider(
        responder=lambda _ctx: json.dumps({
            "weight": {"value": 52, "unit": "kg"},
            "next_visit_date": "2026-12-10",
        })
    )
    out_date = await provider_date.extract(ExtractionContext(text="Weight 52 kg.", today=TODAY))
    assert out_date.extraction.weight_kg == 52
    assert out_date.extraction.next_visit_date is None

    # Pregnancy months ("7 ತಿಂಗಳು ಗರ್ಭಿಣಿ") cannot become follow-up date via Gemini either.
    out_preg = await provider_date.extract(ExtractionContext(text="ಏಳು ತಿಂಗಳು ಗರ್ಭಿಣಿ.", today=TODAY))
    assert out_preg.extraction.next_visit_date is None


# ------------------------------------------------------------------ 8, 12. Timeout, missing key, exception fallback & no network
async def test_gemini_missing_key_timeout_and_exception_fallback():
    no_key = Settings(_env_file=None, gemini_extraction_enabled=True, extraction_provider_mode="gemini", gemini_api_key=None)
    assert isinstance(build_extraction_provider(no_key), DeterministicExtractionProvider)

    async def slow(_ctx):
        await asyncio.sleep(1.0)
        return "{}"

    timeout_provider = MockGeminiExtractionProvider(responder=slow, timeout_s=0.05)
    out_to = await timeout_provider.extract(ExtractionContext(text="Weight 52 kg, next visit 28 November.", today=TODAY))
    assert out_to.used_assist is False and out_to.fallback_reason == "timeout"
    assert out_to.extraction.weight_kg == 52

    def boom(_ctx):
        raise RuntimeError("upstream 503")

    err_provider = MockGeminiExtractionProvider(responder=boom)
    out_err = await err_provider.extract(ExtractionContext(text="Weight 52 kg, next visit 28 November.", today=TODAY))
    assert out_err.used_assist is False and out_err.fallback_reason == "provider_error"
    assert out_err.extraction.weight_kg == 52


async def test_no_external_network_and_sdk_config(monkeypatch):
    # Fail loudly if any code tries to open a real network socket in this test.
    monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("network call")))

    # Verify GeminiCandidate works with google-genai's schema transformer offline.
    from google.genai import _transformers

    transformed = _transformers.t_schema(None, GeminiCandidate).model_dump(exclude_none=True)
    assert transformed.get("additional_properties") is False
    assert "weight" in transformed["properties"]

    captured: dict = {}

    async def fake_generate_content(*, model, contents, config):
        captured["model"] = model
        captured["contents"] = contents
        captured["config"] = config
        return SimpleNamespace(
            text=json.dumps({
                "visit_type": "routine",
                "weight": {"value": 52, "unit": "kg"},
                "next_visit_date": "2026-11-28",
            })
        )

    def fake_factory(*, api_key, http_options):
        captured["api_key"] = api_key
        captured["http_options"] = http_options
        return SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=fake_generate_content)))

    settings = Settings(
        _env_file=None,
        gemini_extraction_enabled=True,
        extraction_provider_mode="gemini",
        gemini_api_key="SYNTHETIC-TEST-KEY-DO-NOT-LOG",
        gemini_model="gemini-3.8-flash",
        gemini_timeout_s=4.5,
        gemini_max_input_chars=120,
    )
    defaults = Settings(_env_file=None)
    assert defaults.gemini_model == "gemini-3.8-flash"
    assert defaults.gemini_timeout_s == 8.0
    assert defaults.gemini_max_output_tokens == 768
    provider = GeminiExtractionProvider(settings, client_factory=fake_factory)
    assert "SYNTHETIC-TEST-KEY-DO-NOT-LOG" not in repr(provider)

    long_text = "Weight 52 kg, next visit 28 November. " + ("x" * 300)
    out = await provider.extract(
        ExtractionContext(
            text=long_text,
            today=TODAY,
            current_visit_type=VisitType.ROUTINE,
            subject_population="general",
            awaiting_confirmation=True,
            draft_weight_kg=50.0,
        )
    )
    assert out.used_assist is True
    assert out.extraction.weight_kg == 52 and out.extraction.next_visit_date == date(2026, 11, 28)
    assert captured["http_options"].timeout == 10_000
    assert captured["http_options"].retry_options.attempts == 1
    assert captured["config"].max_output_tokens == 768
    assert str(captured["config"].thinking_config.thinking_level).lower().endswith("low")
    assert captured["config"].thinking_config.thinking_budget is None
    assert captured["config"].temperature == 0.0
    assert captured["config"].response_mime_type == "application/json"
    assert captured["config"].response_schema is None
    assert captured["config"].response_json_schema == GeminiCandidate.model_json_schema()
    assert "subject_population=general" in captured["contents"]
    assert "awaiting_confirmation=True" in captured["contents"]
    assert "draft_weight_kg=50" in captured["contents"]
    # Prompt length bounded (`x` tail truncated) and contains zero PII.
    assert captured["contents"].count("x") < 120

    long_provider = GeminiExtractionProvider(
        settings.model_copy(update={"gemini_timeout_s": 12.5}),
        client_factory=fake_factory,
    )
    await long_provider.extract(ExtractionContext(text="Weight 52 kg", today=TODAY))
    assert captured["http_options"].timeout == 12_500

    # Worst-case fully populated candidate JSON fits well within token budget (~320 chars << ~1500 chars / 512 tokens).
    worst_case = GeminiCandidate(
        visit_type="routine",
        weight={"value": 55.5, "unit": "kg"},
        next_visit_date=date(2026, 11, 28),
        vaccinations_due=["TT", "BCG", "OPV", "Pentavalent", "Hepatitis B"],
        intent="none",
        is_correction=True,
        wants_correction=False,
        is_negative_answer=False,
        mentions_other_person=False,
        referred_beneficiary_id="P-020",
        needs_clarification=False,
        clarification_field="weight_kg",
        contradiction_detected=False,
    ).model_dump_json()
    assert len(worst_case) < 450


async def test_fallback_and_latency_bounds():
    async def slow_responder(_ctx):
        await asyncio.sleep(2.0)
        return "{}"

    started = time.monotonic()
    timeout_provider = MockGeminiExtractionProvider(responder=slow_responder, timeout_s=0.15)
    out = await timeout_provider.extract(
        ExtractionContext(text="Weight 52 kg, ಮುಂದಿನ ಭೇಟಿ November ಇಪ್ಪತ್ತೆಂಟು", today=TODAY)
    )
    elapsed = time.monotonic() - started
    assert elapsed < 0.5
    assert out.used_assist is False and out.fallback_reason == "timeout"
    assert out.extraction.weight_kg == 52 and out.extraction.next_visit_date == date(2026, 11, 28)


async def test_llm_cannot_trigger_or_suppress_clinical_referral_and_health_safe(tmp_path):
    provider = MockGeminiExtractionProvider(
        responder=lambda _ctx: json.dumps({
            "visit_type": "newborn",
            "weight": {"value": 3, "unit": "kg"},
            "next_visit_date": "2026-11-28",
        })
    )
    events: list = []
    repo = VisitRepository(connect(tmp_path / "safety.db"))

    async def send(ev):
        events.append(ev)

    async def fake_tts(_text: str) -> bytes:
        return b"RIFF-fake"

    # 1) Newborn visit with fever MUST still escalate via deterministic rules regardless of Gemini.
    nb = VoiceSession(
        send, fake_tts, repo, today=lambda: TODAY, respond_delay_s=0,
        require_playback_ack=True, spoken_confirm_saves=False,
        locked_beneficiary_id="P-011", locked_visit_type=VisitType.NEWBORN,
        danger_scope=VisitType.NEWBORN, gate_until_disclosure=True,
        extraction_provider=provider,
    )
    await nb.start()
    nb.on_playback_completed("disclosure", None)
    await _drive_say(nb, "Weight 3 kg, next visit 28 November. ಮಗುವಿಗೆ ತುಂಬಾ ಜ್ವರ ಇದೆ.")
    assert nb.record.danger_signs == ["NB_FEVER"] and nb.record.requires_phc_referral is True

    # 2) Routine visit with symptom words still applies zero maternal/newborn rules.
    rt, rt_events = _sqlite_session(tmp_path, extraction_provider=MockGeminiExtractionProvider())
    await rt.start()
    rt.on_playback_completed("disclosure", None)
    await _drive_say(rt, "Weight 52 kg, fever and bleeding, next visit 28 November.")
    assert rt.record.danger_signs == [] and rt.record.requires_phc_referral is False
    assert not any(e.type == "alert.raised" for e in rt_events)

    # 3) /api/health must never expose Gemini keys or prompt internals.
    with TestClient(create_app(connect(tmp_path / "health.db"))) as c:
        h = c.get("/api/health").json()
    assert "gemini" not in json.dumps(h).lower() or ("key" not in json.dumps(h).lower() and "prompt" not in json.dumps(h).lower())
    assert "gemini_api_key" not in h


# ------------------------------------------------------------------ PostgreSQL integration tests (Phase 5B)
@pytest.fixture(scope="module")
def pg_engine():
    with disposable_pg_database("phase5b") as url:
        command.upgrade(alembic_config(), "head")
        eng = create_engine(url)
        with Session(eng) as db:
            seed_demo(db)
            for user in db.scalars(select(User).where(User.is_demo_data.is_(True))).all():
                set_user_password(db, user, PW)
            db.commit()
        yield eng
        eng.dispose()


@requires_postgres
async def test_mock_gemini_full_flow_correction_readback_and_idempotent_save(pg_engine):
    provider = MockGeminiExtractionProvider()
    h = V2Harness(pg_engine, household="H-005", person_name="Shantamma Kallur", visit_type=VisitType.ROUTINE)
    # Inject optional assist provider into V2VisitSession
    h.s = V2VisitSession(
        send=h.s._send,
        tts=h.s._tts,
        engine=pg_engine,
        binding=h.binding,
        visit_type=VisitType.ROUTINE,
        person_display_name="Shantamma Kallur",
        stt_model="MOCK",
        on_end=h.s._on_end,
        today=lambda: TODAY,
        respond_delay_s=0,
        extraction_provider=provider,
    )
    shantamma = person(pg_engine, "Shantamma Kallur")
    await h.ready()

    await h.say("Weight 52 kg, ಮುಂದಿನ ಭೇಟಿ ನವೆಂಬರ್ ಇಪ್ಪತ್ತೆಂಟು.")
    assert h.s.record.weight_kg == 52 and h.s.record.next_visit_date == date(2026, 11, 28)
    v1 = h.s.readback_version
    h.ack_readback(v1)

    # Spoken correction invalidates earlier read-back and playback ack.
    await h.say("ಇಲ್ಲ, ತೂಕ ಐವತ್ತೈದು ಕಿಲೋ.")
    assert h.s.record.weight_kg == 55
    assert h.s.playback_ack_version is None and h.s.readback_version > v1
    await h.s.confirm(v1)
    assert "CONFIRMATION_REJECTED" in h.errors()
    h.ack_readback()

    # Duplicate confirm still saves exactly once with extraction_source == "deterministic+assist".
    await h.s.confirm(h.s.readback_version)
    await h.s.confirm(h.s.readback_version)
    rows = v2_rows(pg_engine, client_visit_id=h.binding.client_visit_id)
    assert len(rows) == 1
    assert rows[0].person_id == shantamma.id
    assert rows[0].weight_kg == 55.0
    assert rows[0].next_visit_date == date(2026, 11, 28)
    assert rows[0].extraction_source == "deterministic+assist"
    assert rows[0].danger_signs == [] and rows[0].requires_phc_referral is False


@requires_postgres
async def test_gemini_failure_fallback_still_completes_save(pg_engine):
    err_provider = MockGeminiExtractionProvider(responder=lambda _ctx: (_ for _ in ()).throw(RuntimeError("down")))
    h = V2Harness(pg_engine, household="H-005", person_name="Shantamma Kallur", visit_type=VisitType.ROUTINE)
    h.s = V2VisitSession(
        send=h.s._send,
        tts=h.s._tts,
        engine=pg_engine,
        binding=h.binding,
        visit_type=VisitType.ROUTINE,
        person_display_name="Shantamma Kallur",
        stt_model="MOCK",
        on_end=h.s._on_end,
        today=lambda: TODAY,
        respond_delay_s=0,
        extraction_provider=err_provider,
    )
    await h.ready()
    await h.say("Weight 52 kg, ಮುಂದಿನ ಭೇಟಿ ನವೆಂಬರ್ ಇಪ್ಪತ್ತೆಂಟು.")
    h.ack_readback()
    await h.s.confirm(h.s.readback_version)
    rows = v2_rows(pg_engine, client_visit_id=h.binding.client_visit_id)
    assert len(rows) == 1 and rows[0].weight_kg == 52 and rows[0].extraction_source == "deterministic"


@requires_postgres
async def test_cancelled_session_ignores_late_gemini_response(pg_engine):
    release = asyncio.Event()

    async def late_responder(_ctx):
        await release.wait()
        return json.dumps({"weight": {"value": 60, "unit": "kg"}})

    slow_provider = MockGeminiExtractionProvider(responder=late_responder, timeout_s=5.0)
    h = V2Harness(pg_engine, household="H-005", person_name="Shantamma Kallur", visit_type=VisitType.ROUTINE)
    h.s = V2VisitSession(
        send=h.s._send,
        tts=h.s._tts,
        engine=pg_engine,
        binding=h.binding,
        visit_type=VisitType.ROUTINE,
        person_display_name="Shantamma Kallur",
        stt_model="MOCK",
        on_end=h.s._on_end,
        today=lambda: TODAY,
        respond_delay_s=0,
        extraction_provider=slow_provider,
    )
    await h.ready()
    await h.s.on_speech_start()
    await h.s.on_transcript("weight 60 kg, next visit 28 November", "en-IN")
    await asyncio.sleep(0.05)  # extraction is now blocked inside `late_responder`
    await h.s.end("cancelled", "Cancelled mid-extraction.")
    release.set()
    await asyncio.sleep(0.05)

    assert h.s.record.weight_kg is None
    assert not v2_rows(pg_engine, client_visit_id=h.binding.client_visit_id)


@requires_postgres
async def test_prompts_transcripts_and_secrets_absent_from_logs_and_db(pg_engine, caplog):
    secret_key = "GEMINI_SYNTHETIC_SECRET_TOKEN_XYZ_999"
    sentinel_text = "ZEBRA_SENTINEL_TRANSCRIPT_999"

    async def fail_generate(*, model, contents, config):
        raise RuntimeError(f"rejected key {secret_key} and text {sentinel_text}")

    settings = Settings(
        _env_file=None,
        gemini_extraction_enabled=True,
        extraction_provider_mode="gemini",
        gemini_api_key=secret_key,
    )
    provider = GeminiExtractionProvider(
        settings,
        client_factory=lambda **_kw: SimpleNamespace(
            aio=SimpleNamespace(models=SimpleNamespace(generate_content=fail_generate))
        ),
    )

    with caplog.at_level(logging.DEBUG):
        h = V2Harness(pg_engine, household="H-005", person_name="Shantamma Kallur", visit_type=VisitType.ROUTINE)
        h.s = V2VisitSession(
            send=h.s._send,
            tts=h.s._tts,
            engine=pg_engine,
            binding=h.binding,
            visit_type=VisitType.ROUTINE,
            person_display_name="Shantamma Kallur",
            stt_model="MOCK",
            on_end=h.s._on_end,
            today=lambda: TODAY,
            respond_delay_s=0,
            extraction_provider=provider,
        )
        await h.ready()
        await h.say(f"{sentinel_text} weight 55 kg, next visit 28 November.")
        h.ack_readback()
        await h.s.confirm(h.s.readback_version)

    assert secret_key not in caplog.text
    assert sentinel_text not in caplog.text
    assert "reference_date=" not in caplog.text

    with Session(pg_engine) as db:
        dump = " ".join(
            str(r)
            for r in db.execute(
                text(
                    "SELECT row_to_json(v)::text FROM v2_visits v "
                    "UNION ALL SELECT row_to_json(a)::text FROM audit_events a"
                )
            ).scalars()
        )
    assert secret_key not in dump
    assert sentinel_text not in dump
    assert "reference_date=" not in dump


@requires_postgres
async def test_no_clarification_loop_with_mock_gemini(pg_engine):
    provider = MockGeminiExtractionProvider()
    h = V2Harness(pg_engine, household="H-005", person_name="Shantamma Kallur", visit_type=VisitType.UNKNOWN)
    h.s = V2VisitSession(
        send=h.s._send,
        tts=h.s._tts,
        engine=pg_engine,
        binding=h.binding,
        visit_type=VisitType.UNKNOWN,
        person_display_name="Shantamma Kallur",
        stt_model="MOCK",
        on_end=h.s._on_end,
        today=lambda: TODAY,
        respond_delay_s=0,
        extraction_provider=provider,
    )
    await h.ready()
    await h.say("Weight 52 kg, ಮುಂದಿನ ಭೇಟಿ ನವೆಂಬರ್ ಇಪ್ಪತ್ತೆಂಟು.")
    assert [c.field for c in h.of("clarification.requested")] == ["visit_type"]
    await h.say("Hello")
    await h.say("Nothing to change")
    await h.say("ಯಾವುದೂ ಇಲ್ಲ")
    assert not any(e.text == prompts.ASK_WHAT_TO_CHANGE for e in h.of("agent.audio"))
    # Saying "Normal visit" resolves UNKNOWN to ROUTINE and triggers read-back without looping.
    await h.say("Normal visit")
    assert h.s.record.visit_type == VisitType.ROUTINE
    assert h.s.readback_version is not None


@requires_postgres
async def test_phase5b_acceptance_ws_e2e_h005_p020_gemini_mock(pg_engine, monkeypatch):
    """Full V2 WebSocket + REST + PostgreSQL acceptance for H-005 / P-020 with EXTRACTION_PROVIDER_MODE=gemini_mock."""
    monkeypatch.setenv("V2_VOICE_ENABLED", "true")
    monkeypatch.setenv("GEMINI_EXTRACTION_ENABLED", "true")
    monkeypatch.setenv("EXTRACTION_PROVIDER_MODE", "gemini_mock")
    get_settings.cache_clear()
    try:
        with Session(pg_engine) as db:
            before_total = db.scalar(select(func.count()).select_from(V2Visit))
        shantamma = person(pg_engine, "Shantamma Kallur")
        divya = person(pg_engine, "Divya Kallur")
        assert shantamma.public_id == "P-020"

        with TestClient(create_app(pg_engine), base_url="https://testserver") as c:
            assert c.app.state.extraction_provider.name == "gemini_mock"
            c.app.state.voice_provider = MockVoiceProvider(
                [
                    "Weight 52 kg, ಮುಂದಿನ ಭೇಟಿ November ಇಪ್ಪತ್ತೆಂಟು",
                    "ಇಲ್ಲ, ತೂಕ ಐವತ್ತೈದು ಕಿಲೋ",
                ],
                bytes_per_utterance=1024,
            )
            assert c.post(
                "/api/v2/auth/login",
                json={"username": "demo_worker_a", "password": PW},
                headers={CSRF_HEADER: CSRF_VALUE},
            ).status_code == 200

            visit_key = str(uuid.uuid4())
            headers = {
                "origin": "https://testserver",
                "cookie": f"asha_session={c.cookies.get('asha_session')}",
            }

            def recv_until_pred(ws, pred, limit=80):
                seen = []
                for _ in range(limit):
                    ev = ws.receive_json()
                    seen.append(ev)
                    if pred(ev):
                        return ev, seen
                raise AssertionError(f"Predicate not satisfied; got {[e['type'] for e in seen]}")

            with c.websocket_connect("/ws/v2/session", headers=headers) as ws:
                ws.send_json({
                    "type": "v2.session.start",
                    "household_id": "H-005",
                    "person_id": "P-020",
                    "client_visit_id": visit_key,
                    "visit_type": "routine",
                })
                bound, _ = recv_until_pred(ws, lambda e: e["type"] == "v2.session.bound")
                assert (bound["person_public_id"], bound["household_public_id"], bound["visit_type"]) == (
                    "P-020", "H-005", "routine"
                )
                recv_until_pred(ws, lambda e: e["type"] == "agent.audio" and e["purpose"] == "disclosure")
                ws.send_json({"type": "playback.completed", "purpose": "disclosure", "record_version": None})

                # Utterance 1: Weight 52 kg, ಮುಂದಿನ ಭೇಟಿ November ಇಪ್ಪತ್ತೆಂಟು
                ws.send_bytes(b"\x00" * 2048)
                rb1, seen1 = recv_until_pred(ws, lambda e: e["type"] == "agent.audio" and e["purpose"] == "readback")
                upd1 = [e["record"] for e in seen1 if e["type"] == "record.updated"][-1]
                v1 = rb1["record_version"]
                assert upd1["weight_kg"] == 52 and upd1["beneficiary_id"] == "P-020"
                assert upd1["next_visit_date"].endswith("-11-28")

                # Must block confirm before readback playback ack completes.
                ws.send_json({"type": "record.confirm", "record_version": v1})
                err1, _ = recv_until_pred(ws, lambda e: e["type"] == "session.error")
                assert err1["code"] == "READBACK_NOT_FINISHED"
                ws.send_json({"type": "playback.completed", "purpose": "readback", "record_version": v1})

                # Correction: ಇಲ್ಲ, ತೂಕ ಐವತ್ತೈದು ಕಿಲೋ
                ws.send_bytes(b"\x00" * 2048)
                rb2, seen2 = recv_until_pred(
                    ws, lambda e: e["type"] == "agent.audio" and e["purpose"] == "readback" and (e["record_version"] or 0) > v1
                )
                upd2 = [e["record"] for e in seen2 if e["type"] == "record.updated"][-1]
                v2 = rb2["record_version"]
                assert upd2["weight_kg"] == 55 and upd2["beneficiary_id"] == "P-020"

                # Stale version confirm must fail.
                ws.send_json({"type": "record.confirm", "record_version": v1})
                err2, _ = recv_until_pred(ws, lambda e: e["type"] == "session.error")
                assert err2["code"] == "CONFIRMATION_REJECTED"
                # Complete re-triggered readback playback ack before explicit confirm.
                rb3, _ = recv_until_pred(ws, lambda e: e["type"] == "agent.audio" and e["purpose"] == "readback")
                v_final = rb3["record_version"]
                assert v_final == v2

                ws.send_json({"type": "record.confirm", "record_version": v_final})
                err3, _ = recv_until_pred(ws, lambda e: e["type"] == "session.error")
                assert err3["code"] == "READBACK_NOT_FINISHED"

                ws.send_json({"type": "playback.completed", "purpose": "readback", "record_version": v_final})
                ws.send_json({"type": "record.confirm", "record_version": v_final})
                saved, _ = recv_until_pred(ws, lambda e: e["type"] == "v2.visit.saved")
                assert saved["person_public_id"] == "P-020" and saved["record_version"] == v_final

            # History REST check for Shantamma & non-leakage to other H-005 member
            hist = c.get("/api/v2/people/P-020/visits").json()
            matched = [v for v in hist if v["client_visit_id"] == visit_key]
            assert len(matched) == 1
            assert matched[0]["weight_kg"] == 55.0
            assert matched[0]["visit_type"] == "routine"
            assert matched[0]["extraction_source"] == "deterministic+assist"
            assert matched[0]["next_visit_date"].endswith("-11-28")
            assert c.get(f"/api/v2/people/{divya.public_id}/visits").json() == []

        with Session(pg_engine) as db:
            after_total = db.scalar(select(func.count()).select_from(V2Visit))
        assert after_total == before_total + 1
        assert len(v2_rows(pg_engine, client_visit_id=uuid.UUID(visit_key))) == 1
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


async def test_gemini_sdk_error_fallbacks_and_thinking_config():
    # Gemini 2.5.x retains thinking_budget=0 while Gemini 3.x uses thinking_level="low".
    s25 = Settings(
        _env_file=None,
        gemini_extraction_enabled=True,
        extraction_provider_mode="gemini",
        gemini_api_key="SYNTHETIC-TEST-KEY-DO-NOT-LOG",
        gemini_model="gemini-2.5-flash",
    )
    cfg25 = GeminiExtractionProvider(s25).build_config()
    assert cfg25.thinking_config.thinking_budget == 0
    assert cfg25.thinking_config.thinking_level is None
    assert cfg25.response_schema is None
    assert cfg25.response_json_schema == GeminiCandidate.model_json_schema()

    from google.genai import errors as genai_errors

    for exc in (
        genai_errors.ServerError(503, {"error": {"message": "high demand"}}, None),
        genai_errors.ClientError(400, {"error": {"message": "bad request"}}, None),
        TimeoutError("deadline exceeded"),
    ):
        async def _raise(err=exc, **_kw):
            raise err

        fake_client = SimpleNamespace(
            aio=SimpleNamespace(models=SimpleNamespace(generate_content=_raise))
        )
        provider = GeminiExtractionProvider(
            Settings(
                _env_file=None,
                gemini_extraction_enabled=True,
                extraction_provider_mode="gemini",
                gemini_api_key="SYNTHETIC-TEST-KEY-DO-NOT-LOG",
                gemini_model="gemini-3.8-flash",
            ),
            client_factory=lambda **_kw: fake_client,
        )
        out = await provider.extract(
            ExtractionContext(text="Weight 52 kg, next visit 28 November.", today=TODAY)
        )
        assert out.used_assist is False
        assert out.fallback_reason == ("timeout" if isinstance(exc, TimeoutError) else "provider_error")
        assert out.extraction.weight_kg == 52 and out.extraction.next_visit_date == date(2026, 11, 28)

    async def _cancel(**_kw):
        raise asyncio.CancelledError()

    cancel_provider = GeminiExtractionProvider(
        s25,
        client_factory=lambda **_kw: SimpleNamespace(
            aio=SimpleNamespace(models=SimpleNamespace(generate_content=_cancel))
        ),
    )
    with pytest.raises(asyncio.CancelledError):
        await cancel_provider.extract(ExtractionContext(text="Weight 52 kg", today=TODAY))


async def test_voice_session_propagates_non_pii_context_to_gemini_provider(tmp_path):
    prompts_seen: list[str] = []

    async def _gen(*, model, contents, config):
        prompts_seen.append(contents)
        if "draft_weight_kg=52" in contents:
            return SimpleNamespace(
                text=json.dumps({
                    "is_correction": True,
                    "weight": {"value": 55, "unit": "kg"},
                })
            )
        return SimpleNamespace(
            text=json.dumps({
                "visit_type": "routine",
                "weight": {"value": 52, "unit": "kg"},
                "next_visit_date": "2026-11-28",
            })
        )

    fake_client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=_gen)))
    provider = GeminiExtractionProvider(
        Settings(
            _env_file=None,
            gemini_extraction_enabled=True,
            extraction_provider_mode="gemini",
            gemini_api_key="SYNTHETIC-TEST-KEY-DO-NOT-LOG",
            gemini_model="gemini-3.8-flash",
        ),
        client_factory=lambda **_kw: fake_client,
    )

    sess, _events = _sqlite_session(tmp_path, extraction_provider=provider)
    await sess.start()
    sess.on_playback_completed("disclosure", None)
    await _drive_say(sess, "Weight 52 kg, ಮುಂದಿನ ಭೇಟಿ November ಇಪ್ಪತ್ತೆಂಟು.")
    assert sess.record.weight_kg == 52
    await _drive_say(sess, "ಇಲ್ಲ, ತೂಕ ಐವತ್ತೈದು ಕಿಲೋ.")
    assert sess.record.weight_kg == 55

    assert len(prompts_seen) == 2
    assert "subject_population=routine" in prompts_seen[0]
    assert "awaiting_confirmation=False" in prompts_seen[0]
    assert "draft_weight_kg=null" in prompts_seen[0]
    assert "awaiting_confirmation=True" in prompts_seen[1]
    assert "draft_weight_kg=52" in prompts_seen[1]
    assert "draft_next_visit_date=2026-11-28" in prompts_seen[1]
    for p in prompts_seen:
        assert "P-020" not in p
        assert "H-005" not in p
        assert "Shantamma" not in p

    # Newborn scope resolves subject_population="newborn" instead of "general".
    nb = VoiceSession(
        lambda _ev: asyncio.sleep(0),
        lambda _t: asyncio.sleep(0, result=b"RIFF-fake"),
        VisitRepository(connect(tmp_path / "nb_ctx.db")),
        today=lambda: TODAY,
        respond_delay_s=0,
        require_playback_ack=True,
        spoken_confirm_saves=False,
        locked_beneficiary_id="P-011",
        locked_visit_type=VisitType.NEWBORN,
        danger_scope=VisitType.NEWBORN,
        gate_until_disclosure=True,
        extraction_provider=provider,
    )
    await nb.start()
    nb.on_playback_completed("disclosure", None)
    await _drive_say(nb, "Weight 3 kg, next visit 28 November.")
    assert "subject_population=newborn" in prompts_seen[-1]
    assert "P-011" not in prompts_seen[-1]

