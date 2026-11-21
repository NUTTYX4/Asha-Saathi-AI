"""PostgreSQL/PostGIS integration tests (V2 Phase 1).

Run inside Docker:  docker compose exec api python -m pytest -q
They use a separate disposable database `<name>_test` on the same server, never the app
database. Skipped automatically when DATABASE_URL is not a PostgreSQL URL (e.g. host runs).
"""

import os
from datetime import date

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.db.repositories import UnconfirmedRecordError, VisitRepository
from app.schemas.visit import RecordStatus, VisitRecord, VisitType

APP_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not APP_URL.startswith("postgresql"), reason="PostgreSQL DATABASE_URL not set (run inside Docker)"
)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def test_url(monkeypatch_module):
    app_url = make_url(APP_URL)
    test_name = f"{app_url.database}_test"
    admin = create_engine(app_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{test_name}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{test_name}"'))
    url = app_url.set(database=test_name).render_as_string(hide_password=False)
    monkeypatch_module.setenv("DATABASE_URL", url)  # migrations/env.py reads it
    yield url
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{test_name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def _alembic_cfg() -> Config:
    return Config(os.path.join(BACKEND_DIR, "alembic.ini"))


@pytest.fixture(scope="module")
def engine(test_url):
    command.upgrade(_alembic_cfg(), "head")
    eng = create_engine(test_url)
    yield eng
    eng.dispose()


def _confirmed(**kw) -> VisitRecord:
    base = dict(
        beneficiary_id="P-TEST-1",
        visit_type=VisitType.ANC,
        weight_kg=52.0,
        vaccinations_due=["TT"],
        next_visit_date=date(2026, 12, 5),
        status=RecordStatus.CONFIRMED,
        record_version=3,
        language="kn-IN",
    )
    base.update(kw)
    return VisitRecord(**base)


def test_postgis_extension_installed(engine):
    with engine.connect() as conn:
        version = conn.execute(text("SELECT postgis_version()")).scalar_one()
    assert version


def test_migration_creates_visits_schema(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("visits")}
    assert {"id", "beneficiary_id", "visit_type", "vaccinations_due", "danger_signs",
            "requires_phc_referral", "record_version", "created_at"} <= cols
    assert "transcript" not in " ".join(cols)  # no transcript storage


def test_roundtrip_confirmed_visit(engine):
    repo = VisitRepository(engine)
    vid = repo.save_confirmed(_confirmed())
    saved = repo.list_visits()[0]
    assert saved.id == vid
    assert saved.vaccinations_due == ["TT"]
    assert saved.next_visit_date == date(2026, 12, 5)
    assert saved.created_at.tzinfo is not None


def test_none_vs_empty_vaccinations_preserved(engine):
    repo = VisitRepository(engine)
    a = repo.save_confirmed(_confirmed(beneficiary_id="P-TEST-2", vaccinations_due=None))
    b = repo.save_confirmed(_confirmed(beneficiary_id="P-TEST-3", vaccinations_due=[]))
    by_id = {v.id: v for v in repo.list_visits()}
    assert by_id[a].vaccinations_due is None   # not mentioned
    assert by_id[b].vaccinations_due == []     # explicitly none


def test_unconfirmed_never_saved(engine):
    repo = VisitRepository(engine)
    before = len(repo.list_visits())
    with pytest.raises(UnconfirmedRecordError):
        repo.save_confirmed(_confirmed(status=RecordStatus.PENDING_CONFIRMATION))
    assert len(repo.list_visits()) == before


def test_followups_put_referrals_first(engine):
    repo = VisitRepository(engine)
    ref = repo.save_confirmed(_confirmed(beneficiary_id="P-TEST-4", visit_type=VisitType.NEWBORN,
                                         next_visit_date=None, danger_signs=["NB_FEVER"],
                                         requires_phc_referral=True))
    assert repo.list_followups()[0].visit_id == ref


def test_database_check_constraint_rejects_bad_weight(engine):
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO visits (beneficiary_id, visit_type, weight_kg, danger_signs, "
                "requires_phc_referral, record_version) VALUES ('x','ANC',999,'[]',false,1)"))


def test_migrations_match_models(engine):
    """Hand-written migrations must produce exactly the schema the ORM models describe."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.db.models import Base

    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    diff = [d for d in diff if not (isinstance(d, tuple) and "spatial_ref_sys" in str(d))]  # PostGIS table
    assert diff == []


def test_auth_tables_exist_with_constraints(engine):
    tables = set(inspect(engine).get_table_names())
    assert {"users", "territories", "territory_assignments", "auth_sessions", "audit_events"} <= tables
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO users (id, username, display_name, role, password_hash, active, is_demo) "
                              "VALUES (gen_random_uuid(), 'x', 'X', 'superuser', 'h', true, false)"))


def test_downgrade_and_upgrade_again(engine, test_url):
    """Rollback path: downgrade to base, then upgrade to head on a clean schema."""
    engine.dispose()
    command.downgrade(_alembic_cfg(), "base")
    assert "visits" not in inspect(create_engine(test_url)).get_table_names()
    command.upgrade(_alembic_cfg(), "head")
    assert "visits" in inspect(create_engine(test_url)).get_table_names()
