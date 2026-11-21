"""Canonical visit-record contract. Frontend types are generated from this module.

Null means "not mentioned / unknown"; values are never guessed.
"""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class VisitType(str, Enum):
    ANC = "ANC"
    PNC = "PNC"
    NEWBORN = "newborn"
    IMMUNISATION = "immunisation"
    ROUTINE = "routine"
    UNKNOWN = "unknown"


class RecordStatus(str, Enum):
    DRAFT = "draft"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"


# Fields the agent must have before it reads the record back for confirmation.
REQUIRED_FIELDS: tuple[str, ...] = ("beneficiary_id", "visit_type", "next_visit_date")


class VisitRecord(BaseModel):
    """The in-progress or confirmed visit record shared by backend and frontend."""

    model_config = ConfigDict(use_enum_values=False, json_schema_serialization_defaults_required=True)

    beneficiary_id: str | None = None
    visit_type: VisitType = VisitType.UNKNOWN
    weight_kg: float | None = Field(default=None, gt=0, lt=250)
    # None = vaccinations not mentioned; [] = explicitly none due.
    vaccinations_due: list[str] | None = None
    next_visit_date: date | None = None
    danger_signs: list[str] = Field(default_factory=list, description="Matched safety rule IDs")
    requires_phc_referral: bool = False
    language: str | None = None
    status: RecordStatus = RecordStatus.DRAFT
    # Incremented on every change. Confirmation must name the version that was read back.
    record_version: int = 0
    missing_fields: list[str] = Field(default_factory=list)

    def compute_missing(self) -> list[str]:
        missing = []
        for name in REQUIRED_FIELDS:
            value = getattr(self, name)
            if value is None or value == VisitType.UNKNOWN:
                missing.append(name)
        return missing


class SavedVisit(BaseModel):
    """A confirmed visit as persisted. No transcripts or audio are stored."""

    id: int
    beneficiary_id: str
    visit_type: VisitType
    weight_kg: float | None
    vaccinations_due: list[str] | None
    next_visit_date: date | None
    danger_signs: list[str]
    requires_phc_referral: bool
    language: str | None
    record_version: int
    created_at: datetime


class FollowUpItem(BaseModel):
    visit_id: int
    beneficiary_id: str
    visit_type: VisitType
    due_date: date | None
    vaccinations_due: list[str] | None
    requires_phc_referral: bool
    danger_signs: list[str]
