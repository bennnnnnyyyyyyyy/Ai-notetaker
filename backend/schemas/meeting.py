from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime


class MeetingCreate(BaseModel):
    url: str
    campaign_id: Optional[str] = None
    meeting_type: str  # discovery | negotiation | onboarding
    opener_name: Optional[str] = None
    closer_name: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    pre_booking_notes: Optional[str] = None


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
