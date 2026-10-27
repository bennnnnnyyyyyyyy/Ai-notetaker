"""Local scheduler for operator-approved, scheduled meeting captures."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import aiosqlite

from backend.config import settings
from backend.workers.capture import run_capture

logger = logging.getLogger(__name__)


def due_utc_iso(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat()


async def claim_due_meetings(db: aiosqlite.Connection, now: datetime | None = None) -> list[str]:
    """Atomically claim due pending meetings so only one worker starts each."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    await db.execute("BEGIN IMMEDIATE")
    async with db.execute(
        """
        SELECT id, scheduled_at FROM meetings
        WHERE status = 'pending' AND scheduled_at IS NOT NULL
        """
    ) as cur:
        rows = await cur.fetchall()
    due_ids = []
    for row in rows:
        try:
            scheduled = datetime.fromisoformat(row[1].replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=timezone.utc)
        if scheduled.astimezone(timezone.utc) <= current:
            due_ids.append(row[0])
    for meeting_id in due_ids:
        await db.execute(
            """
            UPDATE meetings
            SET status = 'joining', error_message = NULL, updated_at = datetime('now')
            WHERE id = ? AND status = 'pending'
            """,
            (meeting_id,),
        )
    await db.commit()
    return due_ids


async def run_scheduler(stop_event: asyncio.Event) -> None:
    """Poll local SQLite and start due captures while the API process is alive."""
    if not settings.scheduled_capture_enabled:
        logger.info("Scheduled capture is disabled")
        return

    running: set[asyncio.Task] = set()
    try:
        while not stop_event.is_set():
            try:
                async with aiosqlite.connect(settings.database_path) as db:
                    due_ids = await claim_due_meetings(db)
                for meeting_id in due_ids:
                    logger.info("Starting scheduled capture for meeting %s", meeting_id)
                    task = asyncio.create_task(run_capture(meeting_id))
                    running.add(task)
                    task.add_done_callback(running.discard)
            except Exception:
                logger.exception("Scheduled capture polling failed")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=max(1, settings.scheduled_capture_poll_seconds))
            except asyncio.TimeoutError:
                pass
    finally:
        if running:
            await asyncio.gather(*running, return_exceptions=True)
