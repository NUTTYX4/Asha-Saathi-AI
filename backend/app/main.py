"""FastAPI entry point.  Run from backend/:  uvicorn app.main:app --reload"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import websocket
from app.api.routes import health, visits
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.database import connect
from app.db.repositories import VisitRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    conn = connect(get_settings().database_file)
    app.state.repo = VisitRepository(conn)
    yield
    conn.close()


app = FastAPI(title="ASHA SAATHI AI", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(health.router, prefix="/api")
app.include_router(visits.router, prefix="/api")
app.include_router(websocket.router)
