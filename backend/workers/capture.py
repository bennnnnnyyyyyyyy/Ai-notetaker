"""
Capture worker — Milestone 1.

Orchestrates:
  1. Updates meeting status in SQLite.
  2. Starts PlaywrightCaptureAdapter (browser + FFmpeg).
  3. Waits for the meeting to end (or a timeout).
  4. Stops the adapter and saves the recording record.
  5. Triggers the transcription worker.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path

import aiosqlite

from backend.config import settings
from backend.adapters.playwright_capture import PlaywrightCaptureAdapter

logger = logging.getLogger(__name__)

# Maximum recording duration in seconds (2 hours safety cap)
MAX_DURATION = 7200
# Polling interval while waiting for the meeting to end
POLL_INTERVAL = 10


async def _set_status(db: aiosqlite.Connection, meeting_id: str, status: str, error: str = None):
    await db.execute(
        "UPDATE meetings SET status = ?, error_message = ?, updated_at = ? WHERE id = ?",
        (status, error, datetime.utcnow().isoformat(), meeting_id),
    )
    await db.commit()


async def run_capture(meeting_id: str) -> None:
    """Entry point called by the FastAPI background task."""
    db_path = str(settings.database_path)

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        # Fetch meeting
        async with db.execute(
            "SELECT url FROM meetings WHERE id = ?", (meeting_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            logger.error("Meeting %s not found", meeting_id)
            return

        meeting_url = row["url"]
        adapter = PlaywrightCaptureAdapter()

        try:
            await _set_status(db, meeting_id, "joining")
            recording_path = await adapter.start(meeting_url, meeting_id)
            logger.info("Recording to %s", recording_path)
            await _set_status(db, meeting_id, "recording")

            # Wait for meeting end or timeout
            elapsed = 0
            while elapsed < MAX_DURATION:
                await asyncio.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL
                status = await adapter.get_status()
                if status in ("meeting_ended", "failed"):
                    break

            duration = await adapter.stop()
            logger.info("Recording stopped. Duration: %.1f s", duration)

            recording_file = Path(recording_path)
            if not recording_file.exists() or recording_file.stat().st_size == 0:
                raise RuntimeError(
                    "Capture ended without audio data. Check the Windows playback route "
                    "to the configured VB-Audio device."
                )

            # Save recording record
            recording_id = str(uuid.uuid4())
            await db.execute(
                """
                INSERT INTO recordings (id, meeting_id, file_path, duration_seconds)
                VALUES (?, ?, ?, ?)
                """,
                (recording_id, meeting_id, recording_path, duration),
            )
            await _set_status(db, meeting_id, "meeting_ended")

            # Trigger transcription
            from backend.workers.transcribe import run_transcription
            await run_transcription(meeting_id, recording_path, db)

        except Exception as exc:
            logger.exception("Capture failed for meeting %s", meeting_id)
            await adapter.stop()
            partial = Path(adapter._recording_path) if adapter._recording_path else None
            if partial and partial.exists() and partial.stat().st_size == 0:
                partial.unlink()
            await _set_status(db, meeting_id, "failed", error=str(exc))
