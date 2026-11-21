"""Authenticated V2 voice WebSocket (/ws/v2/session).

Phase 2 delivers the gate: the handshake is refused unless the session cookie is valid and the
Origin matches the Host (blocks cross-site WebSocket hijacking). Binding the session to an
authorised household/person and running the Gnani pipeline is Phase 5.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket
from sqlalchemy.orm import Session

from app.auth.deps import COOKIE_NAME
from app.auth.service import Principal, load_principal, user_for_token
from app.core.config import get_settings
from app.schemas.events import SessionError

router = APIRouter()

WS_UNAUTHENTICATED = 4401
WS_FORBIDDEN_ORIGIN = 4403


def origin_allowed(origin: str | None, host: str | None) -> bool:
    """Same-origin (Origin host == Host header, as through the Vite proxy) or a configured origin."""
    if not origin:
        return False
    if origin in get_settings().cors_origin_list:
        return True
    return bool(host) and urlsplit(origin).netloc == host


def authenticate_websocket(ws: WebSocket) -> tuple[Principal | None, int | None]:
    if not origin_allowed(ws.headers.get("origin"), ws.headers.get("host")):
        return None, WS_FORBIDDEN_ORIGIN
    with Session(ws.app.state.engine) as db:
        user = user_for_token(db, ws.cookies.get(COOKIE_NAME))
        if user is None:
            return None, WS_UNAUTHENTICATED
        return load_principal(db, user), None


@router.websocket("/ws/v2/session")
async def v2_session(ws: WebSocket) -> None:
    principal, close_code = authenticate_websocket(ws)
    if principal is None:
        # Closing before accept() rejects the handshake (HTTP 403); nothing reaches Gnani.
        await ws.close(code=close_code)
        return
    await ws.accept()
    await ws.send_text(SessionError(
        code="NOT_READY",
        message="Authenticated. Household/person-bound voice sessions are enabled in Phase 5.",
    ).model_dump_json())
    await ws.close()
