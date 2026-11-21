"""Sessions, principals and territory-scoped access checks.

Authorization lives here (service layer), not only in route wrappers: every territory-scoped
read goes through `visible_territory_ids` / `ensure_territory_access`.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.passwords import verify_password
from app.db.models import AuditEvent, AuthSession, Territory, TerritoryAssignment, User


class AccessDenied(Exception):
    """Raised when a principal may not see a resource. Routes map it to 404 (no ID probing)."""


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    username: str
    display_name: str
    role: str
    territory_ids: frozenset[uuid.UUID]

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ------------------------------------------------------------------ authentication
def authenticate(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username.strip().lower()))
    ok = verify_password(user.password_hash if user else None, password)
    if not ok or user is None or not user.active:
        return None
    return user


def create_session(db: Session, user: User, ttl_hours: int) -> str:
    token = secrets.token_urlsafe(32)
    now = utcnow()
    db.add(AuthSession(token_hash=_token_hash(token), user_id=user.id, created_at=now,
                       expires_at=now + timedelta(hours=ttl_hours)))
    user.last_login_at = now
    return token


def revoke_session(db: Session, token: str) -> None:
    row = db.get(AuthSession, _token_hash(token))
    if row and row.revoked_at is None:
        row.revoked_at = utcnow()


def user_for_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    row = db.get(AuthSession, _token_hash(token))
    if row is None or row.revoked_at is not None or _aware(row.expires_at) <= utcnow():
        return None
    user = db.get(User, row.user_id)
    return user if user and user.active else None


def set_user_password(db: Session, user: User, password: str) -> None:
    """Set a new password, activate the account and revoke all its existing sessions."""
    from app.auth.passwords import hash_password  # local import keeps module import order simple

    user.password_hash = hash_password(password)
    user.active = True
    for session_row in db.scalars(select(AuthSession).where(AuthSession.user_id == user.id,
                                                            AuthSession.revoked_at.is_(None))).all():
        session_row.revoked_at = utcnow()


# ------------------------------------------------------------------ authorization
def active_territory_ids(db: Session, user_id: uuid.UUID) -> frozenset[uuid.UUID]:
    rows = db.scalars(
        select(TerritoryAssignment.territory_id)
        .join(Territory, Territory.id == TerritoryAssignment.territory_id)
        .where(TerritoryAssignment.user_id == user_id, TerritoryAssignment.ends_at.is_(None),
               Territory.active.is_(True))
    ).all()
    return frozenset(rows)


def load_principal(db: Session, user: User) -> Principal:
    return Principal(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        territory_ids=active_territory_ids(db, user.id),
    )


def visible_territory_ids(db: Session, principal: Principal) -> frozenset[uuid.UUID]:
    """Admins see every territory; workers and supervisors only their active assignments."""
    if principal.is_admin:
        return frozenset(db.scalars(select(Territory.id)).all())
    return principal.territory_ids


def ensure_territory_access(db: Session, principal: Principal, territory_id: uuid.UUID) -> None:
    if territory_id not in visible_territory_ids(db, principal):
        raise AccessDenied()


# ------------------------------------------------------------------ audit
def audit(db: Session, *, actor: uuid.UUID | None, action: str, resource_kind: str,
          resource_id: str | None = None, request_id: str | None = None,
          details: dict | None = None) -> None:
    """Record an audit event. `details` must hold only field names / codes, never content."""
    db.add(AuditEvent(actor_user_id=actor, action=action, resource_kind=resource_kind,
                      resource_id=resource_id, request_id=request_id, details=details))
