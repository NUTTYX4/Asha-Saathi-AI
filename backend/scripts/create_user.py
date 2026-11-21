"""Create a user (e.g. the first admin). A random password is generated and shown ONCE.

    docker compose exec api python -m scripts.create_user --username admin --display-name "Admin" --role admin

The password is never written to disk or logs by this script; store it in a password manager.
"""

import argparse
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.auth.service import audit
from app.core.config import get_settings
from app.db.database import connect, connect_postgres
from app.db.models import User


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--role", choices=["worker", "supervisor", "admin"], required=True)
    args = parser.parse_args()

    settings = get_settings()
    engine = (connect_postgres(settings.database_url.get_secret_value()) if settings.database_url
              else connect(settings.database_file))
    username = args.username.strip().lower()
    with Session(engine) as db:
        if db.scalar(select(User).where(User.username == username)):
            raise SystemExit(f"User {username!r} already exists; nothing changed.")
        password = secrets.token_urlsafe(18)
        user = User(username=username, display_name=args.display_name, role=args.role,
                    password_hash=hash_password(password))
        db.add(user)
        db.flush()
        audit(db, actor=None, action="user.create_cli", resource_kind="user", resource_id=str(user.id),
              details={"role": args.role})
        db.commit()
    print(f"Created {args.role} {username!r}.")
    print(f"One-time password (shown once, not stored): {password}")


if __name__ == "__main__":
    main()
