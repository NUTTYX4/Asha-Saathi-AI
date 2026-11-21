"""Gnani Prisma v3.0 realtime STT adapter.

Protocol source: https://docs.gnani.ai/api/STT/stt-websocket
- Config travels as WebSocket upgrade headers (auth: `x-api-key-id`).
- Client sends raw PCM s16le mono frames of exactly 1,024 bytes at real-time cadence.
- `{"type": "commit"}` closes the open utterance immediately.
- Server sends JSON: connected, speech_start, processing, transcript (always final), error.
An unrecognised `model` header silently falls back to prisma-v2.5, so callers should
check `PrismaConnection.connected_info` after connecting.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

from app.core.config import Settings

log = logging.getLogger(__name__)

FRAME_BYTES = 1024  # 512 samples of 16-bit mono PCM


@dataclass
class PrismaEvent:
    kind: str  # connected | speech_start | processing | transcript | error | settings_updated
    text: str = ""
    language: str | None = None
    segment_id: str | None = None
    latency_ms: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def build_headers(settings: Settings) -> dict[str, str]:
    return {
        "x-api-key-id": settings.require_gnani_key(),
        "model": settings.prisma_model,
        "language_code": settings.prisma_languages,
        "format": settings.prisma_format,
        "x-sample-rate": str(settings.prisma_sample_rate),
        "x-min-silence-ms": str(settings.prisma_min_silence_ms),
    }


def parse_message(message: str | bytes) -> PrismaEvent | None:
    if isinstance(message, bytes):
        return None
    data = json.loads(message)
    kind = data.get("type", "")
    if kind == "transcript":
        return PrismaEvent(
            kind="transcript",
            text=(data.get("text") or "").strip(),
            language=data.get("detected_language_code"),
            segment_id=data.get("segment_id"),
            latency_ms=data.get("latency"),
            raw=data,
        )
    if kind == "error":
        return PrismaEvent(kind="error", text=data.get("message", ""), raw=data)
    return PrismaEvent(kind=kind, raw=data)


class PrismaConnection:
    """One realtime STT stream. Use as an async context manager."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._ws: ClientConnection | None = None
        self._buffer = bytearray()
        self.connected_info: dict[str, Any] = {}

    async def __aenter__(self) -> PrismaConnection:
        self._ws = await websockets.connect(
            self._settings.prisma_ws_url,
            additional_headers=build_headers(self._settings),
            open_timeout=10,
            max_size=2**20,
        )
        first = parse_message(await self._ws.recv())
        if first is None or first.kind != "connected":
            detail = first.text if first else "non-JSON first message"
            await self._ws.close()
            raise RuntimeError(f"Prisma did not send 'connected': {detail}")
        self.connected_info = first.raw
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    async def send_audio(self, pcm: bytes) -> None:
        """Buffer arbitrary-length PCM and forward it as exact 1,024-byte frames."""
        assert self._ws is not None
        self._buffer.extend(pcm)
        while len(self._buffer) >= FRAME_BYTES:
            frame = bytes(self._buffer[:FRAME_BYTES])
            del self._buffer[:FRAME_BYTES]
            await self._ws.send(frame)

    async def commit(self) -> None:
        assert self._ws is not None
        await self._ws.send(json.dumps({"type": "commit"}))

    async def events(self) -> AsyncIterator[PrismaEvent]:
        assert self._ws is not None
        async for message in self._ws:
            event = parse_message(message)
            if event is not None:
                yield event
