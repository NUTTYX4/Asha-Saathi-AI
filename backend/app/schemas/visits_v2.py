"""Confirmed, person-linked V2 visit as returned by the history API. Structured fields only:
no transcript, audio, prompt or draft is ever stored or returned."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.visit import VisitType


class V2VisitOut(BaseModel):
    id: uuid.UUID
    client_visit_id: uuid.UUID
    person_public_id: str
    household_public_id: str
    recorded_by: str
    visit_type: VisitType
    subject_population: str
    weight_kg: float | None
    vaccinations_due: list[str] | None
    next_visit_date: date | None
    danger_signs: list[str]
    requires_phc_referral: bool
    rule_status: str
    ruleset_version: str
    extraction_source: str
    record_version: int
    confirmed_at: datetime
    is_demo_data: bool
