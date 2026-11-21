"""Admin-only account, territory and assignment management. Every change is audited."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import get_db, request_id, require_csrf, require_roles
from app.auth.passwords import hash_password
from app.auth.service import Principal, audit, utcnow
from app.db.models import AuditEvent, Territory, TerritoryAssignment, User
from app.schemas.auth import (
    AssignmentCreate,
    AssignmentOut,
    AuditOut,
    TerritoryCreate,
    TerritoryOut,
    UserCreate,
    UserOut,
)

router = APIRouter(prefix="/admin", tags=["v2-admin"])
admin_only = require_roles("admin")


@router.post("/users", response_model=UserOut, status_code=201, dependencies=[Depends(require_csrf)])
def create_user(body: UserCreate, request: Request, admin: Principal = Depends(admin_only),
                db: Session = Depends(get_db)):
    user = User(username=body.username.lower(), display_name=body.display_name, role=body.role,
                password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Username already exists") from None
    audit(db, actor=admin.user_id, action="user.create", resource_kind="user", resource_id=str(user.id),
          request_id=request_id(request), details={"role": body.role})
    db.commit()
    return user


@router.post("/territories", response_model=TerritoryOut, status_code=201, dependencies=[Depends(require_csrf)])
def create_territory(body: TerritoryCreate, request: Request, admin: Principal = Depends(admin_only),
                     db: Session = Depends(get_db)):
    territory = Territory(code=body.code, name=body.name)
    db.add(territory)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Territory code already exists") from None
    audit(db, actor=admin.user_id, action="territory.create", resource_kind="territory",
          resource_id=str(territory.id), request_id=request_id(request))
    db.commit()
    return territory


@router.post("/assignments", response_model=AssignmentOut, status_code=201, dependencies=[Depends(require_csrf)])
def create_assignment(body: AssignmentCreate, request: Request, admin: Principal = Depends(admin_only),
                      db: Session = Depends(get_db)):
    user = db.get(User, body.user_id)
    if user is None or db.get(Territory, body.territory_id) is None:
        raise HTTPException(404, "User or territory not found")
    if user.role == "admin":
        raise HTTPException(422, "Admins have global access and are not assigned to territories")
    row = TerritoryAssignment(user_id=body.user_id, territory_id=body.territory_id, created_by=admin.user_id)
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "User already has an active assignment to this territory") from None
    audit(db, actor=admin.user_id, action="assignment.create", resource_kind="territory_assignment",
          resource_id=str(row.id), request_id=request_id(request),
          details={"user_id": str(body.user_id), "territory_id": str(body.territory_id)})
    db.commit()
    db.refresh(row)
    return row


@router.post("/assignments/{assignment_id}/end", response_model=AssignmentOut,
             dependencies=[Depends(require_csrf)])
def end_assignment(assignment_id: uuid.UUID, request: Request, admin: Principal = Depends(admin_only),
                   db: Session = Depends(get_db)):
    row = db.get(TerritoryAssignment, assignment_id)
    if row is None:
        raise HTTPException(404, "Not found")
    if row.ends_at is None:
        row.ends_at = utcnow()
        audit(db, actor=admin.user_id, action="assignment.end", resource_kind="territory_assignment",
              resource_id=str(row.id), request_id=request_id(request))
        db.commit()
        db.refresh(row)
    return row


@router.get("/audit", response_model=list[AuditOut])
def list_audit(limit: int = Query(50, ge=1, le=500), admin: Principal = Depends(admin_only),
               db: Session = Depends(get_db)):
    return db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)).all()
