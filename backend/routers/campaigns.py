import uuid
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
    campaign_id = str(uuid.uuid4())
    await db.execute(
        """
        INSERT INTO campaigns (id, name, config_path, config_version)
        VALUES (?, ?, ?, ?)
        """,
        (campaign_id, body.name, body.config_path, body.config_version),
    )
    await db.commit()
    async with db.execute(
        "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
    ) as cur:
        row = await cur.fetchone()
    return dict(row)
