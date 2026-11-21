from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "gnani_configured": settings.gnani_configured,
        "stt_model": settings.prisma_model,
        "tts_model": settings.timbre_model,
    }
