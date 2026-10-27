from datetime import datetime, timezone

import aiosqlite
import pytest

from backend.workers.scheduler import claim_due_meetings


@pytest.mark.asyncio
async def test_scheduler_claims_due_utc_and_zulu_meetings_once():
    async with aiosqlite.connect(":memory:") as db:
        await db.execute(
            "CREATE TABLE meetings (id TEXT PRIMARY KEY, scheduled_at TEXT, status TEXT, error_message TEXT, updated_at TEXT)"
        )
        await db.executemany(
            "INSERT INTO meetings VALUES (?, ?, 'pending', NULL, NULL)",
            [
                ("due-offset", "2026-10-27T17:00:00+00:00"),
                ("due-zulu", "2026-10-27T17:00:00Z"),
                ("future", "2026-10-27T18:00:00+00:00"),
                ("invalid", "not-a-date"),
            ],
        )
        await db.commit()

        now = datetime(2026, 10, 27, 17, 0, tzinfo=timezone.utc)
        assert await claim_due_meetings(db, now) == ["due-offset", "due-zulu"]
        assert await claim_due_meetings(db, now) == []

        async with db.execute("SELECT id, status FROM meetings ORDER BY id") as cur:
            assert await cur.fetchall() == [
                ("due-offset", "joining"),
                ("due-zulu", "joining"),
                ("future", "pending"),
                ("invalid", "pending"),
            ]
