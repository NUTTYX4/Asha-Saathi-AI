"""SQLAlchemy ORM models. The PostgreSQL schema is created only by Alembic migrations
(`backend/migrations`). Only confirmed structured fields are stored: no audio, no transcripts.

Spatial tables (households and everything that hangs off them) exist only on PostgreSQL/PostGIS;
the SQLite fallback creates only the Round 1 and auth tables (see app/db/database.py).
"""

import uuid
from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geography, Geometry
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
    UniqueConstraint,
    Uuid,
    cast,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, column_property, mapped_column

# JSONB on PostgreSQL, JSON text on SQLite (compatible with the Round 1 SQLite file).
JsonType = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")
# BIGINT identity on PostgreSQL; INTEGER on SQLite so the rowid autoincrements.
BigIdType = BigInteger().with_variant(Integer, "sqlite")

ROLES = ("worker", "supervisor", "admin")
SEXES = ("female", "male", "other", "not_recorded")
RELATIONSHIPS_TO_HEAD = (
    "head", "spouse", "son", "daughter", "father", "mother", "father_in_law", "mother_in_law",
    "son_in_law", "daughter_in_law", "grandson", "granddaughter", "brother", "sister", "other",
)
RESIDENCE_STATUSES = ("resident", "temporarily_away", "moved_out")
RELATIONSHIP_TYPES = ("mother_of", "father_of", "guardian_of", "spouse_of")
PROGRAMMES = ("ANC", "PNC", "NEWBORN", "IMMUNISATION", "NCD_FOLLOWUP")
ENROLMENT_STATUSES = ("active", "completed", "withdrawn")
RECORD_SOURCES = ("demo_seed", "worker_entry")
LOCATION_SOURCES = ("synthetic_demo", "gps", "manual")
WATER_SOURCES = ("piped", "tube_well", "public_tap", "tanker", "other", "not_recorded")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


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
    __table_args__ = (CheckConstraint(_in("role", ROLES), name="ck_users_role"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
    is_demo_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


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


# ---------------------------------------------------------------- households / people (V2, PostGIS)
class Household(Base):
    """A household and its map pin. The pin is a location, not medical data."""

    __tablename__ = "households"
    __table_args__ = (
        CheckConstraint(r"public_id ~ '^H-[0-9]{3,}$'", name="ck_households_public_id"),
        CheckConstraint(_in("location_source", LOCATION_SOURCES), name="ck_households_location_source"),
        CheckConstraint("location_accuracy_m IS NULL OR location_accuracy_m >= 0",
                        name="ck_households_location_accuracy"),
        Index("ix_households_location", "location", postgresql_using="gist"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    public_id: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    territory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("territories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    landmark: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    location_source: Mapped[str] = mapped_column(String(16), nullable=False)
    location_accuracy_m: Mapped[float | None] = mapped_column(Float)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_demo_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Read-only WGS84 coordinates derived from the PostGIS point.
    latitude: Mapped[float] = column_property(func.ST_Y(cast(location, Geometry)))
    longitude: Mapped[float] = column_property(func.ST_X(cast(location, Geometry)))


class Person(Base):
    """A household member. Programme status lives in programme_enrolments (explicit only);
    nothing clinical is inferred from age, sex or family role."""

    __tablename__ = "people"
    __table_args__ = (
        CheckConstraint(r"public_id ~ '^P-[0-9]{3,}$'", name="ck_people_public_id"),
        CheckConstraint(_in("sex", SEXES), name="ck_people_sex"),
        CheckConstraint(_in("relationship_to_head", RELATIONSHIPS_TO_HEAD), name="ck_people_relationship_to_head"),
        CheckConstraint(_in("residence_status", RESIDENCE_STATUSES), name="ck_people_residence_status"),
        CheckConstraint("recorded_age_years IS NULL OR (recorded_age_years >= 0 AND recorded_age_years <= 120)",
                        name="ck_people_recorded_age_range"),
        CheckConstraint("(recorded_age_years IS NULL) = (age_recorded_on IS NULL)",
                        name="ck_people_recorded_age_has_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    public_id: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    sex: Mapped[str] = mapped_column(String(16), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date)          # NULL = not recorded
    recorded_age_years: Mapped[int | None] = mapped_column(Integer)   # when DOB is unknown
    age_recorded_on: Mapped[date | None] = mapped_column(Date)
    relationship_to_head: Mapped[str] = mapped_column(String(24), nullable=False)
    residence_status: Mapped[str] = mapped_column(String(24), nullable=False, default="resident")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_demo_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PersonRelationship(Base):
    """Explicit family edge, e.g. (mother) --mother_of--> (newborn). spouse_of is stored once."""

    __tablename__ = "person_relationships"
    __table_args__ = (
        UniqueConstraint("person_id", "related_person_id", "relationship_type", name="uq_person_relationships"),
        CheckConstraint("person_id <> related_person_id", name="ck_person_relationships_not_self"),
        CheckConstraint(_in("relationship_type", RELATIONSHIP_TYPES), name="ck_person_relationships_type"),
        CheckConstraint(_in("source", RECORD_SOURCES), name="ck_person_relationships_source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    related_person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProgrammeEnrolment(Base):
    """Explicit programme registration (ANC, PNC, newborn, ...). Never inferred."""

    __tablename__ = "programme_enrolments"
    __table_args__ = (
        CheckConstraint(_in("programme", PROGRAMMES), name="ck_programme_enrolments_programme"),
        CheckConstraint(_in("status", ENROLMENT_STATUSES), name="ck_programme_enrolments_status"),
        CheckConstraint(_in("source", RECORD_SOURCES), name="ck_programme_enrolments_source"),
        CheckConstraint("ended_on IS NULL OR ended_on >= started_on", name="ck_programme_enrolments_dates"),
        Index("uq_programme_enrolments_active", "person_id", "programme", unique=True,
              postgresql_where=text("status = 'active'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    programme: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    ended_on: Mapped[date | None] = mapped_column(Date)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class HouseholdSurvey(Base):
    """Limited, non-medical household survey (water source, toilet)."""

    __tablename__ = "household_surveys"
    __table_args__ = (
        UniqueConstraint("household_id", "survey_version", name="uq_household_surveys_version"),
        CheckConstraint("status IN ('draft', 'confirmed')", name="ck_household_surveys_status"),
        CheckConstraint(_in("drinking_water_source", WATER_SOURCES), name="ck_household_surveys_water"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    survey_version: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    drinking_water_source: Mapped[str] = mapped_column(String(16), nullable=False)
    has_toilet: Mapped[bool | None] = mapped_column(Boolean)  # NULL = not recorded
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    submitted_on: Mapped[date] = mapped_column(Date, nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# Tables the SQLite fallback creates (no PostGIS there).
SQLITE_TABLES = ("visits", "users", "territories", "territory_assignments", "auth_sessions", "audit_events")
