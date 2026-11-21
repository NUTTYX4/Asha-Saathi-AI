from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.db.database import backend_name, ping

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict:
    settings = get_settings()
    engine = request.app.state.repo.engine
    db_ok = ping(engine)
    return {
        "status": "ok" if db_ok else "degraded",
        "gnani_configured": settings.gnani_configured,
        "stt_model": settings.prisma_model,
        "tts_model": settings.timbre_model,
        # Added in V2 (backward compatible): which database is in use and whether it answers.
        "database": backend_name(engine),
        "database_ok": db_ok,
    }
