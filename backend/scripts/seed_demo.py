"""Seed (or check) the synthetic demo dataset. PostgreSQL only; safe to run repeatedly.

    docker compose exec api python -m scripts.seed_demo            # add anything missing, then check
    docker compose exec api python -m scripts.seed_demo --check    # read-only invariant report
    docker compose exec api python -m scripts.seed_demo --as-of 2026-11-21

Never modifies existing rows and never prints passwords. New demo accounts are inactive until
you run `python -m scripts.set_password --demo-accounts`.
"""

import argparse
import json
import sys
from datetime import date

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import connect_postgres
from app.seed.demo import check_demo, seed_demo
from app.seed.demo_data import DEMO_AS_OF


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="read-only invariant report")
    parser.add_argument("--as-of", type=date.fromisoformat, default=DEMO_AS_OF,
                        help="demo clock for dates of birth / enrolment dates (default %(default)s)")
    args = parser.parse_args()

    settings = get_settings()
    if settings.database_url is None:
        print("DATABASE_URL is not set: the demo dataset needs PostgreSQL/PostGIS (run inside Docker).")
        return 2
    engine = connect_postgres(settings.database_url.get_secret_value())
    with Session(engine) as db:
        if not args.check:
            report = seed_demo(db, as_of=args.as_of)
            print("created :", dict(report.created) or "nothing (already seeded)")
            print("existing:", dict(report.existing) or "none")
            if report.accounts_without_password:
                print("New demo accounts are INACTIVE until you set a password:")
                print("  docker compose exec api python -m scripts.set_password --demo-accounts")
        result = check_demo(db)
    print(json.dumps(result, indent=2))
    print("INVARIANTS:", "OK" if not result["violations"] else f"{len(result['violations'])} VIOLATION(S)")
    return 0 if not result["violations"] else 1


if __name__ == "__main__":
    sys.exit(main())
