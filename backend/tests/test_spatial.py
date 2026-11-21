"""V2 Phase 4: authorized map discovery (list, search, bbox, nearby), household confirmation and
member selection, on real PostgreSQL/PostGIS.

Runs inside Docker against a disposable database: the 12/50 synthetic demo seed plus a small
test-only territory TEST-C (H-901/H-902 share one point, H-903 sits 0.001 degrees north) and
test-only accounts. All data is synthetic. Acceptance IDs (P4-xx) follow the Phase 4 handoff.
"""

import math
import uuid

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.auth.deps import COOKIE_NAME, CSRF_HEADER, CSRF_VALUE
from app.auth.ratelimit import RequestRateLimiter
from app.auth.service import set_user_password
from app.db.models import (
    AuditEvent,
    Household,
    Person,
    PersonRelationship,
    ProgrammeEnrolment,
    Territory,
    TerritoryAssignment,
    User,
)
from app.main import create_app
from app.seed import demo_data as D
from app.seed.demo import seed_demo
from tests.conftest import alembic_config, disposable_pg_database, requires_postgres

pytestmark = requires_postgres
PW = "synthetic-test-password-456"  # test-only, set on a disposable database
H = {CSRF_HEADER: CSRF_VALUE}
A_HOUSES = [f"H-{n:03d}" for n in range(1, 7)]
B_HOUSES = [f"H-{n:03d}" for n in range(7, 13)]
C_HOUSES = ["H-901", "H-902", "H-903"]
C_POINT = (12.9800, 77.6000)            # (lat, lon) of H-901 and H-902 (same point on purpose)
C_NORTH = (12.9810, 77.6000)            # H-903: 0.001 degrees north of C_POINT
PIN_KEYS = {"id", "public_id", "label", "landmark", "territory_code", "latitude", "longitude",
            "location_source", "member_count", "is_demo_data"}
ALL_NAMES = [m.name for hh in D.HOUSEHOLDS for m in hh.members]
CLINICAL_WORDS = ["ANC", "PNC", "NEWBORN", "IMMUNISATION", "NCD_FOLLOWUP", "programme", "full_name",
                  "date_of_birth", "relationship", "danger", "referral", "diagnosis"]


def _add_user(db: Session, username: str, role: str, territories: list[Territory]) -> None:
    user = User(username=username, display_name=username, role=role, password_hash="!", active=False,
                is_demo_data=True)
    db.add(user)
    db.flush()
    set_user_password(db, user, PW)
    for territory in territories:
        db.add(TerritoryAssignment(user_id=user.id, territory_id=territory.id))


def _add_household(db: Session, public_id: str, territory: Territory, lat: float, lon: float) -> Household:
    household = Household(public_id=public_id, territory_id=territory.id, label=f"Test House {public_id}",
                          landmark="Test-only synthetic pin", location=f"SRID=4326;POINT({lon} {lat})",
                          location_source="synthetic_demo", is_demo_data=True)
    db.add(household)
    db.flush()
    return household


@pytest.fixture(scope="module")
def engine():
    with disposable_pg_database("spatial") as url:
        command.upgrade(alembic_config(), "head")
        eng = create_engine(url)
        with Session(eng) as db:
            seed_demo(db)
            for user in db.scalars(select(User).where(User.is_demo_data.is_(True))).all():
                set_user_password(db, user, PW)
            territory_a = db.scalar(select(Territory).where(Territory.code == "DEMO-A"))
            territory_c = Territory(code="TEST-C", name="Test-only territory C", is_demo_data=True)
            db.add(territory_c)
            db.flush()
            h901 = _add_household(db, "H-901", territory_c, *C_POINT)
            _add_household(db, "H-902", territory_c, *C_POINT)
            _add_household(db, "H-903", territory_c, *C_NORTH)
            db.add_all([
                Person(public_id="P-901", household_id=h901.id, full_name="Test Person C1", sex="female",
                       relationship_to_head="head", recorded_age_years=40, age_recorded_on=D.DEMO_AS_OF,
                       is_demo_data=True),
                Person(public_id="P-902", household_id=h901.id, full_name="Test Person C2 Inactive", sex="male",
                       relationship_to_head="son", recorded_age_years=20, age_recorded_on=D.DEMO_AS_OF,
                       active=False, is_demo_data=True),
            ])
            _add_user(db, "test_worker_c", "worker", [territory_c])
            _add_user(db, "test_supervisor_a", "supervisor", [territory_a])
            _add_user(db, "test_worker_nogrant", "worker", [])
            db.commit()
        yield eng
        eng.dispose()


@pytest.fixture
def client(engine):
    with TestClient(create_app(engine), base_url="https://testserver") as c:
        yield c


def login(client: TestClient, username: str) -> None:
    r = client.post("/api/v2/auth/login", json={"username": username, "password": PW}, headers=H)
    assert r.status_code == 200, r.text


def ids(response) -> list[str]:
    assert response.status_code == 200, response.text
    return [p["public_id"] for p in response.json()]


def pin_coords(engine, public_id: str) -> tuple[float, float]:
    """(lat, lon) straight from PostGIS: ST_Y is latitude, ST_X is longitude."""
    with Session(engine) as db:
        return db.execute(text("SELECT ST_Y(location::geometry), ST_X(location::geometry) FROM households "
                               "WHERE public_id = :p"), {"p": public_id}).one()


def walk_pages(client: TestClient, limit: int, **params) -> list[str]:
    seen, after = [], None
    for _ in range(50):
        query = {"limit": limit, **params, **({"after": after} if after else {})}
        r = client.get("/api/v2/households", params=query)
        page = ids(r)
        assert len(page) <= limit
        seen += page
        after = r.headers.get("X-Next-After")
        if not after:
            return seen
        assert after == page[-1]
    raise AssertionError("pagination did not terminate")


# ------------------------------------------------------------------ P4-01 / P4-02 scope
def test_p4_01_each_worker_sees_exactly_their_six(client):
    login(client, "demo_worker_a")
    assert ids(client.get("/api/v2/households")) == A_HOUSES
    assert walk_pages(client, limit=2) == A_HOUSES          # stable pages, no duplicates or gaps
    login(client, "demo_worker_b")
    assert ids(client.get("/api/v2/households")) == B_HOUSES
    assert walk_pages(client, limit=4) == B_HOUSES


@pytest.mark.parametrize("user,expected", [
    ("demo_supervisor", A_HOUSES + B_HOUSES),        # granted A and B only: never TEST-C
    ("test_supervisor_a", A_HOUSES),                 # one grant: six, not twelve
    ("demo_admin", A_HOUSES + B_HOUSES + C_HOUSES),  # admin policy: every territory
    ("test_worker_c", C_HOUSES),
    ("test_worker_nogrant", []),
])
def test_p4_02_scope_follows_grants_exactly(client, user, expected):
    login(client, user)
    assert ids(client.get("/api/v2/households")) == expected
    assert walk_pages(client, limit=5) == expected
    # 5 km around the park centre covers every pin (A, B and TEST-C): still only the grants.
    nearby = ids(client.get("/api/v2/households/nearby",
                            params={"lat": 12.975, "lon": 77.594, "radius_m": 5000, "limit": 100}))
    assert sorted(nearby) == sorted(expected)


def test_no_grant_worker_gets_empty_lists_and_404s(client):
    login(client, "test_worker_nogrant")
    assert ids(client.get("/api/v2/households", params={"q": "H-0"})) == []
    assert ids(client.get("/api/v2/households", params={"bbox": "77.58,12.96,77.61,12.99"})) == []
    assert client.get("/api/v2/territories").json() == []
    for path in ("/api/v2/households/H-001", "/api/v2/households/H-001/members", "/api/v2/people/P-001"):
        assert client.get(path).status_code == 404, path


def test_territory_filter_never_widens_scope(client):
    login(client, "demo_worker_a")
    assert ids(client.get("/api/v2/households", params={"territory": "DEMO-B"})) == []
    assert ids(client.get("/api/v2/households", params={"territory": "DEMO-A"})) == A_HOUSES
    login(client, "test_supervisor_a")
    assert ids(client.get("/api/v2/households", params={"territory": "DEMO-B"})) == []


# ------------------------------------------------------------------ search
@pytest.mark.parametrize("user,q,expected", [
    ("demo_worker_a", "H-003", ["H-003"]),
    ("demo_worker_a", "h-003", ["H-003"]),
    ("demo_worker_a", "  H-003  ", ["H-003"]),
    ("demo_worker_a", "Demo House 1,", ["H-001"]),
    ("demo_worker_a", "lane a", A_HOUSES),
    ("demo_worker_a", "H-007", []),                  # another territory's ID: nothing
    ("demo_worker_a", "Lane B", []),
    ("demo_worker_a", "%", []),                      # wildcards are literal
    ("demo_worker_a", "_", []),
    ("demo_worker_a", "' OR '1'='1", []),            # parameterised: just text
    ("demo_worker_a", "Kavya", []),                  # people's names are not searchable from the map
    ("demo_worker_b", "H-00", ["H-007", "H-008", "H-009"]),
    ("demo_supervisor", "H-90", []),                 # TEST-C is not granted to the supervisor
])
def test_search_is_scoped_case_insensitive_and_literal(client, user, q, expected):
    login(client, user)
    assert ids(client.get("/api/v2/households", params={"q": q})) == expected


@pytest.mark.parametrize("q", ["   ", "x" * 65, "Kavya\x00", "\x00"])
def test_bad_search_rejected(client, q):
    login(client, "demo_worker_a")
    assert client.get("/api/v2/households", params={"q": q}).status_code == 422


# ------------------------------------------------------------------ bounding box
def test_bbox_only_narrows_the_callers_households(client, engine):
    lat3, lon3 = pin_coords(engine, "H-003")
    login(client, "demo_worker_a")
    everything = "77.585,12.965,77.600,12.985"            # covers all 12 demo pins
    assert ids(client.get("/api/v2/households", params={"bbox": everything})) == A_HOUSES
    b_area = "77.5895,12.9700,77.5920,12.9722"             # only Territory B pins
    assert ids(client.get("/api/v2/households", params={"bbox": b_area})) == []
    tight = f"{lon3 - 0.0001},{lat3 - 0.0001},{lon3 + 0.0001},{lat3 + 0.0001}"
    assert ids(client.get("/api/v2/households", params={"bbox": tight})) == ["H-003"]
    swapped = f"{lat3 - 0.0001},{lon3 - 0.0001},{lat3 + 0.0001},{lon3 + 0.0001}"  # lat/lon order mistake
    assert ids(client.get("/api/v2/households", params={"bbox": swapped})) == []
    login(client, "demo_worker_b")
    assert ids(client.get("/api/v2/households", params={"bbox": b_area})) == B_HOUSES
    assert ids(client.get("/api/v2/households", params={"bbox": tight})) == []


@pytest.mark.parametrize("bbox", ["1,2,3", "a,b,c,d", "nan,12.9,77.6,13.0", "77.5,12.9,inf,13.0",
                                  "181,12.9,182,13.0", "77.5,-91,77.6,13.0", "77.6,12.9,77.5,13.0",
                                  "70,10,80,20", "x" * 129])
def test_bad_bbox_rejected_without_internal_details(client, bbox):
    login(client, "demo_worker_a")
    r = client.get("/api/v2/households", params={"bbox": bbox})
    assert r.status_code == 422
    body = r.text.lower()
    assert "detail" in body and not any(w in body for w in ("sql", "psycopg", "traceback", "select "))


# ------------------------------------------------------------------ nearby (P4-07)
def meridian_arc_m(lat1: float, lat2: float) -> float:
    """WGS84 meridian arc length between two latitudes on one meridian (independent of PostGIS)."""
    a, e2 = 6378137.0, 0.00669437999014
    phi = math.radians((lat1 + lat2) / 2)
    radius = a * (1 - e2) / (1 - e2 * math.sin(phi) ** 2) ** 1.5
    return radius * math.radians(abs(lat2 - lat1))


def test_p4_07_nearby_is_metres_on_the_spheroid_with_lon_lat_order(client):
    login(client, "test_worker_c")
    lat, lon = C_POINT
    r = client.get("/api/v2/households/nearby", params={"lat": lat, "lon": lon, "radius_m": 200})
    rows = r.json()
    assert [x["public_id"] for x in rows] == ["H-901", "H-902", "H-903"]
    assert rows[0]["distance_m"] == rows[1]["distance_m"] == 0.0     # overlapping pins: both offered
    expected = meridian_arc_m(C_POINT[0], C_NORTH[0])                 # about 110.6 m
    assert abs(rows[2]["distance_m"] - expected) < 0.5               # metres on WGS84, not degrees or sphere
    assert abs(rows[2]["distance_m"] - 111.19) > 0.3                 # a spherical radius would give 111.19
    # Radius is a hard bound: 100 m excludes H-903 at ~110.6 m.
    assert ids(client.get("/api/v2/households/nearby",
                          params={"lat": lat, "lon": lon, "radius_m": 100})) == ["H-901", "H-902"]
    # Swapping latitude and longitude points somewhere else entirely.
    assert ids(client.get("/api/v2/households/nearby", params={"lat": lon, "lon": lat, "radius_m": 5000})) == []


def test_nearby_ties_are_stable(client):
    login(client, "test_worker_c")
    lat, lon = C_POINT
    runs = {tuple(ids(client.get("/api/v2/households/nearby", params={"lat": lat, "lon": lon, "radius_m": 50})))
            for _ in range(3)}
    assert runs == {("H-901", "H-902")}
    assert ids(client.get("/api/v2/households/nearby",
                          params={"lat": lat, "lon": lon, "radius_m": 50, "limit": 1})) == ["H-901"]


def test_nearby_matches_postgis_and_stays_in_scope(client, engine):
    lat3, lon3 = pin_coords(engine, "H-003")
    assert 12.9 < lat3 < 13.0 and 77.5 < lon3 < 77.7                 # Bengaluru: x is longitude
    login(client, "demo_worker_a")
    rows = client.get("/api/v2/households/nearby",
                      params={"lat": lat3, "lon": lon3, "radius_m": 5000, "limit": 100}).json()
    assert rows[0]["public_id"] == "H-003" and rows[0]["distance_m"] == 0.0
    assert sorted(x["public_id"] for x in rows) == A_HOUSES
    distances = [x["distance_m"] for x in rows]
    assert distances == sorted(distances)
    with Session(engine) as db:
        reference = dict(db.execute(text(
            "SELECT public_id, round(ST_Distance(location, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography)"
            "::numeric, 1)::float FROM households"), {"lat": lat3, "lon": lon3}).all())
    for x in rows:  # both rounded to 0.1 m (Python vs SQL rounding may differ by one step)
        assert abs(x["distance_m"] - reference[x["public_id"]]) < 0.15, x["public_id"]
    login(client, "demo_worker_b")                                    # same point, other worker: only B
    assert sorted(ids(client.get("/api/v2/households/nearby",
                                 params={"lat": lat3, "lon": lon3, "radius_m": 5000}))) == B_HOUSES


@pytest.mark.parametrize("params", [
    {"lat": 90.0001, "lon": 77.6}, {"lat": -90.0001, "lon": 77.6}, {"lat": 12.9, "lon": 180.0001},
    {"lat": 12.9, "lon": -180.0001}, {"lat": "nan", "lon": 77.6}, {"lat": 12.9, "lon": "inf"},
    {"lat": "-inf", "lon": 77.6}, {"lat": "abc", "lon": 77.6}, {"lon": 77.6}, {"lat": 12.9},
    {"lat": 12.9, "lon": 77.6, "radius_m": 0}, {"lat": 12.9, "lon": 77.6, "radius_m": 5001},
    {"lat": 12.9, "lon": 77.6, "radius_m": -5}, {"lat": 12.9, "lon": 77.6, "radius_m": 10**12},
    {"lat": 12.9, "lon": 77.6, "radius_m": 10.5}, {"lat": 12.9, "lon": 77.6, "limit": 0},
    {"lat": 12.9, "lon": 77.6, "limit": 101},
])
def test_bad_nearby_input_rejected(client, params):
    login(client, "demo_worker_a")
    r = client.get("/api/v2/households/nearby", params=params)
    assert r.status_code == 422, params
    assert "psycopg" not in r.text.lower() and "traceback" not in r.text.lower()


def test_nearby_maximum_radius_accepted(client):
    login(client, "demo_worker_a")
    assert client.get("/api/v2/households/nearby",
                      params={"lat": 12.975, "lon": 77.594, "radius_m": 5000}).status_code == 200


# ------------------------------------------------------------------ pagination cursor
@pytest.mark.parametrize("user,after,expected", [
    ("demo_worker_a", "H-006", []),
    ("demo_worker_a", "H-002", ["H-003", "H-004", "H-005", "H-006"]),
    ("demo_worker_b", "H-001", B_HOUSES),            # a cursor from elsewhere still only shows B
    ("demo_worker_b", "h-009", ["H-010", "H-011", "H-012"]),
    ("demo_worker_a", "H-999", []),
])
def test_cursor_only_moves_within_scope(client, user, after, expected):
    login(client, user)
    assert ids(client.get("/api/v2/households", params={"after": after})) == expected


@pytest.mark.parametrize("after", ["garbage", "H-1", "P-001", "H-٠٠١"])
def test_bad_cursor_rejected(client, after):
    login(client, "demo_worker_a")
    assert client.get("/api/v2/households", params={"after": after}).status_code == 422


@pytest.mark.parametrize("limit", [0, 101, -1])
def test_page_limit_bounded(client, limit):
    login(client, "demo_worker_a")
    assert client.get("/api/v2/households", params={"limit": limit}).status_code == 422


# ------------------------------------------------------------------ P4-09 minimal pins
def test_p4_09_pin_payloads_are_minimal_everywhere(client, engine):
    lat3, lon3 = pin_coords(engine, "H-003")
    login(client, "demo_worker_a")
    responses = [
        client.get("/api/v2/households"),
        client.get("/api/v2/households", params={"q": "H-003"}),
        client.get("/api/v2/households", params={"bbox": "77.585,12.965,77.600,12.985"}),
        client.get("/api/v2/households/nearby", params={"lat": lat3, "lon": lon3, "radius_m": 5000}),
    ]
    for r in responses:
        assert r.status_code == 200 and r.json()
        for item in r.json():
            extra = {"distance_m"} if "distance_m" in item else set()
            assert set(item) == PIN_KEYS | extra, item.keys()
            assert item["is_demo_data"] is True and item["location_source"] == "synthetic_demo"
        assert not [n for n in ALL_NAMES if n in r.text], "a person's name leaked onto a pin"
        assert not [w for w in CLINICAL_WORDS if w in r.text], "clinical or person field on a pin"


# ------------------------------------------------------------------ P4-05 / P4-06 confirmation and BOLA
def _person(engine, household: str, name: str) -> Person:
    with Session(engine) as db:
        return db.scalar(select(Person).join(Household, Household.id == Person.household_id)
                         .where(Household.public_id == household, Person.full_name == name))


def test_p4_05_selected_member_is_checked_against_the_household(client, engine):
    kavya = _person(engine, "H-003", "Kavya Halli")
    baby = _person(engine, "H-003", "Baby of Kavya Halli")
    login(client, "demo_worker_a")
    detail = client.get("/api/v2/households/H-003")                  # 'Confirm household' recheck
    assert detail.status_code == 200 and detail.json()["member_count"] == 4
    for key in (kavya.public_id, str(kavya.id), kavya.public_id.lower()):
        r = client.get(f"/api/v2/households/H-003/members/{key}")
        assert r.status_code == 200, key
        assert r.json()["id"] == str(kavya.id) and r.json()["household_public_id"] == "H-003"
    with Session(engine) as db:                                       # the real FK in the database
        h3 = db.scalar(select(Household).where(Household.public_id == "H-003"))
        assert db.get(Person, kavya.id).household_id == h3.id == db.get(Person, baby.id).household_id
    by_uuid = client.get(f"/api/v2/households/{h3.id}/members/{baby.id}").json()
    assert by_uuid["full_name"] == "Baby of Kavya Halli"
    assert [p["programme"] for p in by_uuid["programmes"]] == ["NEWBORN"]


def test_p4_06_other_households_and_territories_are_indistinguishable_from_missing(client, engine):
    h7_person = _person(engine, "H-007", "Meghana Gowda")
    h2_person = _person(engine, "H-002", "Shivappa Kerekatte")        # same territory, other household
    with Session(engine) as db:
        h7 = db.scalar(select(Household).where(Household.public_id == "H-007"))
    login(client, "demo_worker_a")
    missing = client.get("/api/v2/households/H-999")
    assert missing.status_code == 404
    paths = [
        "/api/v2/households/H-007", "/api/v2/households/h-007", f"/api/v2/households/{h7.id}",
        "/api/v2/households/H-007/members", f"/api/v2/households/{h7.id}/members",
        f"/api/v2/households/H-007/members/{h7_person.public_id}",
        f"/api/v2/households/H-001/members/{h7_person.public_id}",   # visible house, foreign person
        f"/api/v2/households/H-001/members/{h7_person.id}",
        f"/api/v2/households/H-001/members/{h2_person.public_id}",   # visible person, wrong house
        "/api/v2/households/H-001/members/P-999", "/api/v2/households/H-001/members/not-an-id",
        f"/api/v2/households/H-001/members/{uuid.uuid4()}",
        f"/api/v2/people/{h7_person.public_id}", f"/api/v2/people/{h7_person.id}",
        "/api/v2/people/P-999", f"/api/v2/households/{uuid.uuid4()}", "/api/v2/households/not-an-id",
    ]
    for path in paths:
        r = client.get(path)
        assert r.status_code == 404 and r.json() == missing.json(), path


def test_inactive_member_cannot_be_selected(client):
    login(client, "test_worker_c")
    assert client.get("/api/v2/households/H-901/members/P-901").status_code == 200
    assert client.get("/api/v2/households/H-901/members/P-902").status_code == 404
    assert [m["public_id"] for m in client.get("/api/v2/households/H-901/members").json()] == ["P-901"]


def test_supervisor_with_one_grant_cannot_open_other_territory(client):
    login(client, "test_supervisor_a")
    assert client.get("/api/v2/households/H-003").status_code == 200
    assert client.get("/api/v2/households/H-007").status_code == 404
    assert client.get("/api/v2/households/H-007/members").status_code == 404


def test_relationships_never_name_people_outside_the_callers_scope(client, engine):
    a_person, b_person = _person(engine, "H-001", "Kiran Hosamane"), _person(engine, "H-007", "Tanvi Gowda")
    with Session(engine) as db:            # a cross-territory edge (no API creates one; defence in depth)
        db.add(PersonRelationship(person_id=a_person.id, related_person_id=b_person.id,
                                  relationship_type="guardian_of", source="worker_entry"))
        db.commit()
    try:
        login(client, "demo_worker_a")
        for r in (client.get(f"/api/v2/people/{a_person.public_id}"),
                  client.get(f"/api/v2/households/H-001/members/{a_person.public_id}"),
                  client.get("/api/v2/households/H-001/members")):
            assert r.status_code == 200 and "Tanvi Gowda" not in r.text and b_person.public_id not in r.text
        login(client, "demo_supervisor")   # granted both territories: the edge is visible
        assert "Tanvi Gowda" in client.get(f"/api/v2/people/{a_person.public_id}").text
    finally:
        with Session(engine) as db:
            db.execute(text("DELETE FROM person_relationships WHERE relationship_type = 'guardian_of'"))
            db.commit()


# ------------------------------------------------------------------ audit of refused access
def test_refused_lookups_are_audited_the_same_way_without_names(client):
    login(client, "demo_worker_a")
    engine = client.app.state.engine
    with Session(engine) as db:
        before = db.scalar(select(func.max(AuditEvent.id)))
    for path in ("/api/v2/households/H-007", "/api/v2/households/H-999", "/api/v2/households/Kavya Halli",
                 "/api/v2/people/P-030"):
        assert client.get(path).status_code == 404
    with Session(engine) as db:
        rows = db.scalars(select(AuditEvent).where(AuditEvent.id > before).order_by(AuditEvent.id)).all()
    assert [(e.action, e.resource_kind, e.resource_id, e.details) for e in rows] == [
        ("access.denied", "household", "H-007", {"route": "household.detail"}),
        ("access.denied", "household", "H-999", {"route": "household.detail"}),
        ("access.denied", "household", "<malformed>", {"route": "household.detail"}),
        ("access.denied", "person", "P-030", {"route": "person.detail"}),
    ]


# ------------------------------------------------------------------ sessions and accounts
DISCOVERY = ["/api/v2/households", "/api/v2/households?q=H-003", "/api/v2/households/nearby?lat=12.97&lon=77.59",
             "/api/v2/households/H-003", "/api/v2/households/H-003/members", "/api/v2/people/P-001"]


def test_unauthenticated_requests_get_401(client):
    for path in DISCOVERY:
        assert client.get(path).status_code == 401, path


def test_expired_session_rejected(client, engine):
    login(client, "demo_worker_a")
    assert client.get("/api/v2/households").status_code == 200
    with Session(engine) as db:
        db.execute(text("UPDATE auth_sessions SET expires_at = now() - interval '1 minute' WHERE user_id = "
                        "(SELECT id FROM users WHERE username = 'demo_worker_a') AND revoked_at IS NULL"))
        db.commit()
    for path in DISCOVERY:
        assert client.get(path).status_code == 401, path


def test_logged_out_cookie_cannot_be_replayed(client):
    login(client, "demo_worker_a")
    token = client.cookies.get(COOKIE_NAME)
    assert client.post("/api/v2/auth/logout", headers=H).status_code == 204
    client.cookies.set(COOKIE_NAME, token, domain="testserver")      # replay the old token
    for path in DISCOVERY:
        assert client.get(path).status_code == 401, path


def test_deactivated_account_loses_access_mid_session(client, engine):
    login(client, "test_worker_c")
    assert ids(client.get("/api/v2/households")) == C_HOUSES
    with Session(engine) as db:
        db.execute(text("UPDATE users SET active = false WHERE username = 'test_worker_c'"))
        db.commit()
    try:
        assert client.get("/api/v2/households").status_code == 401
        assert client.get("/api/v2/households/H-901/members/P-901").status_code == 401
    finally:
        with Session(engine) as db:
            db.execute(text("UPDATE users SET active = true WHERE username = 'test_worker_c'"))
            db.commit()


def test_revoked_grant_mid_selection_denies_confirmation(client, engine):
    login(client, "test_worker_c")
    assert "H-901" in ids(client.get("/api/v2/households"))           # pin previewed
    with Session(engine) as db:
        db.execute(text("UPDATE territory_assignments SET ends_at = now() WHERE user_id = "
                        "(SELECT id FROM users WHERE username = 'test_worker_c') AND ends_at IS NULL"))
        db.commit()
    try:
        assert client.get("/api/v2/households/H-901").status_code == 404      # confirm refused
        assert client.get("/api/v2/households/H-901/members/P-901").status_code == 404
    finally:
        with Session(engine) as db:
            user = db.scalar(select(User).where(User.username == "test_worker_c"))
            territory = db.scalar(select(Territory).where(Territory.code == "TEST-C"))
            db.add(TerritoryAssignment(user_id=user.id, territory_id=territory.id))
            db.commit()


# ------------------------------------------------------------------ rate limit, data and legacy
def test_scanning_is_rate_limited_per_user(client):
    client.app.state.discovery_limiter = RequestRateLimiter(3, 60)
    login(client, "demo_worker_a")
    codes = [client.get(f"/api/v2/households/H-{n:03d}").status_code for n in range(1, 5)]
    assert codes == [200, 200, 200, 429]
    login(client, "demo_worker_b")                                    # a different user is unaffected
    assert client.get("/api/v2/households").status_code == 200


def test_discovery_never_changes_seed_rows(client, engine):
    def counts():
        with Session(engine) as db:
            return [db.scalar(select(func.count()).select_from(m))
                    for m in (Household, Person, PersonRelationship, ProgrammeEnrolment, Territory)]

    before = counts()
    login(client, "demo_worker_a")
    for path in DISCOVERY + ["/api/v2/households/H-007", "/api/v2/households/H-003/members/P-010"]:
        client.get(path)
    assert counts() == before


def test_round1_endpoints_stay_off_in_postgres_mode(client):
    assert client.get("/api/health").json()["legacy_round1_api"] is False
    assert client.get("/api/visits").status_code == 404
    assert client.get("/api/followups").status_code == 404


@pytest.mark.parametrize("territory", ["\x00", "DEMO-A'--", "x" * 17])
def test_bad_territory_filter_rejected(client, territory):
    login(client, "demo_worker_a")
    assert client.get("/api/v2/households", params={"territory": territory}).status_code == 422


def test_overlong_ids_get_the_standard_404_and_are_audited_as_malformed(client):
    login(client, "demo_worker_a")
    engine = client.app.state.engine
    with Session(engine) as db:
        before = db.scalar(select(func.max(AuditEvent.id)))
    missing = client.get("/api/v2/households/H-999").json()
    long_h, long_p = "H-" + "1" * 70, "P-" + "1" * 70
    for path in (f"/api/v2/households/{long_h}", f"/api/v2/households/H-001/members/{long_p}",
                 f"/api/v2/people/{long_p}", "/api/v2/households/H-" + "1" * 14):
        r = client.get(path)
        assert r.status_code in (404, 422), path          # never 500
        if r.status_code == 404:
            assert r.json() == missing, path
    with Session(engine) as db:
        ids = [e.resource_id for e in db.scalars(select(AuditEvent).where(AuditEvent.id > before)
                                                  .order_by(AuditEvent.id)).all()]
    assert ids[0] == "H-999" and all(i == "<malformed>" for i in ids[1:]) and len(ids) >= 2
