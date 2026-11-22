"""Admin dashboard responses (Phase 7). Counts come straight from PostgreSQL; nothing is estimated.

Definitions used everywhere (also shown in the UI):
- households_registered: households in scope (territory filter) on the register.
- households_visited: distinct households with at least one CONFIRMED visit in the date range.
- beneficiaries_visited: distinct people with at least one confirmed visit in the date range.
- followups_upcoming: people whose LATEST confirmed visit (any date) records a next-visit date today or later.
- followups_date_passed: people whose latest confirmed visit records a next-visit date before today and
  who have no later confirmed visit. This is a fact about the records, not a judgement about anyone.
Dates are calendar days in India Standard Time.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.auth import Role


class AdminFilters(BaseModel):
    date_from: date | None
    date_to: date | None
    territory_id: uuid.UUID | None
    worker_id: uuid.UUID | None


class AdminOverview(BaseModel):
    filters: AdminFilters
    active_workers: int
    territories_total: int
    territories_with_worker: int
    households_registered: int
    households_without_assigned_worker: int
    beneficiaries_registered: int
    visits_confirmed: int
    households_visited: int
    beneficiaries_visited: int
    visits_by_type: dict[str, int]
    followups_upcoming: int
    followups_date_passed: int


class TerritoryRef(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class AdminWorker(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    active: bool
    territories: list[TerritoryRef]
    households_assigned: int
    visits_confirmed: int
    households_visited: int
    beneficiaries_visited: int
    last_visit_at: datetime | None
    followups_upcoming: int


class AdminVisit(BaseModel):
    """Minimum necessary: public IDs, no names, no transcripts, no clinical free text."""

    id: uuid.UUID
    confirmed_at: datetime
    worker_id: uuid.UUID
    worker_username: str
    worker_display_name: str
    territory_code: str
    household_public_id: str
    person_public_id: str
    visit_type: str
    status: str = "confirmed"
    record_version: int
    next_visit_date: date | None
    danger_sign_count: int
    requires_phc_referral: bool


class AdminVisitPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AdminVisit]


class CoverageHousehold(BaseModel):
    id: uuid.UUID
    public_id: str
    latitude: float
    longitude: float
    visited_in_range: bool
    last_visit_at: datetime | None


class AdminTerritoryCoverage(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    active: bool
    workers: list[str]
    households_registered: int
    households_visited: int
    households_not_visited: int
    last_visit_at: datetime | None
    households: list[CoverageHousehold]


class AdminUser(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    role: Role
    active: bool


class AdminAssignment(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    username: str
    display_name: str
    role: Role
    territory_id: uuid.UUID
    territory_code: str
    territory_name: str
    starts_at: datetime
    ends_at: datetime | None
    created_by_username: str | None


class ReassignRequest(BaseModel):
    model_config = {"extra": "forbid"}

    territory_id: uuid.UUID = Field(description="Territory the worker moves to; the current assignment ends")
