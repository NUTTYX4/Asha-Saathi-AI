"""FastAPI dependencies: DB session, current principal, roles, anti-CSRF header."""

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.service import Principal, load_principal, user_for_token

COOKIE_NAME = "asha_session"
# Unsafe requests must carry this header. A cross-site form cannot set custom headers, and a
# cross-site script would need a CORS preflight that this API does not allow (GET-only CORS).
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "asha-saathi"


def get_db(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


def require_csrf(request: Request) -> None:
    if request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing anti-CSRF header")


def current_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    user = user_for_token(db, request.cookies.get(COOKIE_NAME))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    return load_principal(db, user)


def require_roles(*roles: str):
    def _dep(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted for this role")
        return principal

    return _dep


def request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)
