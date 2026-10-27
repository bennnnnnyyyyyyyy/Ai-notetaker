import asyncio
import sqlite3
import uuid

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException

from backend.adapters.google_sheets import (
    GoogleSheetsSetupError,
    build_export_row,
    export_row,
    get_status,
    load_report_file,
)
from backend.database import get_db
from backend.auth import public_error_message
from backend.adapters.bd_meetings import (
    BDMeetingsSetupError,
    campaign_mapping,
    get_status as get_bd_status,
    get_booking,
    list_bookings,
)
from backend.adapters.google_calendar import (
    CalendarEventError,
    CalendarSetupError,
    get_calendar_event,
    parse_calendar_reference,
)
from backend.schemas.integrations import BookingImportRequest

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/bd-meetings/status")
async def bd_meetings_status():
    return get_bd_status()


@router.get("/bd-meetings/bookings")
async def bd_meetings_bookings(limit: int = 200):
    try:
        return {"bookings": await asyncio.to_thread(list_bookings, limit)}
    except BDMeetingsSetupError as exc:
        raise HTTPException(status_code=503, detail=public_error_message(exc, "BD Meetings source is not available.")) from exc


async def _load_booking(source_row: int) -> dict:
    try:
        booking = await asyncio.to_thread(get_booking, source_row)
    except BDMeetingsSetupError as exc:
        raise HTTPException(status_code=503, detail=public_error_message(exc, "BD Meetings source is not available.")) from exc
    if not booking:
        raise HTTPException(status_code=404, detail="BD Meetings booking row not found")
    return booking


async def _resolve_booking(source_row: int, db: aiosqlite.Connection) -> tuple[dict, dict, dict]:
    booking = await _load_booking(source_row)
    if booking["meet_url"]:
        event = {
            "calendar_id": "bd-google-sheet",
            "event_id": f"row-{source_row}",
            "status": "confirmed",
            "summary": booking["company_name"] or "BD Meetings booking",
            "start": booking["meeting_time"] or None,
            "end": None,
            "meet_url": booking["meet_url"],
        }
    else:
        if not booking["calendar_url"]:
            raise HTTPException(status_code=409, detail="This booking has no Google Calendar event URL to resolve.")
        try:
            calendar_id, event_id = parse_calendar_reference(booking["calendar_url"])
            event = await asyncio.to_thread(get_calendar_event, calendar_id, event_id)
        except (CalendarSetupError, CalendarEventError) as exc:
            raise HTTPException(status_code=getattr(exc, "status_code", 503), detail=str(exc)) from exc
    if event["status"] == "cancelled":
        raise HTTPException(status_code=409, detail="This Google Calendar event is cancelled.")
    if not event["meet_url"]:
        raise HTTPException(status_code=409, detail="This Calendar event has no valid Google Meet video link.")

    mapping = campaign_mapping(booking["campaign_label"])
    async with db.execute("SELECT id, name FROM campaigns WHERE active = 1 ORDER BY name") as cur:
        campaigns = [dict(row) for row in await cur.fetchall()]
    active_ids = {campaign["id"] for campaign in campaigns}
    if mapping["status"] == "mapped" and mapping["campaign_id"] not in active_ids:
        mapping = {"status": "needs_selection", "campaign_id": None}
    mapping["options"] = campaigns
    return booking, event, mapping


@router.get("/bd-meetings/bookings/{source_row}/resolve")
async def resolve_bd_booking(source_row: int, db: aiosqlite.Connection = Depends(get_db)):
    booking, event, mapping = await _resolve_booking(source_row, db)
    return {
        "status": "resolved",
        "source_row": source_row,
        "booking": {
            "client_name": booking["client_name"],
            "company_name": booking["company_name"],
            "campaign_label": booking["campaign_label"],
            "opener_name": booking["opener_name"],
        },
        "event": event,
        "campaign": mapping,
        "capture_started": False,
    }


@router.post("/bd-meetings/bookings/{source_row}/import", status_code=201)
async def import_bd_booking(
    source_row: int,
    body: BookingImportRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    if not body.confirm:
        raise HTTPException(status_code=409, detail="Operator confirmation is required before importing this booking.")
    booking, event, mapping = await _resolve_booking(source_row, db)

    campaign_id = body.campaign_id if "campaign_id" in body.model_fields_set else mapping["campaign_id"]
    if campaign_id is not None:
        async with db.execute("SELECT id FROM campaigns WHERE id = ? AND active = 1", (campaign_id,)) as cur:
            if not await cur.fetchone():
                raise HTTPException(status_code=422, detail="Selected campaign is not an active local campaign.")
    elif mapping["status"] != "mapped" and "campaign_id" not in body.model_fields_set:
        raise HTTPException(status_code=409, detail="Campaign selection is required for this workbook label.")

    async with db.execute(
        "SELECT id FROM meetings WHERE calendar_id = ? AND calendar_event_id = ?",
        (event["calendar_id"], event["event_id"]),
    ) as cur:
        existing = await cur.fetchone()
    if existing:
        raise HTTPException(status_code=409, detail=f"This Calendar event was already imported as meeting {existing['id']}.")

    try:
        await db.execute(
        """
        INSERT INTO meetings
            (id, url, campaign_id, meeting_type, opener_name, scheduled_at,
             pre_booking_notes, calendar_id, calendar_event_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()), event["meet_url"], campaign_id, "discovery",
            booking["opener_name"] or None, event["start"],
            "BD Meetings row " + str(source_row) + ": " + (booking["opener_summary"] or booking["closer_notes"]),
            event["calendar_id"], event["event_id"],
        ),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="This Calendar event was already imported.") from exc
    await db.commit()
    async with db.execute(
        "SELECT id FROM meetings WHERE calendar_id = ? AND calendar_event_id = ?",
        (event["calendar_id"], event["event_id"]),
    ) as cur:
        meeting_id = (await cur.fetchone())["id"]
    return {
        "status": "imported",
        "source_row": source_row,
        "meeting_id": meeting_id,
        "meeting_url": event["meet_url"],
        "meeting_time": event["start"],
        "campaign_id": campaign_id,
        "capture_started": False,
    }


@router.get("/google-sheets/status")
async def google_sheets_status():
    return get_status()


@router.post("/google-sheets/meetings/{meeting_id}/export")
async def export_meeting_to_google_sheets(
    meeting_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)) as cur:
        meeting = await cur.fetchone()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    meeting = dict(meeting)
    if meeting.get("campaign_id"):
        async with db.execute(
            "SELECT name FROM campaigns WHERE id = ?", (meeting["campaign_id"],)
        ) as cur:
            campaign_row = await cur.fetchone()
        if campaign_row:
            meeting["campaign_name"] = campaign_row["name"]

    report = None
    async with db.execute(
        "SELECT file_path FROM reports WHERE meeting_id = ? ORDER BY version DESC LIMIT 1",
        (meeting_id,),
    ) as cur:
        report_row = await cur.fetchone()
    if report_row:
        report = load_report_file(report_row["file_path"])

    try:
        updates = await asyncio.to_thread(export_row, build_export_row(dict(meeting), report))
    except GoogleSheetsSetupError as exc:
        raise HTTPException(status_code=503, detail=public_error_message(exc, "Google Sheets integration is not configured.")) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=public_error_message(exc, "Google Sheets export failed; check the server log.")) from exc

    return {"status": "exported", "meeting_id": meeting_id, "updates": updates}
