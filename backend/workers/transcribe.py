"""
Transcription worker — Milestone 2.

Orchestrates:
  1. Runs FasterWhisperTranscriber on the recording.
  2. Saves the normalized transcript JSON to data/transcripts/.
  3. Writes transcript + segment records to SQLite.
  4. Chains into the analysis worker.
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

import aiosqlite

from backend.config import settings
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
        (datetime.utcnow().isoformat(), meeting_id),
    )
    await db.commit()

    try:
        transcriber = FasterWhisperTranscriber()
        segments = transcriber.transcribe(recording_path)

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
                    seg["start_ms"],
                    seg.get("end_ms"),
                    seg.get("speaker_id"),
                    seg["text"],
                ),
            )
        await db.commit()

        # Chain into analysis
        from backend.workers.analyse import run_analysis_with_db
        await run_analysis_with_db(meeting_id, db)

    except Exception as exc:
        logger.exception("Transcription failed for meeting %s", meeting_id)
        await db.execute(
            "UPDATE meetings SET status = 'failed', error_message = ?, updated_at = ? WHERE id = ?",
            (str(exc), datetime.utcnow().isoformat(), meeting_id),
        )
        await db.commit()
