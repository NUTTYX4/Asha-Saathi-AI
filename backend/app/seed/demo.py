"""Idempotent synthetic demo seed and invariant check (PostgreSQL/PostGIS only).

Rules:
* Only ADDS what is missing (matched by territory code, username, H-###, P-###, and natural
  keys for relationships/enrolments/surveys). Existing rows are never modified or deleted, so
  household edits, accounts, passwords and assignments survive re-runs.
* New demo accounts are created INACTIVE with an unusable random password hash. Nobody can
  log in until the owner sets a password with `python -m scripts.set_password` (interactive).
  No password is generated for display, printed or logged.
"""

from __future__ import annotations

import secrets
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.auth.service import active_territory_ids, audit
from app.db.models import (
    Household,
    HouseholdSurvey,
    Person,
    PersonRelationship,
    ProgrammeEnrolment,
    Territory,
    TerritoryAssignment,
    User,
)
from app.seed import demo_data as D


@dataclass
class SeedReport:
    created: Counter = field(default_factory=Counter)
    existing: Counter = field(default_factory=Counter)
    accounts_without_password: list[str] = field(default_factory=list)


def _get_or_create_territory(db: Session, code: str, name: str, report: SeedReport) -> Territory:
    row = db.scalar(select(Territory).where(Territory.code == code))
    if row:
        report.existing["territories"] += 1
        return row
    row = Territory(id=D.stable_uuid(f"territory:{code}"), code=code, name=name, is_demo_data=True)
    db.add(row)
    report.created["territories"] += 1
    return row


def _get_or_create_user(db: Session, username: str, display: str, role: str, report: SeedReport) -> User:
    row = db.scalar(select(User).where(User.username == username))
    if row:
        report.existing["users"] += 1
        return row
    row = User(id=D.stable_uuid(f"user:{username}"), username=username, display_name=display, role=role,
               password_hash=hash_password(secrets.token_urlsafe(32)),  # unusable; never shown
               active=False, is_demo_data=True)
    db.add(row)
    report.created["users"] += 1
    report.accounts_without_password.append(username)
    return row


def seed_demo(db: Session, as_of: date = D.DEMO_AS_OF) -> SeedReport:
    report = SeedReport()
    territories = {code: _get_or_create_territory(db, code, name, report) for code, name in D.TERRITORIES}
    db.flush()

    users = {}
    for username, display, role, codes in D.ACCOUNTS:
        user = _get_or_create_user(db, username, display, role, report)
        users[username] = user
        db.flush()
        for code in codes:
            territory = territories[code]
            active = db.scalar(select(TerritoryAssignment).where(
                TerritoryAssignment.user_id == user.id, TerritoryAssignment.territory_id == territory.id,
                TerritoryAssignment.ends_at.is_(None)))
            if active:
                report.existing["assignments"] += 1
            else:
                db.add(TerritoryAssignment(user_id=user.id, territory_id=territory.id))
                report.created["assignments"] += 1
    db.flush()

    person_ids = D.person_public_ids()
    for spec in D.HOUSEHOLDS:
        household = db.scalar(select(Household).where(Household.public_id == spec.public_id))
        if household:
            report.existing["households"] += 1
        else:
            lat, lon = D.PINS[spec.public_id]
            household = Household(
                id=D.stable_uuid(f"household:{spec.public_id}"), public_id=spec.public_id,
                territory_id=territories[spec.territory].id, label=spec.label, landmark=D.PIN_LANDMARK,
                location=f"SRID=4326;POINT({lon} {lat})", location_source="synthetic_demo",
                is_demo_data=True,
            )
            db.add(household)
            report.created["households"] += 1
        db.flush()

        people: dict[str, Person] = {}
        for m in spec.members:
            pid = person_ids[(spec.public_id, m.key)]
            person = db.scalar(select(Person).where(Person.public_id == pid))
            if person:
                report.existing["people"] += 1
            else:
                person = Person(
                    id=D.stable_uuid(f"person:{pid}"), public_id=pid, household_id=household.id,
                    full_name=m.name, sex=m.sex, relationship_to_head=m.rel_to_head,
                    date_of_birth=(as_of - timedelta(days=m.dob_days_ago)) if m.dob_days_ago is not None else None,
                    recorded_age_years=m.age_years, age_recorded_on=as_of if m.age_years is not None else None,
                    residence_status="resident", is_demo_data=True,
                )
                db.add(person)
                report.created["people"] += 1
            people[m.key] = person
        db.flush()

        for src, rel_type, dst in spec.relationships:
            exists = db.scalar(select(PersonRelationship).where(
                PersonRelationship.person_id == people[src].id,
                PersonRelationship.related_person_id == people[dst].id,
                PersonRelationship.relationship_type == rel_type))
            if exists:
                report.existing["relationships"] += 1
            else:
                db.add(PersonRelationship(person_id=people[src].id, related_person_id=people[dst].id,
                                          relationship_type=rel_type, source="demo_seed"))
                report.created["relationships"] += 1

        for key, programme, days_ago in spec.enrolments:
            exists = db.scalar(select(ProgrammeEnrolment).where(
                ProgrammeEnrolment.person_id == people[key].id, ProgrammeEnrolment.programme == programme))
            if exists:
                report.existing["enrolments"] += 1
            else:
                db.add(ProgrammeEnrolment(person_id=people[key].id, programme=programme, status="active",
                                          source="demo_seed", started_on=as_of - timedelta(days=days_ago)))
                report.created["enrolments"] += 1

        survey = db.scalar(select(HouseholdSurvey).where(
            HouseholdSurvey.household_id == household.id, HouseholdSurvey.survey_version == D.SURVEY_VERSION))
        if survey:
            report.existing["surveys"] += 1
        else:
            db.add(HouseholdSurvey(household_id=household.id, survey_version=D.SURVEY_VERSION, status="confirmed",
                                   drinking_water_source=spec.water, has_toilet=spec.toilet,
                                   submitted_on=as_of, is_demo_data=True))
            report.created["surveys"] += 1
        db.flush()

    audit(db, actor=None, action="demo.seed", resource_kind="dataset", resource_id="demo-v1",
          details={"created": dict(report.created), "as_of": as_of.isoformat()})
    db.commit()
    return report


# ------------------------------------------------------------------ invariant check (read-only)
def check_demo(db: Session) -> dict:
    """Counts and invariant violations for the synthetic dataset. Never modifies data."""
    violations: list[str] = []
    n_households = db.scalar(select(func.count()).select_from(Household).where(Household.is_demo_data.is_(True)))
    n_people = db.scalar(select(func.count()).select_from(Person).where(Person.is_demo_data.is_(True)))
    n_territories = db.scalar(select(func.count()).select_from(Territory).where(Territory.is_demo_data.is_(True)))
    if n_households != D.EXPECTED_HOUSEHOLDS:
        violations.append(f"expected {D.EXPECTED_HOUSEHOLDS} demo households, found {n_households}")
    if n_people != D.EXPECTED_PEOPLE:
        violations.append(f"expected {D.EXPECTED_PEOPLE} demo people, found {n_people}")
    if n_territories != len(D.TERRITORIES):
        violations.append(f"expected {len(D.TERRITORIES)} demo territories, found {n_territories}")

    rows = db.execute(
        select(Household.public_id, Territory.code, func.count(Person.id))
        .join(Territory, Territory.id == Household.territory_id)
        .outerjoin(Person, (Person.household_id == Household.id) & Person.is_demo_data.is_(True))
        .where(Household.is_demo_data.is_(True))
        .group_by(Household.public_id, Territory.code)
    ).all()
    per_territory = Counter(code for _, code, _ in rows)
    expected_territory = {spec.public_id: spec.territory for spec in D.HOUSEHOLDS}
    for public_id, code, count in rows:
        if D.EXPECTED_MEMBER_COUNTS.get(public_id) != count:
            violations.append(f"{public_id}: expected {D.EXPECTED_MEMBER_COUNTS.get(public_id)} members, found {count}")
        if expected_territory.get(public_id) != code:
            violations.append(f"{public_id}: expected territory {expected_territory.get(public_id)}, found {code}")

    # Every demo person is in the household the dataset says.
    expected_household = {pid: hh for (hh, _), pid in D.person_public_ids().items()}
    for pid, hh in db.execute(select(Person.public_id, Household.public_id)
                              .join(Household, Household.id == Person.household_id)
                              .where(Person.is_demo_data.is_(True))).all():
        if expected_household.get(pid) != hh:
            violations.append(f"{pid}: expected household {expected_household.get(pid)}, found {hh}")

    # Family edges connect people of the same household (true for the whole demo dataset).
    cross = db.scalar(text("""
        SELECT count(*) FROM person_relationships r
        JOIN people a ON a.id = r.person_id JOIN people b ON b.id = r.related_person_id
        WHERE r.source = 'demo_seed' AND a.household_id <> b.household_id"""))
    if cross:
        violations.append(f"{cross} demo relationship(s) cross households")

    # Pins: distinct and well separated (metres, computed by PostGIS on the geography type).
    min_sep, distinct = db.execute(text("""
        SELECT (SELECT min(ST_Distance(a.location, b.location)) FROM households a JOIN households b
                  ON a.id < b.id WHERE a.is_demo_data AND b.is_demo_data),
               (SELECT count(DISTINCT ST_AsText(location::geometry)) FROM households WHERE is_demo_data)""")).one()
    if distinct != n_households:
        violations.append(f"only {distinct} distinct pin locations for {n_households} households")
    if min_sep is not None and min_sep < D.MIN_PIN_SEPARATION_M:
        violations.append(f"pins only {min_sep:.0f} m apart (need >= {D.MIN_PIN_SEPARATION_M} m)")

    visibility = {}
    for username, _, role, codes in D.ACCOUNTS:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            violations.append(f"account {username} missing")
            continue
        if role == "admin":
            visible = n_households
        else:
            tids = active_territory_ids(db, user.id)
            visible = db.scalar(select(func.count()).select_from(Household).where(
                Household.is_demo_data.is_(True), Household.territory_id.in_(tids))) if tids else 0
        visibility[username] = {"role": role, "active": user.active, "demo_households_visible": visible}
        expected_visible = 6 * len(codes) if role != "admin" else D.EXPECTED_HOUSEHOLDS
        if visible != expected_visible:
            violations.append(f"{username} sees {visible} demo households, expected {expected_visible}")

    return {
        "territories": n_territories, "households": n_households, "people": n_people,
        "households_per_territory": dict(per_territory),
        "relationships": db.scalar(select(func.count()).select_from(PersonRelationship)
                                   .where(PersonRelationship.source == "demo_seed")),
        "active_enrolments": dict(db.execute(select(ProgrammeEnrolment.programme, func.count())
                                             .where(ProgrammeEnrolment.source == "demo_seed",
                                                    ProgrammeEnrolment.status == "active")
                                             .group_by(ProgrammeEnrolment.programme)).all()),
        "min_pin_separation_m": round(float(min_sep), 1) if min_sep is not None else None,
        "accounts": visibility,
        "violations": violations,
    }
