"""Live silence detection for an in-progress recording.

FFmpeg writes the WAV as a stream, so the header's length fields are not valid
until the file is closed. This module therefore ignores the header and reads the
most recent raw 16-bit mono samples straight from the end of the file.
"""

import math
import time
from pathlib import Path
from typing import Callable, Optional

SAMPLE_RATE = 16000
BYTES_PER_SECOND = SAMPLE_RATE * 2  # 16 kHz, mono, 16-bit
WAV_HEADER_BYTES = 44

# Quiet speech sits well above this; the silent recordings on file were -91 to -108 dB.
SILENCE_THRESHOLD_DB = -65.0

SILENCE_MESSAGE = (
    "No sound has reached the recording for {minutes} minute(s). Check that Windows "
    "plays the meeting audio to CABLE Input (VB-Audio Virtual Cable), then check the call."
)


def tail_level_db(path: Path, seconds: float = 10.0) -> Optional[float]:
    """RMS level in dB (0 dB = full scale) of the last `seconds` of a growing WAV.

    Returns None when there is not yet a full second of audio to judge.
    """
    try:
        size = Path(path).stat().st_size
    except OSError:
        return None
    available = size - WAV_HEADER_BYTES
    if available < BYTES_PER_SECOND:
        return None
    wanted = min(int(seconds * BYTES_PER_SECOND), available)
    wanted -= wanted % 2
    try:
        with open(path, "rb") as handle:
            handle.seek(size - wanted)
            data = handle.read(wanted)
    except OSError:
        return None
    count = len(data) // 2
    if count == 0:
        return None
    total = 0
    for i in range(0, count * 2, 2):
        sample = int.from_bytes(data[i:i + 2], "little", signed=True)
        total += sample * sample
    rms = math.sqrt(total / count) / 32768.0
    return 20 * math.log10(rms) if rms > 0 else -120.0


class SilenceWatchdog:
    """Tracks how long a recording has been silent and when to warn or clear."""

    def __init__(self, warn_after_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic):
        self._warn_after = warn_after_seconds
        self._clock = clock
        self._silent_since: Optional[float] = None
        self.warning_active = False

    def update(self, level_db: Optional[float]) -> Optional[str]:
        """Feed one level reading.

        Returns "warn" when the warning should be shown, "clear" when sound has
        returned after a warning, otherwise None. Unknown levels change nothing.
        """
        if level_db is None:
            return None
        now = self._clock()
        if level_db > SILENCE_THRESHOLD_DB:
            self._silent_since = None
            if self.warning_active:
                self.warning_active = False
                return "clear"
            return None
        if self._silent_since is None:
            self._silent_since = now
        if not self.warning_active and now - self._silent_since >= self._warn_after:
            self.warning_active = True
            return "warn"
        return None

    def silent_minutes(self) -> int:
        if self._silent_since is None:
            return 0
        return max(1, round((self._clock() - self._silent_since) / 60))
