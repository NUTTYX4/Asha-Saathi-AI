"""FastAPI entry point.

V2 (Docker):  docker compose up --build -d   (DATABASE_URL -> PostgreSQL/PostGIS)
Round 1:      run from backend/: uvicorn app.main:app   (no DATABASE_URL -> SQLite file)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import websocket
from app.api.routes import health, visits
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.database import connect, connect_postgres
from app.db.repositories import VisitRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    if settings.database_url is not None:
        engine = connect_postgres(settings.database_url.get_secret_value())
    else:
        engine = connect(settings.database_file)
    app.state.repo = VisitRepository(engine)
    yield
    engine.dispose()


app = FastAPI(title="ASHA SAATHI AI", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(health.router, prefix="/api")
app.include_router(visits.router, prefix="/api")
app.include_router(websocket.router)
