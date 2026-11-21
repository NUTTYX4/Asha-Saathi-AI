"""V2 Phase 3: synthetic households/people seed, PostGIS pins, integrity, and territory scoping.

PostgreSQL/PostGIS only (run inside Docker). Uses a disposable test database; synthetic data only.
"""

import uuid

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import CSRF_HEADER, CSRF_VALUE
from app.auth.service import set_user_password
from app.db.models import AuditEvent, Household, Person, PersonRelationship, Territory, User
from app.main import create_app
from app.seed import demo_data as D
from app.seed.demo import check_demo, seed_demo
from tests.conftest import alembic_config, disposable_pg_database, requires_postgres

pytestmark = requires_postgres
PW = "synthetic-test-password-123"  # test-only, set on a disposable database
H = {CSRF_HEADER: CSRF_VALUE}


@pytest.fixture(scope="module")
def engine():
    with disposable_pg_database("households") as url:
        command.upgrade(alembic_config(), "head")
        eng = create_engine(url)
        with Session(eng) as db:
            first = seed_demo(db)
            assert first.created["households"] == 12 and first.created["people"] == 50
            for user in db.scalars(select(User).where(User.is_demo_data.is_(True))).all():
                set_user_password(db, user, PW)
            db.commit()
        yield eng
        eng.dispose()


@pytest.fixture
def client(engine):
    with TestClient(create_app(engine), base_url="https://testserver") as c:
        yield c


def login(client, username):
    r = client.post("/api/v2/auth/login", json={"username": username, "password": PW}, headers=H)
    assert r.status_code == 200, r.text
    return r


# ------------------------------------------------------------------ dataset invariants
def test_exact_counts_and_territories(engine):
    with Session(engine) as db:
        report = check_demo(db)
    assert report["violations"] == []
    assert report["households"] == 12
    assert report["people"] == 50
    assert report["territories"] == 2
    assert report["households_per_territory"] == {"DEMO-A": 6, "DEMO-B": 6}
    assert report["accounts"]["demo_worker_a"]["demo_households_visible"] == 6
    assert report["accounts"]["demo_worker_b"]["demo_households_visible"] == 6
    assert report["accounts"]["demo_supervisor"]["demo_households_visible"] == 12


def test_every_member_in_expected_household(engine):
    expected = {pid: hh for (hh, _), pid in D.person_public_ids().items()}
    with Session(engine) as db:
        rows = db.execute(select(Person.public_id, Household.public_id)
                          .join(Household, Household.id == Person.household_id)).all()
    assert len(rows) == 50
    assert {p: h for p, h in rows} == expected


def test_member_counts_match_specification(engine):
    with Session(engine) as db:
        counts = dict(db.execute(select(Household.public_id, func.count(Person.id))
                                 .join(Person, Person.household_id == Household.id)
                                 .group_by(Household.public_id)).all())
    assert counts == D.EXPECTED_MEMBER_COUNTS


def test_mother_newborn_relationship_in_h003(engine):
    with Session(engine) as db:
        mother = db.scalar(select(Person).where(Person.full_name == "Kavya Halli"))
        baby = db.scalar(select(Person).where(Person.full_name == "Baby of Kavya Halli"))
        edge = db.scalar(select(PersonRelationship).where(
            PersonRelationship.person_id == mother.id, PersonRelationship.related_person_id == baby.id,
            PersonRelationship.relationship_type == "mother_of"))
    assert edge is not None
    assert mother.household_id == baby.household_id


def test_pins_distinct_separated_and_in_cubbon_park_area(engine):
    with engine.connect() as conn:
        n, distinct, min_sep = conn.execute(text("""
            SELECT count(*), count(DISTINCT ST_AsText(location::geometry)),
                   (SELECT min(ST_Distance(a.location, b.location)) FROM households a JOIN households b ON a.id < b.id)
            FROM households""")).one()
        bbox_ok = conn.execute(text("""
            SELECT bool_and(ST_Y(location::geometry) BETWEEN 12.9679 AND 12.9804
                        AND ST_X(location::geometry) BETWEEN 77.5879 AND 77.5990) FROM households""")).scalar()
        stored = dict(conn.execute(text(
            "SELECT public_id, ST_AsText(location::geometry) FROM households")).all())
    assert n == distinct == 12
    assert min_sep >= D.MIN_PIN_SEPARATION_M
    assert bbox_ok  # within the Cubbon Park bounding box (OSM way 22895320)
    for public_id, (lat, lon) in D.PINS.items():
        assert stored[public_id] == f"POINT({lon} {lat})"


def test_seed_is_idempotent(engine):
    with Session(engine) as db:
        before = {t: db.scalar(text(f"SELECT count(*) FROM {t}")) for t in
                  ("territories", "users", "territory_assignments", "households", "people",
                   "person_relationships", "programme_enrolments", "household_surveys")}
        report = seed_demo(db)
        after = {t: db.scalar(text(f"SELECT count(*) FROM {t}")) for t in before}
    assert sum(report.created.values()) == 0
    assert before == after


def test_seed_never_overwrites_existing_rows(engine):
    with Session(engine) as db:
        h = db.scalar(select(Household).where(Household.public_id == "H-004"))
        h.label = "Edited by worker"
        u = db.scalar(select(User).where(User.username == "demo_worker_a"))
        old_hash = u.password_hash
        db.commit()
        seed_demo(db)
        db.expire_all()
        assert db.scalar(select(Household.label).where(Household.public_id == "H-004")) == "Edited by worker"
        assert db.scalar(select(User.password_hash).where(User.username == "demo_worker_a")) == old_hash
        h = db.scalar(select(Household).where(Household.public_id == "H-004"))
        h.label = "Demo House 4, Synthetic Lane A"
        db.commit()


def test_pregnancy_and_newborn_status_only_from_explicit_enrolment(engine):
    """Nothing is inferred: only the people the dataset enrols have programme rows."""
    expected = sum(len(spec.enrolments) for spec in D.HOUSEHOLDS)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM programme_enrolments")).scalar() == expected


# ------------------------------------------------------------------ database integrity
@pytest.mark.parametrize("sql", [
    # person in a household that does not exist
    "INSERT INTO people (id, public_id, household_id, full_name, sex, relationship_to_head, residence_status, active, is_demo_data) "
    "VALUES (gen_random_uuid(), 'P-900', gen_random_uuid(), 'X', 'female', 'head', 'resident', true, false)",
    # bad public ID format (two statements; the territory insert rolls back with the failure)
    ("INSERT INTO territories (id, code, name, active, is_demo_data) VALUES (gen_random_uuid(), 'ZZ', 'Z', true, false)",
     "INSERT INTO households (id, public_id, territory_id, label, location, location_source, is_demo_data) "
     "SELECT gen_random_uuid(), 'HOUSE-1', id, 'x', 'SRID=4326;POINT(77.59 12.97)', 'manual', false "
     "FROM territories WHERE code='ZZ'"),
    # self relationship
    "INSERT INTO person_relationships (id, person_id, related_person_id, relationship_type, source) "
    "SELECT gen_random_uuid(), id, id, 'mother_of', 'worker_entry' FROM people WHERE public_id='P-001'",
    # unknown relationship type
    "INSERT INTO person_relationships (id, person_id, related_person_id, relationship_type, source) "
    "SELECT gen_random_uuid(), a.id, b.id, 'owner_of', 'worker_entry' FROM people a, people b "
    "WHERE a.public_id='P-001' AND b.public_id='P-002'",
    # unknown programme
    "INSERT INTO programme_enrolments (id, person_id, programme, status, source, started_on) "
    "SELECT gen_random_uuid(), id, 'DIAGNOSIS', 'active', 'worker_entry', current_date FROM people WHERE public_id='P-001'",
    # duplicate household public ID
    "INSERT INTO households (id, public_id, territory_id, label, location, location_source, is_demo_data) "
    "SELECT gen_random_uuid(), 'H-001', territory_id, 'dup', location, 'manual', false FROM households WHERE public_id='H-001'",
    # recorded age without the date it was recorded
    "UPDATE people SET recorded_age_years = 30, age_recorded_on = NULL WHERE public_id='P-001'",
])
def test_constraints_reject_bad_data(engine, sql):
    statements = sql if isinstance(sql, tuple) else (sql,)
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))


def test_household_with_members_cannot_be_deleted(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM households WHERE public_id = 'H-001'"))


def test_territory_with_households_cannot_be_deleted(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM territories WHERE code = 'DEMO-A'"))


# ------------------------------------------------------------------ authorization (REST)
A_HOUSES = [f"H-{n:03d}" for n in range(1, 7)]
B_HOUSES = [f"H-{n:03d}" for n in range(7, 13)]


def test_unauthenticated_cannot_list_households(client):
    assert client.get("/api/v2/households").status_code == 401
    assert client.get("/api/v2/households/H-001").status_code == 401
    assert client.get("/api/v2/people/P-001").status_code == 401


def test_worker_a_sees_only_territory_a(client):
    login(client, "demo_worker_a")
    pins = client.get("/api/v2/households").json()
    assert [p["public_id"] for p in pins] == A_HOUSES
    assert all(p["territory_code"] == "DEMO-A" for p in pins)


def test_worker_b_sees_only_territory_b(client):
    login(client, "demo_worker_b")
    assert [p["public_id"] for p in client.get("/api/v2/households").json()] == B_HOUSES


@pytest.mark.parametrize("user", ["demo_supervisor", "demo_admin"])
def test_supervisor_and_admin_see_all_twelve(client, user):
    login(client, user)
    assert [p["public_id"] for p in client.get("/api/v2/households").json()] == A_HOUSES + B_HOUSES


def test_map_pins_carry_no_programme_or_clinical_data(client):
    login(client, "demo_worker_a")
    pin = client.get("/api/v2/households").json()[2]
    assert set(pin) == {"id", "public_id", "label", "landmark", "territory_code", "latitude", "longitude",
                        "location_source", "member_count", "is_demo_data"}
    assert pin["is_demo_data"] is True and pin["location_source"] == "synthetic_demo"


def test_worker_a_cannot_reach_territory_b_by_public_id_uuid_members_or_person(client, engine):
    login(client, "demo_worker_a")
    with Session(engine) as db:
        h7 = db.scalar(select(Household).where(Household.public_id == "H-007"))
        p_b = db.scalar(select(Person).where(Person.household_id == h7.id))
    for path in ("/api/v2/households/H-007", f"/api/v2/households/{h7.id}",
                 "/api/v2/households/h-007", "/api/v2/households/H-007/members",
                 f"/api/v2/people/{p_b.public_id}", f"/api/v2/people/{p_b.id}"):
        assert client.get(path).status_code == 404, path
    # Same response as a household that does not exist at all (no ID probing).
    assert client.get("/api/v2/households/H-999").json() == client.get("/api/v2/households/H-007").json()
    assert client.get(f"/api/v2/households/{uuid.uuid4()}").status_code == 404


def test_worker_a_reads_own_household_members_with_relationships(client):
    login(client, "demo_worker_a")
    detail = client.get("/api/v2/households/H-003").json()
    assert detail["member_count"] == 4 and detail["latest_survey"]["survey_version"] == "demo-v1"
    members = client.get("/api/v2/households/H-003/members").json()
    by_name = {m["full_name"]: m for m in members}
    baby = by_name["Baby of Kavya Halli"]
    assert baby["age"]["basis"] == "date_of_birth" and baby["age"]["days"] is not None
    assert [p["programme"] for p in baby["programmes"]] == ["NEWBORN"]
    assert {"relationship_type": "mother_of", "direction": "incoming",
            "other_person_public_id": by_name["Kavya Halli"]["public_id"],
            "other_person_name": "Kavya Halli"} in baby["relationships"]
    assert by_name["Nagamma Halli"]["programmes"] == []  # nothing inferred from age/role


def test_worker_adds_member_in_own_territory_only_and_it_is_audited(client, engine):
    login(client, "demo_worker_a")
    body = {"full_name": "Synthetic New Member", "sex": "female", "relationship_to_head": "daughter",
            "recorded_age_years": 3}
    assert client.post("/api/v2/households/H-007/members", json=body, headers=H).status_code == 404
    assert client.post("/api/v2/households/H-001/members", json=body).status_code == 403  # no CSRF header
    r = client.post("/api/v2/households/H-001/members", json=body, headers=H)
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["public_id"] == "P-051" and created["is_demo_data"] is False
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Person).where(Person.is_demo_data.is_(True))) == 50
        event = db.scalar(select(AuditEvent).where(AuditEvent.action == "person.create"))
        assert event.resource_id == "P-051"
        assert "Synthetic New Member" not in str(event.details)  # field names only, no names
        db.execute(text("DELETE FROM people WHERE public_id = 'P-051'"))
        db.commit()


def test_supervisor_is_read_only(client):
    login(client, "demo_supervisor")
    body = {"full_name": "X", "sex": "male", "relationship_to_head": "son"}
    assert client.post("/api/v2/households/H-001/members", json=body, headers=H).status_code == 403


def test_future_date_of_birth_rejected(client):
    login(client, "demo_worker_a")
    body = {"full_name": "X", "sex": "male", "relationship_to_head": "son", "date_of_birth": "2099-01-01"}
    assert client.post("/api/v2/households/H-001/members", json=body, headers=H).status_code == 422


def test_ending_assignment_hides_households_immediately(client, engine):
    login(client, "demo_worker_b")
    assert len(client.get("/api/v2/households").json()) == 6
    with Session(engine) as db:
        db.execute(text("""UPDATE territory_assignments SET ends_at = now()
                           WHERE user_id = (SELECT id FROM users WHERE username = 'demo_worker_b')"""))
        db.commit()
    try:
        assert client.get("/api/v2/households").json() == []
        assert client.get("/api/v2/households/H-007").status_code == 404
    finally:
        with Session(engine) as db:  # restore for other tests (seed re-adds the active assignment)
            seed_demo(db)
            assert db.scalar(select(func.count()).select_from(Territory)) >= 2
