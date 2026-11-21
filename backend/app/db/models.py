"""SQLAlchemy ORM models. The PostgreSQL schema is created only by Alembic migrations
(`backend/migrations`). Only confirmed structured fields are stored: no audio, no transcripts."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# JSONB on PostgreSQL, JSON text on SQLite (compatible with the Round 1 SQLite file).
JsonType = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")
# BIGINT identity on PostgreSQL; INTEGER on SQLite so the rowid autoincrements.
BigIdType = BigInteger().with_variant(Integer, "sqlite")

ROLES = ("worker", "supervisor", "admin")


class Base(DeclarativeBase):
    pass


class Visit(Base):
    """A confirmed visit. Column names match the Round 1 SQLite `visits` table."""

    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    beneficiary_id: Mapped[str] = mapped_column(String(64), nullable=False)
    visit_type: Mapped[str] = mapped_column(String(32), nullable=False)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    vaccinations_due: Mapped[list[str] | None] = mapped_column(JsonType)  # NULL = not mentioned
    next_visit_date: Mapped[date | None] = mapped_column(Date, index=True)
    danger_signs: Mapped[list[str]] = mapped_column(JsonType, nullable=False)  # rule IDs
    requires_phc_referral: Mapped[bool] = mapped_column(Boolean, nullable=False)
    language: Mapped[str | None] = mapped_column(String(16))
    record_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    __table_args__ = (
        CheckConstraint("record_version >= 0", name="ck_visits_record_version_nonneg"),
        CheckConstraint("weight_kg IS NULL OR (weight_kg > 0 AND weight_kg < 250)", name="ck_visits_weight_range"),
    )


# ---------------------------------------------------------------- identity / access (V2)
class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(f"role IN {ROLES}", name="ck_users_role"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Territory(Base):
    __tablename__ = "territories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TerritoryAssignment(Base):
    """Which user may act in which territory. Ending an assignment sets ends_at (never deleted)."""

    __tablename__ = "territory_assignments"
    __table_args__ = (
        Index(
            "uq_territory_assignments_active",
            "user_id",
            "territory_id",
            unique=True,
            postgresql_where=text("ends_at IS NULL"),
            sqlite_where=text("ends_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    territory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("territories.id", ondelete="RESTRICT"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class AuthSession(Base):
    """Server-side login session. Only a SHA-256 hash of the cookie token is stored."""

    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    """Who did what to which resource. Never holds transcripts, audio, passwords or tokens."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigIdType, Identity(), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict | None] = mapped_column(JsonType)  # sanitised: field names / codes only
