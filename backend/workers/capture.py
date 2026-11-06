"""
Capture worker — Milestone 1.

Orchestrates:
  1. Updates meeting status in SQLite.
  2. Starts PlaywrightCaptureAdapter (browser + FFmpeg).
  3. Waits for the meeting to end (or a timeout).
  4. Stops the adapter and saves the recording record.
  5. Triggers the transcription worker; analysis is started separately by its API action.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite

from backend.config import settings
from backend.auth import public_error_message
from backend.adapters.playwright_capture import PlaywrightCaptureAdapter
from backend.audio_watchdog import SILENCE_MESSAGE, SilenceWatchdog, tail_level_db

logger = logging.getLogger(__name__)

# Maximum recording duration in seconds (2 hours safety cap)
MAX_DURATION = 7200
# Polling interval while waiting for the meeting to end
POLL_INTERVAL = 2
# How often (seconds) the recording's loudness is checked, and how long it must
# stay silent after admission before the operator is warned.
WATCHDOG_INTERVAL = 10
# Seconds of the most recent audio inspected on each check
WATCHDOG_WINDOW = 10
SILENCE_WARN_SECONDS = 60

_active_captures: dict[str, PlaywrightCaptureAdapter] = {}


def get_active_capture(meeting_id: str) -> Optional[PlaywrightCaptureAdapter]:
    return _active_captures.get(meeting_id)


async def stop_capture(meeting_id: str) -> bool:
    adapter = _active_captures.get(meeting_id)
    if adapter:
        logger.info("Stopping active capture for meeting %s via stop_capture request", meeting_id)
        adapter._status = "meeting_ended"
        return True
    return False


async def _set_status(db: aiosqlite.Connection, meeting_id: str, status: str, error: str = None):
    await db.execute(
        "UPDATE meetings SET status = ?, error_message = ?, updated_at = ? WHERE id = ?",
        (status, error, datetime.now(timezone.utc).isoformat(), meeting_id),
    )
    await db.commit()


async def _set_warning(db: aiosqlite.Connection, meeting_id: str, message: Optional[str]):
    """Show or clear a live warning without changing the meeting's status."""
    await db.execute(
        "UPDATE meetings SET error_message = ?, updated_at = ? WHERE id = ?",
        (message, datetime.now(timezone.utc).isoformat(), meeting_id),
    )
    await db.commit()


async def run_capture(meeting_id: str) -> None:
    """Entry point called by the FastAPI background task."""
    db_path = str(settings.database_path)

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")

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
        _active_captures[meeting_id] = adapter

        try:
            await _set_status(db, meeting_id, "joining")
            recording_path = await adapter.start(meeting_url, meeting_id)
            logger.info("Recording to %s", recording_path)
            current_status = "joining"
            watchdog = SilenceWatchdog(warn_after_seconds=SILENCE_WARN_SECONDS)
            last_level_check = -WATCHDOG_INTERVAL
            # Wait for meeting end or timeout
            elapsed = 0
            while elapsed < MAX_DURATION:
                await asyncio.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL
                status = await adapter.get_status()
                if status != current_status and status not in ("meeting_ended", "failed"):
                    current_status = status
                    await _set_status(db, meeting_id, status)
                if status in ("meeting_ended", "failed"):
                    break

                # Warn the operator while the call is still running if only silence is arriving.
                if status == "recording" and elapsed - last_level_check >= WATCHDOG_INTERVAL:
                    last_level_check = elapsed
                    level = await asyncio.to_thread(tail_level_db, Path(recording_path), WATCHDOG_WINDOW)
                    verdict = watchdog.update(level)
                    if verdict == "warn":
                        logger.warning("Meeting %s: recording has been silent; warning operator", meeting_id)
                        await _set_warning(db, meeting_id, SILENCE_MESSAGE.format(minutes=watchdog.silent_minutes()))
                    elif verdict == "clear":
                        await _set_warning(db, meeting_id, None)

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
            await _set_status(db, meeting_id, "failed", error=public_error_message(exc, "Capture failed; check the server log and retry."))
        finally:
            _active_captures.pop(meeting_id, None)
