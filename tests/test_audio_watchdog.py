"""Tests for live silence detection during capture."""

import math
import struct

import aiosqlite
import pytest

from backend import audio_watchdog
from backend.audio_watchdog import SILENCE_THRESHOLD_DB, SilenceWatchdog, tail_level_db
from backend.config import settings
from backend.database import _DDL
from backend.workers import capture, transcribe

HEADER = b"\x00" * 44  # FFmpeg's streaming header is not trustworthy; the code must ignore it


def _pcm(seconds, amplitude):
    """16 kHz mono 16-bit sine wave; amplitude 0 gives digital silence."""
    n = int(16000 * seconds)
    return b"".join(
        struct.pack("<h", int(amplitude * math.sin(2 * math.pi * 440 * i / 16000))) for i in range(n)
    )


def test_level_of_silence_and_tone(tmp_path):
    silent = tmp_path / "silent.wav"
    silent.write_bytes(HEADER + _pcm(3, 0))
    loud = tmp_path / "loud.wav"
    loud.write_bytes(HEADER + _pcm(3, 8000))
    assert tail_level_db(silent) == -120.0
    assert -20 < tail_level_db(loud) < -10  # sine at 8000/32768 is about -15 dB RMS


def test_level_reads_only_the_recent_end_of_the_file(tmp_path):
    path = tmp_path / "late.wav"
    path.write_bytes(HEADER + _pcm(20, 8000) + _pcm(10, 0))  # loud, then 10 s of silence
    assert tail_level_db(path, seconds=10) == -120.0


def test_level_unknown_when_file_missing_or_too_short(tmp_path):
    assert tail_level_db(tmp_path / "missing.wav") is None
    short = tmp_path / "short.wav"
    short.write_bytes(HEADER + _pcm(0.5, 8000))
    assert tail_level_db(short) is None


def test_watchdog_warns_after_sustained_silence_and_clears_on_sound():
    now = [0.0]
    dog = SilenceWatchdog(warn_after_seconds=60, clock=lambda: now[0])
    quiet = SILENCE_THRESHOLD_DB - 30

    assert dog.update(quiet) is None  # silence starts
    now[0] = 59
    assert dog.update(quiet) is None  # not long enough yet
    now[0] = 61
    assert dog.update(quiet) == "warn"
    now[0] = 90
    assert dog.update(quiet) is None  # only warns once
    assert dog.silent_minutes() >= 1
    now[0] = 100
    assert dog.update(-30.0) == "clear"
    assert dog.update(-30.0) is None


def test_watchdog_ignores_unknown_levels_and_brief_gaps():
    now = [0.0]
    dog = SilenceWatchdog(warn_after_seconds=60, clock=lambda: now[0])
    quiet = SILENCE_THRESHOLD_DB - 30
    dog.update(quiet)
    now[0] = 50
    assert dog.update(None) is None
    assert dog.update(-30.0) is None  # speech resumed before the limit
    now[0] = 100
    assert dog.update(quiet) is None  # silence timer restarted, no warning


class _RecordingAdapter:
    """Fake adapter that is admitted, then plays whatever audio the test writes."""

    def __init__(self, path, audio_by_poll):
        self._recording_path = path
        self._audio = list(audio_by_poll)
        self.polls = 0

    async def start(self, meeting_url, meeting_id):
        self._recording_path.write_bytes(HEADER)
        return str(self._recording_path)

    async def get_status(self):
        self.polls += 1
        if self._audio:
            with open(self._recording_path, "ab") as handle:
                handle.write(self._audio.pop(0))
            return "recording"
        return "meeting_ended"

    async def stop(self):
        return 5.0


async def _run_worker(tmp_path, monkeypatch, audio):
    db_path = tmp_path / "wd.db"
    monkeypatch.setattr(settings, "database_path", db_path)
    monkeypatch.setattr(capture, "POLL_INTERVAL", 0)
    monkeypatch.setattr(capture, "WATCHDOG_INTERVAL", 0)
    monkeypatch.setattr(capture, "SILENCE_WARN_SECONDS", 0)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(_DDL)
        await db.execute(
            "INSERT INTO meetings (id, url, meeting_type) VALUES ('wd', 'https://meet.google.com/abc-defg-hij', 'discovery')"
        )
        await db.commit()

    adapter = _RecordingAdapter(tmp_path / "wd.wav", audio)
    monkeypatch.setattr(capture, "PlaywrightCaptureAdapter", lambda: adapter)

    messages = []
    original = capture._set_warning

    async def spy(db, meeting_id, message):
        messages.append(message)
        await original(db, meeting_id, message)

    monkeypatch.setattr(capture, "_set_warning", spy)

    async def no_transcription(meeting_id, recording_path, db):
        return None

    monkeypatch.setattr(transcribe, "run_transcription", no_transcription)
    await capture.run_capture("wd")
    return messages


@pytest.mark.asyncio
async def test_worker_warns_operator_when_recording_is_silent(tmp_path, monkeypatch):
    messages = await _run_worker(tmp_path, monkeypatch, [_pcm(2, 0), _pcm(2, 0)])
    assert len(messages) == 1
    assert "CABLE Input" in messages[0]


@pytest.mark.asyncio
async def test_worker_does_not_warn_when_sound_is_present(tmp_path, monkeypatch):
    messages = await _run_worker(tmp_path, monkeypatch, [_pcm(2, 8000), _pcm(2, 8000)])
    assert messages == []


@pytest.mark.asyncio
async def test_worker_clears_warning_when_sound_returns(tmp_path, monkeypatch):
    messages = await _run_worker(tmp_path, monkeypatch, [_pcm(2, 0), _pcm(12, 8000)])
    assert messages[0] and "CABLE Input" in messages[0]
    assert messages[-1] is None
