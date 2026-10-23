from abc import ABC, abstractmethod


class BaseTranscriber(ABC):
    """
    Abstract interface for transcription providers.
    Concrete implementations: FasterWhisperTranscriber (local, default).
    Future: OpenAIWhisperTranscriber.
    """

    @abstractmethod
    def transcribe(self, audio_path: str) -> list[dict]:
        """
        Transcribe the audio file at audio_path.

        Returns a list of segment dicts:
        [
            {
                "segment_index": int,
                "start_ms": int,
                "end_ms": int | None,
                "speaker_id": str | None,
                "text": str,
            },
            ...
        ]
        """
        ...
