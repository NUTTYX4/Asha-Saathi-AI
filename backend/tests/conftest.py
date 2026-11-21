"""Shared test helpers.

PostgreSQL tests (run inside Docker) each get their own disposable database
`<app db>_test_<suffix>` on the same server; the application database is never touched.
"""

import os
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

# Tests assume the safe default V2_VOICE_ENABLED=false even when the operator's .env has it enabled
# for a live demo; voice tests opt in explicitly via monkeypatch.
os.environ["V2_VOICE_ENABLED"] = "false"

APP_URL = os.environ.get("DATABASE_URL", "")
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
requires_postgres = pytest.mark.skipif(
    not APP_URL.startswith("postgresql"), reason="PostgreSQL DATABASE_URL not set (run inside Docker)"
)


@contextmanager
def disposable_pg_database(suffix: str):
    """Create an empty database, point DATABASE_URL at it (for Alembic), drop it afterwards."""
    app_url = make_url(APP_URL)
    name = f"{app_url.database}_test_{suffix}"
    admin = create_engine(app_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = app_url.set(database=name).render_as_string(hide_password=False)
    mp = pytest.MonkeyPatch()
    mp.setenv("DATABASE_URL", url)  # migrations/env.py reads it
    try:
        yield url
    finally:
        mp.undo()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def alembic_config():
    from alembic.config import Config

    return Config(os.path.join(BACKEND_DIR, "alembic.ini"))


@pytest.fixture(scope="session", autouse=True)
def _reset_settings_cache():
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
