"""
Transcription worker — Milestone 2.

Orchestrates:
  1. Runs FasterWhisperTranscriber on the recording.
  2. Saves the normalized transcript JSON to data/transcripts/.
  3. Writes transcript + segment records to SQLite.
  4. Marks the meeting completed; analysis is an explicit separate action.
"""

import json
import logging
import uuid
import asyncio
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from backend.config import settings
from backend.auth import public_error_message
from backend.adapters.faster_whisper_transcriber import FasterWhisperTranscriber

logger = logging.getLogger(__name__)


async def run_transcription(
    meeting_id: str,
    recording_path: str,
    db: aiosqlite.Connection,
) -> None:
    """Called by the capture worker after a successful recording."""
    await db.execute(
        "UPDATE meetings SET status = 'processing', updated_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), meeting_id),
    )
    await db.commit()

    try:
        transcriber = FasterWhisperTranscriber()
        segments = await asyncio.to_thread(transcriber.transcribe, recording_path)

        # Build transcript document
        transcript_doc = {
            "meeting_id": meeting_id,
            "model_used": f"faster-whisper/{settings.whisper_model}",
            "segments": [
                {
                    "segment_id": f"seg_{s['segment_index']:04d}",
                    **s,
                }
                for s in segments
            ],
        }

        # Save to file
        transcript_path = Path(settings.transcripts_dir) / f"{meeting_id}.json"
        transcript_path.write_text(json.dumps(transcript_doc, indent=2))
        logger.info("Transcript saved to %s", transcript_path)

        # Replace an earlier transcript for this meeting atomically on retry.
        # The old rows are removed only after transcription succeeded.
        async with db.execute(
            "SELECT id FROM transcripts WHERE meeting_id = ?", (meeting_id,)
        ) as cur:
            previous_ids = [row["id"] for row in await cur.fetchall()]
        for previous_id in previous_ids:
            await db.execute(
                "DELETE FROM transcript_segments WHERE transcript_id = ?",
                (previous_id,),
            )
        await db.execute("DELETE FROM transcripts WHERE meeting_id = ?", (meeting_id,))

        # Write to DB
        transcript_id = str(uuid.uuid4())
        await db.execute(
            """
            INSERT INTO transcripts (id, meeting_id, file_path, model_used)
            VALUES (?, ?, ?, ?)
            """,
            (
                transcript_id,
                meeting_id,
                str(transcript_path),
                transcript_doc["model_used"],
            ),
        )

        for seg in transcript_doc["segments"]:
            seg_id = str(uuid.uuid4())
            await db.execute(
                """
                INSERT INTO transcript_segments
                    (id, transcript_id, segment_index, start_ms, end_ms, speaker_id, text)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    seg_id,
                    transcript_id,
                    seg["segment_index"],
                    int(round(seg["start"] * 1000)),
                    int(round(seg["end"] * 1000)),
                    seg.get("speaker_id"),
                    seg["text"],
                ),
            )
        await db.commit()
        await db.execute(
            "UPDATE meetings SET status = 'completed', error_message = NULL, updated_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), meeting_id),
        )
        await db.commit()

    except Exception as exc:
        logger.exception("Transcription failed for meeting %s", meeting_id)
        await db.execute(
            "UPDATE meetings SET status = 'failed', error_message = ?, updated_at = ? WHERE id = ?",
        (public_error_message(exc, "Transcription failed; check the server log and retry."), datetime.now(timezone.utc).isoformat(), meeting_id),
        )
        await db.commit()
