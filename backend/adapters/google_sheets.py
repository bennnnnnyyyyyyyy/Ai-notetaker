"""Controlled Google Sheets export using a local OAuth desktop credential."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

from backend.config import settings

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class GoogleSheetsSetupError(RuntimeError):
    """Raised when local Google Sheets setup is incomplete."""


def get_status() -> dict[str, Any]:
    credentials_path = Path(settings.google_sheets_credentials_path)
    token_path = Path(settings.google_sheets_token_path)
    try:
        import googleapiclient  # noqa: F401
        libraries_ready = True
    except ImportError:
        libraries_ready = False

    configured = bool(settings.google_sheets_spreadsheet_id)
    if not libraries_ready:
        detail = "Install the Google Sheets dependencies from requirements.txt."
    elif not configured:
        detail = "Set GOOGLE_SHEETS_SPREADSHEET_ID in .env."
    elif not credentials_path.is_file():
        detail = f"Place OAuth desktop credentials at {credentials_path}."
    elif not token_path.is_file():
        detail = "Run scripts/google_sheets_auth.py once to authorize this PC."
    else:
        detail = "Google Sheets export is configured and authorized."

    ready = libraries_ready and configured and credentials_path.is_file() and token_path.is_file()
    return {
        "status": "ready" if ready else "needs_setup",
        "libraries_ready": libraries_ready,
        "spreadsheet_id_configured": configured,
        "credentials_path": str(credentials_path),
        "credentials_found": credentials_path.is_file(),
        "token_path": str(token_path),
        "token_found": token_path.is_file(),
        "worksheet": settings.google_sheets_worksheet,
        "detail": detail,
    }


def _credentials():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise GoogleSheetsSetupError("Google Sheets libraries are not installed.") from exc

    token_path = Path(settings.google_sheets_token_path)
    credentials_path = Path(settings.google_sheets_credentials_path)
    if not token_path.is_file():
        raise GoogleSheetsSetupError(
            "Google Sheets is not authorized. Run scripts/google_sheets_auth.py interactively."
        )
    if not credentials_path.is_file():
        raise GoogleSheetsSetupError(f"Missing OAuth credentials: {credentials_path}")

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds
    raise GoogleSheetsSetupError("Google Sheets authorization expired; run scripts/google_sheets_auth.py again.")


def build_export_row(meeting: dict[str, Any], report: dict[str, Any] | None = None) -> list[str]:
    report = report or {}
    profile = report.get("prospect_profile") or {}
    return [
        datetime.now(timezone.utc).isoformat(),
        str(meeting.get("id", "")),
        str(meeting.get("created_at", "")),
        str(meeting.get("status", "")),
        str(meeting.get("meeting_type", "")),
        str(meeting.get("url", "")),
        str(meeting.get("campaign_id") or ""),
        str(meeting.get("opener_name") or ""),
        str(meeting.get("closer_name") or ""),
        str(profile.get("name") or ""),
        str(profile.get("company") or ""),
        str(report.get("qualification_status") or ""),
        str(report.get("outcome") or ""),
        str(report.get("pipeline_stage") or ""),
        str(report.get("executive_summary") or ""),
        str(meeting.get("error_message") or ""),
    ]


def export_row(row: list[str]) -> dict[str, Any]:
    if not settings.google_sheets_spreadsheet_id:
        raise GoogleSheetsSetupError("Set GOOGLE_SHEETS_SPREADSHEET_ID in .env first.")
    creds = _credentials()
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise GoogleSheetsSetupError("Google Sheets libraries are not installed.") from exc

    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return (
        service.spreadsheets().values().append(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{settings.google_sheets_worksheet}!A:P",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute().get("updates", {})
    )


def load_report_file(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
