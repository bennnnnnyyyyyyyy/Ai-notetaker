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

router = APIRouter(prefix="/integrations", tags=["integrations"])


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
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Google Sheets export failed: {exc}") from exc

    return {"status": "exported", "meeting_id": meeting_id, "updates": updates}
