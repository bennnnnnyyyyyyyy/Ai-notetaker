import aiosqlite
import pytest

from backend.config import settings
from backend.database import _DDL
from backend.workers import transcribe


@pytest.mark.asyncio
async def test_transcription_worker_persists_idempotently_without_analysis(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "transcripts_dir", tmp_path)

    async with aiosqlite.connect(":memory:") as db:
        db.row_factory = aiosqlite.Row
        await db.executescript(_DDL)
        await db.execute(
            "INSERT INTO meetings (id, url, meeting_type) VALUES (?, ?, ?)",
            ("worker-test", "https://meet.google.com/test-test-test", "discovery"),
        )
        await db.commit()

        monkeypatch.setattr(
            transcribe.FasterWhisperTranscriber,
            "transcribe",
            lambda self, path: [
                {
                    "segment_index": 0,
                    "start": 0.5,
                    "end": 1.5,
                    "speaker_id": None,
                    "text": "test speech",
                }
            ],
        )

        await transcribe.run_transcription("worker-test", "fixture.wav", db)
        await transcribe.run_transcription("worker-test", "fixture.wav", db)

        transcript_count = (await (await db.execute("SELECT COUNT(*) AS n FROM transcripts")).fetchone())["n"]
        segment_count = (await (await db.execute("SELECT COUNT(*) AS n FROM transcript_segments")).fetchone())["n"]
        report_count = (await (await db.execute("SELECT COUNT(*) AS n FROM reports")).fetchone())["n"]
        meeting = await (await db.execute("SELECT status, error_message FROM meetings WHERE id = ?", ("worker-test",))).fetchone()
        segment = await (await db.execute("SELECT start_ms, end_ms, text FROM transcript_segments")).fetchone()

    assert (transcript_count, segment_count, report_count) == (1, 1, 0)
    assert dict(meeting) == {"status": "completed", "error_message": None}
    assert dict(segment) == {"start_ms": 500, "end_ms": 1500, "text": "test speech"}
