"""Campaign API routes — CRUD + session progression."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services import campaign_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CampaignCreate(BaseModel):
    name: str
    description: str = ""


class CampaignResponse(BaseModel):
    id: str
    name: str
    description: str
    session_ids: list[str]
    current_session_index: int
    character_ids: list[str]
    xp_pool: dict
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, c) -> CampaignResponse:
        return cls(
            id=c.id,
            name=c.name,
            description=c.description,
            session_ids=c.session_ids or [],
            current_session_index=c.current_session_index,
            character_ids=c.character_ids or [],
            xp_pool=c.xp_pool or {},
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
        )


class AttachSessionBody(BaseModel):
    session_id: str


class AdvanceSessionBody(BaseModel):
    new_session_name: str


class AwardXpBody(BaseModel):
    character_id: str
    xp: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(body: CampaignCreate, db: AsyncSession = Depends(get_db)):
    campaign = await campaign_service.create_campaign(body.name, body.description, db)
    return CampaignResponse.from_orm(campaign)


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    campaigns = await campaign_service.list_campaigns(db)
    return [CampaignResponse.from_orm(c) for c in campaigns]


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    campaign = await campaign_service.get_campaign(campaign_id, db)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignResponse.from_orm(campaign)


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import delete

    from app.models.campaign import Campaign
    await db.execute(delete(Campaign).where(Campaign.id == campaign_id))
    await db.commit()


@router.post("/{campaign_id}/sessions", response_model=CampaignResponse)
async def attach_session(
    campaign_id: str,
    body: AttachSessionBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        campaign = await campaign_service.attach_session(campaign_id, body.session_id, db)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return CampaignResponse.from_orm(campaign)


@router.post("/{campaign_id}/advance")
async def advance_campaign(
    campaign_id: str,
    body: AdvanceSessionBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await campaign_service.advance_to_next_session(
            campaign_id, body.new_session_name, db
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "campaign": CampaignResponse.from_orm(result["campaign"]),
        "new_session_id": result["new_session_id"],
        "characters_transferred": result["characters_transferred"],
    }


@router.post("/{campaign_id}/xp", response_model=CampaignResponse)
async def award_xp(
    campaign_id: str,
    body: AwardXpBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        campaign = await campaign_service.award_xp(
            campaign_id, body.character_id, body.xp, db
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return CampaignResponse.from_orm(campaign)
