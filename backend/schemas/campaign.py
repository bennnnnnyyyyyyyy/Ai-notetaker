from pydantic import BaseModel
from typing import Optional


class CampaignCreate(BaseModel):
    name: str
    config_path: str   # relative path to YAML file
    config_version: str


class CampaignResponse(BaseModel):
    id: str
    name: str
    config_path: str
    config_version: str
    active: bool
    created_at: str
