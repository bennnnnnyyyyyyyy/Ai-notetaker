"""Read-only adapter for the shared BD Meetings Google Sheet."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backend.adapters.google_calendar import is_valid_meet_url
from backend.config import settings

_HYPERLINK_RE = re.compile(r'HYPERLINK\("([^" ]+)', re.IGNORECASE)
_CALENDAR_PREFIX = "https://calendar.google.com/"


class BDMeetingsSetupError(RuntimeError):
    pass


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _links(value: Any) -> tuple[str, str]:
    text = _cell_text(value)
    match = _HYPERLINK_RE.search(text)
    url = match.group(1) if match else (text if text.startswith("http") else "")
    return (
        url if is_valid_meet_url(url) else "",
        url if url.startswith(_CALENDAR_PREFIX) else "",
    )


def _credentials():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise BDMeetingsSetupError("Google Sheets libraries are not installed.") from exc

    credentials_path = settings.resolve_bd_meetings_credentials_path()
    token_path = Path(settings.bd_meetings_token_path)
    if not credentials_path.is_file():
        raise BDMeetingsSetupError("BD Google Sheet OAuth credentials are not configured.")
    if not token_path.is_file():
        raise BDMeetingsSetupError("Authorize read-only BD Sheet access with scripts/google_bd_sheets_auth.py.")

    scope = "https://www.googleapis.com/auth/spreadsheets.readonly"
    creds = Credentials.from_authorized_user_file(str(token_path), [scope])
    if not creds.has_scopes([scope]):
        raise BDMeetingsSetupError("The BD Sheet token lacks read-only Sheets permission; reauthorize this PC.")
    if creds.expired:
        if not creds.refresh_token:
            raise BDMeetingsSetupError("BD Google Sheet authorization has expired; reauthorize this PC.")
        try:
            creds.refresh(Request())
        except Exception as exc:
            raise BDMeetingsSetupError("BD Google Sheet authorization could not be refreshed.") from exc
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _load_rows() -> list[dict[str, Any]]:
    if not settings.bd_meetings_spreadsheet_id:
        raise BDMeetingsSetupError("Set BD_MEETINGS_SPREADSHEET_ID in .env.")
    try:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ImportError as exc:
        raise BDMeetingsSetupError("Google Sheets libraries are not installed.") from exc

    try:
        service = build("sheets", "v4", credentials=_credentials(), cache_discovery=False)
        result = service.spreadsheets().values().get(
            spreadsheetId=settings.bd_meetings_spreadsheet_id,
            range=f"{settings.bd_meetings_worksheet}!A:Z",
            valueRenderOption="FORMULA",
        ).execute()
    except HttpError as exc:
        status = getattr(exc.resp, "status", 502)
        if status in {401, 403}:
            raise BDMeetingsSetupError("Access to the shared BD Google Sheet was denied or expired.") from exc
        if status == 404:
            raise BDMeetingsSetupError("The configured BD Google Sheet or worksheet was not found.") from exc
        raise BDMeetingsSetupError("The BD Google Sheet could not be read.") from exc
    except BDMeetingsSetupError:
        raise
    except Exception as exc:
        raise BDMeetingsSetupError("The BD Google Sheet could not be read.") from exc

    values = result.get("values", [])
    if not values:
        return []
    headers = [_cell_text(value).lower() for value in values[0]]
    positions = {header: index for index, header in enumerate(headers) if header}

    def value(row: list[Any], header: str) -> Any:
        index = positions.get(header)
        return row[index] if index is not None and index < len(row) else None

    result_rows = []
    for row_number, row in enumerate(values[1:], start=2):
        company = _cell_text(value(row, "company name"))
        contact = _cell_text(value(row, "authorized person"))
        email = _cell_text(value(row, "email"))
        if not any((company, contact, email)):
            continue
        meeting_value = value(row, "meeting time")
        meet_url, calendar_url = _links(meeting_value)
        result_rows.append({
            "source_row": row_number,
            "campaign_label": _cell_text(value(row, "sub")),
            "opener_name": _cell_text(value(row, "opener")),
            "source_status": _cell_text(value(row, "status")),
            "date_added": _cell_text(value(row, "date added")),
            "company_name": company,
            "client_name": contact,
            "email": email,
            "meeting_time": _cell_text(meeting_value),
            "opener_summary": _cell_text(value(row, "opener summary")),
            "closer_notes": _cell_text(value(row, "closer's notes")),
            "calendar_url": calendar_url,
            "meet_url": meet_url,
            "ready_to_import": bool(meet_url or calendar_url),
        })
    return result_rows


def get_status() -> dict[str, Any]:
    credentials_path = settings.resolve_bd_meetings_credentials_path()
    token_path = Path(settings.bd_meetings_token_path)
    configured = bool(settings.bd_meetings_spreadsheet_id)
    ready = configured and credentials_path.is_file() and token_path.is_file()
    return {
        "status": "ready" if ready else "needs_setup",
        "source": "google_sheets",
        "spreadsheet_id_configured": configured,
        "credentials_found": credentials_path.is_file(),
        "token_found": token_path.is_file(),
        "worksheet": settings.bd_meetings_worksheet,
        "detail": "Read-only shared BD Google Sheet is configured." if ready else "Authorize the shared BD Google Sheet with scripts/google_bd_sheets_auth.py.",
    }


def list_bookings(limit: int = 200) -> list[dict[str, Any]]:
    return _load_rows()[: max(1, min(limit, 500))]


def get_booking(source_row: int) -> dict[str, Any] | None:
    return next((row for row in _load_rows() if row["source_row"] == source_row), None)


def campaign_mapping(label: str) -> dict[str, Any]:
    """Map only exact, unambiguous labels; unknown labels require review."""
    normalized = " ".join((label or "").upper().replace("+", " + ").split())
    if normalized == "CGM":
        return {"status": "mapped", "campaign_id": "cgm_patient_acquisition"}
    if normalized == "ROOFING":
        return {"status": "mapped", "campaign_id": "roofing_appointment_setting"}
    if normalized in {"ORT", "ORT + CGM"}:
        return {"status": "mapped", "campaign_id": "dme_lead_generation"}
    return {"status": "needs_selection", "campaign_id": None}
