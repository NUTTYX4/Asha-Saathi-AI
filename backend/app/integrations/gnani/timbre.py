"""Gnani Timbre v3.0 TTS adapter (REST).

Protocol source: https://docs.gnani.ai/api/TTS/tts-inference
- POST JSON {text, model, voice, language, speed, audio_config}, header `X-API-Key-ID`.
- Success: HTTP 200 with raw audio bytes (Content-Type follows the container).
- Some accounts allow only one active request at a time (429 RATE_LIMITED),
  so requests are serialized with a process-wide lock.
- Numbers should be passed as spoken words.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.core.config import Settings

log = logging.getLogger(__name__)

_request_lock = asyncio.Lock()


class TimbreError(RuntimeError):
    pass


def build_payload(settings: Settings, text: str, language: str | None = None) -> dict:
    return {
        "text": text,
        "model": settings.timbre_model,
        "voice": settings.timbre_voice,
        "language": language or settings.timbre_language,
        "speed": 1.0,
        "audio_config": {
            "sample_rate": settings.timbre_sample_rate,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    }


async def synthesize(
    settings: Settings, text: str, language: str | None = None, timeout_s: float = 20.0
) -> bytes:
    """Return WAV bytes for `text`. Raises TimbreError with a safe message on failure."""
    headers = {"X-API-Key-ID": settings.require_gnani_key(), "Content-Type": "application/json"}
    payload = build_payload(settings, text, language)
    async with _request_lock:
        response = None
        # One retry for dropped connections only (observed live: httpx.ReadError).
        # HTTP error statuses (400/401/402/429/5xx) are reported, not retried.
        for attempt in (1, 2):
            try:
                async with httpx.AsyncClient(timeout=timeout_s) as client:
                    response = await client.post(settings.timbre_url, json=payload, headers=headers)
                break
            except (httpx.TransportError,) as exc:
                if attempt == 2 or isinstance(exc, httpx.TimeoutException):
                    raise TimbreError(f"Timbre request failed: {type(exc).__name__}") from exc
                log.warning("Timbre connection error (%s); retrying once", type(exc).__name__)
        assert response is not None
    if response.status_code != 200:
        raise TimbreError(f"Timbre HTTP {response.status_code}: {_error_message(response)}")
    if not response.content:
        raise TimbreError("Timbre returned an empty body")
    return fix_streaming_wav_header(response.content)


_UNKNOWN_SIZE = 0xFFFFFFFF


def fix_streaming_wav_header(wav: bytes) -> bytes:
    """Timbre's WAV (observed 21 Nov 2026) uses streaming-style headers: RIFF and
    `data` sizes are 0xFFFFFFFF. Strict decoders reject that, so set the real sizes."""
    if len(wav) < 12 or wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
        return wav
    out = bytearray(wav)
    if int.from_bytes(out[4:8], "little") == _UNKNOWN_SIZE:
        out[4:8] = (len(out) - 8).to_bytes(4, "little")
    pos = 12
    while pos + 8 <= len(out):
        chunk_id = bytes(out[pos : pos + 4])
        size = int.from_bytes(out[pos + 4 : pos + 8], "little")
        if chunk_id == b"data":
            if size == _UNKNOWN_SIZE or pos + 8 + size > len(out):
                out[pos + 4 : pos + 8] = (len(out) - pos - 8).to_bytes(4, "little")
            break
        pos += 8 + size + (size & 1)
    return bytes(out)


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(body.get("detail"), dict):
        detail = body["detail"]
        return f"{detail.get('error_code', '')} {detail.get('message', '')}".strip()
    return str(body.get("message", body))[:200]
