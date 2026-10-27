from pydantic import BaseModel


class BookingImportRequest(BaseModel):
    confirm: bool = False
    campaign_id: str | None = None
    company: str | None = None
