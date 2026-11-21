"""V2 Phase 5: person-bound voice visit and exactly-once PostgreSQL save.

PostgreSQL only (Docker), disposable database, synthetic data only. Speech is a MOCK: a fake TTS
and scripted transcripts (no Gnani call, no credits). Covers identity binding, disclosure gating,
versioned correction + read-back acknowledgement, explicit Confirm-and-Save (spoken "ಹೌದು" never
saves), subject separation, revocation at every stage incl. the save transaction race, idempotent
confirmation under concurrency, history/receipt authorisation, WebSocket wiring and Round 1
isolation.
"""

import asyncio
import threading
import time
import uuid
from datetime import date

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.auth.deps import CSRF_HEADER, CSRF_VALUE
from app.auth.service import create_session, set_user_password
from app.core.config import get_settings
from app.db import visits_v2
from app.db.models import AuditEvent, Person, User, V2Visit, Visit
from app.db.visits_v2 import VisitSaveRefused, confirm_visit
from app.integrations.voice_provider import MockVoiceProvider
from app.main import create_app
from app.schemas.events import V2SessionStart
from app.schemas.visit import RecordStatus, VisitRecord, VisitType
from app.seed.demo import seed_demo
from app.services import prompts
from app.services.voice_v2 import StartRefused, V2VisitSession, authorize_start
from tests.conftest import alembic_config, disposable_pg_database, requires_postgres

pytestmark = requires_postgres
PW = "synthetic-test-password-789"  # test-only, disposable database
H = {CSRF_HEADER: CSRF_VALUE}
TODAY = date(2026, 11, 22)
NOTE = "weight 52 kg. next visit 28 November."
SENTINEL = "ZEBRAQUARTZSENTINEL"


@pytest.fixture(scope="module")
def engine():
    with disposable_pg_database("voice") as url:
        command.upgrade(alembic_config(), "head")
        eng = create_engine(url)
        with Session(eng) as db:
            seed_demo(db)
            for user in db.scalars(select(User).where(User.is_demo_data.is_(True))).all():
                set_user_password(db, user, PW)
            db.commit()
        yield eng
        eng.dispose()


def person(engine, name):
    with Session(engine) as db:
        return db.scalar(select(Person).where(Person.full_name == name))


def token_for(engine, username):
    with Session(engine) as db:
        token = create_session(db, db.scalar(select(User).where(User.username == username)), 12)
        db.commit()
        return token


def binding_for(engine, username, household, person_name, client_visit_id=None):
    p = person(engine, person_name)
    start = V2SessionStart(household_id=household, person_id=p.public_id,
                           client_visit_id=client_visit_id or uuid.uuid4())
    return authorize_start(engine, token_for(engine, username), start)


def v2_rows(engine, **where):
    with Session(engine) as db:
        stmt = select(V2Visit)
        for k, v in where.items():
            stmt = stmt.where(getattr(V2Visit, k) == v)
        return db.scalars(stmt).all()


def restore_assignments(engine):
    with Session(engine) as db:
        seed_demo(db)  # re-adds any ended demo assignment; never modifies existing rows


class V2Harness:
    """Drives V2VisitSession directly (MOCK speech) against the disposable PostgreSQL database."""

    def __init__(self, engine, username="demo_worker_a", household="H-003", person_name="Kavya Halli",
                 visit_type=VisitType.PNC):
        self.engine = engine
        self.events: list = []
        self.ended: list[str] = []
        self.binding, display = binding_for(engine, username, household, person_name)

        async def send(e):
            self.events.append(e)

        async def tts(_text):  # MOCK: no Gnani call
            await asyncio.sleep(0)
            return b"RIFF-fake"

        async def on_end(reason):
            self.ended.append(reason)

        self.s = V2VisitSession(send=send, tts=tts, engine=engine, binding=self.binding, visit_type=visit_type,
                                person_display_name=display, stt_model="MOCK", on_end=on_end,
                                today=lambda: TODAY, respond_delay_s=0)

    async def ready(self):
        await self.s.start()
        await asyncio.sleep(0.02)
        self.s.on_playback_completed("disclosure", None)

    async def say(self, text):
        await self.s.on_speech_start()
        await self.s.on_transcript(text, "en-IN")
        await asyncio.sleep(0.15)

    def ack_readback(self, version=None):
        self.s.on_playback_completed("readback", self.s.readback_version if version is None else version)

    def of(self, kind):
        return [e for e in self.events if e.type == kind]

    def errors(self):
        return [e.code for e in self.of("session.error")]


# ------------------------------------------------------------------ session start authorisation
def test_start_authorisation_refuses_out_of_scope_and_wrong_household(engine):
    kavya = person(engine, "Kavya Halli")
    cases = [
        ("demo_worker_b", "H-003", kavya.public_id, "NOT_AVAILABLE"),   # another territory
        ("demo_worker_a", "H-001", kavya.public_id, "NOT_AVAILABLE"),   # visible person, wrong household
        ("demo_worker_a", "H-003", "P-999", "NOT_AVAILABLE"),           # guessed id
        ("demo_worker_a", "H-007", "P-026", "NOT_AVAILABLE"),           # B's household and person
        ("demo_supervisor", "H-003", kavya.public_id, "ROLE_FORBIDDEN"),  # read-only role
        ("demo_admin", "H-003", kavya.public_id, "ROLE_FORBIDDEN"),
    ]
    for user, household, person_id, code in cases:
        start = V2SessionStart(household_id=household, person_id=person_id, client_visit_id=uuid.uuid4())
        with pytest.raises(StartRefused) as exc:
            authorize_start(engine, token_for(engine, user), start)
        assert exc.value.code == code, (user, household, person_id)
    with pytest.raises(StartRefused) as exc:
        authorize_start(engine, "not-a-real-token", V2SessionStart(household_id="H-003", person_id=kavya.public_id,
                                                                   client_visit_id=uuid.uuid4()))
    assert exc.value.code == "AUTH_EXPIRED"


def test_start_binds_the_exact_selected_person(engine):
    binding, display = binding_for(engine, "demo_worker_a", "h-003", "Baby of Kavya Halli")
    baby = person(engine, "Baby of Kavya Halli")
    assert binding.person_id == baby.id and binding.household_public_id == "H-003"
    assert display == "Baby of Kavya Halli" and binding.person_public_id == baby.public_id


# ------------------------------------------------------------------ disclosure, versions, confirmation
async def test_nothing_is_heard_before_the_disclosure_has_played(engine):
    h = V2Harness(engine)
    await h.s.start()
    await h.say(NOTE)
    assert h.s.record.record_version == 0 and not h.of("transcript.final")
    h.s.on_playback_completed("disclosure", None)
    await h.say(NOTE)
    assert h.s.record.weight_kg == 52 and h.s.record.beneficiary_id == h.binding.person_public_id


async def test_full_flow_saves_exactly_one_person_linked_visit(engine):
    h = V2Harness(engine)
    await h.ready()
    await h.say(NOTE)
    readback = [e for e in h.of("agent.audio") if e.purpose == "readback"]
    assert readback and readback[-1].record_version == h.s.record.record_version
    version = h.s.readback_version
    await h.s.confirm(version)                          # read-back not played yet
    assert "READBACK_NOT_FINISHED" in h.errors() and not v2_rows(engine, client_visit_id=h.binding.client_visit_id)
    h.ack_readback()
    await h.s.confirm(version)
    saved = h.of("v2.visit.saved")
    assert len(saved) == 1 and saved[0].idempotent_replay is False
    rows = v2_rows(engine, client_visit_id=h.binding.client_visit_id)
    kavya = person(engine, "Kavya Halli")
    assert len(rows) == 1
    row = rows[0]
    assert (row.person_id, row.household_id, row.worker_id) == (kavya.id, kavya.household_id, h.binding.worker_id)
    assert row.visit_type == "PNC" and row.subject_population == "maternal" and row.weight_kg == 52
    assert row.record_version == version and row.rule_status == "demo_only_pending_clinical_review"
    assert row.is_demo_data is True and row.ruleset_version.startswith("rules-")
    await h.s.confirm(version)                          # repeat: same receipt, no second row
    assert h.of("v2.visit.saved")[-1].visit_id == saved[0].visit_id and h.of("v2.visit.saved")[-1].idempotent_replay
    assert len(v2_rows(engine, client_visit_id=h.binding.client_visit_id)) == 1
    await h.say("weight 99 kg")                         # nothing more is heard after the save
    assert v2_rows(engine, client_visit_id=h.binding.client_visit_id)[0].weight_kg == 52


async def test_correction_invalidates_earlier_readback_and_its_acknowledgement(engine):
    h = V2Harness(engine)
    await h.ready()
    await h.say(NOTE)
    v1 = h.s.readback_version
    h.ack_readback()
    await h.say("no, weight is 55 kg")
    v2 = h.s.record.record_version
    assert v2 > v1 and h.s.playback_ack_version is None
    await h.s.confirm(v1)                               # stale version
    assert "CONFIRMATION_REJECTED" in h.errors() and not v2_rows(engine, client_visit_id=h.binding.client_visit_id)
    h.s.on_playback_completed("readback", v1)           # a stale acknowledgement counts for nothing
    await h.s.confirm(h.s.readback_version)
    assert "READBACK_NOT_FINISHED" in h.errors() and not v2_rows(engine, client_visit_id=h.binding.client_visit_id)
    h.ack_readback()
    await h.s.confirm(h.s.readback_version)
    assert v2_rows(engine, client_visit_id=h.binding.client_visit_id)[0].weight_kg == 55


async def test_spoken_yes_never_saves(engine):
    h = V2Harness(engine)
    await h.ready()
    await h.say(NOTE)
    h.ack_readback()
    await h.say("ಹೌದು")
    assert not v2_rows(engine, client_visit_id=h.binding.client_visit_id)
    assert any(e.text == prompts.PRESS_TO_SAVE for e in h.of("agent.audio"))


async def test_another_beneficiary_or_visit_type_in_speech_never_moves_the_record(engine):
    h = V2Harness(engine)
    await h.ready()
    await h.say("ID 1 2 3 4. weight 50 kg")
    assert h.of("clarification.requested")[-1].field == "subject"
    assert h.s.record.beneficiary_id == h.binding.person_public_id and h.s.record.weight_kg is None
    await h.say("newborn visit, weight 3 kg")
    assert h.of("clarification.requested")[-1].field == "subject"
    assert h.s.record.visit_type == VisitType.PNC and h.s.record.weight_kg is None


async def test_unknown_visit_type_stays_unresolved(engine):
    h = V2Harness(engine, person_name="Aarav Hebbar", household="H-006", visit_type=VisitType.UNKNOWN)
    await h.ready()
    await h.say(NOTE)
    assert h.s.record.visit_type == VisitType.UNKNOWN          # not inferred from the enrolment
    assert h.of("clarification.requested")[-1].field == "visit_type"


async def test_mother_and_newborn_signs_are_kept_on_the_right_person(engine):
    baby = V2Harness(engine, person_name="Baby of Kavya Halli", visit_type=VisitType.NEWBORN)
    await baby.ready()
    await baby.say("mother has bleeding")
    other = [a for a in baby.of("alert.raised") if a.scope == "other_person"]
    assert other and other[0].rule_ids == ["MAT_VAGINAL_BLEEDING"]  # surfaced at once...
    assert baby.s.record.danger_signs == []                        # ...never recorded on the baby
    await baby.say("baby has fever")
    assert baby.s.record.danger_signs == ["NB_FEVER"]
    mother = V2Harness(engine, person_name="Kavya Halli", visit_type=VisitType.PNC)
    await mother.ready()
    await mother.say("baby has fever")
    assert mother.s.record.danger_signs == []                      # newborn sign not on the mother
    assert [a.scope for a in mother.of("alert.raised")] == ["other_person"]


# ------------------------------------------------------------------ revocation at every stage
async def test_grant_revoked_mid_session_ends_it_without_saving(engine):
    h = V2Harness(engine)
    await h.ready()
    await h.say(NOTE)
    h.ack_readback()
    with Session(engine) as db:
        db.execute(text("UPDATE territory_assignments SET ends_at = now() WHERE ends_at IS NULL AND user_id = "
                        "(SELECT id FROM users WHERE username = 'demo_worker_a')"))
        db.commit()
    try:
        await h.s.confirm(h.s.readback_version)
        assert h.ended == ["revoked"] and h.of("session.ended")[-1].reason == "revoked"
        assert h.s.record.record_version == 0                  # draft discarded
        assert not v2_rows(engine, client_visit_id=h.binding.client_visit_id)
    finally:
        restore_assignments(engine)


async def test_logout_elsewhere_ends_the_session_without_saving(engine):
    h = V2Harness(engine)
    await h.ready()
    await h.say(NOTE)
    h.ack_readback()
    with Session(engine) as db:
        db.execute(text("UPDATE auth_sessions SET revoked_at = now() WHERE token_hash = :t"),
                   {"t": h.binding.session_token_hash})
        db.commit()
    await h.s.confirm(h.s.readback_version)
    assert h.ended == ["revoked"] and not v2_rows(engine, client_visit_id=h.binding.client_visit_id)


async def test_person_moved_to_another_household_blocks_the_save(engine):
    h = V2Harness(engine)
    await h.ready()
    await h.say(NOTE)
    h.ack_readback()
    kavya = person(engine, "Kavya Halli")
    with Session(engine) as db:
        db.execute(text("UPDATE people SET household_id = (SELECT id FROM households WHERE public_id = 'H-004') "
                        "WHERE id = :p"), {"p": kavya.id})
        db.commit()
    try:
        await h.s.confirm(h.s.readback_version)
        assert h.ended == ["revoked"] and not v2_rows(engine, client_visit_id=h.binding.client_visit_id)
    finally:
        with Session(engine) as db:
            db.execute(text("UPDATE people SET household_id = :hh WHERE id = :p"),
                       {"hh": kavya.household_id, "p": kavya.id})
            db.commit()


async def test_periodic_revalidation_ends_a_session_after_revocation(engine):
    h = V2Harness(engine)
    await h.ready()
    assert await h.s.revalidate() is True
    with Session(engine) as db:
        db.execute(text("UPDATE users SET active = false WHERE username = 'demo_worker_a'"))
        db.commit()
    try:
        assert await h.s.revalidate() is False and h.ended == ["revoked"]
    finally:
        with Session(engine) as db:
            db.execute(text("UPDATE users SET active = true WHERE username = 'demo_worker_a'"))
            db.commit()


def confirmed_record(binding, weight=52.0, version=3):
    return VisitRecord(beneficiary_id=binding.person_public_id, visit_type=VisitType.PNC, weight_kg=weight,
                       next_visit_date=date(2026, 11, 28), status=RecordStatus.CONFIRMED, record_version=version)


def test_revocation_committed_first_wins_over_the_save(engine):
    binding, _ = binding_for(engine, "demo_worker_a", "H-003", "Kavya Halli")
    with Session(engine) as db:
        db.execute(text("UPDATE territory_assignments SET ends_at = now() WHERE ends_at IS NULL AND user_id = :u"),
                   {"u": binding.worker_id})
        db.commit()
    try:
        with pytest.raises(VisitSaveRefused) as exc:
            confirm_visit(engine, binding, confirmed_record(binding))
        assert exc.value.code == "AUTH_REVOKED" and not v2_rows(engine, client_visit_id=binding.client_visit_id)
    finally:
        restore_assignments(engine)


def test_a_save_holding_its_locks_makes_the_revocation_wait(engine, monkeypatch):
    """Save first: the concurrent revocation waits for the visit to commit (FOR SHARE vs UPDATE)."""
    binding, _ = binding_for(engine, "demo_worker_a", "H-003", "Kavya Halli")
    original = visits_v2._existing
    inside = threading.Event()

    def slow_existing(db, b):
        inside.set()
        time.sleep(1.5)  # hold the share locks
        return original(db, b)

    monkeypatch.setattr(visits_v2, "_existing", slow_existing)
    result = {}
    saver = threading.Thread(target=lambda: result.update(r=confirm_visit(engine, binding, confirmed_record(binding))))
    saver.start()
    assert inside.wait(5)
    started = time.monotonic()
    with Session(engine) as db:
        db.execute(text("SET lock_timeout = '10s'"))
        db.execute(text("UPDATE territory_assignments SET ends_at = now() WHERE ends_at IS NULL AND user_id = :u"),
                   {"u": binding.worker_id})
        db.commit()
    waited = time.monotonic() - started
    saver.join(10)
    try:
        assert waited > 0.8                                    # the revocation was blocked
        assert result["r"].idempotent_replay is False and len(v2_rows(engine, client_visit_id=binding.client_visit_id)) == 1
    finally:
        restore_assignments(engine)


# ------------------------------------------------------------------ exactly once
def test_concurrent_identical_confirms_insert_one_row(engine):
    binding, _ = binding_for(engine, "demo_worker_a", "H-005", "Divya Kallur")
    record = confirmed_record(binding)
    barrier, results = threading.Barrier(4), []

    def go():
        barrier.wait()
        results.append(confirm_visit(engine, binding, record))

    threads = [threading.Thread(target=go) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert len(results) == 4 and len({r.visit_id for r in results}) == 1
    assert sum(not r.idempotent_replay for r in results) == 1
    assert len(v2_rows(engine, client_visit_id=binding.client_visit_id)) == 1


def test_reused_key_with_different_content_is_refused(engine):
    binding, _ = binding_for(engine, "demo_worker_a", "H-005", "Divya Kallur")
    first = confirm_visit(engine, binding, confirmed_record(binding, weight=60))
    with pytest.raises(VisitSaveRefused) as exc:
        confirm_visit(engine, binding, confirmed_record(binding, weight=61))
    assert exc.value.code == "IDEMPOTENCY_KEY_CONFLICT"
    rows = v2_rows(engine, client_visit_id=binding.client_visit_id)
    assert len(rows) == 1 and rows[0].id == first.visit_id and rows[0].weight_kg == 60


def test_separate_visits_for_the_same_person_are_allowed(engine):
    a, _ = binding_for(engine, "demo_worker_a", "H-001", "Lakshmi Hosamane")
    b, _ = binding_for(engine, "demo_worker_a", "H-001", "Lakshmi Hosamane")
    confirm_visit(engine, a, confirmed_record(a))
    confirm_visit(engine, b, confirmed_record(b))
    lakshmi = person(engine, "Lakshmi Hosamane")
    assert len(v2_rows(engine, person_id=lakshmi.id)) == 2


# ------------------------------------------------------------------ history and receipts (REST)
@pytest.fixture
def client(engine):
    with TestClient(create_app(engine), base_url="https://testserver") as c:
        yield c


def login(client, username):
    assert client.post("/api/v2/auth/login", json={"username": username, "password": PW}, headers=H).status_code == 200


def test_history_and_receipt_are_scoped(client, engine):
    binding, _ = binding_for(engine, "demo_worker_a", "H-002", "Savitha Kerekatte")
    receipt = confirm_visit(engine, binding, confirmed_record(binding))
    savitha = person(engine, "Savitha Kerekatte")
    login(client, "demo_worker_a")
    history = client.get(f"/api/v2/people/{savitha.public_id}/visits").json()
    assert [v["id"] for v in history] == [str(receipt.visit_id)]
    assert history[0]["person_public_id"] == savitha.public_id and history[0]["household_public_id"] == "H-002"
    assert "transcript" not in str(history[0]).lower()
    one = client.get(f"/api/v2/people/{savitha.public_id}/visits/{receipt.visit_id}")
    assert one.status_code == 200
    assert client.get(f"/api/v2/visits/by-client-key/{binding.client_visit_id}").json()["id"] == str(receipt.visit_id)
    other = person(engine, "Manjunath Kerekatte")                   # same household, other person
    assert client.get(f"/api/v2/people/{other.public_id}/visits").json() == []
    assert client.get(f"/api/v2/people/{other.public_id}/visits/{receipt.visit_id}").status_code == 404
    assert client.get(f"/api/v2/visits/by-client-key/{uuid.uuid4()}").status_code == 404
    login(client, "demo_worker_b")                                   # other territory: indistinguishable
    assert client.get(f"/api/v2/people/{savitha.public_id}/visits").status_code == 404
    assert client.get(f"/api/v2/people/{savitha.public_id}/visits/{receipt.visit_id}").status_code == 404
    assert client.get(f"/api/v2/visits/by-client-key/{binding.client_visit_id}").status_code == 404
    login(client, "demo_supervisor")                                 # granted both: read-only history
    assert len(client.get(f"/api/v2/people/{savitha.public_id}/visits").json()) == 1
    assert client.get(f"/api/v2/visits/by-client-key/{binding.client_visit_id}").status_code == 404  # not theirs


def test_round1_store_and_routes_stay_isolated(client, engine):
    with Session(engine) as db:
        before = db.scalar(select(func.count()).select_from(Visit))
    binding, _ = binding_for(engine, "demo_worker_a", "H-004", "Rekha Doddamane")
    confirm_visit(engine, binding, confirmed_record(binding))
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Visit)) == before  # Round 1 table untouched
    assert client.get("/api/visits").status_code == 404
    assert client.get("/api/followups").status_code == 404


async def test_no_transcript_text_is_persisted(engine):
    h = V2Harness(engine, household="H-004", person_name="Suresh Doddamane", visit_type=VisitType.UNKNOWN)
    await h.ready()
    await h.say(f"{SENTINEL} ANC visit. weight 70 kg. next visit 28 November.")
    with Session(engine) as db:
        dump = " ".join(str(r) for r in db.execute(text(
            "SELECT row_to_json(v)::text FROM v2_visits v UNION ALL SELECT row_to_json(a)::text FROM audit_events a"
        )).scalars())
    assert SENTINEL not in dump


# ------------------------------------------------------------------ WebSocket wiring (MOCK provider)
@pytest.fixture
def voice_on(monkeypatch):
    monkeypatch.setenv("V2_VOICE_ENABLED", "true")
    get_settings.cache_clear()
    yield
    monkeypatch.undo()
    get_settings.cache_clear()


ORIGIN = {"origin": "https://testserver"}


def ws_headers(client):
    """Same-origin handshake with the login cookie (as the browser sends it)."""
    return {**ORIGIN, "cookie": f"asha_session={client.cookies.get('asha_session')}"}


def recv_until(ws, kind, limit=60):
    seen = []
    for _ in range(limit):
        event = ws.receive_json()
        seen.append(event)
        if event["type"] == kind:
            return event, seen
    raise AssertionError(f"{kind} not received; got {[e['type'] for e in seen]}")


def start_frame(household, person_public_id, client_visit_id=None, visit_type="PNC"):
    return {"type": "v2.session.start", "household_id": household, "person_id": person_public_id,
            "client_visit_id": str(client_visit_id or uuid.uuid4()), "visit_type": visit_type}


def test_voice_disabled_by_default(client):
    login(client, "demo_worker_a")
    with client.websocket_connect("/ws/v2/session", headers=ws_headers(client)) as ws:
        assert ws.receive_json()["code"] == "NOT_READY"


def test_ws_refuses_a_foreign_person_before_any_speech(client, engine, voice_on):
    client.app.state.voice_provider = MockVoiceProvider([NOTE], bytes_per_utterance=1024)
    login(client, "demo_worker_b")
    kavya = person(engine, "Kavya Halli")
    with client.websocket_connect("/ws/v2/session", headers=ws_headers(client)) as ws:
        ws.send_json(start_frame("H-003", kavya.public_id))
        event = ws.receive_json()
        assert event["type"] == "session.error" and event["code"] == "NOT_AVAILABLE"
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_ws_full_visit_saves_once_and_identity_cannot_change(client, engine, voice_on):
    client.app.state.voice_provider = MockVoiceProvider([NOTE], bytes_per_utterance=1024)
    login(client, "demo_worker_a")
    nagamma = person(engine, "Nagamma Halli")
    key = uuid.uuid4()
    with client.websocket_connect("/ws/v2/session", headers=ws_headers(client)) as ws:
        ws.send_json(start_frame("H-003", nagamma.public_id, key, visit_type="unknown"))
        bound, _ = recv_until(ws, "v2.session.bound")
        assert bound["person_public_id"] == nagamma.public_id and bound["household_public_id"] == "H-003"
        recv_until(ws, "agent.audio")                                  # disclosure
        ws.send_bytes(b"\x00" * 2048)                                  # before the disclosure ack: ignored
        ws.send_json({"type": "playback.completed", "purpose": "disclosure"})
        ws.send_json(start_frame("H-007", "P-026", key))               # try to switch subject
        err, _ = recv_until(ws, "session.error")
        assert err["code"] == "SUBJECT_IMMUTABLE"
        ws.send_bytes(b"\x00" * 2048)                                  # mock STT emits the note
        clar, _ = recv_until(ws, "clarification.requested")
        assert clar["field"] == "visit_type"                           # unknown stays unresolved
        assert not v2_rows(engine, client_visit_id=key)
    assert not v2_rows(engine, client_visit_id=key)                    # disconnect: nothing saved


def test_ws_second_tab_with_the_same_visit_supersedes_the_first(client, engine, voice_on):
    client.app.state.voice_provider = MockVoiceProvider([], bytes_per_utterance=1024)
    login(client, "demo_worker_a")
    kavya = person(engine, "Kavya Halli")
    key = uuid.uuid4()
    with client.websocket_connect("/ws/v2/session", headers=ws_headers(client)) as first:
        first.send_json(start_frame("H-003", kavya.public_id, key))
        recv_until(first, "v2.session.bound")
        with client.websocket_connect("/ws/v2/session", headers=ws_headers(client)) as second:
            second.send_json(start_frame("H-003", kavya.public_id, key))
            recv_until(second, "v2.session.bound")
            ended, _ = recv_until(first, "session.ended")
            assert ended["reason"] == "superseded"


def test_mock_provider_is_refused_outside_the_e2e_database(engine, monkeypatch):
    monkeypatch.setenv("VOICE_PROVIDER_MODE", "mock")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="_e2e"):
            with TestClient(create_app(engine)):
                pass
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_refused_start_is_audited_without_names(client, engine, voice_on):
    client.app.state.voice_provider = MockVoiceProvider([], bytes_per_utterance=1024)
    login(client, "demo_worker_b")
    with Session(engine) as db:
        before = db.scalar(select(func.max(AuditEvent.id)))
    kavya = person(engine, "Kavya Halli")
    with client.websocket_connect("/ws/v2/session", headers=ws_headers(client)) as ws:
        ws.send_json(start_frame("H-003", kavya.public_id))
        assert ws.receive_json()["code"] == "NOT_AVAILABLE"
    with Session(engine) as db:
        rows = db.scalars(select(AuditEvent).where(AuditEvent.id > before)).all()
    assert [r.action for r in rows] == ["access.denied"] and "Kavya" not in str(rows[0].details)


async def test_routine_visit_shantamma_full_flow_and_correction(client, engine):
    """H-005 -> Shantamma Kallur (P-020) -> ROUTINE: weight + date -> correction -> PostgreSQL + history."""
    h = V2Harness(engine, household="H-005", person_name="Shantamma Kallur", visit_type=VisitType.ROUTINE)
    shantamma = person(engine, "Shantamma Kallur")
    assert shantamma.public_id == "P-020"
    await h.ready()
    await h.say("Weight 52 kg, ಮುಂದಿನ ಭೇಟಿ ನವೆಂಬರ್ ಇಪ್ಪತ್ತೆಂಟು.")
    assert not h.of("clarification.requested")
    assert h.s.record.visit_type == VisitType.ROUTINE
    assert h.s.record.weight_kg == 52
    assert h.s.record.next_visit_date == date(2026, 11, 28)
    assert h.s.record.beneficiary_id == "P-020"
    v1 = h.s.readback_version
    assert v1 is not None and any(e.purpose == "readback" and e.record_version == v1 for e in h.of("agent.audio"))
    await h.s.confirm(v1)
    assert "READBACK_NOT_FINISHED" in h.errors()
    h.ack_readback(v1)

    await h.say("ಇಲ್ಲ, ತೂಕ ಐವತ್ತೈದು ಕಿಲೋ.")
    v2 = h.s.record.record_version
    assert v2 > v1 and h.s.record.weight_kg == 55 and h.s.playback_ack_version is None
    await h.s.confirm(v1)
    assert "CONFIRMATION_REJECTED" in h.errors()
    assert not v2_rows(engine, client_visit_id=h.binding.client_visit_id)
    h.ack_readback()
    await h.s.confirm(h.s.readback_version)

    saved = h.of("v2.visit.saved")
    assert len(saved) == 1
    rows = v2_rows(engine, client_visit_id=h.binding.client_visit_id)
    assert len(rows) == 1
    row = rows[0]
    assert (row.person_id, row.visit_type, row.subject_population, row.weight_kg) == (
        shantamma.id, "routine", "unresolved", 55.0
    )
    assert row.danger_signs == [] and row.requires_phc_referral is False

    login(client, "demo_worker_a")
    history = client.get("/api/v2/people/P-020/visits").json()
    assert any(v["id"] == str(row.id) and v["visit_type"] == "routine" and v["weight_kg"] == 55 for v in history)


async def test_routine_visit_invents_no_clinical_alerts(engine):
    h = V2Harness(engine, household="H-005", person_name="Shantamma Kallur", visit_type=VisitType.ROUTINE)
    await h.ready()
    await h.say("Weight 52 kg. fever and bleeding. ಮುಂದಿನ ಭೇಟಿ ನವೆಂಬರ್ ಇಪ್ಪತ್ತೆಂಟು.")
    assert not h.of("alert.raised")
    assert h.s.record.danger_signs == [] and h.s.record.requires_phc_referral is False


async def test_clarification_loop_and_conversational_replies(engine):
    """Unresolved visit type asks once, handles negations/greetings without ASK_WHAT_TO_CHANGE loops."""
    h = V2Harness(engine, household="H-005", person_name="Shantamma Kallur", visit_type=VisitType.UNKNOWN)
    await h.ready()
    await h.say("Weight 52 kg, ಮುಂದಿನ ಭೇಟಿ ನವೆಂಬರ್ ಇಪ್ಪತ್ತೆಂಟು.")
    assert [c.field for c in h.of("clarification.requested")] == ["visit_type"]

    await h.say("Hello.")
    assert len(h.of("clarification.requested")) == 1
    assert not any(e.text == prompts.ASK_WHAT_TO_CHANGE for e in h.of("agent.audio"))

    await h.say("ಇಲ್ಲ.")
    assert h.s.record.visit_type == VisitType.UNKNOWN
    assert not any(e.text == prompts.ASK_WHAT_TO_CHANGE for e in h.of("agent.audio"))
    assert [e.text for e in h.of("agent.audio") if e.purpose == "clarification"][-1] == prompts.ASK_ROUTINE_VISIT

    await h.say("ಯಾವುದೂ ಅಲ್ಲ.")
    assert h.s.record.visit_type == VisitType.UNKNOWN
    assert not any(e.text == prompts.ASK_WHAT_TO_CHANGE for e in h.of("agent.audio"))
    # No repeated identical prompt loop.
    assert [e.text for e in h.of("agent.audio") if e.purpose == "clarification"].count(prompts.ASK_ROUTINE_VISIT) == 1

    # Confirming the routine visit prompt resolves once and proceeds to read-back.
    h2 = V2Harness(engine, household="H-005", person_name="Shantamma Kallur", visit_type=VisitType.UNKNOWN)
    await h2.ready()
    await h2.say("Weight 52 kg, ಮುಂದಿನ ಭೇಟಿ ನವೆಂಬರ್ ಇಪ್ಪತ್ತೆಂಟು.")
    await h2.say("ಇಲ್ಲ.")
    await h2.say("ಹೌದು")
    assert h2.s.record.visit_type == VisitType.ROUTINE
    assert h2.s.readback_version is not None
    h2.ack_readback()

    # In awaiting confirmation: greetings, no-change, and standalone "ಇಲ್ಲ" do not ask ASK_WHAT_TO_CHANGE.
    for phrase in ("Hello.", "ಯಾವುದೂ ಬದಲಾವಣೆ ಇಲ್ಲ.", "ಇಲ್ಲ."):
        await h2.say(phrase)
    assert not any(e.text == prompts.ASK_WHAT_TO_CHANGE for e in h2.of("agent.audio"))

    # Speaking "Normal visit." resolves UNKNOWN directly to ROUTINE.
    h3 = V2Harness(engine, household="H-005", person_name="Shantamma Kallur", visit_type=VisitType.UNKNOWN)
    await h3.ready()
    await h3.say("Normal visit. Weight 52 kg, ಮುಂದಿನ ಭೇಟಿ ನವೆಂಬರ್ ಇಪ್ಪತ್ತೆಂಟು.")
    assert h3.s.record.visit_type == VisitType.ROUTINE
    assert h3.s.readback_version is not None
