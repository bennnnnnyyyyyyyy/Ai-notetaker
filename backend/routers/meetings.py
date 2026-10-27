import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
import aiosqlite
import json

from backend.database import get_db
from backend.schemas.meeting import MeetingCreate, MeetingResponse, MeetingStatusResponse

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.post("", response_model=MeetingResponse, status_code=201)
async def create_meeting(
    body: MeetingCreate,
    db: aiosqlite.Connection = Depends(get_db),
):
    meeting_id = str(uuid.uuid4())
    await db.execute(
        """
        INSERT INTO meetings
            (id, url, campaign_id, meeting_type, opener_name, closer_name,
             scheduled_at, pre_booking_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            meeting_id,
            str(body.url),
            body.campaign_id,
            body.meeting_type,
            body.opener_name,
            body.closer_name,
            body.scheduled_at.isoformat() if body.scheduled_at else None,
            body.pre_booking_notes,
        ),
    )
    await db.commit()
    return await _get_meeting_or_404(meeting_id, db)


@router.get("", response_model=list[MeetingResponse])
async def list_meetings(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute(
        """
        SELECT * FROM meetings
        ORDER BY
            CASE status
                WHEN 'joining' THEN 0
                WHEN 'waiting_for_admission' THEN 0
                WHEN 'recording' THEN 0
                WHEN 'processing' THEN 0
                WHEN 'pending' THEN 1
                ELSE 2
            END,
            CASE WHEN scheduled_at IS NULL THEN 1 ELSE 0 END,
            CASE WHEN status IN ('joining','waiting_for_admission','recording','processing','pending')
                 THEN scheduled_at END ASC,
            CASE WHEN status NOT IN ('joining','waiting_for_admission','recording','processing','pending')
                 THEN scheduled_at END DESC,
            created_at DESC
        """
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    return await _get_meeting_or_404(meeting_id, db)


@router.get("/{meeting_id}/status", response_model=MeetingStatusResponse)
async def get_meeting_status(
    meeting_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    row = await _get_meeting_or_404(meeting_id, db)
    return {"id": row["id"], "status": row["status"], "error_message": row.get("error_message")}


@router.post("/{meeting_id}/start-capture", status_code=202)
async def start_capture(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Trigger the capture worker in the background."""
    meeting = await _get_meeting_or_404(meeting_id, db)
    if meeting["status"] not in ("pending", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot start capture from status '{meeting['status']}'",
        )
    from backend.workers.capture import _active_captures
    if _active_captures:
        raise HTTPException(status_code=409, detail="Another capture is already running")

    # Claim the meeting before scheduling the task so repeated clicks cannot
    # start competing browser/FFmpeg workers.
    async with db.execute(
        """
        UPDATE meetings
        SET status = 'joining', error_message = NULL, updated_at = datetime('now')
        WHERE id = ? AND status IN ('pending', 'failed')
        """,
        (meeting_id,),
    ) as cur:
        claimed = cur.rowcount
    await db.commit()
    if claimed != 1:
        raise HTTPException(status_code=409, detail="Capture is already active or cannot be restarted")

    # Import here to avoid circular imports
    from backend.workers.capture import run_capture
    background_tasks.add_task(run_capture, meeting_id)
    return {"detail": "Capture started", "meeting_id": meeting_id}


@router.post("/{meeting_id}/stop-capture", status_code=200)
async def stop_capture_route(
    meeting_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Signal an active capture worker to cleanly stop recording."""
    from backend.workers.capture import stop_capture
    stopped = await stop_capture(meeting_id)
    return {"detail": "Capture stopping" if stopped else "No active capture in memory", "meeting_id": meeting_id}


@router.post("/{meeting_id}/retry", status_code=202)
async def retry_meeting(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Retry a failed meeting's processing pipeline."""
    meeting = await _get_meeting_or_404(meeting_id, db)
    if meeting["status"] != "failed":
        raise HTTPException(
            status_code=409,
            detail=f"Only failed meetings can be retried (current: '{meeting['status']}')",
        )
    from backend.workers.capture import _active_captures
    if _active_captures:
        raise HTTPException(status_code=409, detail="Another capture is already running")
    async with db.execute(
        """
        UPDATE meetings
        SET status = 'joining', error_message = NULL, updated_at = datetime('now')
        WHERE id = ? AND status = 'failed'
        """,
        (meeting_id,),
    ) as cur:
        claimed = cur.rowcount
    await db.commit()
    if claimed != 1:
        raise HTTPException(status_code=409, detail="Meeting changed before retry could start")

    from backend.workers.capture import run_capture
    background_tasks.add_task(run_capture, meeting_id)
    return {"detail": "Retry started", "meeting_id": meeting_id}


@router.get("/{meeting_id}/status-stream")
async def status_stream(
    meeting_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Server-Sent Events stream for live status updates."""
    import asyncio

    async def event_generator():
        last_status = None
        for _ in range(300):  # max ~5 minutes at 1 s interval
            async with db.execute(
                "SELECT status, error_message FROM meetings WHERE id = ?", (meeting_id,)
            ) as cur:
                row = await cur.fetchone()
            if row:
                status = row["status"]
                if status != last_status:
                    last_status = status
                    data = json.dumps({"status": status, "error": row["error_message"]})
                    yield f"data: {data}\n\n"
                if status in ("completed", "failed", "cancelled"):
                    break
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_meeting_or_404(meeting_id: str, db: aiosqlite.Connection) -> dict:
    async with db.execute(
        "SELECT * FROM meetings WHERE id = ?", (meeting_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return dict(row)
