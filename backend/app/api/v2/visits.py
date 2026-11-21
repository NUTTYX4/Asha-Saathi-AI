"""Confirmed V2 visit history (Phase 5). Every call re-authorises the person against the caller's
current territories; another territory's (or a missing) person or visit is the same 404."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.api.v2.households import reader
from app.auth.deps import get_db, request_id
from app.auth.service import AccessDenied, Principal, visible_territory_ids
from app.db.models import Household, Person, User, V2Visit
from app.db.visits_v2 import find_receipt
from app.schemas.visits_v2 import V2VisitOut
from app.services import households as svc

router = APIRouter(tags=["v2-visits"])
NOT_FOUND = HTTPException(404, "Not found")
Key = Annotated[str, Path(max_length=64)]


def _out(db: Session, rows: list[V2Visit]) -> list[V2VisitOut]:
    if not rows:
        return []
    people = dict(db.execute(select(Person.id, Person.public_id).where(Person.id.in_({r.person_id for r in rows}))).all())
    homes = dict(db.execute(select(Household.id, Household.public_id)
                            .where(Household.id.in_({r.household_id for r in rows}))).all())
    workers = dict(db.execute(select(User.id, User.display_name).where(User.id.in_({r.worker_id for r in rows}))).all())
    return [V2VisitOut(
        id=r.id, client_visit_id=r.client_visit_id, person_public_id=people[r.person_id],
        household_public_id=homes[r.household_id], recorded_by=workers[r.worker_id], visit_type=r.visit_type,
        subject_population=r.subject_population, weight_kg=r.weight_kg, vaccinations_due=r.vaccinations_due,
        next_visit_date=r.next_visit_date, danger_signs=r.danger_signs, requires_phc_referral=r.requires_phc_referral,
        rule_status=r.rule_status, ruleset_version=r.ruleset_version, extraction_source=r.extraction_source,
        record_version=r.record_version, confirmed_at=r.confirmed_at, is_demo_data=r.is_demo_data,
    ) for r in rows]


@router.get("/people/{key}/visits", response_model=list[V2VisitOut])
def person_visits(key: Key, request: Request, limit: int = Query(20, ge=1, le=50),
                  before: uuid.UUID | None = Query(None, description="Last visit id of the previous page"),
                  principal: Principal = Depends(reader), db: Session = Depends(get_db)):
    """Confirmed visits of one person, newest first."""
    try:
        person = svc.get_person(db, principal, key, request_id=request_id(request))
    except AccessDenied:
        raise NOT_FOUND from None
    stmt = select(V2Visit).where(V2Visit.person_id == person.id)
    if before is not None:
        anchor = db.scalar(select(V2Visit).where(V2Visit.id == before, V2Visit.person_id == person.id))
        if anchor is None:
            raise HTTPException(422, "before must be a visit of this person")
        stmt = stmt.where(tuple_(V2Visit.confirmed_at, V2Visit.id) < tuple_(anchor.confirmed_at, anchor.id))
    rows = db.scalars(stmt.order_by(V2Visit.confirmed_at.desc(), V2Visit.id.desc()).limit(limit)).all()
    return _out(db, list(rows))


@router.get("/people/{key}/visits/{visit_id}", response_model=V2VisitOut)
def person_visit(key: Key, visit_id: uuid.UUID, request: Request, principal: Principal = Depends(reader),
                 db: Session = Depends(get_db)):
    try:
        person = svc.get_person(db, principal, key, request_id=request_id(request))
    except AccessDenied:
        raise NOT_FOUND from None
    row = db.scalar(select(V2Visit).where(V2Visit.id == visit_id, V2Visit.person_id == person.id))
    if row is None:
        raise NOT_FOUND
    return _out(db, [row])[0]


@router.get("/visits/by-client-key/{client_visit_id}", response_model=V2VisitOut)
def receipt(client_visit_id: uuid.UUID, principal: Principal = Depends(reader), db: Session = Depends(get_db)):
    """The caller's own confirmed visit for a logical visit key, if it committed. Used when a
    save acknowledgement was lost: the browser asks instead of saving again with a new key."""
    row = find_receipt(db, principal.user_id, client_visit_id)
    if row is None:
        raise NOT_FOUND
    territory = db.scalar(select(Household.territory_id).where(Household.id == row.household_id))
    if territory not in visible_territory_ids(db, principal):
        raise NOT_FOUND
    return _out(db, [row])[0]
