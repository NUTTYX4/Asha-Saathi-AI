"""Timbre adapter: WAV header repair (header layout observed from the live API)."""

import io
import struct
import wave

from app.integrations.gnani.timbre import fix_streaming_wav_header


def _streaming_wav(pcm: bytes) -> bytes:
    fmt = struct.pack("<HHIIHH", 1, 1, 16000, 32000, 2, 16)
    return (
        b"RIFF" + struct.pack("<I", 0xFFFFFFFF) + b"WAVE"
        + b"fmt " + struct.pack("<I", 16) + fmt
        + b"data" + struct.pack("<I", 0xFFFFFFFF) + pcm
    )


def test_streaming_sizes_are_replaced_with_real_sizes():
    pcm = bytes(range(256)) * 4
    fixed = fix_streaming_wav_header(_streaming_wav(pcm))
    assert struct.unpack("<I", fixed[4:8])[0] == len(fixed) - 8
    assert struct.unpack("<I", fixed[40:44])[0] == len(pcm)
    with wave.open(io.BytesIO(fixed)) as w:
        assert w.getnframes() == len(pcm) // 2


def test_valid_wav_is_unchanged():
    pcm = b"\x00\x01" * 100
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm)
    assert fix_streaming_wav_header(buf.getvalue()) == buf.getvalue()


def test_non_wav_passthrough():
    assert fix_streaming_wav_header(b"ID3mp3data") == b"ID3mp3data"


# ---------- retry behaviour (MOCKED transport: no Gnani call) ----------
import httpx  # noqa: E402
import pytest  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.integrations.gnani import timbre  # noqa: E402

SETTINGS = Settings(gnani_api_key="test-key", _env_file=None)


def _patch_post(monkeypatch, outcomes):
    calls = []

    async def fake_post(self, url, json=None, headers=None):
        calls.append(url)
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    return calls


async def test_retries_once_on_dropped_connection(monkeypatch):
    ok = httpx.Response(200, content=_streaming_wav(b"\x00\x00" * 10))
    calls = _patch_post(monkeypatch, [httpx.ReadError("reset"), ok])
    audio = await timbre.synthesize(SETTINGS, "ನಮಸ್ಕಾರ")
    assert len(calls) == 2 and audio.startswith(b"RIFF")


async def test_http_error_status_is_not_retried(monkeypatch):
    limited = httpx.Response(429, json={"detail": {"error_code": "RATE_LIMITED", "message": "busy"}})
    calls = _patch_post(monkeypatch, [limited, limited])
    with pytest.raises(timbre.TimbreError, match="429"):
        await timbre.synthesize(SETTINGS, "ನಮಸ್ಕಾರ")
    assert len(calls) == 1
