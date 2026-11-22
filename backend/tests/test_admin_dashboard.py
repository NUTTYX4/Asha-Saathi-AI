"""Phase 7: admin dashboard API and the full endpoint x role authorization matrix.

PostgreSQL/PostGIS only (run inside Docker). Disposable test database, synthetic data only. Visits are
inserted directly so every metric can be checked against a hand-counted expectation.
"""

import hashlib
import uuid
from datetime import date, datetime, time, timedelta, timezone

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.auth.deps import CSRF_HEADER, CSRF_VALUE
from app.auth.service import set_user_password
from app.db.models import AuditEvent, Household, Person, Territory, TerritoryAssignment, User, V2Visit
from app.main import create_app
from app.seed.demo import seed_demo
from tests.conftest import alembic_config, disposable_pg_database, requires_postgres

pytestmark = requires_postgres
PW = "synthetic-test-password-123"  # test-only, set on a disposable database
H = {CSRF_HEADER: CSRF_VALUE}
IST = timezone(timedelta(hours=5, minutes=30))
TODAY = datetime.now(IST).date()
ROLES = ("anonymous", "demo_worker_a", "demo_worker_b", "demo_supervisor", "demo_admin")
ADMIN_GETS = ("/api/v2/admin/overview", "/api/v2/admin/workers", "/api/v2/admin/visits", "/api/v2/admin/coverage",
              "/api/v2/admin/users", "/api/v2/admin/assignments", "/api/v2/admin/audit")


def add_visit(db, person_public_id, worker, day, visit_type="routine", next_visit=None, hour=10):
    person = db.scalar(select(Person).where(Person.public_id == person_public_id))
    household = db.get(Household, person.household_id)
    user = db.scalar(select(User).where(User.username == worker))
    row = V2Visit(person_id=person.id, household_id=household.id, worker_id=user.id,
                  territory_id=household.territory_id, client_visit_id=uuid.uuid4(), session_ref="qa",
                  record_version=2, visit_type=visit_type, subject_population="unresolved", weight_kg=50.0,
                  vaccinations_due=None, next_visit_date=next_visit, danger_signs=[], requires_phc_referral=False,
                  ruleset_version="demo", rule_status="demo_only_pending_clinical_review",
                  extraction_source="deterministic", payload_sha256=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
                  language="kn-IN", confirmed_at=datetime.combine(day, time(hour), IST), is_demo_data=True)
    db.add(row)
    return row


@pytest.fixture(scope="module")
def engine():
    with disposable_pg_database("admin_dash") as url:
        command.upgrade(alembic_config(), "head")
        eng = create_engine(url)
        with Session(eng) as db:
            seed_demo(db)
            for user in db.scalars(select(User).where(User.is_demo_data.is_(True))).all():
                set_user_password(db, user, PW)
            # Territory A people (worker A) and one territory B person (worker B).
            a_people = db.scalars(select(Person.public_id).join(Household).join(Territory)
                                  .where(Territory.code == "DEMO-A").order_by(Person.public_id)).all()
            b_people = db.scalars(select(Person.public_id).join(Household).join(Territory)
                                  .where(Territory.code == "DEMO-B").order_by(Person.public_id)).all()
            d0 = TODAY - timedelta(days=10)
            add_visit(db, a_people[0], "demo_worker_a", d0, "ANC", next_visit=TODAY + timedelta(days=5))
            add_visit(db, a_people[0], "demo_worker_a", d0 + timedelta(days=1), "ANC",
                      next_visit=TODAY + timedelta(days=7))  # latest for this person
            add_visit(db, a_people[1], "demo_worker_a", d0 + timedelta(days=2), "routine",
                      next_visit=TODAY - timedelta(days=1))  # date passed, no later visit
            add_visit(db, b_people[0], "demo_worker_b", TODAY, "immunisation")
            db.commit()
            eng.info = {"a_people": a_people, "b_people": b_people, "d0": d0}  # type: ignore[attr-defined]
        yield eng
        eng.dispose()


@pytest.fixture
def client(engine):
    with TestClient(create_app(engine), base_url="https://testserver") as c:
        yield c


def as_role(client, role):
    client.cookies.clear()
    if role != "anonymous":
        r = client.post("/api/v2/auth/login", json={"username": role, "password": PW}, headers=H)
        assert r.status_code == 200, r.text
    return client


def ids(engine):
    with Session(engine) as db:
        t = {c: db.scalar(select(Territory.id).where(Territory.code == c)) for c in ("DEMO-A", "DEMO-B")}
        u = {n: db.scalar(select(User.id).where(User.username == n))
             for n in ("demo_worker_a", "demo_worker_b", "demo_supervisor", "demo_admin")}
        visit = db.scalar(select(V2Visit).join(User, User.id == V2Visit.worker_id)
                          .where(User.username == "demo_worker_a").order_by(V2Visit.confirmed_at))
        person_a = db.scalar(select(Person.public_id).where(Person.id == visit.person_id))
        member_a = db.scalar(select(Person.public_id).join(Household).where(Household.public_id == "H-001"))
        assignment_b = db.scalar(select(TerritoryAssignment.id).where(
            TerritoryAssignment.user_id == u["demo_worker_b"], TerritoryAssignment.ends_at.is_(None)))
    return {"t": t, "u": u, "visit_id": visit.id, "client_visit_id": visit.client_visit_id, "person_a": person_a,
            "member_a": member_a, "assignment_b": assignment_b}


# ------------------------------------------------------------------ metrics match the records
def test_overview_counts_match_hand_counted_records(client, engine):
    as_role(client, "demo_admin")
    o = client.get("/api/v2/admin/overview").json()
    assert o["active_workers"] == 2
    assert o["territories_total"] == 2 and o["territories_with_worker"] == 2
    assert o["households_registered"] == 12 and o["households_without_assigned_worker"] == 0
    assert o["beneficiaries_registered"] == 50
    assert o["visits_confirmed"] == 4
    assert o["households_visited"] <= o["visits_confirmed"]
    assert o["beneficiaries_visited"] == 3
    assert o["visits_by_type"] == {"ANC": 2, "immunisation": 1, "routine": 1}
    assert o["followups_upcoming"] == 1, "latest ANC visit of person 1 (the earlier one is superseded)"
    assert o["followups_date_passed"] == 1


def test_filters_narrow_counts(client, engine):
    as_role(client, "demo_admin")
    i = ids(engine)
    a = client.get("/api/v2/admin/overview", params={"territory_id": str(i["t"]["DEMO-A"])}).json()
    assert a["households_registered"] == 6 and a["visits_confirmed"] == 3 and a["active_workers"] == 1
    w = client.get("/api/v2/admin/overview", params={"worker_id": str(i["u"]["demo_worker_b"])}).json()
    assert w["visits_confirmed"] == 1 and w["households_registered"] == 6 and w["visits_by_type"] == {"immunisation": 1}
    today = client.get("/api/v2/admin/overview", params={"date_from": TODAY.isoformat(),
                                                         "date_to": TODAY.isoformat()}).json()
    assert today["visits_confirmed"] == 1 and today["households_registered"] == 12, "registered ignores dates"
    bad = client.get("/api/v2/admin/overview", params={"date_from": TODAY.isoformat(),
                                                       "date_to": (TODAY - timedelta(days=1)).isoformat()})
    assert bad.status_code == 422
    assert client.get("/api/v2/admin/overview", params={"worker_id": "not-a-uuid"}).status_code == 422


def test_worker_activity_rows(client, engine):
    as_role(client, "demo_admin")
    rows = {w["username"]: w for w in client.get("/api/v2/admin/workers").json()}
    assert set(rows) == {"demo_worker_a", "demo_worker_b"}, "only worker accounts are listed"
    a = rows["demo_worker_a"]
    assert [t["code"] for t in a["territories"]] == ["DEMO-A"]
    assert a["households_assigned"] == 6 and a["visits_confirmed"] == 3 and a["beneficiaries_visited"] == 2
    assert a["followups_upcoming"] == 1 and a["last_visit_at"] is not None
    assert rows["demo_worker_b"]["visits_confirmed"] == 1


def test_visit_list_is_minimal_sorted_filtered_and_paged(client, engine):
    as_role(client, "demo_admin")
    page = client.get("/api/v2/admin/visits", params={"limit": 2}).json()
    assert page["total"] == 4 and len(page["items"]) == 2
    times = [v["confirmed_at"] for v in page["items"]]
    assert times == sorted(times, reverse=True)
    item = page["items"][0]
    assert set(item) >= {"worker_username", "territory_code", "household_public_id", "person_public_id",
                         "visit_type", "record_version", "status"}
    for forbidden in ("full_name", "weight_kg", "transcript", "audio", "danger_signs", "payload_sha256"):
        assert forbidden not in item
    assert item["status"] == "confirmed"
    older = client.get("/api/v2/admin/visits", params={"sort": "oldest", "offset": 3}).json()
    assert older["total"] == 4 and len(older["items"]) == 1
    anc = client.get("/api/v2/admin/visits", params={"visit_type": "ANC"}).json()
    assert anc["total"] == 2 and {v["visit_type"] for v in anc["items"]} == {"ANC"}
    assert client.get("/api/v2/admin/visits", params={"limit": 0}).status_code == 422
    assert client.get("/api/v2/admin/visits", params={"sort": "random"}).status_code == 422


def test_coverage_counts_registered_vs_visited(client, engine):
    as_role(client, "demo_admin")
    cov = {t["code"]: t for t in client.get("/api/v2/admin/coverage").json()}
    a, b = cov["DEMO-A"], cov["DEMO-B"]
    assert a["households_registered"] == 6 and len(a["households"]) == 6
    assert a["households_visited"] + a["households_not_visited"] == 6
    assert b["households_visited"] == 1 and len(b["workers"]) == 1
    for h in a["households"]:
        assert -90 <= h["latitude"] <= 90 and -180 <= h["longitude"] <= 180
    future = client.get("/api/v2/admin/coverage", params={"date_from": (TODAY + timedelta(days=1)).isoformat()}).json()
    assert all(t["households_visited"] == 0 for t in future), "no visits in a future range"
    assert all(t["last_visit_at"] for t in future if t["code"] in ("DEMO-A", "DEMO-B")), "last visit ignores dates"


def test_users_and_assignments_listing(client, engine):
    as_role(client, "demo_admin")
    users = client.get("/api/v2/admin/users").json()
    assert {u["username"] for u in users} >= {"demo_worker_a", "demo_admin"}
    for u in users:
        assert "password_hash" not in u and "password" not in u
    workers = client.get("/api/v2/admin/users", params={"role": "worker"}).json()
    assert {u["role"] for u in workers} == {"worker"}
    active = client.get("/api/v2/admin/assignments", params={"include_ended": "false"}).json()
    assert all(a["ends_at"] is None for a in active)
    assert {a["username"] for a in active} >= {"demo_worker_a", "demo_worker_b"}


# ------------------------------------------------------------------ reassignment
def test_reassign_is_transactional_audited_and_keeps_visits(client, engine):
    i = ids(engine)
    as_role(client, "demo_admin")
    with Session(engine) as db:
        b_visits_before = db.scalar(select(func.count()).select_from(V2Visit).where(V2Visit.worker_id == i["u"]["demo_worker_b"]))
    # CSRF required
    r = client.post(f"/api/v2/admin/assignments/{i['assignment_b']}/reassign", json={"territory_id": str(i["t"]["DEMO-A"])})
    assert r.status_code == 403
    # Unknown fields refused
    r = client.post(f"/api/v2/admin/assignments/{i['assignment_b']}/reassign",
                    json={"territory_id": str(i["t"]["DEMO-A"]), "role": "admin"}, headers=H)
    assert r.status_code == 422
    # Same territory is a conflict
    r = client.post(f"/api/v2/admin/assignments/{i['assignment_b']}/reassign",
                    json={"territory_id": str(i["t"]["DEMO-B"])}, headers=H)
    assert r.status_code == 409
    # Unknown territory / assignment
    assert client.post(f"/api/v2/admin/assignments/{i['assignment_b']}/reassign",
                       json={"territory_id": str(uuid.uuid4())}, headers=H).status_code == 404
    assert client.post(f"/api/v2/admin/assignments/{uuid.uuid4()}/reassign",
                       json={"territory_id": str(i["t"]["DEMO-A"])}, headers=H).status_code == 404
    try:
        r = client.post(f"/api/v2/admin/assignments/{i['assignment_b']}/reassign",
                        json={"territory_id": str(i["t"]["DEMO-A"])}, headers=H)
        assert r.status_code == 201, r.text
        new = r.json()
        assert new["username"] == "demo_worker_b" and new["territory_code"] == "DEMO-A" and new["ends_at"] is None
        assert new["created_by_username"] == "demo_admin"
        with Session(engine) as db:
            old = db.get(TerritoryAssignment, i["assignment_b"])
            assert old.ends_at is not None, "the old assignment ended in the same transaction"
            active = db.scalars(select(TerritoryAssignment).where(
                TerritoryAssignment.user_id == i["u"]["demo_worker_b"], TerritoryAssignment.ends_at.is_(None))).all()
            assert [a.territory_id for a in active] == [i["t"]["DEMO-A"]]
            ev = db.scalar(select(AuditEvent).where(AuditEvent.action == "assignment.reassign")
                           .order_by(AuditEvent.id.desc()))
            assert ev.actor_user_id == i["u"]["demo_admin"]
            assert ev.details["from_territory_id"] == str(i["t"]["DEMO-B"])
            after = db.scalar(select(func.count()).select_from(V2Visit).where(V2Visit.worker_id == i["u"]["demo_worker_b"]))
            assert after == b_visits_before, "visits stay with the worker who recorded them"
        # Ended assignment cannot be reassigned again
        assert client.post(f"/api/v2/admin/assignments/{i['assignment_b']}/reassign",
                           json={"territory_id": str(i["t"]["DEMO-A"])}, headers=H).status_code == 409
        # The moved worker now sees territory A and no longer territory B
        as_role(client, "demo_worker_b")
        assert client.get("/api/v2/households/H-001").status_code == 200
        assert client.get("/api/v2/households/H-007").status_code == 404
    finally:
        with Session(engine) as db:  # restore the seeded assignments for other tests
            db.query(TerritoryAssignment).filter(TerritoryAssignment.user_id == i["u"]["demo_worker_b"],
                                                 TerritoryAssignment.ends_at.is_(None)).update(
                {"ends_at": func.now()}, synchronize_session=False)
            db.commit()
            seed_demo(db)


def test_workers_cannot_reassign_themselves(client, engine):
    i = ids(engine)
    for role, expected in (("anonymous", 401), ("demo_worker_a", 403), ("demo_worker_b", 403), ("demo_supervisor", 403)):
        as_role(client, role)
        r = client.post(f"/api/v2/admin/assignments/{i['assignment_b']}/reassign",
                        json={"territory_id": str(i["t"]["DEMO-A"])}, headers=H)
        assert r.status_code == expected, (role, r.status_code)
    with Session(engine) as db:
        assert db.get(TerritoryAssignment, i["assignment_b"]).ends_at is None


# ------------------------------------------------------------------ full endpoint x role matrix
def matrix(i):
    """(method, path, expected status per role). 404 for out-of-scope objects is deliberate:
    it does not confirm that another territory's record exists."""
    A, P, M = "H-001", i["person_a"], i["member_a"]
    std = {"anonymous": 401, "demo_worker_a": 200, "demo_worker_b": 404, "demo_supervisor": 200, "demo_admin": 200}
    every = {r: 200 for r in ROLES} | {"anonymous": 401}
    admin = {"anonymous": 401, "demo_worker_a": 403, "demo_worker_b": 403, "demo_supervisor": 403, "demo_admin": 200}
    rows = [
        ("GET", "/api/health", {r: 200 for r in ROLES}),
        ("GET", "/api/v2/auth/me", every),
        ("GET", "/api/v2/territories", every),
        ("GET", f"/api/v2/territories/{i['t']['DEMO-A']}", std),
        ("GET", f"/api/v2/territories/{uuid.uuid4()}", {r: 404 for r in ROLES} | {"anonymous": 401}),
        ("GET", "/api/v2/households", every),
        ("GET", "/api/v2/households/nearby?lat=12.9745&lon=77.5925", every),
        ("GET", f"/api/v2/households/{A}", std),
        ("GET", f"/api/v2/households/{A}/members", std),
        ("GET", f"/api/v2/households/{A}/members/{M}", std),
        ("GET", f"/api/v2/people/{P}", std),
        ("GET", f"/api/v2/people/{P}/visits", std),
        ("GET", f"/api/v2/people/{P}/visits/{i['visit_id']}", std),
        ("GET", f"/api/v2/visits/by-client-key/{i['client_visit_id']}",
         {"anonymous": 401, "demo_worker_a": 200, "demo_worker_b": 404, "demo_supervisor": 404, "demo_admin": 404}),
        *[("GET", path, admin) for path in ADMIN_GETS],
    ]
    return rows


def test_endpoint_role_matrix(client, engine):
    i = ids(engine)
    failures = []
    count = 0
    for role in ROLES:
        as_role(client, role)
        for method, path, expected in matrix(i):
            r = client.request(method, path)
            count += 1
            if r.status_code != expected[role]:
                failures.append(f"{role} {method} {path}: {r.status_code} != {expected[role]}")
            if r.status_code >= 400:
                body = r.text.lower()
                assert "traceback" not in body and "password" not in body and "sqlalchemy" not in body, path
    assert not failures, "\n".join(failures)
    assert count == len(ROLES) * len(matrix(i))


@pytest.mark.parametrize("path,body", [
    ("/api/v2/admin/users", {"username": "qa_new_user", "display_name": "QA", "role": "worker",
                             "password": "another-synthetic-pass-123"}),
    ("/api/v2/admin/territories", {"code": "QA-T1", "name": "QA territory"}),
    ("/api/v2/admin/assignments", {"user_id": str(uuid.uuid4()), "territory_id": str(uuid.uuid4())}),
    (f"/api/v2/admin/assignments/{uuid.uuid4()}/end", None),
])
def test_admin_writes_require_admin_and_csrf(client, engine, path, body):
    for role in ("anonymous", "demo_worker_a", "demo_supervisor"):
        as_role(client, role)
        r = client.post(path, json=body, headers=H)
        assert r.status_code == (401 if role == "anonymous" else 403), (role, path, r.status_code)
    as_role(client, "demo_admin")
    assert client.post(path, json=body).status_code == 403, "missing anti-CSRF header"


def test_admin_write_validation_and_role_escalation(client, engine):
    as_role(client, "demo_admin")
    bad_role = client.post("/api/v2/admin/users", json={"username": "x_user", "display_name": "X", "role": "root",
                                                        "password": "another-synthetic-pass-123"}, headers=H)
    assert bad_role.status_code == 422
    missing = client.post("/api/v2/admin/territories", json={"name": "no code"}, headers=H)
    assert missing.status_code == 422
    unknown = client.post("/api/v2/admin/assignments", json={"user_id": str(uuid.uuid4()),
                                                             "territory_id": str(uuid.uuid4())}, headers=H)
    assert unknown.status_code == 404
    # A worker cannot promote themselves through any route: /me has no write and admin routes are 403.
    as_role(client, "demo_worker_a")
    assert client.post("/api/v2/auth/me", json={"role": "admin"}, headers=H).status_code == 405
    assert client.get("/api/v2/auth/me").json()["role"] == "worker"


def test_logout_ends_access_and_login_requires_csrf(client, engine):
    as_role(client, "demo_admin")
    assert client.get("/api/v2/admin/overview").status_code == 200
    assert client.post("/api/v2/auth/logout").status_code == 403, "logout needs the anti-CSRF header"
    assert client.post("/api/v2/auth/logout", headers=H).status_code == 204
    assert client.get("/api/v2/admin/overview").status_code == 401
    client.cookies.clear()
    r = client.post("/api/v2/auth/login", json={"username": "demo_admin", "password": PW})
    assert r.status_code == 403
    r = client.post("/api/v2/auth/login", json={"username": "demo_admin", "password": "wrong-password-xyz"}, headers=H)
    assert r.status_code == 401 and "password_hash" not in r.text
    r = client.post("/api/v2/auth/login", json={"username": "demo_admin", "password": PW, "extra": 1}, headers=H)
    assert r.status_code in (200, 422)
