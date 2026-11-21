"""Territory-scoped household / person access. Every read and write goes through here, so
authorization is enforced in the service layer, not only in route wrappers."""

from __future__ import annotations

import re
import uuid
from datetime import date

from sqlalchemy import Integer, cast, func, or_, select
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
    PersonOut,
    RelationshipOut,
    SurveyOut,
)


def _parse_key(key: str, prefix: str) -> tuple[str, object] | None:
    try:
        return "id", uuid.UUID(key)
    except ValueError:
        k = key.strip().upper()
        return ("public_id", k) if re.fullmatch(rf"{prefix}-\d{{3,}}", k) else None


def _member_count():
    return (select(func.count(Person.id))
            .where(Person.household_id == Household.id, Person.active.is_(True))
            .correlate(Household).scalar_subquery())


def _pin(h: Household, territory_code: str, member_count: int) -> HouseholdPin:
    return HouseholdPin(id=h.id, public_id=h.public_id, label=h.label, landmark=h.landmark,
                        territory_code=territory_code, latitude=h.latitude, longitude=h.longitude,
                        location_source=h.location_source, member_count=member_count,
                        is_demo_data=h.is_demo_data)


def list_households(db: Session, principal: Principal, territory_code: str | None = None) -> list[HouseholdPin]:
    ids = visible_territory_ids(db, principal)
    if not ids:
        return []
    stmt = (select(Household, Territory.code, _member_count())
            .join(Territory, Territory.id == Household.territory_id)
            .where(Household.territory_id.in_(ids)).order_by(Household.public_id))
    if territory_code:
        stmt = stmt.where(Territory.code == territory_code)
    return [_pin(h, code, n) for h, code, n in db.execute(stmt).all()]


def get_household(db: Session, principal: Principal, key: str) -> Household:
    """The household if the principal may see it; AccessDenied otherwise (same for 'missing')."""
    parsed = _parse_key(key, "H")
    if parsed is None:
        raise AccessDenied()
    column, value = parsed
    household = db.scalar(select(Household).where(getattr(Household, column) == value))
    if household is None or household.territory_id not in visible_territory_ids(db, principal):
        raise AccessDenied()
    return household


def household_detail(db: Session, household: Household) -> HouseholdDetail:
    code = db.scalar(select(Territory.code).where(Territory.id == household.territory_id))
    count = db.scalar(select(func.count(Person.id)).where(Person.household_id == household.id,
                                                          Person.active.is_(True)))
    survey = db.scalar(select(HouseholdSurvey).where(HouseholdSurvey.household_id == household.id)
                       .order_by(HouseholdSurvey.submitted_on.desc(), HouseholdSurvey.created_at.desc()))
    pin = _pin(household, code, count)
    return HouseholdDetail(**pin.model_dump(), latest_survey=SurveyOut.model_validate(survey, from_attributes=True)
                           if survey else None)


def get_person(db: Session, principal: Principal, key: str) -> Person:
    parsed = _parse_key(key, "P")
    if parsed is None:
        raise AccessDenied()
    column, value = parsed
    row = db.execute(select(Person, Household.territory_id).join(Household, Household.id == Person.household_id)
                     .where(getattr(Person, column) == value)).first()
    if row is None or row[1] not in visible_territory_ids(db, principal):
        raise AccessDenied()
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


def people_out(db: Session, persons: list[Person], today: date | None = None) -> list[PersonOut]:
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
    for r, pa, pb in db.execute(
        select(PersonRelationship, a, b)
        .join(a, a.id == PersonRelationship.person_id).join(b, b.id == PersonRelationship.related_person_id)
        .where(or_(PersonRelationship.person_id.in_(ids), PersonRelationship.related_person_id.in_(ids)))
    ).all():
        if pa.id in rels:
            rels[pa.id].append(RelationshipOut(relationship_type=r.relationship_type, direction="outgoing",
                                               other_person_public_id=pb.public_id, other_person_name=pb.full_name))
        if pb.id in rels:
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
