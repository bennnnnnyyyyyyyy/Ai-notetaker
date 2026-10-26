"""
FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from backend.config import settings
from backend.database import init_db
from backend.routers import meetings, reports, campaigns, system, integrations

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG if settings.app_debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_data_dirs()
    await init_db()
    logging.getLogger(__name__).info(
        "Prime Ad Meeting Intelligence started at http://%s:%d",
        settings.app_host,
        settings.app_port,
    )
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Prime Ad Meeting Intelligence",
    version="0.1.0",
    lifespan=lifespan,
)

# API routes
app.include_router(meetings.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(campaigns.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1")

# Serve frontend static files
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
