import asyncio

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
from backend.adapters.bd_meetings import BDMeetingsSetupError, get_status as get_bd_status, get_booking, list_bookings

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


@router.post("/bd-meetings/bookings/{source_row}/import", status_code=201)
async def import_bd_booking(source_row: int, db: aiosqlite.Connection = Depends(get_db)):
    try:
        booking = await asyncio.to_thread(get_booking, source_row)
    except BDMeetingsSetupError as exc:
        raise HTTPException(status_code=503, detail=public_error_message(exc, "BD Meetings source is not available.")) from exc
    if not booking:
        raise HTTPException(status_code=404, detail="BD Meetings booking row not found")
    if not booking["meet_url"]:
        raise HTTPException(
            status_code=409,
            detail="This booking has no direct Google Meet URL. Its source cell contains a calendar event link or meeting-time text.",
        )

    campaign_map = {
        "cgm": "cgm_patient_acquisition",
        "roofing": "roofing_appointment_setting",
        "ort": "dme_lead_generation",
    }
    label = booking["campaign_label"].lower()
    campaign_id = next((value for key, value in campaign_map.items() if key in label), None)
    meeting_type = "discovery"
    await db.execute(
        """
        INSERT INTO meetings
            (id, url, campaign_id, meeting_type, opener_name, scheduled_at, pre_booking_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(__import__("uuid").uuid4()), booking["meet_url"], campaign_id, meeting_type,
            booking["opener_name"] or None, None,
            "BD Meetings row " + str(source_row) + ": " + (booking["opener_summary"] or booking["closer_notes"]),
        ),
    )
    await db.commit()
    return {"status": "imported", "source_row": source_row, "meeting_url": booking["meet_url"]}


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
