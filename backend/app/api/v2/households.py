"""Households and people (V2). All access is territory-scoped in app/services/households.py;
another territory's household or person is reported as 404 (no ID probing).

Map discovery (Phase 4): list/search/bbox and nearby return map-safe pins only (no names, no
programmes). A pin is a candidate; the browser confirms a household by fetching its detail, and
confirms a member through /households/{key}/members/{person_key}, which rechecks that the person
belongs to that household. Nothing here selects a household from GPS.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from sqlalchemy.orm import Session

from app.auth.deps import current_principal, get_db, request_id, require_csrf, require_roles
from app.auth.service import AccessDenied, Principal, visible_territory_ids
from app.schemas.households import HouseholdDetail, HouseholdPin, MemberCreate, NearbyHousehold, PersonOut
from app.services import geo
from app.services import households as svc

router = APIRouter(tags=["v2-households"])
NOT_FOUND = HTTPException(404, "Not found")
NEXT_PAGE_HEADER = "X-Next-After"
# Longest valid key is a UUID (36 chars) or H-/P- with up to 13 digits.
Key = Annotated[str, Path(max_length=64)]


def reader(request: Request, principal: Principal = Depends(current_principal)) -> Principal:
    """Signed-in caller of a household/person read endpoint, within the per-user request budget."""
    if not request.app.state.discovery_limiter.allow(str(principal.user_id)):
        raise HTTPException(429, "Too many requests; wait a minute and try again")
    return principal


@router.get("/households", response_model=list[HouseholdPin])
def list_households(
    response: Response,
    territory: str | None = Query(None, pattern=r"^[A-Za-z0-9-]{1,16}$"),
    q: str | None = Query(None, max_length=geo.MAX_SEARCH_LENGTH,
                          description="Household ID or label text (case-insensitive)"),
    bbox: str | None = Query(None, max_length=128, description="min_lon,min_lat,max_lon,max_lat"),
    after: str | None = Query(None, max_length=16, description=f"Cursor from the {NEXT_PAGE_HEADER} header"),
    limit: int = Query(geo.MAX_PAGE_LIMIT, ge=1, le=geo.MAX_PAGE_LIMIT),
    principal: Principal = Depends(reader),
    db: Session = Depends(get_db),
):
    """Map pins for the caller's territories: location and member count only.

    Filters only narrow the caller's own households. Pages are in natural ID order; when more
    remain, the response carries the next cursor in the X-Next-After header."""
    try:
        search = geo.normalise_search(q) if q is not None else None
        box = geo.parse_bbox(bbox) if bbox is not None else None
        cursor = geo.normalise_household_cursor(after) if after is not None else None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    page, next_after = svc.list_households(db, principal, territory, search=search, bbox=box,
                                           after=cursor, limit=limit)
    if next_after:
        response.headers[NEXT_PAGE_HEADER] = next_after
    return page


# Declared before /households/{key} so that "nearby" is never read as a household key.
@router.get("/households/nearby", response_model=list[NearbyHousehold])
def nearby_households(
    lat: float = Query(..., ge=-90, le=90, allow_inf_nan=False),
    lon: float = Query(..., ge=-180, le=180, allow_inf_nan=False),
    radius_m: int = Query(geo.DEFAULT_NEARBY_RADIUS_M, ge=1, le=geo.MAX_NEARBY_RADIUS_M),
    limit: int = Query(geo.DEFAULT_NEARBY_LIMIT, ge=1, le=geo.MAX_PAGE_LIMIT),
    principal: Principal = Depends(reader),
    db: Session = Depends(get_db),
):
    """The caller's pins within radius_m metres, nearest first, with distance_m. A hint only."""
    return svc.nearby_households(db, principal, lat=lat, lon=lon, radius_m=radius_m, limit=limit)


@router.get("/households/{key}", response_model=HouseholdDetail)
def get_household(key: Key, request: Request, principal: Principal = Depends(reader),
                  db: Session = Depends(get_db)):
    try:
        return svc.household_detail(db, svc.get_household(db, principal, key, request_id=request_id(request)))
    except AccessDenied:
        raise NOT_FOUND from None


@router.get("/households/{key}/members", response_model=list[PersonOut])
def list_members(key: Key, request: Request, principal: Principal = Depends(reader),
                 db: Session = Depends(get_db)):
    try:
        household = svc.get_household(db, principal, key, request_id=request_id(request),
                                      route="household.members")
    except AccessDenied:
        raise NOT_FOUND from None
    return svc.people_out(db, svc.household_members(db, household),
                          visible_territories=visible_territory_ids(db, principal))


@router.get("/households/{key}/members/{person_key}", response_model=PersonOut)
def get_member(key: Key, person_key: Key, request: Request, principal: Principal = Depends(reader),
               db: Session = Depends(get_db)):
    """One active member of an authorized household; 404 if the person lives anywhere else."""
    try:
        person = svc.get_household_member(db, principal, key, person_key, request_id=request_id(request))
    except AccessDenied:
        raise NOT_FOUND from None
    return svc.people_out(db, [person], visible_territories=visible_territory_ids(db, principal))[0]


@router.post("/households/{key}/members", response_model=PersonOut, status_code=201,
             dependencies=[Depends(require_csrf)])
def add_member(key: Key, body: MemberCreate, request: Request,
               principal: Principal = Depends(require_roles("worker", "admin")),
               db: Session = Depends(get_db)):
    """Supervisors are read-only. Workers may add members only in their own territory."""
    try:
        household = svc.get_household(db, principal, key, request_id=request_id(request),
                                      route="household.add_member")
    except AccessDenied:
        raise NOT_FOUND from None
    try:
        person = svc.add_member(db, principal, household, body, request_id(request))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return svc.people_out(db, [person], visible_territories=visible_territory_ids(db, principal))[0]


@router.get("/people/{key}", response_model=PersonOut)
def get_person(key: Key, request: Request, principal: Principal = Depends(reader),
               db: Session = Depends(get_db)):
    try:
        person = svc.get_person(db, principal, key, request_id=request_id(request))
    except AccessDenied:
        raise NOT_FOUND from None
    return svc.people_out(db, [person], visible_territories=visible_territory_ids(db, principal))[0]
