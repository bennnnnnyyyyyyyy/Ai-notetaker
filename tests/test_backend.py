import pytest
import aiosqlite
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.main import app
from backend.config import settings
from backend.auth import create_session, get_session, hash_password
from backend.database import _DDL
from backend.schemas.meeting import MeetingCreate
from backend.adapters.google_sheets import build_export_row
import backend.routers.integrations as integrations


@pytest.fixture
def admin_client(monkeypatch):
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password_hash", hash_password("correct-password"))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "correct-password"},
        )
        assert response.status_code == 200
        yield client


def test_health_and_readiness_endpoints(admin_client):
    assert admin_client.get("/health").json() == {"status": "ok"}
    response = admin_client.get("/api/v1/system/readiness")
    assert response.status_code == 200
    assert set(response.json()["checks"]) == {
        "python", "playwright_chromium", "ffmpeg", "browser_profile", "audio"
    }
    readiness_text = response.text
    assert "resolved_path" not in readiness_text
    assert "profile_dir" not in readiness_text
    assert "audio_devices" not in readiness_text


def test_sensitive_routes_require_authentication(monkeypatch):
    monkeypatch.setattr(settings, "admin_password_hash", hash_password("correct-password"))
    with TestClient(app) as client:
        assert client.get("/api/v1/meetings").status_code == 401
        assert client.get("/api/v1/system/readiness").status_code == 401


def test_invalid_credentials_and_private_files_are_rejected(monkeypatch):
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password_hash", hash_password("correct-password"))
    with TestClient(app) as client:
        assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
        assert client.get("/data/app.db").status_code == 404


@pytest.mark.asyncio
async def test_expired_server_session_is_rejected():
    async with aiosqlite.connect(":memory:") as db:
        db.row_factory = aiosqlite.Row
        await db.executescript(_DDL)
        token, _, _ = await create_session(db, "admin")
        await db.execute("UPDATE admin_sessions SET expires_at = ?", ("2000-01-01T00:00:00+00:00",))
        await db.commit()
        assert await get_session(db, token) is None


def test_login_csrf_and_logout(admin_client):
    csrf_cookie = admin_client.cookies.get("ai_admin_csrf")
    assert csrf_cookie
    response = admin_client.post("/api/v1/campaigns", json={
        "name": "Invalid", "config_path": "..\\secrets.yaml", "config_version": "1.0"
    })
    assert response.status_code == 403
    response = admin_client.post(
        "/api/v1/campaigns",
        headers={"X-CSRF-Token": csrf_cookie},
        json={"name": "Invalid", "config_path": "..\\secrets.yaml", "config_version": "1.0"},
    )
    assert response.status_code == 422
    assert admin_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf_cookie}).status_code == 200
    assert admin_client.get("/api/v1/meetings").status_code == 401


def test_secure_cookie_attribute_is_emitted_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password_hash", hash_password("correct-password"))
    monkeypatch.setattr(settings, "admin_secure_cookies", True)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "correct-password"},
        )
    cookies = response.headers.get_list("set-cookie")
    assert any("ai_admin_session=" in value and "Secure" in value and "HttpOnly" in value for value in cookies)
    assert any("ai_admin_csrf=" in value and "Secure" in value and "HttpOnly" not in value for value in cookies)


def test_public_security_configuration_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "app_host", "0.0.0.0")
    monkeypatch.setattr(settings, "app_public", True)
    monkeypatch.setattr(settings, "app_https", False)
    monkeypatch.setattr(settings, "admin_secure_cookies", False)
    with pytest.raises(RuntimeError, match="Public deployment requires"):
        settings.validate_security_config()


def test_meeting_url_requires_https_google_meet():
    meeting = MeetingCreate(
        url="https://meet.google.com/abc-defg-hij",
        meeting_type="discovery",
    )
    assert str(meeting.url) == "https://meet.google.com/abc-defg-hij"

    with pytest.raises(ValidationError):
        MeetingCreate(url="https://example.com/meeting", meeting_type="discovery")


def test_campaign_creation_rejects_paths_outside_bundle(admin_client):
    csrf_cookie = admin_client.cookies.get("ai_admin_csrf")
    response = admin_client.post(
        "/api/v1/campaigns",
        headers={"X-CSRF-Token": csrf_cookie},
        json={
            "name": "Invalid",
            "config_path": "..\\secrets.yaml",
            "config_version": "1.0",
        },
    )
    assert response.status_code == 422


def test_google_sheets_status_is_explicitly_unconfigured(monkeypatch, admin_client):
    monkeypatch.setattr(settings, "google_sheets_spreadsheet_id", "")
    response = admin_client.get("/api/v1/integrations/google-sheets/status")
    assert response.status_code == 200
    assert response.json()["status"] == "needs_setup"


def test_google_sheets_ai_row_has_requested_columns():
    row = build_export_row(
        {
            "scheduled_at": "2026-10-26T21:00:00+00:00",
            "campaign_name": "Prime Ad DME Lead Generation",
            "opener_name": "Jane",
            "closer_name": "Daniel",
            "status": "completed",
        },
        {
            "prospect_profile": {"name": "Ahmed", "company": "Example DME"},
            "outcome": "Interested — no confirmed next meeting",
            "executive_summary": "Prospect discussed lead quality and next steps.",
        },
    )
    assert row == [
        "2026-10-26T21:00:00+00:00",
        "Prime Ad DME Lead Generation",
        "Ahmed",
        "Example DME",
        "Jane",
        "Daniel",
        "Interested — no confirmed next meeting",
        "Prospect discussed lead quality and next steps.",
    ]


def test_bd_meetings_read_only_preview_and_calendar_link_is_not_importable(admin_client, monkeypatch):
    sample = {
        "source_row": 2,
        "client_name": "Alex",
        "company_name": "Example Co",
        "campaign_label": "CGM",
        "opener_name": "Jane",
        "meeting_time": "2026-10-28T10:00:00+00:00",
        "calendar_url": "https://calendar.google.com/calendar/u/0/r/eventedit/abc",
        "meet_url": "",
    }
    monkeypatch.setattr(integrations, "list_bookings", lambda limit=200: [sample])
    monkeypatch.setattr(integrations, "get_booking", lambda source_row: sample)
    status = admin_client.get("/api/v1/integrations/bd-meetings/status")
    assert status.status_code == 200
    bookings = admin_client.get("/api/v1/integrations/bd-meetings/bookings?limit=1")
    assert bookings.status_code == 200
    row = bookings.json()["bookings"][0]
    assert row["calendar_url"].startswith("https://calendar.google.com/")
    assert row["meet_url"] == ""
    csrf = admin_client.cookies.get("ai_admin_csrf")
    response = admin_client.post(
        f"/api/v1/integrations/bd-meetings/bookings/{row['source_row']}/import",
        headers={"X-CSRF-Token": csrf},
        json={"confirm": False},
    )
    assert response.status_code == 409
