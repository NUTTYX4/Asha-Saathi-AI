"""V2 auth / territory / admin API schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["worker", "supervisor", "admin"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class TerritoryOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    active: bool
    is_demo_data: bool


class MeOut(BaseModel):
    user_id: uuid.UUID
    username: str
    display_name: str
    role: Role
    territories: list[TerritoryOut]


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=120)
    role: Role
    password: str = Field(min_length=12, max_length=256)


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    role: Role
    active: bool


class TerritoryCreate(BaseModel):
    code: str = Field(min_length=1, max_length=16, pattern=r"^[A-Z0-9-]+$")
    name: str = Field(min_length=1, max_length=120)


class AssignmentCreate(BaseModel):
    user_id: uuid.UUID
    territory_id: uuid.UUID


class AssignmentOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    territory_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime | None


class AuditOut(BaseModel):
    id: int
    occurred_at: datetime
    actor_user_id: uuid.UUID | None
    action: str
    resource_kind: str
    resource_id: str | None
    request_id: str | None
    details: dict | None
