"""
faster-whisper transcription adapter.

Uses the faster-whisper library (CTranslate2 backend) with the configured
model size. Runs entirely on CPU — no GPU required.

Model download happens on first use; models are cached by faster-whisper
in the default HuggingFace cache directory.
"""

import logging
from typing import Optional

from backend.adapters.base_transcriber import BaseTranscriber
from backend.config import settings

logger = logging.getLogger(__name__)

_model_instance = None  # module-level singleton to avoid reloading


def _get_model():
    global _model_instance
    if _model_instance is None:
        from faster_whisper import WhisperModel
        logger.info("Loading faster-whisper model: %s (CPU)", settings.whisper_model)
        _model_instance = WhisperModel(
            settings.whisper_model,
            device="cpu",
            compute_type="int8",  # int8 is fastest on CPU
        )
    return _model_instance


class FasterWhisperTranscriber(BaseTranscriber):

    def transcribe(self, audio_path: str) -> list[dict]:
        """
        Transcribe the audio file and return normalized segments.
        Speaker diarisation is NOT performed in this adapter.
        speaker_id will be None for all segments.
        """
        model = _get_model()
        logger.info("Transcribing %s with model '%s'", audio_path, settings.whisper_model)

        segments, info = model.transcribe(
            audio_path,
            beam_size=5,
            language="en",
            vad_filter=True,
        )

        results = []
        for idx, seg in enumerate(segments):
            results.append({
                "segment_index": idx,
                "start_ms": int(seg.start * 1000),
                "end_ms": int(seg.end * 1000),
                "speaker_id": None,  # diarisation not implemented
                "text": seg.text.strip(),
            })

        logger.info(
            "Transcription complete: %d segments, language=%s, prob=%.2f",
            len(results),
            info.language,
            info.language_probability,
        )
        return results
