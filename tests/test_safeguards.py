"""Regression tests for the Meet-link, no-speech, short-transcript and capture-worker safeguards."""

import json

import aiosqlite
import pytest
from pydantic import ValidationError

from backend.config import settings
from backend.database import _DDL
from backend.schemas.meeting import MeetingCreate, is_valid_meet_url
from backend.workers import analyse, capture, transcribe


@pytest.mark.parametrize(
    "url",
    [
        "https://meet.google.com/abc-defg-hij",
        "https://meet.google.com/abc-defg-hij?authuser=0",
        "https://meet.google.com/ABC-DEFG-HIJ",
    ],
)
def test_real_meet_links_are_accepted(url):
    assert is_valid_meet_url(url)
    MeetingCreate(url=url, meeting_type="discovery")


@pytest.mark.parametrize(
    "url",
    [
        "https://meet.google.com/",
        "https://meet.google.com/not-a-code-at-all",
        "https://meet.google.com/abc-defg-hij/extra",
        "http://meet.google.com/abc-defg-hij",
        "https://meet.google.com.evil.example/abc-defg-hij",
        "https://meet.googleusercontent.com/abc-defg-hij",
        "https://user@meet.google.com/abc-defg-hij",
        "https://example.com/abc-defg-hij",
    ],
)
def test_non_meet_links_are_rejected(url):
    assert not is_valid_meet_url(url)
    with pytest.raises(ValidationError):
        MeetingCreate(url=url, meeting_type="discovery")


async def _db_with_meeting(meeting_id: str) -> aiosqlite.Connection:
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.executescript(_DDL)
    await db.execute(
        "INSERT INTO meetings (id, url, meeting_type) VALUES (?, ?, ?)",
        (meeting_id, "https://meet.google.com/abc-defg-hij", "discovery"),
    )
    await db.commit()
    return db


@pytest.mark.asyncio
async def test_silent_recording_is_marked_failed_not_completed(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "transcripts_dir", tmp_path)
    monkeypatch.setattr(transcribe.FasterWhisperTranscriber, "transcribe", lambda self, path: [])
    db = await _db_with_meeting("silent")
    try:
        await transcribe.run_transcription("silent", "silent.wav", db)
        row = await (await db.execute("SELECT status, error_message FROM meetings WHERE id='silent'")).fetchone()
        transcripts = (await (await db.execute("SELECT COUNT(*) FROM transcripts")).fetchone())[0]
    finally:
        await db.close()
    assert row["status"] == "failed"
    assert row["error_message"] == transcribe.NO_SPEECH_MESSAGE
    assert transcripts == 1  # the (empty) transcript is still kept for inspection


@pytest.mark.asyncio
async def test_analysis_refuses_near_empty_transcript(tmp_path, monkeypatch):
    transcript_file = tmp_path / "short.json"
    transcript_file.write_text(json.dumps({"segments": [{"segment_id": "seg_0000", "text": "hello can you hear"}]}))

    async def must_not_run(*args, **kwargs):
        raise AssertionError("LLM pipeline must not run on a near-empty transcript")

    monkeypatch.setattr(analyse, "_run_pipeline", must_not_run)
    db = await _db_with_meeting("short")
    try:
        await db.execute(
            "INSERT INTO transcripts (id, meeting_id, file_path, model_used) VALUES ('t1', 'short', ?, 'test')",
            (str(transcript_file),),
        )
        await db.commit()
        await analyse.run_analysis_with_db("short", db)
        row = await (await db.execute("SELECT status, error_message FROM meetings WHERE id='short'")).fetchone()
        reports = (await (await db.execute("SELECT COUNT(*) FROM reports")).fetchone())[0]
    finally:
        await db.close()
    assert row["status"] == "failed"
    assert "only 4 words" in row["error_message"]
    assert reports == 0


class _FakeAdapter:
    """Stands in for the browser + FFmpeg adapter; never opens a browser."""

    def __init__(self, recording_path, statuses):
        self._recording_path = recording_path
        self._statuses = list(statuses)
        self.stopped = False

    async def start(self, meeting_url, meeting_id):
        self._recording_path.write_bytes(b"RIFF-fake-audio")
        return str(self._recording_path)

    async def get_status(self):
        return self._statuses.pop(0) if len(self._statuses) > 1 else self._statuses[0]

    async def stop(self):
        self.stopped = True
        return 12.5


async def _capture_db(tmp_path, monkeypatch):
    db_path = tmp_path / "capture.db"
    monkeypatch.setattr(settings, "database_path", db_path)
    monkeypatch.setattr(capture, "POLL_INTERVAL", 0)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(_DDL)
        await db.execute(
            "INSERT INTO meetings (id, url, meeting_type) VALUES ('cap', 'https://meet.google.com/abc-defg-hij', 'discovery')"
        )
        await db.commit()
    return db_path


@pytest.mark.asyncio
async def test_capture_worker_saves_recording_and_starts_transcription(tmp_path, monkeypatch):
    db_path = await _capture_db(tmp_path, monkeypatch)
    adapter = _FakeAdapter(tmp_path / "cap.wav", ["waiting_for_admission", "recording", "meeting_ended"])
    monkeypatch.setattr(capture, "PlaywrightCaptureAdapter", lambda: adapter)
    calls = []

    async def fake_transcription(meeting_id, recording_path, db):
        calls.append((meeting_id, recording_path))

    monkeypatch.setattr(transcribe, "run_transcription", fake_transcription)

    await capture.run_capture("cap")

    async with aiosqlite.connect(db_path) as db:
        status = (await (await db.execute("SELECT status FROM meetings WHERE id='cap'")).fetchone())[0]
        rec = await (await db.execute("SELECT file_path, duration_seconds FROM recordings")).fetchall()
    assert adapter.stopped
    assert status == "meeting_ended"
    assert rec == [(str(tmp_path / "cap.wav"), 12.5)]
    assert calls == [("cap", str(tmp_path / "cap.wav"))]
    assert capture.get_active_capture("cap") is None


@pytest.mark.asyncio
async def test_capture_worker_marks_empty_recording_failed(tmp_path, monkeypatch):
    db_path = await _capture_db(tmp_path, monkeypatch)
    adapter = _FakeAdapter(tmp_path / "empty.wav", ["meeting_ended"])

    async def start_without_audio(meeting_url, meeting_id):
        adapter._recording_path.write_bytes(b"")
        return str(adapter._recording_path)

    adapter.start = start_without_audio
    monkeypatch.setattr(capture, "PlaywrightCaptureAdapter", lambda: adapter)

    await capture.run_capture("cap")

    async with aiosqlite.connect(db_path) as db:
        status = (await (await db.execute("SELECT status FROM meetings WHERE id='cap'")).fetchone())[0]
        recordings = (await (await db.execute("SELECT COUNT(*) FROM recordings")).fetchone())[0]
    assert status == "failed"
    assert recordings == 0
    assert not (tmp_path / "empty.wav").exists()  # zero-byte file cleaned up
