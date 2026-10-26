import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
import aiosqlite

from backend.database import get_db
from backend.schemas.campaign import CampaignCreate, CampaignResponse

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM campaigns WHERE active = 1 ORDER BY name") as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute(
        "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return dict(row)


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    body: CampaignCreate,
    db: aiosqlite.Connection = Depends(get_db),
):
    campaigns_root = (Path(__file__).resolve().parent.parent / "campaigns").resolve()
    config_path = (campaigns_root / body.config_path).resolve()
    if campaigns_root not in config_path.parents or config_path.suffix.lower() not in {".yaml", ".yml"}:
        raise HTTPException(status_code=422, detail="Campaign config must be a YAML file under backend/campaigns")
    if not config_path.is_file():
        raise HTTPException(status_code=422, detail="Campaign config file does not exist")
    campaign_id = str(uuid.uuid4())
    await db.execute(
        """
        INSERT INTO campaigns (id, name, config_path, config_version)
        VALUES (?, ?, ?, ?)
        """,
        (campaign_id, body.name, str(config_path), body.config_version),
    )
    await db.commit()
    async with db.execute(
        "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
    ) as cur:
        row = await cur.fetchone()
    return dict(row)
