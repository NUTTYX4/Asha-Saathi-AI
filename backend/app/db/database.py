"""Database engines.

- PostgreSQL/PostGIS (V2, Docker): schema is managed only by Alembic; never `create_all`.
- SQLite (Round 1 local workflow and unit tests): tables are created if missing. An existing
  Round 1 file is used as-is; nothing is altered or deleted.

Only confirmed structured fields are stored: no audio and no transcripts.
"""

from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text

from app.db.models import SQLITE_TABLES, Base


def connect(db_file: Path) -> Engine:
    """SQLite engine for the Round 1 file or a test file."""
    db_file.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_file.as_posix()}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    # Only non-spatial tables: households/people need PostGIS and exist only on PostgreSQL.
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[name] for name in SQLITE_TABLES])
    return engine


def connect_postgres(url: str) -> Engine:
    """PostgreSQL engine. Assumes `alembic upgrade head` has already run."""
    # hide_parameters: SQL errors never echo bound values (search text, coordinates) into logs.
    return create_engine(url, pool_pre_ping=True, hide_parameters=True)


def backend_name(engine: Engine) -> str:
    return engine.dialect.name


def ping(engine: Engine) -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
