"""Read-only Google Calendar access for resolving shared-sheet event references."""

from __future__ import annotations

import base64
import binascii
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from backend.config import settings

CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"


class CalendarSetupError(RuntimeError):
    pass


class CalendarEventError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def is_valid_meet_url(value: str | None) -> bool:
    parsed = urlsplit(value or "")
    return parsed.scheme == "https" and parsed.hostname == "meet.google.com" and bool(parsed.path.strip("/"))


def _decode_event_reference(token: str) -> tuple[str, str]:
    try:
        decoded = base64.urlsafe_b64decode(token + "===").decode("utf-8")
    except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise CalendarEventError("The Calendar event reference is invalid.", 422) from exc
    parts = decoded.split(" ", 1)
    if len(parts) != 2 or not all(parts):
        raise CalendarEventError("The Calendar event reference is incomplete.", 422)
    return parts[1], parts[0]


def parse_calendar_reference(calendar_url: str) -> tuple[str, str]:
    """Extract calendar ID and event ID from a Google Calendar event URL only."""
    parsed = urlsplit(calendar_url)
    if parsed.scheme != "https" or parsed.hostname != "calendar.google.com":
        raise CalendarEventError("The booking does not contain a valid Google Calendar URL.", 422)

    query_eid = parse_qs(parsed.query).get("eid", [])
    if query_eid:
        return _decode_event_reference(query_eid[0])

    path_parts = [part for part in parsed.path.split("/") if part]
    if path_parts and path_parts[-2:-1] == ["eventedit"]:
        return _decode_event_reference(path_parts[-1])
    raise CalendarEventError("The Calendar event URL format is not supported.", 422)


def _credentials():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise CalendarSetupError("Google Calendar libraries are not installed.") from exc

    credentials_path = settings.resolve_google_calendar_credentials_path()
    token_path = Path(settings.google_calendar_token_path)
    if not credentials_path.is_file():
        raise CalendarSetupError("Google Calendar OAuth credentials are not configured.")
    if not token_path.is_file():
        raise CalendarSetupError(
            "Google Calendar read-only authorization is required; run scripts/google_calendar_auth.py."
        )

    creds = Credentials.from_authorized_user_file(str(token_path), [CALENDAR_READONLY_SCOPE])
    if not creds.has_scopes([CALENDAR_READONLY_SCOPE]):
        raise CalendarSetupError(
            "The saved Google token lacks Calendar read-only permission; run scripts/google_calendar_auth.py."
        )
    if creds.expired:
        if not creds.refresh_token:
            raise CalendarSetupError("Google Calendar authorization has expired; reauthorize this PC.")
        try:
            creds.refresh(Request())
        except Exception as exc:
            raise CalendarSetupError("Google Calendar authorization could not be refreshed.") from exc
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _meet_url(event: dict[str, Any]) -> str | None:
    candidates: list[str] = []
    conference = event.get("conferenceData") or {}
    for entry in conference.get("entryPoints", []) or []:
        if entry.get("entryPointType") == "video":
            candidates.append(entry.get("uri", ""))
    candidates.append(event.get("hangoutLink", ""))
    for candidate in candidates:
        if is_valid_meet_url(candidate):
            return candidate
    return None


def normalize_calendar_event(event: dict[str, Any], calendar_id: str) -> dict[str, Any]:
    """Return only safe event fields needed by the operator import flow."""
    return {
        "calendar_id": calendar_id,
        "event_id": event.get("id"),
        "status": event.get("status", "confirmed"),
        "summary": event.get("summary") or "Untitled event",
        "start": (event.get("start") or {}).get("dateTime") or (event.get("start") or {}).get("date"),
        "end": (event.get("end") or {}).get("dateTime") or (event.get("end") or {}).get("date"),
        "meet_url": _meet_url(event),
    }


def get_calendar_event(calendar_id: str, event_id: str) -> dict[str, Any]:
    """Fetch one event using Calendar API events.get; never follows the edit URL."""
    try:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ImportError as exc:
        raise CalendarSetupError("Google Calendar libraries are not installed.") from exc

    try:
        service = build("calendar", "v3", credentials=_credentials(), cache_discovery=False)
        event = service.events().get(
            calendarId=calendar_id,
            eventId=event_id,
            fields="id,status,summary,start,end,hangoutLink,conferenceData(entryPoints(entryPointType,uri))",
        ).execute()
    except HttpError as exc:
        status = getattr(exc.resp, "status", 502)
        if status in {401, 403}:
            raise CalendarEventError("Google Calendar access was denied or has expired.", 403) from exc
        if status in {404, 410}:
            raise CalendarEventError("The Calendar event is unavailable or no longer exists.", 404) from exc
        raise CalendarEventError("Google Calendar could not retrieve this event.", 502) from exc
    except CalendarSetupError:
        raise
    except Exception as exc:
        raise CalendarEventError("Google Calendar could not retrieve this event.", 502) from exc

    return normalize_calendar_event(event, calendar_id)
