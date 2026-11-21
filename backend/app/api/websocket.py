"""Browser <-> backend voice session gateway.

Binary frames from the browser are PCM s16le mono 16 kHz and are forwarded to
Prisma. Prisma events drive the VoiceSession. The Gnani key never leaves the server.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.core.config import get_settings
from app.integrations.gnani import timbre
from app.integrations.gnani.prisma import PrismaConnection, describe_stt_model  # noqa: F401 (re-export)
from app.schemas.events import ClientEvent, RecordConfirm, SessionError, SessionStart, SessionStop
from app.services.session_service import VoiceSession

log = logging.getLogger(__name__)
router = APIRouter()
_client_events = TypeAdapter(ClientEvent)


@router.websocket("/ws/session")
async def voice_session(ws: WebSocket) -> None:
    await ws.accept()
    settings = get_settings()

    async def send(event: BaseModel) -> None:
        await ws.send_text(event.model_dump_json())

    if not settings.gnani_configured:
        await send(SessionError(code="GNANI_NOT_CONFIGURED", message="GNANI_API_KEY is not set on the server."))
        await ws.close()
        return

    # Wait for the explicit session.start from the client.
    try:
        first = _client_events.validate_json(await ws.receive_text())
    except (ValidationError, WebSocketDisconnect, KeyError):
        await ws.close()
        return
    if not isinstance(first, SessionStart):
        await ws.close()
        return

    try:
        prisma = await PrismaConnection(settings).__aenter__()
    except Exception as exc:
        log.warning("Prisma connect failed: %s", type(exc).__name__)
        await send(SessionError(code="STT_CONNECT_FAILED", message=f"Speech service unavailable: {exc}", retryable=True))
        await ws.close()
        return

    stt_model = describe_stt_model(prisma.connected_info, settings.prisma_model)
    session = VoiceSession(
        send=send,
        tts=lambda text: timbre.synthesize(settings, text),
        repo=ws.app.state.repo,
        stt_model=stt_model,
    )

    async def client_loop() -> None:
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                return
            if message.get("bytes"):
                await prisma.send_audio(message["bytes"])
            elif message.get("text"):
                try:
                    event = _client_events.validate_json(message["text"])
                except ValidationError:
                    await send(SessionError(code="BAD_CLIENT_EVENT", message="Unrecognised client event"))
                    continue
                if isinstance(event, RecordConfirm):
                    await session.confirm(event.record_version)
                elif isinstance(event, SessionStop):
                    return

    async def prisma_loop() -> None:
        async for event in prisma.events():
            if event.kind == "speech_start":
                await session.on_speech_start()
            elif event.kind == "transcript":
                await session.on_transcript(event.text, event.language)
            elif event.kind == "error":
                await send(SessionError(code="STT_ERROR", message=event.text, retryable=True))
                return

    await session.start()
    tasks = [asyncio.create_task(client_loop()), asyncio.create_task(prisma_loop())]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if task.exception() and not isinstance(task.exception(), WebSocketDisconnect):
                log.warning("Session task failed: %r", task.exception())
    finally:
        for task in tasks:
            task.cancel()
        await session.close()
        await prisma.__aexit__(None, None, None)
        try:
            await ws.close()
        except RuntimeError:
            pass
