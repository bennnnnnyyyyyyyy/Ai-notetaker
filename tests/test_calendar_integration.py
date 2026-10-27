import base64

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from backend.adapters.bd_meetings import campaign_mapping
from backend.adapters.google_calendar import (
    CalendarEventError,
    is_valid_meet_url,
    normalize_calendar_event,
    parse_calendar_reference,
)
from backend.adapters.playwright_capture import browser_launch_args
from backend.auth import hash_password
from backend.config import settings
from backend.database import _DDL
from backend.main import app
import backend.routers.integrations as integrations


def _calendar_url(event_id="event-123", calendar_id="calendar@example.com"):
    token = base64.urlsafe_b64encode(f"{event_id} {calendar_id}".encode()).decode().rstrip("=")
    return f"https://calendar.google.com/calendar/u/0/r/eventedit/{token}"


def _booking(label="CGM"):
    return {
        "source_row": 12,
        "campaign_label": label,
        "opener_name": "Jane",
        "company_name": "Example Co",
        "client_name": "Alex",
        "calendar_url": _calendar_url(),
        "meet_url": "",
        "meeting_time": "2026-10-28T10:00:00+00:00",
        "opener_summary": "Needs qualified leads",
        "closer_notes": "",
    }


def _event(**overrides):
    value = {
        "calendar_id": "calendar@example.com",
        "event_id": "event-123",
        "status": "confirmed",
        "summary": "Example meeting",
        "start": "2026-10-28T10:00:00+00:00",
        "end": "2026-10-28T11:00:00+00:00",
        "meet_url": "https://meet.google.com/abc-defg-hij",
    }
    value.update(overrides)
    return value


def test_capture_launch_args_do_not_grant_media_permissions():
    args = browser_launch_args()
    assert "--use-fake-ui-for-media-stream" not in args
    assert "--autoplay-policy=no-user-gesture-required" in args


def test_calendar_reference_requires_google_event_url_and_decodes_eventedit():
    assert parse_calendar_reference(_calendar_url()) == ("calendar@example.com", "event-123")
    with pytest.raises(CalendarEventError):
        parse_calendar_reference("https://example.com/eventedit/not-calendar")
    with pytest.raises(CalendarEventError):
        parse_calendar_reference("https://calendar.google.com/calendar/u/0/r")


def test_meet_url_validation_accepts_only_real_https_meet_urls():
    assert is_valid_meet_url("https://meet.google.com/abc-defg-hij")
    assert not is_valid_meet_url("http://meet.google.com/abc-defg-hij")
    assert not is_valid_meet_url("https://example.com/abc-defg-hij")
    assert not is_valid_meet_url("https://meet.google.com/")


def test_calendar_event_meet_link_is_optional_and_never_guessed():
    with_link = normalize_calendar_event({"id": "1", "conferenceData": {"entryPoints": [{"entryPointType": "video", "uri": "https://meet.google.com/abc-defg-hij"}]}}, "cal")
    without_link = normalize_calendar_event({"id": "2", "htmlLink": "https://calendar.google.com/calendar/event?eid=x"}, "cal")
    assert with_link["meet_url"] == "https://meet.google.com/abc-defg-hij"
    assert without_link["meet_url"] is None


def test_campaign_mapping_requires_review_for_unknown_labels():
    assert campaign_mapping("CGM") == {"status": "mapped", "campaign_id": "cgm_patient_acquisition"}
    assert campaign_mapping("Roofing") == {"status": "mapped", "campaign_id": "roofing_appointment_setting"}
    assert campaign_mapping("ORT+CGM") == {"status": "mapped", "campaign_id": "dme_lead_generation"}
    assert campaign_mapping("Something else")["status"] == "needs_selection"


@pytest.fixture
def calendar_client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_path", tmp_path / "calendar-test.db")
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password_hash", hash_password("correct-password"))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "correct-password"},
        )
        assert response.status_code == 200
        yield client


def test_calendar_api_requires_authentication(calendar_client):
    calendar_client.cookies.clear()
    response = calendar_client.get("/api/v1/integrations/bd-meetings/bookings/12/resolve")
    assert response.status_code == 401


def test_resolve_import_confirmation_and_duplicate_protection(calendar_client, monkeypatch):
    monkeypatch.setattr(integrations, "get_booking", lambda source_row: _booking())
    monkeypatch.setattr(integrations, "get_calendar_event", lambda calendar_id, event_id: _event())
    csrf = calendar_client.cookies.get("ai_admin_csrf")
    headers = {"X-CSRF-Token": csrf}

    preview = calendar_client.get("/api/v1/integrations/bd-meetings/bookings/12/resolve")
    assert preview.status_code == 200
    assert preview.json()["event"]["meet_url"] == "https://meet.google.com/abc-defg-hij"
    assert preview.json()["capture_started"] is False

    no_confirmation = calendar_client.post(
        "/api/v1/integrations/bd-meetings/bookings/12/import",
        headers=headers,
        json={"confirm": False},
    )
    assert no_confirmation.status_code == 409

    imported = calendar_client.post(
        "/api/v1/integrations/bd-meetings/bookings/12/import",
        headers=headers,
        json={"confirm": True},
    )
    assert imported.status_code == 201
    assert imported.json()["capture_started"] is False

    duplicate = calendar_client.post(
        "/api/v1/integrations/bd-meetings/bookings/12/import",
        headers=headers,
        json={"confirm": True},
    )
    assert duplicate.status_code == 409

    async def check_db():
        async with aiosqlite.connect(settings.database_path) as db:
            row = await (await db.execute("SELECT url, status, calendar_event_id FROM meetings")).fetchone()
            return row

    row = __import__("asyncio").run(check_db())
    assert row == ("https://meet.google.com/abc-defg-hij", "pending", "event-123")


@pytest.mark.parametrize(
    ("event", "status", "message"),
    [
        (_event(meet_url=None), 409, "no valid Google Meet"),
        (_event(status="cancelled"), 409, "cancelled"),
    ],
)
def test_calendar_event_safety_states(calendar_client, monkeypatch, event, status, message):
    monkeypatch.setattr(integrations, "get_booking", lambda source_row: _booking())
    monkeypatch.setattr(integrations, "get_calendar_event", lambda calendar_id, event_id: event)
    response = calendar_client.get("/api/v1/integrations/bd-meetings/bookings/12/resolve")
    assert response.status_code == status
    assert message in response.json()["detail"]


def test_calendar_access_error_is_sanitized(calendar_client, monkeypatch):
    monkeypatch.setattr(integrations, "get_booking", lambda source_row: _booking())
    monkeypatch.setattr(
        integrations,
        "get_calendar_event",
        lambda calendar_id, event_id: (_ for _ in ()).throw(CalendarEventError("access denied", 403)),
    )
    response = calendar_client.get("/api/v1/integrations/bd-meetings/bookings/12/resolve")
    assert response.status_code == 403
    assert response.json()["detail"] == "access denied"
