"""Single-admin authentication, server-side sessions, CSRF, and audit helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import aiosqlite
from fastapi import HTTPException, Request

from backend.config import settings

SESSION_COOKIE = "ai_admin_session"
CSRF_COOKIE = "ai_admin_csrf"
PBKDF2_ITERATIONS = 600_000


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode().rstrip("="),
        base64.urlsafe_b64encode(digest).decode().rstrip("="),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        def decode(value: str) -> bytes:
            return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

        salt = decode(salt_text)
        expected = decode(digest_text)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_session(db: aiosqlite.Connection, username: str) -> tuple[str, str, datetime]:
    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    now = utc_now()
    expires = now + timedelta(seconds=settings.admin_session_ttl_seconds)
    await db.execute(
        """
        INSERT INTO admin_sessions
            (id, token_hash, csrf_hash, username, created_at, expires_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()), _token_hash(session_token), _token_hash(csrf_token),
            username, now.isoformat(), expires.isoformat(), now.isoformat(),
        ),
    )
    await db.commit()
    return session_token, csrf_token, expires


async def get_session(db: aiosqlite.Connection, token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    async with db.execute(
        "SELECT * FROM admin_sessions WHERE token_hash = ? AND revoked_at IS NULL",
        (_token_hash(token),),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    session = dict(row)
    try:
        expires = datetime.fromisoformat(session["expires_at"])
    except ValueError:
        return None
    if expires <= utc_now():
        return None
    return session


async def require_session(request: Request, db: aiosqlite.Connection) -> dict[str, Any]:
    if not settings.admin_password_hash:
        raise HTTPException(status_code=503, detail="Admin authentication is not configured.")
    session = await get_session(db, request.cookies.get(SESSION_COOKIE))
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return session


async def validate_csrf(request: Request, session: dict[str, Any]) -> bool:
    supplied = request.headers.get("X-CSRF-Token")
    if not supplied:
        return False
    return hmac.compare_digest(_token_hash(supplied), session["csrf_hash"])


async def audit(
    db: aiosqlite.Connection,
    *,
    actor: str | None,
    action: str,
    result: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: str | None = None,
) -> None:
    await db.execute(
        """
        INSERT INTO audit_events (id, actor, action, result, resource_type, resource_id, detail)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), actor, action, result, resource_type, resource_id, detail),
    )
    await db.commit()
