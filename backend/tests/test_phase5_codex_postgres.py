"""Run only on a fresh private PostGIS server, without migrations or shared fixtures."""

import base64
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.auth.deps import COOKIE_NAME
from app.auth.service import create_session, user_for_token
from app.core.config import get_settings
from app.db.models import Base, Person, Territory, TerritoryAssignment, User, V2Visit
from app.db.visits_v2 import VisitSaveRefused, confirm_visit
from app.integrations.voice_provider import MockVoiceProvider
from app.main import create_app
from app.schemas.events import V2SessionStart
from app.schemas.visit import RecordStatus, VisitRecord, VisitType
from app.seed.demo import seed_demo
from app.services.voice_v2 import authorize_start


PRIVATE_URL = "postgresql+psycopg://postgres@127.0.0.1/novix_codex_e2e"
pytestmark = pytest.mark.skipif(os.getenv("NOVIX_CODEX_PRIVATE_PG") != "1",
                                reason="requires a fresh network-isolated Codex PostGIS server")
TRANSCRIPT_MARKER = "QAQUARTZTRANSCRIPT"
AUDIO_MARKER = b"QAQUARTZPCMFRAME"


@pytest.fixture(scope="module")
def engine():
    engine = create_engine(PRIVATE_URL)
    try:
        existing = set(inspect(engine).get_table_names())
        assert not existing.intersection(Base.metadata.tables), "Use an empty disposable database"
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            seed_demo(db)
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def worker(engine):
    with Session(engine) as db:
        user = User(username=f"qa-{uuid4().hex}", display_name="Synthetic QA worker",
                    role="worker", active=True, password_hash="unused")
        db.add(user)
        db.flush()
        grant = TerritoryAssignment(user_id=user.id, territory_id=db.scalar(
            select(Territory.id).where(Territory.code == "DEMO-A")))
        db.add(grant)
        token = create_session(db, user, 1)
        person_key = db.scalar(select(Person.public_id).where(Person.full_name == "Kavya Halli"))
        db.flush()
        result = (token, grant.id, person_key)
        db.commit()
        return result


@pytest.fixture
def client(engine, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", PRIVATE_URL)
    monkeypatch.setenv("V2_VOICE_ENABLED", "true")
    monkeypatch.setenv("VOICE_PROVIDER_MODE", "mock")
    monkeypatch.setenv("LEGACY_ROUND1_API_ENABLED", "true")
    monkeypatch.setenv("VOICE_IDLE_TIMEOUT_S", "5")
    get_settings.cache_clear()
    try:
        with TestClient(create_app(engine), base_url="https://testserver") as client:
            client.app.state.voice_provider = MockVoiceProvider(
                [f"{TRANSCRIPT_MARKER}. Weight 52 kg. Next visit 28 November."],
                bytes_per_utterance=len(AUDIO_MARKER),
            )
            yield client
    finally:
        get_settings.cache_clear()


def receive(ws, kind, purpose=None):
    for _ in range(60):
        event = ws.receive_json()
        if event["type"] == kind and (purpose is None or event.get("purpose") == purpose):
            return event
        assert event["type"] not in ("session.error", "session.ended"), event
    pytest.fail(f"Missing {kind} ({purpose})")


def rows(engine, key):
    with Session(engine) as db:
        return db.scalars(select(V2Visit).where(V2Visit.client_visit_id == key)).all()


def seed_snapshot(engine):
    with engine.connect() as conn:
        return {
            name: conn.execute(text(f"SELECT row_to_json(r)::text FROM {name} r ORDER BY id")).scalars().all()
            for name in ("households", "people", "person_relationships", "programme_enrolments", "household_surveys")
        }


def start_maternal_visit(ws, key, person_key):
    ws.send_json({"type": "v2.session.start", "household_id": "H-003", "person_id": person_key,
                  "client_visit_id": str(key), "visit_type": "PNC"})
    bound = receive(ws, "v2.session.bound")
    assert bound["person_public_id"] == person_key and bound["household_public_id"] == "H-003"
    assert receive(ws, "agent.audio", "disclosure")["audio_b64"]
    ws.send_json({"type": "playback.completed", "purpose": "disclosure"})


@pytest.mark.parametrize("finish", ["confirm", "cancel", "revoke"])
def test_read_back_over_socket_then_finish(engine, client, worker, finish):
    token, grant_id, person_key = worker
    key = uuid4()
    before = seed_snapshot(engine)
    client.cookies.set(COOKIE_NAME, token)
    pins = client.get("/api/v2/households")
    assert pins.status_code == 200
    assert {r["public_id"] for r in pins.json()} == {f"H-{n:03}" for n in range(1, 7)}
    with client.websocket_connect("/ws/v2/session", headers={
        "origin": "https://testserver", "cookie": f"{COOKIE_NAME}={token}",
    }) as ws:
        start_maternal_visit(ws, key, person_key)
        ws.send_bytes(AUDIO_MARKER)
        clip = receive(ws, "agent.audio", "readback")
        version = clip["record_version"]
        assert clip["audio_b64"] and version > 0
        ws.send_json({"type": "playback.completed", "purpose": "readback", "record_version": version})
        assert rows(engine, key) == []
        confirm = {"type": "record.confirm", "record_version": version}
        if finish == "cancel":
            ws.send_json({"type": "session.cancel"})
            assert receive(ws, "session.ended")["reason"] == "cancelled"
        elif finish == "revoke":
            with Session(engine) as db:
                db.get(TerritoryAssignment, grant_id).ends_at = datetime.now(UTC)
                db.commit()
            ws.send_json(confirm)
            assert receive(ws, "session.ended")["reason"] == "revoked"
        else:
            ws.send_json(confirm)
            saved = receive(ws, "v2.visit.saved")
            ws.send_json(confirm)
            replay = receive(ws, "v2.visit.saved")
            assert saved["idempotent_replay"] is False and replay["idempotent_replay"] is True
            assert saved["visit_id"] == replay["visit_id"]

    assert seed_snapshot(engine) == before
    stored = rows(engine, key)
    if finish != "confirm":
        assert stored == []
        return
    assert len(stored) == 1 and str(stored[0].id) == saved["visit_id"]
    with Session(engine) as db:
        assert db.get(Person, stored[0].person_id).public_id == person_key
        for name in ("v2_visits", "visits", "audit_events"):
            data = "\n".join(db.scalars(text(f"SELECT row_to_json(r)::text FROM {name} r")))
            for marker in (TRANSCRIPT_MARKER, AUDIO_MARKER.decode(), AUDIO_MARKER.hex(),
                           base64.b64encode(AUDIO_MARKER).decode()):
                assert marker not in data
    history = client.get(f"/api/v2/people/{person_key}/visits")
    assert history.status_code == 200
    assert any(r["id"] == saved["visit_id"] and r["weight_kg"] == 52 for r in history.json())
    for path in ("/api/visits", "/api/followups"):
        response = client.get(path)
        assert response.status_code == 200 and response.json() == []


def test_confirmed_maternal_history_excludes_babys_note(engine, client, worker):
    token, _, person_key = worker
    key = uuid4()
    client.cookies.set(COOKIE_NAME, token)
    client.app.state.voice_provider = MockVoiceProvider(
        ["The baby's weight is 3 kg. The baby had a seizure.", "Next visit 28 November."],
        bytes_per_utterance=len(AUDIO_MARKER),
    )
    with client.websocket_connect("/ws/v2/session", headers={
        "origin": "https://testserver", "cookie": f"{COOKIE_NAME}={token}",
    }) as ws:
        start_maternal_visit(ws, key, person_key)
        ws.send_bytes(AUDIO_MARKER)
        receive(ws, "clarification.requested")
        ws.send_bytes(AUDIO_MARKER)
        clip = receive(ws, "agent.audio", "readback")
        assert clip["audio_b64"]
        ws.send_json({"type": "playback.completed", "purpose": "readback", "record_version": clip["record_version"]})
        ws.send_json({"type": "record.confirm", "record_version": clip["record_version"]})
        receipt = receive(ws, "v2.visit.saved")
    saved, = rows(engine, key)
    history = client.get(f"/api/v2/people/{person_key}/visits/{receipt['visit_id']}")
    assert history.status_code == 200
    assert (saved.weight_kg, saved.danger_signs, saved.requires_phc_referral) == (None, [], False)
    assert (history.json()["weight_kg"], history.json()["danger_signs"]) == (None, [])


def test_concurrent_different_payloads_resolve_to_winner_and_conflict(engine, worker):
    token, _, person_key = worker
    key = uuid4()
    start = V2SessionStart(household_id="H-003", person_id=person_key, client_visit_id=key)
    binding, _ = authorize_start(engine, token, start)
    barrier = Barrier(2)

    def submit(weight):
        record = VisitRecord(beneficiary_id=person_key, visit_type=VisitType.PNC, weight_kg=weight,
                             record_version=1, status=RecordStatus.CONFIRMED, next_visit_date=date(2026, 11, 28))
        barrier.wait(timeout=5)
        try:
            return weight, confirm_visit(engine, binding, record)
        except VisitSaveRefused as exc:
            return weight, exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, [52, 55]))
    stored = rows(engine, key)
    assert len(stored) == 1
    winner = dict(results)[stored[0].weight_kg]
    assert winner.visit_id == stored[0].id and not winner.idempotent_replay
    assert [v for _, v in results if isinstance(v, str)] == ["IDEMPOTENCY_KEY_CONFLICT"]


def test_expired_login_rejected_at_socket_handshake(engine, client, worker):
    token, _, _ = worker
    with Session(engine) as db:
        expired = create_session(db, user_for_token(db, token), -1)
        db.commit()
        before = db.scalar(select(func.count()).select_from(V2Visit))
    with pytest.raises(WebSocketDisconnect) as refused:
        with client.websocket_connect("/ws/v2/session", headers={
            "origin": "https://testserver", "cookie": f"{COOKIE_NAME}={expired}",
        }):
            pytest.fail("Expired session was accepted")
    assert refused.value.code == 4401
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(V2Visit)) == before
