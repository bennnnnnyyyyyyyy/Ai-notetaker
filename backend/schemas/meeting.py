import re
from pydantic import BaseModel, HttpUrl, field_validator
from typing import Literal, Optional
from datetime import datetime
from urllib.parse import urlsplit

# Google Meet meeting codes look like abc-defg-hij (3-4-3 lowercase letters).
_MEET_CODE_PATH = re.compile(r"^/[a-z]{3}-[a-z]{4}-[a-z]{3}/?$")


def is_valid_meet_url(value: object) -> bool:
    """True only for https://meet.google.com/<abc-defg-hij> (query string allowed)."""
    parsed = urlsplit(str(value or ""))
    return (
        parsed.scheme == "https"
        and parsed.hostname == "meet.google.com"
        and parsed.port is None
        and not parsed.username
        and bool(_MEET_CODE_PATH.match(parsed.path.lower()))
    )


class MeetingCreate(BaseModel):
    url: HttpUrl
    campaign_id: Optional[str] = None
    meeting_type: Literal["discovery", "negotiation", "onboarding"]
    opener_name: Optional[str] = None
    closer_name: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    pre_booking_notes: Optional[str] = None

    @field_validator("url")
    @classmethod
    def validate_meet_url(cls, value: HttpUrl) -> HttpUrl:
        if not is_valid_meet_url(value):
            raise ValueError("URL must be an HTTPS Google Meet link such as https://meet.google.com/abc-defg-hij")
        return value


class MeetingResponse(BaseModel):
    id: str
    url: str
    campaign_id: Optional[str]
    meeting_type: str
    opener_name: Optional[str]
    closer_name: Optional[str]
    scheduled_at: Optional[datetime]
    status: str
    pre_booking_notes: Optional[str]
    error_message: Optional[str]
    created_at: str
    updated_at: str
    source_type: str = "google_meet"
    source_filename: Optional[str] = None


class MeetingStatusResponse(BaseModel):
    id: str
    status: str
    error_message: Optional[str]
