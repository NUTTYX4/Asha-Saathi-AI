"""V2 household / person API schemas. The map list (HouseholdPin) carries no clinical data."""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Sex = Literal["female", "male", "other", "not_recorded"]
RelationshipToHead = Literal[
    "head", "spouse", "son", "daughter", "father", "mother", "father_in_law", "mother_in_law",
    "son_in_law", "daughter_in_law", "grandson", "granddaughter", "brother", "sister", "other",
]


class HouseholdPin(BaseModel):
    """Map-safe summary: location and counts only (no programmes, no conditions)."""

    id: uuid.UUID
    public_id: str
    label: str
    landmark: str | None
    territory_code: str
    latitude: float
    longitude: float
    location_source: str
    member_count: int
    is_demo_data: bool


class NearbyHousehold(HouseholdPin):
    """A map pin plus its server-computed distance from the query point (metres, geography).
    A suggestion only: being near a pin never selects or confirms that household."""

    distance_m: float


class SurveyOut(BaseModel):
    survey_version: str
    status: str
    drinking_water_source: str
    has_toilet: bool | None
    submitted_on: date


class HouseholdDetail(HouseholdPin):
    latest_survey: SurveyOut | None


class AgeOut(BaseModel):
    basis: Literal["date_of_birth", "recorded_age", "unknown"]
    years: int | None = None
    months: int | None = None   # for children under 2
    days: int | None = None     # for infants under 60 days


class EnrolmentOut(BaseModel):
    programme: str
    status: str
    started_on: date
    source: str


class RelationshipOut(BaseModel):
    relationship_type: str
    direction: Literal["outgoing", "incoming"]   # outgoing: THIS person is <type> of the other
    other_person_public_id: str
    other_person_name: str


class PersonOut(BaseModel):
    id: uuid.UUID
    public_id: str
    household_public_id: str
    full_name: str
    sex: Sex
    date_of_birth: date | None
    age: AgeOut
    relationship_to_head: RelationshipToHead
    residence_status: str
    programmes: list[EnrolmentOut]
    relationships: list[RelationshipOut]
    is_demo_data: bool


class MemberCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    sex: Sex
    relationship_to_head: RelationshipToHead
    date_of_birth: date | None = None
    recorded_age_years: int | None = Field(default=None, ge=0, le=120)
