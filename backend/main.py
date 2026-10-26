"""
FastAPI application entry point.
"""

import logging
import aiosqlite
from contextlib import asynccontextmanager
from fastapi import Request
from fastapi.responses import JSONResponse

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from backend.config import settings
from backend.database import init_db
from backend.routers import meetings, reports, campaigns, system, integrations, auth
from backend.auth import SESSION_COOKIE, audit, get_session, validate_csrf

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
    docs_url="/docs" if settings.app_debug else None,
    redoc_url="/redoc" if settings.app_debug else None,
    openapi_url="/openapi.json" if settings.app_debug else None,
)

_PUBLIC_API_PATHS = {"/api/v1/auth/login"}
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@app.middleware("http")
async def admin_security_boundary(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api/v1/") or path in _PUBLIC_API_PATHS:
        return await call_next(request)

    if not settings.admin_password_hash:
        return JSONResponse(status_code=503, content={"detail": "Admin authentication is not configured."})

    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        session = await get_session(db, request.cookies.get(SESSION_COOKIE))
        if not session:
            return JSONResponse(status_code=401, content={"detail": "Authentication required."})
        if request.method not in _SAFE_METHODS and not await validate_csrf(request, session):
            await audit(db, actor=session["username"], action=f"{request.method} {path}", result="csrf_rejected")
            return JSONResponse(status_code=403, content={"detail": "CSRF validation failed."})

        response = await call_next(request)
        await audit(db, actor=session["username"], action=f"{request.method} {path}", result=str(response.status_code))
        return response

# API routes
app.include_router(meetings.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(campaigns.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")

# Serve frontend static files
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
