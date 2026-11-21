import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import current_principal, get_db
from app.auth.service import AccessDenied, Principal, ensure_territory_access, visible_territory_ids
from app.db.models import Territory
from app.schemas.auth import TerritoryOut

router = APIRouter(prefix="/territories", tags=["v2-territories"])


@router.get("", response_model=list[TerritoryOut])
def list_territories(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    ids = visible_territory_ids(db, principal)
    if not ids:
        return []
    return db.scalars(select(Territory).where(Territory.id.in_(ids)).order_by(Territory.code)).all()


@router.get("/{territory_id}", response_model=TerritoryOut)
def get_territory(territory_id: uuid.UUID, principal: Principal = Depends(current_principal),
                  db: Session = Depends(get_db)):
    try:
        ensure_territory_access(db, principal, territory_id)
    except AccessDenied:
        # 404, not 403: do not confirm that another territory's ID exists.
        raise HTTPException(404, "Not found") from None
    territory = db.get(Territory, territory_id)
    if territory is None:
        raise HTTPException(404, "Not found")
    return territory
