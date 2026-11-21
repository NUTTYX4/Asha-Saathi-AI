"""Create a user (e.g. the first admin). The password is typed interactively: never echoed,
printed, stored in plain text or logged.

    docker compose exec api python -m scripts.create_user --username admin --display-name "Admin" --role admin
"""

import argparse
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.passwords import MIN_PASSWORD_LENGTH, hash_password
from app.auth.service import audit
from app.core.config import get_settings
from app.db.database import connect, connect_postgres
from app.db.models import User


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--role", choices=["worker", "supervisor", "admin"], required=True)
    args = parser.parse_args()

    if not sys.stdin.isatty():
        print("Refusing: run this in an interactive terminal (docker compose exec allocates one).")
        return 2

    settings = get_settings()
    engine = (connect_postgres(settings.database_url.get_secret_value()) if settings.database_url
              else connect(settings.database_file))
    username = args.username.strip().lower()
    with Session(engine) as db:
        if db.scalar(select(User).where(User.username == username)):
            print(f"User {username!r} already exists; nothing changed.")
            return 1
        first = getpass.getpass(f"Password for {username} (min {MIN_PASSWORD_LENGTH} characters): ")
        if first != getpass.getpass("Repeat password: ") or len(first) < MIN_PASSWORD_LENGTH:
            print("Passwords differ or are too short; nothing changed.")
            return 1
        user = User(username=username, display_name=args.display_name, role=args.role,
                    password_hash=hash_password(first))
        db.add(user)
        db.flush()
        audit(db, actor=None, action="user.create_cli", resource_kind="user", resource_id=str(user.id),
              details={"role": args.role})
        db.commit()
    print(f"Created {args.role} {username!r}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
