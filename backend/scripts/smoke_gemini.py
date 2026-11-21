"""Opt-in live Gemini API smoke check on synthetic, non-clinical MCH demo data.

Usage (from backend/, inside container or venv with GEMINI_API_KEY configured):
    python -m scripts.smoke_gemini
    python -m scripts.smoke_gemini --model gemini-3.6-flash
    python -m scripts.smoke_gemini --with-disposable-pg

Never modifies `.env` or live databases. Uses Mock TTS / scripted transcripts so zero Gnani
paid credits are spent, and runs DB tests only against an ephemeral disposable database
when `--with-disposable-pg` is requested. Never prints `GEMINI_API_KEY` or raw prompts.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from types import SimpleNamespace

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import create_engine, func, select, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.auth.service import create_session, set_user_password  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.database import connect  # noqa: E402
from app.db.models import Person, User, V2Visit  # noqa: E402
from app.db.repositories import VisitRepository  # noqa: E402
from app.integrations.extraction_provider import ExtractionContext, GeminiExtractionProvider  # noqa: E402
from app.schemas.events import V2SessionStart  # noqa: E402
from app.schemas.visit import VisitType  # noqa: E402
from app.seed.demo import seed_demo  # noqa: E402
from app.services.extraction import Intent  # noqa: E402
from app.services.session_service import VoiceSession  # noqa: E402
from app.services.voice_v2 import V2VisitSession, authorize_start  # noqa: E402

TODAY = date(2026, 11, 1)


class _LogCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@contextmanager
def _disposable_pg(base_database_url: object):
    raw_url = (
        base_database_url.get_secret_value()
        if hasattr(base_database_url, "get_secret_value")
        else str(base_database_url)
    )
    base = make_url(raw_url)
    temp_name = f"smoke_gemini_{uuid.uuid4().hex[:8]}"
    admin_url = base.set(database="postgres")
    temp_url = base.set(database=temp_name)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{temp_name}"'))
    prev_env = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = temp_url.render_as_string(hide_password=False)
    try:
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", temp_url.render_as_string(hide_password=False))
        command.upgrade(cfg, "head")
        yield temp_url.render_as_string(hide_password=False)
    finally:
        if prev_env is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prev_env
        with admin_engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{temp_name}" WITH (FORCE)'))
        admin_engine.dispose()


async def _run_case(provider: GeminiExtractionProvider, name: str, ctx: ExtractionContext, check) -> dict:
    started = time.monotonic()
    out = await provider.extract(ctx)
    elapsed_ms = round((time.monotonic() - started) * 1000, 1)
    ok, detail = check(out)
    return {
        "case": name,
        "passed": bool(ok),
        "used_assist": out.used_assist,
        "fallback_reason": out.fallback_reason,
        "latency_ms": elapsed_ms,
        "detail": detail,
    }


async def _run_extraction_suite(provider: GeminiExtractionProvider) -> list[dict]:
    cases = [
        (
            "kannada_english_extract",
            ExtractionContext(
                text="Weight 52 kg, ಮುಂದಿನ ಭೇಟಿ November ಇಪ್ಪತ್ತೆಂಟು",
                today=TODAY,
                current_visit_type=VisitType.ROUTINE,
                subject_population="routine",
            ),
            lambda out: (
                out.extraction.weight_kg == 52.0 and out.extraction.next_visit_date == date(2026, 11, 28),
                f"weight={out.extraction.weight_kg}, date={out.extraction.next_visit_date}",
            ),
        ),
        (
            "correction_52_to_55",
            ExtractionContext(
                text="ಇಲ್ಲ, ತೂಕ ಐವತ್ತೈದು ಕಿಲೋ",
                today=TODAY,
                current_visit_type=VisitType.ROUTINE,
                subject_population="routine",
                awaiting_confirmation=True,
                draft_weight_kg=52.0,
                draft_next_visit_date=date(2026, 11, 28),
            ),
            lambda out: (
                out.extraction.weight_kg == 55.0
                and (out.extraction.is_correction or out.extraction.intent == Intent.CORRECT),
                f"weight={out.extraction.weight_kg}, corr={out.extraction.is_correction}, intent={out.extraction.intent.value}",
            ),
        ),
        (
            "routine_normal_visit",
            ExtractionContext(
                text="Normal visit",
                today=TODAY,
                expecting_visit_type=True,
                subject_population="unresolved",
            ),
            lambda out: (
                out.extraction.visit_type == VisitType.ROUTINE,
                f"visit_type={out.extraction.visit_type.value}",
            ),
        ),
        (
            "none_of_these_kn",
            ExtractionContext(
                text="ಯಾವುದೂ ಇಲ್ಲ",
                today=TODAY,
                current_visit_type=VisitType.ROUTINE,
                subject_population="routine",
            ),
            lambda out: (
                not out.extraction.fields
                and (
                    out.extraction.is_negative_answer
                    or out.extraction.intent in (Intent.NONE, Intent.NO_CHANGE, Intent.REJECT)
                ),
                f"intent={out.extraction.intent.value}, neg={out.extraction.is_negative_answer}",
            ),
        ),
        (
            "greeting",
            ExtractionContext(
                text="Hello",
                today=TODAY,
                current_visit_type=VisitType.ROUTINE,
                subject_population="routine",
            ),
            lambda out: (
                out.extraction.intent == Intent.GREETING
                and not out.extraction.fields
                and not out.extraction.is_correction,
                f"intent={out.extraction.intent.value}, fields={len(out.extraction.fields)}",
            ),
        ),
        (
            "unclear_missing",
            ExtractionContext(
                text="Patient seems fine today, weight was checked earlier",
                today=TODAY,
                current_visit_type=VisitType.ROUTINE,
                subject_population="routine",
            ),
            lambda out: (
                out.extraction.weight_kg is None
                and out.extraction.next_visit_date is None
                and out.extraction.vaccinations_due is None,
                f"weight={out.extraction.weight_kg}, date={out.extraction.next_visit_date}",
            ),
        ),
        (
            "contradiction",
            ExtractionContext(
                text="Weight 52 kg and weight 60 kg",
                today=TODAY,
                current_visit_type=VisitType.ROUTINE,
                subject_population="routine",
            ),
            lambda out: (
                out.extraction.weight_kg is None,
                f"weight={out.extraction.weight_kg}",
            ),
        ),
        (
            "wrong_person",
            ExtractionContext(
                text="Husband weight 72 kg",
                today=TODAY,
                current_visit_type=VisitType.ROUTINE,
                subject_population="routine",
            ),
            lambda out: (
                out.extraction.subject_conflict and out.extraction.weight_kg is None,
                f"subject_conflict={out.extraction.subject_conflict}, weight={out.extraction.weight_kg}",
            ),
        ),
    ]
    results = []
    for name, ctx, check in cases:
        results.append(await _run_case(provider, name, ctx, check))
    return results


async def _run_disposable_pg_flow(provider: GeminiExtractionProvider, database_url: str) -> dict:
    with _disposable_pg(database_url) as temp_url:
        eng = create_engine(temp_url)
        try:
            with Session(eng) as db:
                seed_demo(db)
                for u in db.scalars(select(User).where(User.is_demo_data.is_(True))).all():
                    set_user_password(db, u, "synthetic-smoke-pw")
                db.commit()
                shantamma = db.scalar(select(Person).where(Person.full_name == "Shantamma Kallur"))
                divya = db.scalar(select(Person).where(Person.public_id == "P-018"))
                shantamma_id = shantamma.id
                shantamma_public_id = shantamma.public_id
                divya_id = divya.id
                worker = db.scalar(select(User).where(User.username == "demo_worker_a"))
                token = create_session(db, worker, 1)
                db.commit()

            visit_uuid = uuid.uuid4()
            binding, display = authorize_start(
                eng,
                token,
                V2SessionStart(
                    household_id="H-005",
                    person_id=shantamma_public_id,
                    client_visit_id=visit_uuid,
                    visit_type=VisitType.ROUTINE,
                ),
            )
            events = []

            async def _send(ev):
                events.append(ev)

            async def _fake_tts(_txt: str) -> bytes:
                return b"RIFF-smoke"

            async def _on_end(_reason: str) -> None:
                return None

            sess = V2VisitSession(
                send=_send,
                tts=_fake_tts,
                engine=eng,
                binding=binding,
                visit_type=VisitType.ROUTINE,
                person_display_name=display,
                stt_model="MOCK",
                on_end=_on_end,
                today=lambda: TODAY,
                respond_delay_s=0,
                extraction_provider=provider,
            )
            await sess.start()
            sess.on_playback_completed("disclosure", None)

            await sess.on_speech_start()
            await sess.on_transcript("Weight 52 kg, ಮುಂದಿನ ಭೇಟಿ November ಇಪ್ಪತ್ತೆಂಟು", "kn-IN")
            for _ in range(300):
                if any(
                    getattr(e, "type", None) == "agent.audio" and getattr(e, "purpose", None) == "readback"
                    for e in events
                ):
                    break
                await asyncio.sleep(0.05)
            v1 = sess.readback_version
            assert sess.record.weight_kg == 52 and sess.record.next_visit_date == date(2026, 11, 28)
            assert v1 is not None
            sess.on_playback_completed("readback", v1)

            await sess.on_speech_start()
            await sess.on_transcript("ಇಲ್ಲ, ತೂಕ ಐವತ್ತೈದು ಕಿಲೋ", "kn-IN")
            for _ in range(300):
                if any(
                    getattr(e, "type", None) == "agent.audio"
                    and getattr(e, "purpose", None) == "readback"
                    and (getattr(e, "record_version", None) or 0) > v1
                    for e in events
                ):
                    break
                await asyncio.sleep(0.05)
            v2 = sess.readback_version
            assert sess.record.weight_kg == 55 and v2 is not None and v2 > v1
            assert sess.playback_ack_version is None

            await sess.confirm(v1)
            assert any(getattr(e, "code", None) == "CONFIRMATION_REJECTED" for e in events)
            sess.on_playback_completed("readback", v2)
            await sess.confirm(v2)

            with Session(eng) as db:
                rows = db.scalars(select(V2Visit).where(V2Visit.client_visit_id == visit_uuid)).all()
                total = db.scalar(select(func.count()).select_from(V2Visit))
                divya_rows = db.scalars(select(V2Visit).where(V2Visit.person_id == divya_id)).all()

                assert len(rows) == 1 and total == 1
                assert len(divya_rows) == 0
                row = rows[0]
                assert row.person_id == shantamma_id
                assert row.weight_kg == 55.0
                assert row.next_visit_date == date(2026, 11, 28)
                assert row.visit_type == "routine"
                assert row.danger_signs == [] and row.requires_phc_referral is False

                return {
                    "passed": True,
                    "saved_rows": len(rows),
                    "weight_kg": row.weight_kg,
                    "next_visit_date": row.next_visit_date.isoformat(),
                    "visit_type": row.visit_type,
                    "extraction_source": row.extraction_source,
                    "other_member_rows": len(divya_rows),
                }
        finally:
            eng.dispose()


async def _run_danger_independence_check(provider: GeminiExtractionProvider) -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = VisitRepository(connect(Path(tmpdir) / "smoke_danger.db"))
        events: list = []

        async def _send(ev) -> None:
            events.append(ev)

        async def _fake_tts(_txt: str) -> bytes:
            return b"RIFF-smoke"

        nb = VoiceSession(
            _send,
            _fake_tts,
            repo,
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
        await nb.on_speech_start()
        await nb.on_transcript("Weight 3 kg, next visit 28 November. ಮಗುವಿಗೆ ತುಂಬಾ ಜ್ವರ ಇದೆ.", "kn-IN")
        for _ in range(300):
            if nb.record.danger_signs and nb.readback_version is not None:
                break
            await asyncio.sleep(0.05)

        passed = nb.record.danger_signs == ["NB_FEVER"] and nb.record.requires_phc_referral is True
        return {
            "passed": passed,
            "danger_signs": list(nb.record.danger_signs),
            "requires_phc_referral": nb.record.requires_phc_referral,
            "weight_kg": nb.record.weight_kg,
        }


async def _main_async(model_name: str, with_disposable_pg: bool) -> int:
    settings = get_settings()
    if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value().strip():
        print(json.dumps({"error": "GEMINI_API_KEY not configured"}))
        return 2

    effective = settings.model_copy(
        update={
            "gemini_extraction_enabled": True,
            "extraction_provider_mode": "gemini",
            "gemini_model": model_name,
        }
    )
    provider = GeminiExtractionProvider(effective)
    capture = _LogCapture()
    root_logger = logging.getLogger()
    root_logger.addHandler(capture)
    try:
        suite = await _run_extraction_suite(provider)
        danger_result = await _run_danger_independence_check(provider)
        pg_result = None
        if with_disposable_pg:
            pg_result = await _run_disposable_pg_flow(provider, settings.database_url)
    finally:
        root_logger.removeHandler(capture)

    secret = settings.gemini_api_key.get_secret_value().strip()
    leaked_secret = any(secret in m for m in capture.messages)
    leaked_utterance = any("Shantamma" in m or "Weight 52 kg" in m or "ಐವತ್ತೈದು" in m for m in capture.messages)

    assist_count = sum(1 for r in suite if r["used_assist"])
    all_passed = (
        assist_count > 0
        and all(r["passed"] for r in suite)
        and danger_result["passed"]
        and (pg_result is None or pg_result["passed"])
    )
    out = {
        "model": model_name,
        "cases_total": len(suite),
        "cases_passed": sum(1 for r in suite if r["passed"]),
        "used_assist_count": assist_count,
        "danger_independence": danger_result,
        "leaked_secret_in_logs": leaked_secret,
        "leaked_utterance_in_logs": leaked_utterance,
        "cases": suite,
        "disposable_pg": pg_result,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if leaked_secret or leaked_utterance or not all_passed:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Opt-in live Gemini extraction smoke test (synthetic data only)")
    parser.add_argument("--model", default=None, help="Gemini model name override (default: settings.gemini_model)")
    parser.add_argument("--with-disposable-pg", action="store_true", help="Also run full V2VisitSession flow in a disposable PostgreSQL DB")
    args = parser.parse_args()
    settings = get_settings()
    model_name = args.model or settings.gemini_model
    return asyncio.run(_main_async(model_name, args.with_disposable_pg))


if __name__ == "__main__":
    raise SystemExit(main())
