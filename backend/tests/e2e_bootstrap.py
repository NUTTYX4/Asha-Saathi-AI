"""Browser end-to-end support: create and remove the disposable e2e database.

Run only by the harness (`e2e/phase4_browser.py`), in a one-off api-e2e container:
    docker compose --profile e2e run --rm -T api-e2e python -m tests.e2e_bootstrap setup   (passwords on stdin)
    docker compose --profile e2e run --rm -T api-e2e python -m tests.e2e_bootstrap teardown

DATABASE_URL only supplies the server and credentials: the one database this module creates,
migrates, seeds or drops is the constant E2E_DB (`asha_saathi_e2e`). The application database
is never opened. The harness generates one-time random passwords for the demo accounts of this
disposable database and sends them on stdin; they are hashed with the normal Argon2 code and
never printed or logged. Real accounts get passwords only through the interactive
`scripts.set_password`.
"""

from __future__ import annotations

import json
import os
import sys

from alembic import command
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

E2E_DB = "asha_saathi_e2e"
EXTRA_SUPERVISOR = "e2e_supervisor_a"   # e2e-only account: supervisor granted Territory A only


def _urls() -> tuple[URL, URL]:
    """(maintenance database URL, e2e database URL) on the server named by DATABASE_URL."""
    server = make_url(os.environ["DATABASE_URL"])
    return server.set(database="postgres"), server.set(database=E2E_DB)


def _drop_and_create(admin_url: URL, create: bool) -> None:
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{E2E_DB}" WITH (FORCE)'))
        if create:
            conn.execute(text(f'CREATE DATABASE "{E2E_DB}"'))
    engine.dispose()


def setup() -> None:
    from alembic.config import Config

    from app.auth.service import set_user_password
    from app.db.models import Territory, TerritoryAssignment, User
    from app.seed.demo import check_demo, seed_demo

    passwords: dict[str, str] = json.load(sys.stdin)
    admin_url, e2e_url = _urls()
    _drop_and_create(admin_url, create=True)
    url = e2e_url.render_as_string(hide_password=False)
    os.environ["DATABASE_URL"] = url  # migrations/env.py reads it
    command.upgrade(Config(os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini")), "head")

    engine = create_engine(url)
    with Session(engine) as db:
        seed_demo(db)
        territory_a = db.scalar(select(Territory).where(Territory.code == "DEMO-A"))
        extra = User(username=EXTRA_SUPERVISOR, display_name="E2E Supervisor (Territory A only)",
                     role="supervisor", password_hash="!", active=False, is_demo_data=True)
        db.add(extra)
        db.flush()
        db.add(TerritoryAssignment(user_id=extra.id, territory_id=territory_a.id))
        for username, password in passwords.items():
            user = db.scalar(select(User).where(User.username == username))
            if user is None:
                raise SystemExit(f"unknown account in e2e password list: {username}")
            set_user_password(db, user, password)
        db.commit()
        report = check_demo(db)
    engine.dispose()
    # Counts only: never passwords.
    print(json.dumps({"database": E2E_DB, "households": report["households"], "people": report["people"],
                      "per_territory": report["households_per_territory"], "violations": report["violations"],
                      "accounts_with_password": sorted(passwords)}))


def teardown() -> None:
    admin_url, _ = _urls()
    _drop_and_create(admin_url, create=False)
    print(json.dumps({"dropped": E2E_DB}))


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"setup", "teardown"}:
        raise SystemExit("usage: python -m tests.e2e_bootstrap setup|teardown")
    setup() if sys.argv[1] == "setup" else teardown()
