"""Live smoke test for Gnani Timbre v3.0 (TTS) and Prisma v3.0 (STT).

Spends a small number of real Gnani credits. Uses synthetic text only.

1. Timbre synthesizes a synthetic Kannada visit sentence (16 kHz WAV).
2. That audio is streamed to Prisma in 1,024-byte frames at real-time cadence.
3. Reports the model Prisma echoes back and the transcripts it returns.

Run from backend/:  .venv\\Scripts\\python -m scripts.smoke_gnani
"""

from __future__ import annotations

import asyncio
import io
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import REPO_ROOT, get_settings  # noqa: E402
from app.integrations.gnani import timbre  # noqa: E402
from app.integrations.gnani.prisma import FRAME_BYTES, PrismaConnection  # noqa: E402

SYNTHETIC_TEXT = (
    "ಫಲಾನುಭವಿ ಐಡಿ ಒಂದು ಎರಡು ಮೂರು ನಾಲ್ಕು. ANC checkup ಮಾಡಿದೆ. "
    "ತೂಕ ಐವತ್ತೆರಡು ಕಿಲೋ. TT injection ಕೊಡಬೇಕು."
)


async def run() -> int:
    settings = get_settings()
    if not settings.gnani_configured:
        print("BLOCKED: GNANI_API_KEY is not set in the repository-root .env file.")
        return 2

    tts_settings = settings.model_copy(update={"timbre_sample_rate": 16000})
    print(f"[timbre] model={settings.timbre_model} voice={settings.timbre_voice} lang={settings.timbre_language}")
    started = time.perf_counter()
    try:
        audio = await timbre.synthesize(tts_settings, SYNTHETIC_TEXT)
    except timbre.TimbreError as exc:
        print(f"[timbre] FAILED: {exc}")
        return 1
    print(f"[timbre] OK: {len(audio)} bytes in {time.perf_counter() - started:.2f}s")

    out_dir = REPO_ROOT / "tmp"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "smoke_timbre.wav").write_bytes(audio)

    with wave.open(io.BytesIO(audio)) as wav:
        rate, channels, width = wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
        pcm = wav.readframes(wav.getnframes())
    print(f"[timbre] wav: {rate} Hz, {channels} ch, {width * 8}-bit, {len(pcm) / (rate * width):.2f}s")
    if (rate, channels, width) != (16000, 1, 2):
        print("[prisma] SKIPPED: smoke audio is not 16 kHz mono 16-bit")
        return 1

    print(f"[prisma] connecting model={settings.prisma_model} langs={settings.prisma_languages} format={settings.prisma_format}")
    try:
        async with PrismaConnection(settings) as stream:
            info = stream.connected_info
            print(f"[prisma] connected: config={info.get('config')} request_id={info.get('request_id')}")

            async def send() -> None:
                silence = bytes(FRAME_BYTES * 30)  # ~1 s of silence to let VAD close the segment
                payload = pcm + silence
                for i in range(0, len(payload), FRAME_BYTES):
                    await stream.send_audio(payload[i : i + FRAME_BYTES])
                    await asyncio.sleep(0.032)
                await stream.commit()

            texts: list[str] = []  # shared, so a receive timeout keeps what arrived

            async def receive() -> None:
                async for event in stream.events():
                    if event.kind == "transcript":
                        print(f"[prisma] transcript ({event.language}, {event.latency_ms} ms): {event.text}")
                        texts.append(event.text)
                    elif event.kind == "error":
                        print(f"[prisma] error: {event.text}")
                        break
                    else:
                        print(f"[prisma] event: {event.kind}")

            sender = asyncio.create_task(send())
            try:
                # The socket stays open after the last transcript, so this normally times out.
                await asyncio.wait_for(receive(), timeout=len(pcm) / 32000 + 6)
            except asyncio.TimeoutError:
                pass
            await sender
    except Exception as exc:  # report, never hide
        print(f"[prisma] FAILED: {type(exc).__name__}: {exc}")
        return 1

    if not texts:
        print("[prisma] FAILED: no transcript received")
        return 1
    print("SMOKE TEST PASSED: Timbre audio produced and Prisma returned a transcript.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
