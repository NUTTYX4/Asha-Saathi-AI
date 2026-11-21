from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import COOKIE_NAME, current_principal, get_db, request_id, require_csrf
from app.auth.service import (
    Principal,
    audit,
    authenticate,
    create_session,
    load_principal,
    revoke_session,
    user_for_token,
    visible_territory_ids,
)
from app.core.config import get_settings
from app.db.models import Territory
from app.schemas.auth import LoginRequest, MeOut, TerritoryOut

router = APIRouter(prefix="/auth", tags=["v2-auth"])

GENERIC_LOGIN_ERROR = "Invalid username or password"


def me_out(db: Session, principal: Principal) -> MeOut:
    ids = visible_territory_ids(db, principal)
    rows = db.scalars(select(Territory).where(Territory.id.in_(ids)).order_by(Territory.code)).all() if ids else []
    return MeOut(
        user_id=principal.user_id, username=principal.username, display_name=principal.display_name,
        role=principal.role,  # type: ignore[arg-type]
        territories=[TerritoryOut.model_validate(t, from_attributes=True) for t in rows],
    )


@router.post("/login", response_model=MeOut, dependencies=[Depends(require_csrf)])
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> MeOut:
    settings = get_settings()
    limiter = request.app.state.login_limiter
    username = body.username.strip().lower()
    client = request.client.host if request.client else "unknown"
    if limiter.blocked(username, client):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts; try again later")

    user = authenticate(db, username, body.password)
    if user is None:
        limiter.record_failure(username, client)
        audit(db, actor=None, action="auth.login_failed", resource_kind="user", resource_id=username,
              request_id=request_id(request), details={"reason": "bad_credentials_or_inactive"})
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_LOGIN_ERROR)

    limiter.reset(username, client)
    token = create_session(db, user, settings.session_ttl_hours)
    audit(db, actor=user.id, action="auth.login", resource_kind="user", resource_id=str(user.id),
          request_id=request_id(request))
    db.commit()
    response.set_cookie(
        COOKIE_NAME, token, max_age=settings.session_ttl_hours * 3600, httponly=True,
        secure=settings.session_cookie_secure, samesite="strict", path="/",
    )
    return me_out(db, load_principal(db, user))


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> Response:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        user = user_for_token(db, token)
        revoke_session(db, token)
        audit(db, actor=user.id if user else None, action="auth.logout", resource_kind="session",
              request_id=request_id(request))
        db.commit()
    response.delete_cookie(COOKIE_NAME, path="/", samesite="strict", secure=get_settings().session_cookie_secure,
                           httponly=True)
    response.status_code = 204
    return response


@router.get("/me", response_model=MeOut)
def me(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> MeOut:
    return me_out(db, principal)
