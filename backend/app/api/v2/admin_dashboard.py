"""Admin dashboard (Phase 7): read-only activity views plus one transactional reassignment.

Every route requires the admin role server-side (require_roles("admin")); the single write also
requires the anti-CSRF header, runs in one transaction and is audited. Metric definitions live in
app/schemas/admin.py. Visits are listed with public IDs only (no names, transcripts or audio).
"""

import uuid
from collections import defaultdict
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import Date, Select, and_, cast, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.auth.deps import get_db, request_id, require_csrf, require_roles
from app.auth.service import Principal, audit, utcnow
from app.db.models import Household, Person, Territory, TerritoryAssignment, User, V2Visit
from app.schemas.admin import (
    AdminAssignment,
    AdminFilters,
    AdminOverview,
    AdminTerritoryCoverage,
    AdminUser,
    AdminVisit,
    AdminVisitPage,
    AdminWorker,
    CoverageHousehold,
    ReassignRequest,
    TerritoryRef,
)

router = APIRouter(prefix="/admin", tags=["v2-admin-dashboard"])
admin_only = require_roles("admin")
IST = "Asia/Kolkata"


def _visit_day():
    return cast(func.timezone(IST, V2Visit.confirmed_at), Date)


def _today() -> date:
    return datetime.now(ZoneInfo(IST)).date()


class Scope:
    """Validated dashboard filters, shared by every view."""

    def __init__(self, date_from: date | None = Query(None), date_to: date | None = Query(None),
                 territory_id: uuid.UUID | None = Query(None), worker_id: uuid.UUID | None = Query(None)):
        if date_from and date_to and date_from > date_to:
            raise HTTPException(422, "date_from must be on or before date_to")
        self.date_from, self.date_to = date_from, date_to
        self.territory_id, self.worker_id = territory_id, worker_id

    def filters(self) -> AdminFilters:
        return AdminFilters(date_from=self.date_from, date_to=self.date_to, territory_id=self.territory_id,
                            worker_id=self.worker_id)

    def visits(self, stmt: Select, *, dates: bool = True) -> Select:
        if dates and self.date_from:
            stmt = stmt.where(_visit_day() >= self.date_from)
        if dates and self.date_to:
            stmt = stmt.where(_visit_day() <= self.date_to)
        if self.territory_id:
            stmt = stmt.where(V2Visit.territory_id == self.territory_id)
        if self.worker_id:
            stmt = stmt.where(V2Visit.worker_id == self.worker_id)
        return stmt


def _active_assignment():
    return and_(TerritoryAssignment.ends_at.is_(None))


def _latest_visits(db: Session, scope: Scope):
    """Latest confirmed visit per person (any date) within the territory/worker scope."""
    ranked = scope.visits(
        select(V2Visit.person_id, V2Visit.worker_id, V2Visit.next_visit_date,
               func.row_number().over(partition_by=V2Visit.person_id,
                                      order_by=(V2Visit.confirmed_at.desc(), V2Visit.id.desc())).label("rn")),
        dates=False,
    ).subquery()
    return db.execute(select(ranked.c.worker_id, ranked.c.next_visit_date).where(ranked.c.rn == 1)).all()


@router.get("/overview", response_model=AdminOverview)
def overview(scope: Scope = Depends(), admin: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    worker_assignments = (select(TerritoryAssignment.territory_id, TerritoryAssignment.user_id)
                          .join(User, User.id == TerritoryAssignment.user_id)
                          .where(_active_assignment(), User.role == "worker", User.active.is_(True)))
    if scope.territory_id:
        worker_assignments = worker_assignments.where(TerritoryAssignment.territory_id == scope.territory_id)
    if scope.worker_id:
        worker_assignments = worker_assignments.where(TerritoryAssignment.user_id == scope.worker_id)
    wa = worker_assignments.subquery()

    if scope.worker_id:
        active_workers = db.scalar(select(func.count()).select_from(User).where(
            User.id == scope.worker_id, User.role == "worker", User.active.is_(True))) or 0
    elif scope.territory_id:
        active_workers = db.scalar(select(func.count(func.distinct(wa.c.user_id)))) or 0
    else:
        active_workers = db.scalar(select(func.count()).select_from(User).where(
            User.role == "worker", User.active.is_(True))) or 0

    territories = select(Territory.id).where(Territory.active.is_(True))
    households = select(Household.id)
    if scope.territory_id:
        territories = territories.where(Territory.id == scope.territory_id)
        households = households.where(Household.territory_id == scope.territory_id)
    if scope.worker_id:  # the worker's own area
        territories = territories.where(Territory.id.in_(select(wa.c.territory_id)))
        households = households.where(Household.territory_id.in_(select(wa.c.territory_id)))

    territories_total = db.scalar(select(func.count()).select_from(territories.subquery())) or 0
    territories_with_worker = db.scalar(select(func.count(func.distinct(wa.c.territory_id)))) or 0
    households_registered = db.scalar(select(func.count()).select_from(households.subquery())) or 0
    covered = select(func.distinct(TerritoryAssignment.territory_id)).join(
        User, User.id == TerritoryAssignment.user_id).where(_active_assignment(), User.role == "worker",
                                                             User.active.is_(True))
    households_without_worker = db.scalar(select(func.count()).select_from(
        households.where(Household.territory_id.not_in(covered)).subquery())) or 0
    beneficiaries_registered = db.scalar(select(func.count()).select_from(Person).where(
        Person.active.is_(True), Person.household_id.in_(households))) or 0

    v = scope.visits(select(func.count(V2Visit.id), func.count(func.distinct(V2Visit.household_id)),
                            func.count(func.distinct(V2Visit.person_id)))).select_from(V2Visit)
    visits_confirmed, households_visited, beneficiaries_visited = db.execute(v).one()
    by_type = dict(db.execute(scope.visits(select(V2Visit.visit_type, func.count()).group_by(V2Visit.visit_type)
                                           )).all())

    today = _today()
    latest = _latest_visits(db, scope)
    upcoming = sum(1 for _, nvd in latest if nvd is not None and nvd >= today)
    passed = sum(1 for _, nvd in latest if nvd is not None and nvd < today)

    return AdminOverview(
        filters=scope.filters(), active_workers=active_workers, territories_total=territories_total,
        territories_with_worker=territories_with_worker, households_registered=households_registered,
        households_without_assigned_worker=households_without_worker,
        beneficiaries_registered=beneficiaries_registered, visits_confirmed=visits_confirmed,
        households_visited=households_visited, beneficiaries_visited=beneficiaries_visited,
        visits_by_type={k: int(n) for k, n in sorted(by_type.items())},
        followups_upcoming=upcoming, followups_date_passed=passed,
    )


@router.get("/workers", response_model=list[AdminWorker])
def workers(scope: Scope = Depends(), admin: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    users = select(User).where(User.role == "worker").order_by(User.display_name)
    if scope.worker_id:
        users = users.where(User.id == scope.worker_id)
    rows = db.scalars(users).all()
    if not rows:
        return []
    ids = [u.id for u in rows]

    assigned: dict[uuid.UUID, list[TerritoryRef]] = defaultdict(list)
    for uid, t in db.execute(select(TerritoryAssignment.user_id, Territory)
                             .join(Territory, Territory.id == TerritoryAssignment.territory_id)
                             .where(_active_assignment(), TerritoryAssignment.user_id.in_(ids))
                             .order_by(Territory.code)).all():
        assigned[uid].append(TerritoryRef(id=t.id, code=t.code, name=t.name))
    hh_per_territory = dict(db.execute(select(Household.territory_id, func.count()).group_by(Household.territory_id)).all())

    stats = {r[0]: r[1:] for r in db.execute(scope.visits(
        select(V2Visit.worker_id, func.count(V2Visit.id), func.count(func.distinct(V2Visit.household_id)),
               func.count(func.distinct(V2Visit.person_id))).where(V2Visit.worker_id.in_(ids))
        .group_by(V2Visit.worker_id))).all()}
    last = dict(db.execute(select(V2Visit.worker_id, func.max(V2Visit.confirmed_at))
                           .where(V2Visit.worker_id.in_(ids)).group_by(V2Visit.worker_id)).all())
    today = _today()
    upcoming: dict[uuid.UUID, int] = defaultdict(int)
    for wid, nvd in _latest_visits(db, scope):
        if nvd is not None and nvd >= today:
            upcoming[wid] += 1

    out = []
    for u in rows:
        territories = [t for t in assigned.get(u.id, []) if not scope.territory_id or t.id == scope.territory_id]
        if scope.territory_id and not territories and u.id not in stats:
            continue
        visits_n, hh_n, people_n = stats.get(u.id, (0, 0, 0))
        out.append(AdminWorker(
            id=u.id, username=u.username, display_name=u.display_name, active=u.active, territories=territories,
            households_assigned=sum(hh_per_territory.get(t.id, 0) for t in territories),
            visits_confirmed=visits_n, households_visited=hh_n, beneficiaries_visited=people_n,
            last_visit_at=last.get(u.id), followups_upcoming=upcoming.get(u.id, 0),
        ))
    return out


@router.get("/visits", response_model=AdminVisitPage)
def visits(scope: Scope = Depends(), visit_type: str | None = Query(None, max_length=16),
           sort: Literal["newest", "oldest"] = "newest", limit: int = Query(50, ge=1, le=200),
           offset: int = Query(0, ge=0, le=100_000), admin: Principal = Depends(admin_only),
           db: Session = Depends(get_db)):
    base = scope.visits(select(V2Visit))
    if visit_type:
        base = base.where(V2Visit.visit_type == visit_type)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    order = (V2Visit.confirmed_at.desc(), V2Visit.id.desc()) if sort == "newest" else (
        V2Visit.confirmed_at.asc(), V2Visit.id.asc())
    stmt = (base.add_columns(User.username, User.display_name, Territory.code, Household.public_id, Person.public_id)
            .join(User, User.id == V2Visit.worker_id).join(Territory, Territory.id == V2Visit.territory_id)
            .join(Household, Household.id == V2Visit.household_id).join(Person, Person.id == V2Visit.person_id)
            .order_by(*order).limit(limit).offset(offset))
    items = [
        AdminVisit(id=v.id, confirmed_at=v.confirmed_at, worker_id=v.worker_id, worker_username=un,
                   worker_display_name=dn, territory_code=tc, household_public_id=hp, person_public_id=pp,
                   visit_type=v.visit_type, record_version=v.record_version, next_visit_date=v.next_visit_date,
                   danger_sign_count=len(v.danger_signs or []), requires_phc_referral=v.requires_phc_referral)
        for v, un, dn, tc, hp, pp in db.execute(stmt).all()
    ]
    return AdminVisitPage(total=total, limit=limit, offset=offset, items=items)


@router.get("/coverage", response_model=list[AdminTerritoryCoverage])
def coverage(scope: Scope = Depends(), admin: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    terr = select(Territory).order_by(Territory.code)
    if scope.territory_id:
        terr = terr.where(Territory.id == scope.territory_id)
    if scope.worker_id:
        terr = terr.where(Territory.id.in_(select(TerritoryAssignment.territory_id).where(
            _active_assignment(), TerritoryAssignment.user_id == scope.worker_id)))
    territories = db.scalars(terr).all()
    names: dict[uuid.UUID, list[str]] = defaultdict(list)
    for tid, name in db.execute(select(TerritoryAssignment.territory_id, User.display_name)
                                .join(User, User.id == TerritoryAssignment.user_id)
                                .where(_active_assignment(), User.role == "worker").order_by(User.display_name)).all():
        names[tid].append(name)
    in_range = set(db.scalars(scope.visits(select(func.distinct(V2Visit.household_id)))).all())
    last = dict(db.execute(scope.visits(select(V2Visit.household_id, func.max(V2Visit.confirmed_at))
                                        .group_by(V2Visit.household_id), dates=False)).all())
    out = []
    for t in territories:
        hhs = db.scalars(select(Household).where(Household.territory_id == t.id).order_by(Household.public_id)).all()
        items = [CoverageHousehold(id=h.id, public_id=h.public_id, latitude=h.latitude, longitude=h.longitude,
                                   visited_in_range=h.id in in_range, last_visit_at=last.get(h.id)) for h in hhs]
        visited = sum(1 for i in items if i.visited_in_range)
        lasts = [i.last_visit_at for i in items if i.last_visit_at]
        out.append(AdminTerritoryCoverage(
            id=t.id, code=t.code, name=t.name, active=t.active, workers=names.get(t.id, []),
            households_registered=len(items), households_visited=visited, households_not_visited=len(items) - visited,
            last_visit_at=max(lasts) if lasts else None, households=items,
        ))
    return out


@router.get("/users", response_model=list[AdminUser])
def users(role: Literal["worker", "supervisor", "admin"] | None = None, admin: Principal = Depends(admin_only),
          db: Session = Depends(get_db)):
    stmt = select(User).order_by(User.role, User.display_name)
    if role:
        stmt = stmt.where(User.role == role)
    return db.scalars(stmt).all()


@router.get("/assignments", response_model=list[AdminAssignment])
def assignments(include_ended: bool = True, admin: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    creator = aliased(User)
    stmt = (select(TerritoryAssignment, User, Territory, creator.username)
            .join(User, User.id == TerritoryAssignment.user_id)
            .join(Territory, Territory.id == TerritoryAssignment.territory_id)
            .outerjoin(creator, creator.id == TerritoryAssignment.created_by)
            .order_by(TerritoryAssignment.ends_at.is_not(None), TerritoryAssignment.starts_at.desc()))
    if not include_ended:
        stmt = stmt.where(_active_assignment())
    return [
        AdminAssignment(id=a.id, user_id=u.id, username=u.username, display_name=u.display_name, role=u.role,
                        territory_id=t.id, territory_code=t.code, territory_name=t.name, starts_at=a.starts_at,
                        ends_at=a.ends_at, created_by_username=c)
        for a, u, t, c in db.execute(stmt).all()
    ]


@router.post("/assignments/{assignment_id}/reassign", response_model=AdminAssignment, status_code=201,
             dependencies=[Depends(require_csrf)])
def reassign(assignment_id: uuid.UUID, body: ReassignRequest, request: Request,
             admin: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    """End one active assignment and start the same user on another territory, atomically.
    Visits stay with the worker who recorded them; no beneficiary record moves."""
    row = db.execute(select(TerritoryAssignment).where(TerritoryAssignment.id == assignment_id)
                     .with_for_update()).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Assignment not found")
    if row.ends_at is not None:
        raise HTTPException(409, "This assignment has already ended")
    if row.territory_id == body.territory_id:
        raise HTTPException(409, "The worker is already assigned to that territory")
    target = db.get(Territory, body.territory_id)
    if target is None or not target.active:
        raise HTTPException(404, "Territory not found")
    user = db.get(User, row.user_id)
    if user is None or user.role == "admin":
        raise HTTPException(422, "Only worker and supervisor accounts are assigned to territories")
    row.ends_at = utcnow()
    new = TerritoryAssignment(user_id=row.user_id, territory_id=body.territory_id, created_by=admin.user_id)
    db.add(new)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "User already has an active assignment to that territory") from None
    audit(db, actor=admin.user_id, action="assignment.reassign", resource_kind="territory_assignment",
          resource_id=str(new.id), request_id=request_id(request),
          details={"user_id": str(row.user_id), "from_assignment": str(row.id),
                   "from_territory_id": str(row.territory_id), "to_territory_id": str(body.territory_id)})
    db.commit()
    db.refresh(new)
    creator = db.get(User, admin.user_id)
    return AdminAssignment(id=new.id, user_id=user.id, username=user.username, display_name=user.display_name,
                           role=user.role, territory_id=target.id, territory_code=target.code,
                           territory_name=target.name, starts_at=new.starts_at, ends_at=new.ends_at,
                           created_by_username=creator.username if creator else None)
