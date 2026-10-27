import uuid
import asyncio
import subprocess
import wave
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, File, Form, UploadFile
from fastapi.responses import StreamingResponse
import aiosqlite
import json

from backend.database import get_db
from backend.schemas.meeting import MeetingCreate, MeetingResponse, MeetingStatusResponse
from backend.config import settings

router = APIRouter(prefix="/meetings", tags=["meetings"])
_IMPORT_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4", ".webm", ".ogg", ".flac"}


async def _save_import(upload: UploadFile, path: Path) -> int:
    size = 0
    with path.open("wb") as destination:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > settings.import_max_bytes:
                path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Imported recording is too large.")
            destination.write(chunk)
    if size == 0:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Imported recording is empty.")
    return size


def _normalize_import(source: Path, destination: Path) -> float:
    ffmpeg = settings.resolve_ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required to import and normalize recordings.")
    completed = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
         "-vn", "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", str(destination)],
        capture_output=True, text=True, timeout=180, check=False,
    )
    if completed.returncode != 0 or not destination.is_file():
        raise RuntimeError("The imported recording could not be decoded.")
    try:
        with wave.open(str(destination), "rb") as audio:
            duration = audio.getnframes() / float(audio.getframerate() or 1)
            if audio.getnchannels() != 1 or audio.getframerate() != 16000 or duration <= 0:
                raise RuntimeError("The normalized recording is invalid.")
            return duration
    except (wave.Error, EOFError) as exc:
        raise RuntimeError("The normalized recording is invalid.") from exc


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


@router.post("/import", response_model=MeetingResponse, status_code=202)
async def import_meeting(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    meeting_type: str = Form("discovery"),
    campaign_id: str | None = Form(None),
    opener_name: str | None = Form(None),
    closer_name: str | None = Form(None),
    pre_booking_notes: str | None = Form(None),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Import a local recording and run the existing transcription worker."""
    if meeting_type not in {"discovery", "negotiation", "onboarding"}:
        raise HTTPException(status_code=422, detail="Invalid meeting type.")
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in _IMPORT_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Use WAV, MP3, M4A, MP4, WEBM, OGG, or FLAC.")
    from backend.workers.capture import _active_captures
    if _active_captures:
        raise HTTPException(status_code=409, detail="Import is unavailable while capture is active.")

    meeting_id = str(uuid.uuid4())
    settings.ensure_data_dirs()
    upload_path = settings.recordings_dir / f".{meeting_id}.upload{suffix}"
    recording_path = settings.recordings_dir / f"{meeting_id}.wav"
    try:
        await _save_import(file, upload_path)
        duration = await asyncio.to_thread(_normalize_import, upload_path, recording_path)
    except HTTPException:
        raise
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        recording_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        upload_path.unlink(missing_ok=True)
        await file.close()

    await db.execute(
        """
        INSERT INTO meetings
            (id, url, campaign_id, meeting_type, opener_name, closer_name,
             status, pre_booking_notes, updated_at, source_type, source_filename)
        VALUES (?, ?, ?, ?, ?, ?, 'processing', ?, ?, 'local_import', ?)
        """,
        (meeting_id, f"local://{meeting_id}", campaign_id, meeting_type, opener_name,
         closer_name, pre_booking_notes, datetime.now(timezone.utc).isoformat(), filename),
    )
    await db.execute(
        "INSERT INTO recordings (id, meeting_id, file_path, duration_seconds) VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), meeting_id, str(recording_path), duration),
    )
    await db.commit()
    from backend.workers.transcribe import run_import_transcription
    background_tasks.add_task(run_import_transcription, meeting_id, str(recording_path))
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
