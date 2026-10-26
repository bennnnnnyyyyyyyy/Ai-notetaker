import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.main import app
from backend.config import settings
from backend.schemas.meeting import MeetingCreate


def test_health_and_readiness_endpoints():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        response = client.get("/api/v1/system/readiness")
        assert response.status_code == 200
        assert set(response.json()["checks"]) == {
            "python", "playwright_chromium", "ffmpeg", "browser_profile", "audio"
        }


def test_meeting_url_requires_https_google_meet():
    meeting = MeetingCreate(
        url="https://meet.google.com/abc-defg-hij",
        meeting_type="discovery",
    )
    assert str(meeting.url) == "https://meet.google.com/abc-defg-hij"

    with pytest.raises(ValidationError):
        MeetingCreate(url="https://example.com/meeting", meeting_type="discovery")


def test_campaign_creation_rejects_paths_outside_bundle():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/campaigns",
            json={
                "name": "Invalid",
                "config_path": "..\\secrets.yaml",
                "config_version": "1.0",
            },
        )
    assert response.status_code == 422


def test_google_sheets_status_is_explicitly_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "google_sheets_spreadsheet_id", "")
    with TestClient(app) as client:
        response = client.get("/api/v1/integrations/google-sheets/status")
    assert response.status_code == 200
    assert response.json()["status"] == "needs_setup"
