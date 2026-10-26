"""Controlled Google Sheets export using a local service account or OAuth."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from backend.config import settings

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class GoogleSheetsSetupError(RuntimeError):
    """Raised when local Google Sheets setup is incomplete."""


def get_status() -> dict[str, Any]:
    service_account_path = Path(settings.google_sheets_service_account_path)
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
    elif service_account_path.is_file():
        detail = "Service account configured; share the target Sheet with its service-account email."
    elif not credentials_path.is_file():
        detail = f"Place a service-account JSON at {service_account_path}, or OAuth credentials at {credentials_path}."
    elif not token_path.is_file():
        detail = "Run scripts/google_sheets_auth.py once to authorize this PC."
    else:
        detail = "Google Sheets export is configured and authorized."

    service_account_found = service_account_path.is_file()
    oauth_ready = credentials_path.is_file() and token_path.is_file()
    ready = libraries_ready and configured and (service_account_found or oauth_ready)
    return {
        "status": "ready" if ready else "needs_setup",
        "libraries_ready": libraries_ready,
        "spreadsheet_id_configured": configured,
        "service_account_path": str(service_account_path),
        "service_account_found": service_account_found,
        "credentials_path": str(credentials_path),
        "credentials_found": credentials_path.is_file(),
        "token_path": str(token_path),
        "token_found": token_path.is_file(),
        "worksheet": settings.google_sheets_worksheet,
        "detail": detail,
    }


def _credentials():
    service_account_path = Path(settings.google_sheets_service_account_path)
    if service_account_path.is_file():
        try:
            from google.oauth2 import service_account
        except ImportError as exc:
            raise GoogleSheetsSetupError("Google Sheets libraries are not installed.") from exc
        return service_account.Credentials.from_service_account_file(
            str(service_account_path), scopes=SCOPES
        )

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
    """Build the compact human-facing AI worksheet row.

    The AI tab is intentionally a summary view. Detailed evidence remains in
    the local report and transcript rather than being copied into Sheets.
    """
    report = report or {}
    profile = report.get("prospect_profile") or {}
    campaign = (
        meeting.get("campaign_name")
        or report.get("campaign_name")
        or meeting.get("campaign_id")
        or "Generalized"
    )
    date = meeting.get("scheduled_at") or meeting.get("created_at") or ""
    summary = report.get("executive_summary") or report.get("crm_ready_notes") or ""
    return [
        str(date),
        str(campaign),
        str(profile.get("name") or ""),
        str(profile.get("company") or ""),
        str(meeting.get("opener_name") or ""),
        str(meeting.get("closer_name") or ""),
        str(report.get("outcome") or meeting.get("status") or ""),
        str(summary),
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
            range=f"{settings.google_sheets_worksheet}!A:H",
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
