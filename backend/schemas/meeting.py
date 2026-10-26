from pydantic import BaseModel, HttpUrl, field_validator
from typing import Literal, Optional
from datetime import datetime


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
        if value.scheme != "https" or value.host not in {"meet.google.com", "meet.googleusercontent.com"}:
            raise ValueError("URL must be an HTTPS Google Meet URL")
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


class MeetingStatusResponse(BaseModel):
    id: str
    status: str
    error_message: Optional[str]
