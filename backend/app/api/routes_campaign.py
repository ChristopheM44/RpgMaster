"""Campaign API routes — CRUD + session progression."""
from __future__ import annotations

from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services import campaign_dossier_service, campaign_service

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
    tagline: str = ""
    generation_status: str = "empty"
    active_chapter: dict = Field(default_factory=dict)
    progress: dict = Field(default_factory=dict)
    counts: dict = Field(default_factory=dict)

    @classmethod
    def from_orm(cls, c, summary: Optional[dict] = None) -> CampaignResponse:
        summary = summary or {}
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
            tagline=summary.get("tagline", c.description or ""),
            generation_status=summary.get("generation_status", "empty"),
            active_chapter=summary.get("active_chapter", {}),
            progress=summary.get("progress", {"done": 0, "total": 1}),
            counts=summary.get("counts", {}),
        )


class AttachSessionBody(BaseModel):
    session_id: str


class AdvanceSessionBody(BaseModel):
    new_session_name: str


class AwardXpBody(BaseModel):
    character_id: str
    xp: int


class ImportSourceBody(BaseModel):
    kind: str
    title: Optional[str] = None
    url: Optional[str] = None
    content: Optional[str] = None
    filename: Optional[str] = None


class ForgeDraftBody(BaseModel):
    brief: dict = Field(default_factory=dict)
    options: dict = Field(default_factory=dict)


class ValidateContractBody(BaseModel):
    player_contract: dict = Field(default_factory=dict)


class SynthesizeCanonBody(BaseModel):
    game_state: dict = Field(default_factory=dict)
    recent_messages: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(body: CampaignCreate, db: AsyncSession = Depends(get_db)):
    campaign = await campaign_service.create_campaign(body.name, body.description, db)
    summary = await campaign_dossier_service.public_summary(campaign, db)
    return CampaignResponse.from_orm(campaign, summary)


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    campaigns = await campaign_service.list_campaigns(db)
    responses = []
    for campaign in campaigns:
        summary = await campaign_dossier_service.public_summary(campaign, db)
        responses.append(CampaignResponse.from_orm(campaign, summary))
    return responses


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    campaign = await campaign_service.get_campaign(campaign_id, db)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    summary = await campaign_dossier_service.public_summary(campaign, db)
    return CampaignResponse.from_orm(campaign, summary)


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import delete

    from app.models.campaign import Campaign
    await db.execute(delete(Campaign).where(Campaign.id == campaign_id))
    await db.commit()


@router.post("/{campaign_id}/import-source")
async def import_campaign_source(
    campaign_id: str,
    body: ImportSourceBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await campaign_dossier_service.import_source(
            campaign_id,
            body.model_dump(exclude_none=True),
            db,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"Import URL impossible: {exc}")


@router.post("/{campaign_id}/forge-draft")
async def forge_campaign_draft(
    campaign_id: str,
    body: ForgeDraftBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        dossier = await campaign_dossier_service.forge_draft(
            campaign_id,
            body.brief,
            body.options,
            db,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return campaign_dossier_service.response_for_draft(dossier)


@router.post("/{campaign_id}/validate-contract")
async def validate_campaign_contract(
    campaign_id: str,
    body: ValidateContractBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        dossier = await campaign_dossier_service.validate_contract(
            campaign_id,
            body.player_contract,
            db,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return campaign_dossier_service.response_for_draft(dossier)


@router.get("/{campaign_id}/scenario")
async def get_campaign_scenario(campaign_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await campaign_dossier_service.scenario_view(campaign_id, db)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{campaign_id}/gm-dossier")
async def get_campaign_gm_dossier(campaign_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await campaign_dossier_service.gm_dossier_view(campaign_id, db)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{campaign_id}/synthesize-canon")
async def synthesize_campaign_canon(
    campaign_id: str,
    body: SynthesizeCanonBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        dossier = await campaign_dossier_service.synthesize_canon(
            campaign_id,
            body.game_state,
            body.recent_messages,
            db,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return campaign_dossier_service.response_for_draft(dossier)


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
    summary = await campaign_dossier_service.public_summary(campaign, db)
    return CampaignResponse.from_orm(campaign, summary)


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
    summary = await campaign_dossier_service.public_summary(result["campaign"], db)
    return {
        "campaign": CampaignResponse.from_orm(result["campaign"], summary),
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
    summary = await campaign_dossier_service.public_summary(campaign, db)
    return CampaignResponse.from_orm(campaign, summary)
