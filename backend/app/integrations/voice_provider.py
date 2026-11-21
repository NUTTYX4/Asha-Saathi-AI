"""Speech providers for the V2 voice session (Phase 5).

`GnaniVoiceProvider` is the only production provider: it wraps the existing, unchanged Gnani
adapters (Prisma v3.0 streaming STT, Timbre v3.0 TTS). There is no other speech vendor and no
text-only fallback.

`MockVoiceProvider` exists only for the browser end-to-end test against the disposable
`*_e2e` database. `build_voice_provider` refuses to create it for any other database, so the
application can never silently run without Gnani.
"""

from __future__ import annotations

import asyncio
import io
import json
import wave
from collections.abc import AsyncIterator
from typing import Protocol

from app.core.config import Settings
from app.integrations.gnani import timbre
from app.integrations.gnani.prisma import PrismaConnection, PrismaEvent, describe_stt_model

E2E_DATABASE_SUFFIX = "_e2e"


class SttStream(Protocol):
    async def send_audio(self, pcm: bytes) -> None: ...

    def events(self) -> AsyncIterator[PrismaEvent]: ...

    async def close(self) -> None: ...


class VoiceProvider(Protocol):
    name: str

    async def open_stt(self) -> tuple[SttStream, str]: ...

    async def tts(self, text: str) -> bytes: ...


# ---------------------------------------------------------------- Gnani (production)
class _PrismaStream:
    def __init__(self, conn: PrismaConnection) -> None:
        self._conn = conn

    async def send_audio(self, pcm: bytes) -> None:
        await self._conn.send_audio(pcm)

    def events(self) -> AsyncIterator[PrismaEvent]:
        return self._conn.events()

    async def close(self) -> None:
        await self._conn.__aexit__(None, None, None)


class GnaniVoiceProvider:
    name = "gnani"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def open_stt(self) -> tuple[SttStream, str]:
        conn = await PrismaConnection(self._settings).__aenter__()
        return _PrismaStream(conn), describe_stt_model(conn.connected_info, self._settings.prisma_model)

    async def tts(self, text: str) -> bytes:
        return await timbre.synthesize(self._settings, text)


# ---------------------------------------------------------------- scripted mock (e2e only)
DEFAULT_MOCK_SCRIPT = [
    # Synthetic notes only (no real patient). The second line is a correction.
    "ತೂಕ ಎರಡು ಪಾಯಿಂಟ್ ಐದು ಕಿಲೋ, ಮುಂದಿನ ಭೇಟಿ ನವೆಂಬರ್ ಇಪ್ಪತ್ತೆಂಟು",
    "ಇಲ್ಲ, ತೂಕ ಮೂರು ಕಿಲೋ",
]


def _silent_wav(seconds: float = 0.25, rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


class _MockStream:
    """Emits the next scripted transcript after every `bytes_per_utterance` of received audio."""

    def __init__(self, script: list[str], bytes_per_utterance: int) -> None:
        self._script = list(script)
        self._every = bytes_per_utterance
        self._received = 0
        self._queue: asyncio.Queue[PrismaEvent | None] = asyncio.Queue()

    async def send_audio(self, pcm: bytes) -> None:
        self._received += len(pcm)
        if self._script and self._received >= self._every:
            self._received = 0
            text = self._script.pop(0)
            await self._queue.put(PrismaEvent(kind="speech_start"))
            await self._queue.put(PrismaEvent(kind="transcript", text=text, language="kn-IN"))

    async def events(self) -> AsyncIterator[PrismaEvent]:
        while (event := await self._queue.get()) is not None:
            yield event

    async def close(self) -> None:
        await self._queue.put(None)


class MockVoiceProvider:
    name = "mock"

    def __init__(self, script: list[str], bytes_per_utterance: int = 4 * 32000) -> None:
        self._script = script
        self._bytes_per_utterance = bytes_per_utterance

    async def open_stt(self) -> tuple[SttStream, str]:
        return _MockStream(self._script, self._bytes_per_utterance), "MOCK (not Gnani; e2e test only)"

    async def tts(self, text: str) -> bytes:
        return _silent_wav()


def build_voice_provider(settings: Settings, database_name: str | None) -> VoiceProvider | None:
    """The configured provider, or None when Gnani is not configured (sessions then refuse)."""
    if settings.voice_provider_mode == "mock":
        if not (database_name or "").endswith(E2E_DATABASE_SUFFIX):
            raise RuntimeError("VOICE_PROVIDER_MODE=mock is allowed only for the disposable *_e2e database")
        script = json.loads(settings.mock_voice_script) if settings.mock_voice_script else DEFAULT_MOCK_SCRIPT
        return MockVoiceProvider(script)
    return GnaniVoiceProvider(settings) if settings.gnani_configured else None
