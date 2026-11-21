"""FastAPI entry point.

V2 (Docker):  docker compose up --build -d   (DATABASE_URL -> PostgreSQL/PostGIS)
Round 1:      run from backend/: uvicorn app.main:app   (no DATABASE_URL -> SQLite file)
"""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from app.api import websocket
from app.api.routes import health, visits
from app.api.v2 import admin as v2_admin
from app.api.v2 import auth as v2_auth
from app.api.v2 import households as v2_households
from app.api.v2 import territories as v2_territories
from app.api.v2 import visits as v2_visits
from app.api.v2 import ws as v2_ws
from app.auth.ratelimit import LoginRateLimiter, RequestRateLimiter
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.database import connect, connect_postgres
from app.db.repositories import VisitRepository
from app.integrations.voice_provider import build_voice_provider
from app.services.voice_v2 import SessionRegistry


def _default_engine() -> Engine:
    settings = get_settings()
    if settings.database_url is not None:
        return connect_postgres(settings.database_url.get_secret_value())
    return connect(settings.database_file)


def create_app(engine: Engine | None = None) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging()
        eng = engine or _default_engine()
        app.state.engine = eng
        app.state.repo = VisitRepository(eng)
        app.state.login_limiter = LoginRateLimiter(settings.login_max_failures, settings.login_failure_window_s)
        app.state.discovery_limiter = RequestRateLimiter(settings.discovery_requests_per_minute, 60)
        # V2 voice (Phase 5): Gnani provider (mock only for the *_e2e database) and live sessions.
        app.state.voice_provider = build_voice_provider(settings, eng.url.database)
        app.state.voice_registry = SessionRegistry(settings.voice_max_sessions_per_worker)
        yield
        if engine is None:
            eng.dispose()

    app = FastAPI(title="ASHA SAATHI AI", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        incoming = request.headers.get("x-request-id", "")
        request.state.request_id = incoming if 0 < len(incoming) <= 64 else str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    app.include_router(health.router, prefix="/api")
    if settings.legacy_round1_enabled:
        app.include_router(visits.router, prefix="/api")
        app.include_router(websocket.router)
    app.include_router(v2_auth.router, prefix="/api/v2")
    app.include_router(v2_territories.router, prefix="/api/v2")
    app.include_router(v2_admin.router, prefix="/api/v2")
    app.include_router(v2_households.router, prefix="/api/v2")
    app.include_router(v2_visits.router, prefix="/api/v2")
    app.include_router(v2_ws.router)
    return app


app = create_app()
