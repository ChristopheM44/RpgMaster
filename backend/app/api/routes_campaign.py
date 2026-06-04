"""Campaign API routes — CRUD + session progression."""

from __future__ import annotations

import asyncio
import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.campaign import (
    AdvanceSessionBody,
    AttachSessionBody,
    AwardXpBody,
    CampaignCreate,
    CampaignResetResponse,
    CampaignResponse,
    ForgeDraftBody,
    ImportSourceBody,
    SynthesizeCanonBody,
    ValidateContractBody,
)
from app.services import campaign_dossier_service, campaign_service, chronicle_archive_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


async def _campaign_response(campaign, db: AsyncSession) -> CampaignResponse:
    summary = await campaign_dossier_service.public_summary(campaign, db)
    summaries = await campaign_service.session_summaries(campaign, db)
    return CampaignResponse.from_orm(campaign, summary, summaries)


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(body: CampaignCreate, db: AsyncSession = Depends(get_db)):
    campaign = await campaign_service.create_campaign(body.name, body.description, db)
    return await _campaign_response(campaign, db)


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    campaigns = await campaign_service.list_campaigns(db)
    responses = []
    for campaign in campaigns:
        responses.append(await _campaign_response(campaign, db))
    return responses


@router.post("/import/preview")
async def preview_chronicle_import(body: dict, db: AsyncSession = Depends(get_db)):
    try:
        return await chronicle_archive_service.preview_import(body, db)
    except chronicle_archive_service.ChronicleArchiveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/import")
async def import_chronicle(body: dict, db: AsyncSession = Depends(get_db)):
    try:
        result = await chronicle_archive_service.import_chronicle(body, db)
    except chronicle_archive_service.ChronicleArchiveConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), "conflicts": exc.conflicts},
        ) from exc
    except chronicle_archive_service.ChronicleArchiveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "campaign": await _campaign_response(result.campaign, db),
        "active_session_id": result.active_session_id,
        "imported": result.imported,
        "warnings": result.warnings,
    }


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    campaign = await campaign_service.get_campaign(campaign_id, db)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return await _campaign_response(campaign, db)


@router.get("/{campaign_id}/export")
async def export_chronicle(campaign_id: str, db: AsyncSession = Depends(get_db)):
    try:
        archive = await chronicle_archive_service.export_chronicle(campaign_id, db)
    except chronicle_archive_service.ChronicleArchiveNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    filename = chronicle_archive_service.safe_archive_filename(
        str(archive.get("campaign", {}).get("name") or campaign_id)
    )
    return Response(
        content=json.dumps(archive, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    try:
        await campaign_service.delete_campaign(campaign_id, db)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{campaign_id}/reset", response_model=CampaignResetResponse)
async def reset_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await campaign_service.reset_campaign(campaign_id, db)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return CampaignResetResponse(
        campaign=await _campaign_response(result["campaign"], db),
        session_id=result["session_id"],
        characters_reset=result["characters_reset"],
        sessions_removed=result["sessions_removed"],
    )


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
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return campaign_dossier_service.response_for_draft(dossier)


@router.post("/{campaign_id}/forge-draft/jobs")
async def start_campaign_forge_job(
    campaign_id: str,
    body: ForgeDraftBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        job, should_start = await campaign_dossier_service.begin_forge_job(
            campaign_id,
            body.brief,
            body.options,
            db,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if should_start:
        session_factory = request.app.state.db_session_factory
        asyncio.create_task(
            campaign_dossier_service.run_forge_job(
                job["job_id"],
                campaign_id,
                body.brief,
                body.options,
                session_factory,
            )
        )
    return job


@router.get("/{campaign_id}/forge-draft/jobs/{job_id}")
async def get_campaign_forge_job(
    campaign_id: str,
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await campaign_dossier_service.forge_job_status(campaign_id, job_id, db)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


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


@router.get("/{campaign_id}/personas")
async def get_campaign_personas(campaign_id: str, db: AsyncSession = Depends(get_db)):
    """Liste les personas connues d'une campagne (PNJ, monstres, compagnons).

    Retourne un dict ``{npcs, monsters, companions}`` où chaque entrée est une
    persona Pydantic dumpée en JSON. Utile pour debug / admin / inspection MJ.

    NB : les secrets et motivations cachées sont inclus (GM-only). Ne pas
    exposer cet endpoint au-delà du contexte MJ.
    """
    personas = await campaign_dossier_service.list_personas(campaign_id, db)
    return {
        "campaign_id": campaign_id,
        "npcs": [p.model_dump(mode="json") for p in personas["npcs"]],
        "monsters": [p.model_dump(mode="json") for p in personas["monsters"]],
        "companions": [p.model_dump(mode="json") for p in personas["companions"]],
        "counts": {
            "npcs": len(personas["npcs"]),
            "monsters": len(personas["monsters"]),
            "companions": len(personas["companions"]),
        },
    }


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
    return await _campaign_response(campaign, db)


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
        "campaign": await _campaign_response(result["campaign"], db),
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
        campaign = await campaign_service.award_xp(campaign_id, body.character_id, body.xp, db)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return await _campaign_response(campaign, db)
