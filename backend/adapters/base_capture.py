from abc import ABC, abstractmethod


class BaseCaptureAdapter(ABC):
    """
    Abstract interface for meeting capture providers.
    Concrete implementations: PlaywrightCaptureAdapter (local, default).
    Future: RecallAICaptureAdapter, MeetingBaaSAdapter.
    """

    @abstractmethod
    async def start(self, meeting_url: str, meeting_id: str) -> str:
        """
        Join the meeting and begin recording.
        Returns the path to the recording file (may be partial until stop() is called).
        """
        ...

    @abstractmethod
    async def stop(self) -> float:
        """
        Stop recording and return the duration in seconds.
        """
        ...

    @abstractmethod
    async def get_status(self) -> str:
        """
        Return the current normalized status string.
        One of: joining | waiting_for_admission | recording | meeting_ended | failed
        """
        ...
