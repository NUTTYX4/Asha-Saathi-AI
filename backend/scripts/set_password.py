"""Set a password interactively (typed, never echoed, printed or logged). Activates the account
and revokes its existing sessions.

    docker compose exec api python -m scripts.set_password --username demo_worker_a
    docker compose exec api python -m scripts.set_password --demo-accounts   # same password for all demo accounts

Must be run in an interactive terminal; it refuses piped input so passwords never pass through
shell history, pipes or logs.
"""

import argparse
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.passwords import MIN_PASSWORD_LENGTH
from app.auth.service import audit, set_user_password
from app.core.config import get_settings
from app.db.database import connect, connect_postgres
from app.db.models import User


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--username")
    group.add_argument("--demo-accounts", action="store_true", help="all accounts marked is_demo_data")
    args = parser.parse_args()

    if not sys.stdin.isatty():
        print("Refusing: run this in an interactive terminal (docker compose exec allocates one).")
        return 2

    settings = get_settings()
    engine = (connect_postgres(settings.database_url.get_secret_value()) if settings.database_url
              else connect(settings.database_file))
    with Session(engine) as db:
        if args.demo_accounts:
            users = db.scalars(select(User).where(User.is_demo_data.is_(True)).order_by(User.username)).all()
        else:
            users = db.scalars(select(User).where(User.username == args.username.strip().lower())).all()
        if not users:
            print("No matching account; nothing changed.")
            return 1
        print("Setting the password for:", ", ".join(u.username for u in users))
        first = getpass.getpass(f"New password (min {MIN_PASSWORD_LENGTH} characters): ")
        second = getpass.getpass("Repeat password: ")
        if first != second:
            print("Passwords do not match; nothing changed.")
            return 1
        if len(first) < MIN_PASSWORD_LENGTH:
            print(f"Too short (min {MIN_PASSWORD_LENGTH}); nothing changed.")
            return 1
        for user in users:
            set_user_password(db, user, first)
            audit(db, actor=None, action="user.password_set_cli", resource_kind="user", resource_id=str(user.id))
        db.commit()
    print(f"Password set and account(s) activated: {len(users)}. Existing sessions were revoked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
