import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
import aiosqlite

from backend.auth import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    audit,
    create_session,
    require_session,
    verify_password,
)
from backend.config import settings
from backend.database import get_db
from backend.schemas.auth import LoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])
_failed_logins: dict[str, list[float]] = {}
_MAX_FAILURES = 5
_FAILURE_WINDOW_SECONDS = 300


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
):
    if not settings.admin_password_hash:
        raise HTTPException(status_code=503, detail="Admin authentication is not configured.")
    client_key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    recent_failures = [stamp for stamp in _failed_logins.get(client_key, []) if now - stamp < _FAILURE_WINDOW_SECONDS]
    _failed_logins[client_key] = recent_failures
    if len(recent_failures) >= _MAX_FAILURES:
        await audit(db, actor=body.username[:128], action="login", result="rate_limited")
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    if body.username != settings.admin_username or not verify_password(body.password, settings.admin_password_hash):
        recent_failures.append(now)
        _failed_logins[client_key] = recent_failures
        await audit(db, actor=body.username[:128], action="login", result="failure", detail="Invalid credentials")
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    _failed_logins.pop(client_key, None)

    session_token, csrf_token, expires = await create_session(db, settings.admin_username)
    await audit(db, actor=settings.admin_username, action="login", result="success")
    cookie_kwargs = {
        "secure": settings.admin_secure_cookies,
        "httponly": True,
        "samesite": "lax",
        "max_age": settings.admin_session_ttl_seconds,
    }
    response.set_cookie(SESSION_COOKIE, session_token, **cookie_kwargs)
    response.set_cookie(CSRF_COOKIE, csrf_token, secure=settings.admin_secure_cookies, httponly=False, samesite="lax", max_age=settings.admin_session_ttl_seconds)
    return {"authenticated": True, "username": settings.admin_username, "expires_at": expires.isoformat()}


@router.get("/me")
async def me(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
):
    session = await require_session(request, db)
    return {"authenticated": True, "username": session["username"], "expires_at": session["expires_at"]}


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: aiosqlite.Connection = Depends(get_db),
):
    session = await require_session(request, db)
    await db.execute("UPDATE admin_sessions SET revoked_at = datetime('now') WHERE id = ?", (session["id"],))
    await db.commit()
    await audit(db, actor=session["username"], action="logout", result="success")
    response.delete_cookie(SESSION_COOKIE)
    response.delete_cookie(CSRF_COOKIE)
    return {"authenticated": False}
