"""Authenticated V2 voice WebSocket (/ws/v2/session).

Handshake (Phase 2): refused before accept() unless the session cookie is valid and the Origin
is the page's own origin (Origin host == Host header; the Vite proxy keeps the browser's Host
for /ws) or a configured origin. This blocks cross-site WebSocket hijacking.

Phase 5 (when V2_VOICE_ENABLED): the first frame must be `v2.session.start` naming the explicitly
selected household and person and a fresh logical visit key. The server re-authorises that pair
for this worker, binds the session to it immutably, then runs the unchanged Gnani pipeline
(Prisma v3.0 STT, Timbre v3.0 TTS) through `V2VisitSession`. Binary frames are PCM s16le mono
16 kHz and are forwarded only after the AI disclosure has played.
"""

from __future__ import annotations

import asyncio
import logging
import time
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.auth.deps import COOKIE_NAME
from app.auth.service import Principal, load_principal, user_for_token
from app.core.config import get_settings
from app.schemas.events import (
    PlaybackCompleted,
    ReadbackRequest,
    RecordConfirm,
    SessionCancel,
    SessionError,
    SessionStop,
    V2ClientEvent,
    V2SessionStart,
)
from app.services.voice_v2 import StartRefused, V2VisitSession, authorize_start

log = logging.getLogger(__name__)
router = APIRouter()
_events = TypeAdapter(V2ClientEvent)

WS_UNAUTHENTICATED = 4401
WS_FORBIDDEN_ORIGIN = 4403
WS_SUPERSEDED = 4409
WS_TIMEOUT = 4408
WS_POLICY = 1008
START_TIMEOUT_S = 10
MAX_AUDIO_FRAME_BYTES = 64 * 1024
CLOSE_CODES = {"superseded": WS_SUPERSEDED, "expired": WS_TIMEOUT, "idle": WS_TIMEOUT, "revoked": WS_POLICY,
               "cancelled": 1000, "provider_unavailable": 1011}


def origin_allowed(origin: str | None, host: str | None) -> bool:
    """Same-origin (Origin host == Host header) or an explicitly configured origin."""
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


async def _close(ws: WebSocket, code: int = 1000) -> None:
    try:
        await ws.close(code=code)
    except RuntimeError:
        pass  # already closed by the client or by us


@router.websocket("/ws/v2/session")
async def v2_session(ws: WebSocket) -> None:
    principal, close_code = authenticate_websocket(ws)
    if principal is None:
        # Closing before accept() rejects the handshake (HTTP 403); nothing reaches Gnani.
        await ws.close(code=close_code)
        return
    await ws.accept()
    settings = get_settings()

    async def send(event: BaseModel) -> None:
        try:
            await ws.send_text(event.model_dump_json())
        except (RuntimeError, WebSocketDisconnect):
            pass  # the browser went away; cleanup follows

    if not settings.v2_voice_enabled:
        await send(SessionError(code="NOT_READY", message="Voice visits are not enabled on this server."))
        await _close(ws)
        return
    provider = ws.app.state.voice_provider
    if provider is None:
        await send(SessionError(code="GNANI_NOT_CONFIGURED", message="The speech service is not configured."))
        await _close(ws)
        return

    # 1. The explicit selection, re-authorised by the server.
    try:
        start = _events.validate_json(await asyncio.wait_for(ws.receive_text(), START_TIMEOUT_S))
    except (ValidationError, WebSocketDisconnect, KeyError, TimeoutError, RuntimeError):
        await _close(ws, WS_POLICY)
        return
    if not isinstance(start, V2SessionStart):
        await _close(ws, WS_POLICY)
        return
    engine = ws.app.state.engine
    try:
        binding, display_name = await asyncio.to_thread(authorize_start, engine, ws.cookies.get(COOKIE_NAME), start)
    except StartRefused as exc:
        await send(SessionError(code=exc.code, message=exc.message))
        await _close(ws, WS_POLICY)
        return

    # 2. Speech-to-text stream (Gnani Prisma, or the e2e-only mock).
    try:
        stt, stt_model = await provider.open_stt()
    except Exception as exc:
        log.warning("STT connect failed: %s", type(exc).__name__)
        await send(SessionError(code="STT_CONNECT_FAILED", message="Speech service unavailable. Try again.",
                                retryable=True))
        await _close(ws, 1011)
        return

    ended = asyncio.Event()

    async def on_end(_reason: str) -> None:
        ended.set()

    extraction_provider = getattr(ws.app.state, "extraction_provider", None)
    session = V2VisitSession(send=send, tts=provider.tts, engine=engine, binding=binding,
                             visit_type=start.visit_type, person_display_name=display_name,
                             stt_model=stt_model, on_end=on_end,
                             extraction_provider=extraction_provider)
    registry = ws.app.state.voice_registry
    try:
        previous = registry.claim(session)
    except StartRefused as exc:
        await send(SessionError(code=exc.code, message=exc.message))
        await stt.close()
        await _close(ws, WS_POLICY)
        return
    if previous is not None:
        await previous.end("superseded", "This visit was opened again in another tab or window.")

    last_activity = time.monotonic()

    async def client_loop() -> None:
        nonlocal last_activity
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                return
            last_activity = time.monotonic()
            if message.get("bytes") is not None:
                frame = message["bytes"]
                if len(frame) > MAX_AUDIO_FRAME_BYTES:
                    await send(SessionError(code="AUDIO_FRAME_TOO_LARGE", message="Audio frame too large."))
                    await session.end("cancelled", "The visit was stopped (invalid audio).")
                    return
                if session.active and session.accepting_speech:
                    await stt.send_audio(frame)
                continue
            try:
                event = _events.validate_json(message.get("text") or "")
            except ValidationError:
                await send(SessionError(code="BAD_CLIENT_EVENT", message="Unrecognised client event"))
                continue
            if isinstance(event, RecordConfirm):
                await session.confirm(event.record_version)
            elif isinstance(event, PlaybackCompleted):
                session.on_playback_completed(event.purpose, event.record_version)
            elif isinstance(event, ReadbackRequest):
                await session.request_readback()
            elif isinstance(event, SessionStop | SessionCancel):
                await session.end("cancelled", "The visit was cancelled; nothing was saved.")
                return
            else:  # e.g. a second v2.session.start: the subject can never change mid-session
                await send(SessionError(code="SUBJECT_IMMUTABLE",
                                        message="This session is bound to the selected person. Start a new visit."))

    async def stt_loop() -> None:
        async for event in stt.events():
            if event.kind == "speech_start":
                await session.on_speech_start()
            elif event.kind == "transcript":
                await session.on_transcript(event.text, event.language)
            elif event.kind == "error":
                await send(SessionError(code="STT_ERROR", message="Speech recognition failed. Try again.",
                                        retryable=True))
                await session.end("provider_unavailable", "The speech service stopped; nothing was saved.")
                return

    async def watchdog() -> None:
        started = last_check = time.monotonic()
        while session.ended_reason is None:
            await asyncio.sleep(0.5)
            now = time.monotonic()
            if now - started > settings.voice_session_ttl_s:
                await session.end("expired", "The visit session expired; nothing was saved.")
            elif now - last_activity > settings.voice_idle_timeout_s:
                await session.end("idle", "The visit stopped after a period of inactivity.")
            elif session.active and now - last_check > settings.voice_revalidate_s:
                last_check = now
                await session.revalidate()

    await session.start()
    tasks = [asyncio.create_task(t()) for t in (client_loop, stt_loop, watchdog)]
    tasks.append(asyncio.create_task(ended.wait()))
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            exc = task.exception()
            if exc and not isinstance(exc, WebSocketDisconnect):
                log.warning("V2 voice task failed: %s", type(exc).__name__)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if session.saved is None and session.ended_reason is None:
            session.ended_reason = "cancelled"
            session._discard_draft()  # nothing unconfirmed survives the connection
        await session.close()
        registry.release(session)
        await stt.close()
        await _close(ws, CLOSE_CODES.get(session.ended_reason or "cancelled", 1000))
