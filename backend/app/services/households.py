"""Territory-scoped household / person access. Every read and write goes through here, so
authorization is enforced in the service layer, not only in route wrappers.

A household or person the caller may not see raises AccessDenied, exactly as if it did not exist
(routes answer 404). Each denial is audited the same way whether the record exists or not, so
neither the response nor its timing tells the caller which IDs are real.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Collection
from datetime import date
from typing import NoReturn

from geoalchemy2 import Geography
from sqlalchemy import Integer, cast, func, or_, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.auth.service import AccessDenied, Principal, audit, visible_territory_ids
from app.db.models import (
    Household,
    HouseholdSurvey,
    Person,
    PersonRelationship,
    ProgrammeEnrolment,
    Territory,
)
from app.schemas.households import (
    AgeOut,
    EnrolmentOut,
    HouseholdDetail,
    HouseholdPin,
    MemberCreate,
    NearbyHousehold,
    PersonOut,
    RelationshipOut,
    SurveyOut,
)
from app.services.geo import MAX_PAGE_LIMIT, BBox

_POINT = Geography(geometry_type="POINT", srid=4326, spatial_index=False)


def _parse_key(key: str, prefix: str) -> tuple[str, object] | None:
    try:
        return "id", uuid.UUID(key)
    except ValueError:
        k = key.strip().upper()
        # Bounded: public_id is VARCHAR(16), so longer keys are malformed (and fit the audit column).
        return ("public_id", k) if re.fullmatch(rf"{prefix}-[0-9]{{3,13}}", k) else None


def _deny(db: Session, principal: Principal, *, kind: str, key: str, prefix: str, route: str,
          request_id: str | None) -> NoReturn:
    """Audit a refused lookup (missing and not-visible alike) and raise AccessDenied.

    Only a well-formed ID is recorded; anything else is stored as '<malformed>' so arbitrary
    caller text never reaches the audit log."""
    parsed = _parse_key(key, prefix)
    audit(db, actor=principal.user_id, action="access.denied", resource_kind=kind,
          resource_id=str(parsed[1]) if parsed else "<malformed>", request_id=request_id,
          details={"route": route})
    db.commit()
    raise AccessDenied()


def _natural_order():
    """H-002 before H-010 (shorter IDs first, then text). Unique, so pages are stable."""
    return func.length(Household.public_id), Household.public_id


def _member_count():
    return (select(func.count(Person.id))
            .where(Person.household_id == Household.id, Person.active.is_(True))
            .correlate(Household).scalar_subquery())


def _pin(h: Household, territory_code: str, member_count: int) -> HouseholdPin:
    return HouseholdPin(id=h.id, public_id=h.public_id, label=h.label, landmark=h.landmark,
                        territory_code=territory_code, latitude=h.latitude, longitude=h.longitude,
                        location_source=h.location_source, member_count=member_count,
                        is_demo_data=h.is_demo_data)


def _visible_pins(ids: Collection[uuid.UUID], *extra_columns):
    return (select(Household, Territory.code, _member_count(), *extra_columns)
            .join(Territory, Territory.id == Household.territory_id)
            .where(Household.territory_id.in_(ids)))


def list_households(db: Session, principal: Principal, territory_code: str | None = None, *,
                    search: str | None = None, bbox: BBox | None = None, after: str | None = None,
                    limit: int = MAX_PAGE_LIMIT) -> tuple[list[HouseholdPin], str | None]:
    """One page of the pins the principal may see, in natural ID order.

    Every filter (territory code, search text, bounding box, cursor) only narrows the caller's
    authorized set; none of them can widen it. Returns (page, next_after); next_after is the
    cursor for the following page, or None on the last page."""
    ids = visible_territory_ids(db, principal)
    if not ids:
        return [], None
    stmt = _visible_pins(ids)
    if territory_code:
        stmt = stmt.where(Territory.code == territory_code)
    if search:
        # autoescape: % and _ in the text are matched literally, not as wildcards.
        stmt = stmt.where(or_(Household.public_id.icontains(search, autoescape=True),
                              Household.label.icontains(search, autoescape=True)))
    if bbox:
        # Exact longitude/latitude rectangle (what a map viewport shows), inclusive.
        stmt = stmt.where(Household.longitude.between(bbox.min_lon, bbox.max_lon),
                          Household.latitude.between(bbox.min_lat, bbox.max_lat))
    if after:
        stmt = stmt.where(tuple_(*_natural_order()) > tuple_(len(after), after))
    rows = db.execute(stmt.order_by(*_natural_order()).limit(limit + 1)).all()
    page = [_pin(h, code, n) for h, code, n in rows[:limit]]
    return page, (page[-1].public_id if len(rows) > limit else None)


def nearby_households(db: Session, principal: Principal, *, lat: float, lon: float, radius_m: int,
                      limit: int) -> list[NearbyHousehold]:
    """Visible pins within radius_m metres of (lat, lon), nearest first (ties by ID).

    Geography (spheroid) metres via ST_DWithin, which can use the GiST index on location.
    A suggestion list only: proximity never selects or confirms a household."""
    ids = visible_territory_ids(db, principal)
    if not ids:
        return []
    point = cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), _POINT)  # x = longitude
    distance = func.ST_Distance(Household.location, point)
    rows = db.execute(
        _visible_pins(ids, distance)
        .where(func.ST_DWithin(Household.location, point, radius_m))
        .order_by(distance, *_natural_order()).limit(limit)
    ).all()
    return [NearbyHousehold(**_pin(h, code, n).model_dump(), distance_m=round(float(d), 1))
            for h, code, n, d in rows]


def get_household(db: Session, principal: Principal, key: str, *, request_id: str | None = None,
                  route: str = "household.detail") -> Household:
    """The household if the principal may see it; AccessDenied otherwise (same for 'missing')."""
    parsed = _parse_key(key, "H")
    household = None
    if parsed is not None:
        column, value = parsed
        household = db.scalar(select(Household).where(getattr(Household, column) == value))
    if household is None or household.territory_id not in visible_territory_ids(db, principal):
        _deny(db, principal, kind="household", key=key, prefix="H", route=route, request_id=request_id)
    return household


def get_household_member(db: Session, principal: Principal, household_key: str, person_key: str, *,
                         request_id: str | None = None) -> Person:
    """An active member of a visible household: the server-side check behind 'Select member'.

    A person who exists but lives in another household (even a visible one) is refused exactly
    like a missing person."""
    household = get_household(db, principal, household_key, request_id=request_id, route="household.member")
    parsed = _parse_key(person_key, "P")
    person = None
    if parsed is not None:
        column, value = parsed
        person = db.scalar(select(Person).where(getattr(Person, column) == value,
                                                Person.household_id == household.id,
                                                Person.active.is_(True)))
    if person is None:
        _deny(db, principal, kind="person", key=person_key, prefix="P", route="household.member",
              request_id=request_id)
    return person


def household_detail(db: Session, household: Household) -> HouseholdDetail:
    code = db.scalar(select(Territory.code).where(Territory.id == household.territory_id))
    count = db.scalar(select(func.count(Person.id)).where(Person.household_id == household.id,
                                                          Person.active.is_(True)))
    survey = db.scalar(select(HouseholdSurvey).where(HouseholdSurvey.household_id == household.id)
                       .order_by(HouseholdSurvey.submitted_on.desc(), HouseholdSurvey.created_at.desc()))
    pin = _pin(household, code, count)
    return HouseholdDetail(**pin.model_dump(), latest_survey=SurveyOut.model_validate(survey, from_attributes=True)
                           if survey else None)


def get_person(db: Session, principal: Principal, key: str, *, request_id: str | None = None) -> Person:
    parsed = _parse_key(key, "P")
    row = None
    if parsed is not None:
        column, value = parsed
        row = db.execute(select(Person, Household.territory_id)
                         .join(Household, Household.id == Person.household_id)
                         .where(getattr(Person, column) == value)).first()
    if row is None or row[1] not in visible_territory_ids(db, principal):
        _deny(db, principal, kind="person", key=key, prefix="P", route="person.detail", request_id=request_id)
    return row[0]


def age_of(person: Person, today: date) -> AgeOut:
    if person.date_of_birth:
        dob = person.date_of_birth
        days = (today - dob).days
        years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        months = (today.year - dob.year) * 12 + today.month - dob.month - (today.day < dob.day)
        return AgeOut(basis="date_of_birth", years=years, months=months if months < 24 else None,
                      days=days if days < 60 else None)
    if person.recorded_age_years is not None and person.age_recorded_on is not None:
        years = person.recorded_age_years + (today.year - person.age_recorded_on.year
                                             - ((today.month, today.day) < (person.age_recorded_on.month,
                                                                            person.age_recorded_on.day)))
        return AgeOut(basis="recorded_age", years=years)
    return AgeOut(basis="unknown")


def people_out(db: Session, persons: list[Person], today: date | None = None, *,
               visible_territories: Collection[uuid.UUID]) -> list[PersonOut]:
    """Serialize people. A relationship is listed only if the related person's household is in
    `visible_territories` (the caller's scope), so a family edge never leaks another territory's
    name or ID."""
    if not persons:
        return []
    today = today or date.today()
    ids = [p.id for p in persons]
    hh_public = dict(db.execute(select(Household.id, Household.public_id)
                                .where(Household.id.in_({p.household_id for p in persons}))).all())
    enrol: dict[uuid.UUID, list[EnrolmentOut]] = {i: [] for i in ids}
    for e in db.scalars(select(ProgrammeEnrolment).where(ProgrammeEnrolment.person_id.in_(ids))
                        .order_by(ProgrammeEnrolment.started_on)).all():
        enrol[e.person_id].append(EnrolmentOut.model_validate(e, from_attributes=True))
    rels: dict[uuid.UUID, list[RelationshipOut]] = {i: [] for i in ids}
    a, b = aliased(Person), aliased(Person)
    ha, hb = aliased(Household), aliased(Household)
    for r, pa, pb, territory_a, territory_b in db.execute(
        select(PersonRelationship, a, b, ha.territory_id, hb.territory_id)
        .join(a, a.id == PersonRelationship.person_id).join(b, b.id == PersonRelationship.related_person_id)
        .join(ha, ha.id == a.household_id).join(hb, hb.id == b.household_id)
        .where(or_(PersonRelationship.person_id.in_(ids), PersonRelationship.related_person_id.in_(ids)))
        .order_by(PersonRelationship.relationship_type, a.public_id, b.public_id)
    ).all():
        if pa.id in rels and territory_b in visible_territories:
            rels[pa.id].append(RelationshipOut(relationship_type=r.relationship_type, direction="outgoing",
                                               other_person_public_id=pb.public_id, other_person_name=pb.full_name))
        if pb.id in rels and territory_a in visible_territories:
            rels[pb.id].append(RelationshipOut(relationship_type=r.relationship_type, direction="incoming",
                                               other_person_public_id=pa.public_id, other_person_name=pa.full_name))
    return [PersonOut(
        id=p.id, public_id=p.public_id, household_public_id=hh_public[p.household_id], full_name=p.full_name,
        sex=p.sex, date_of_birth=p.date_of_birth, age=age_of(p, today),
        relationship_to_head=p.relationship_to_head, residence_status=p.residence_status,
        programmes=enrol[p.id], relationships=rels[p.id], is_demo_data=p.is_demo_data,
    ) for p in persons]


def household_members(db: Session, household: Household) -> list[Person]:
    return db.scalars(select(Person).where(Person.household_id == household.id, Person.active.is_(True))
                      .order_by(Person.public_id)).all()


def _next_person_public_id(db: Session) -> str:
    """Next P-### after the highest numeric suffix in use (P-051 after the 50 demo people)."""
    max_n = db.scalar(select(func.max(cast(func.substring(Person.public_id, 3), Integer))))
    return f"P-{(max_n or 0) + 1:03d}"


def add_member(db: Session, principal: Principal, household: Household, body: MemberCreate,
               request_id: str | None, today: date | None = None) -> Person:
    """Add a person to an authorised household (worker-entered, not demo data). Audited."""
    today = today or date.today()
    if body.date_of_birth and body.date_of_birth > today:
        raise ValueError("date_of_birth cannot be in the future")
    for _ in range(3):  # retry if another request took the same P-### at the same moment
        public_id = _next_person_public_id(db)
        person =Person(public_id=public_id, household_id=household.id, full_name=body.full_name.strip(),
                        sex=body.sex, relationship_to_head=body.relationship_to_head,
                        date_of_birth=body.date_of_birth, recorded_age_years=body.recorded_age_years,
                        age_recorded_on=today if body.recorded_age_years is not None else None,
                        residence_status="resident", created_by=principal.user_id, is_demo_data=False)
        db.add(person)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        audit(db, actor=principal.user_id, action="person.create", resource_kind="person",
              resource_id=public_id, request_id=request_id,
              details={"household": household.public_id,
                       "fields": sorted(k for k, v in body.model_dump().items() if v is not None)})
        db.commit()
        return person
    raise RuntimeError("Could not allocate a person ID; try again")
