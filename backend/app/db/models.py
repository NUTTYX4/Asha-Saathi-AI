"""SQLAlchemy ORM models. The PostgreSQL schema is created only by Alembic migrations
(`backend/migrations`). Only confirmed structured fields are stored: no audio, no transcripts."""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, Identity, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# JSONB on PostgreSQL, JSON text on SQLite (compatible with the Round 1 SQLite file).
JsonType = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


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
    next_visit_date: Mapped[date | None] = mapped_column(Date)
    danger_signs: Mapped[list[str]] = mapped_column(JsonType, nullable=False)  # rule IDs
    requires_phc_referral: Mapped[bool] = mapped_column(Boolean, nullable=False)
    language: Mapped[str | None] = mapped_column(String(16))
    record_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
