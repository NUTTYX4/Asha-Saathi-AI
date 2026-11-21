"""Households and people (V2). All access is territory-scoped in app/services/households.py;
another territory's household or person is reported as 404 (no ID probing)."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.auth.deps import current_principal, get_db, request_id, require_csrf, require_roles
from app.auth.service import AccessDenied, Principal
from app.schemas.households import HouseholdDetail, HouseholdPin, MemberCreate, PersonOut
from app.services import households as svc

router = APIRouter(tags=["v2-households"])
NOT_FOUND = HTTPException(404, "Not found")


@router.get("/households", response_model=list[HouseholdPin])
def list_households(territory: str | None = Query(None, max_length=16),
                    principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    """Map pins for the caller's territories: location and member count only."""
    return svc.list_households(db, principal, territory)


@router.get("/households/{key}", response_model=HouseholdDetail)
def get_household(key: str, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    try:
        return svc.household_detail(db, svc.get_household(db, principal, key))
    except AccessDenied:
        raise NOT_FOUND from None


@router.get("/households/{key}/members", response_model=list[PersonOut])
def list_members(key: str, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    try:
        household = svc.get_household(db, principal, key)
    except AccessDenied:
        raise NOT_FOUND from None
    return svc.people_out(db, svc.household_members(db, household))


@router.post("/households/{key}/members", response_model=PersonOut, status_code=201,
             dependencies=[Depends(require_csrf)])
def add_member(key: str, body: MemberCreate, request: Request,
               principal: Principal = Depends(require_roles("worker", "admin")),
               db: Session = Depends(get_db)):
    """Supervisors are read-only. Workers may add members only in their own territory."""
    try:
        household = svc.get_household(db, principal, key)
    except AccessDenied:
        raise NOT_FOUND from None
    try:
        person = svc.add_member(db, principal, household, body, request_id(request))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return svc.people_out(db, [person])[0]


@router.get("/people/{key}", response_model=PersonOut)
def get_person(key: str, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    try:
        person = svc.get_person(db, principal, key)
    except AccessDenied:
        raise NOT_FOUND from None
    return svc.people_out(db, [person])[0]
