"""Idempotent repairs for visual map/scene coherence."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.game.scene_theme import coerce_scene_theme, infer_scene_theme


def visual_context_corpus(state_data: dict[str, Any]) -> str:
    journal = state_data.get("adventure_journal") if isinstance(state_data, dict) else {}
    journal = journal if isinstance(journal, dict) else {}
    scene = state_data.get("current_scene") if isinstance(state_data, dict) else {}
    scene = scene if isinstance(scene, dict) else {}
    campaign = state_data.get("campaign_context") if isinstance(state_data, dict) else {}
    campaign = campaign if isinstance(campaign, dict) else {}
    chapter = campaign.get("active_chapter") if isinstance(campaign, dict) else {}
    chapter = chapter if isinstance(chapter, dict) else {}
    opening_scene = chapter.get("opening_scene") if isinstance(chapter, dict) else {}
    opening_scene = opening_scene if isinstance(opening_scene, dict) else {}

    parts: list[Any] = [
        journal.get("location_region"),
        journal.get("location_place"),
        journal.get("location_venue"),
        journal.get("weather"),
        scene.get("terrain"),
        scene.get("scene_theme"),
        scene.get("description"),
        opening_scene.get("region"),
        opening_scene.get("place"),
        opening_scene.get("venue"),
        opening_scene.get("description"),
        opening_scene.get("weather"),
    ]
    for poi in scene.get("pois", []) or []:
        if isinstance(poi, dict):
            parts.extend([poi.get("name"), poi.get("description"), poi.get("action_hint")])
    for exit_ in scene.get("exits", []) or []:
        if isinstance(exit_, dict):
            parts.extend([exit_.get("label"), exit_.get("leads_to"), exit_.get("description")])
    return " ".join(str(part or "") for part in parts)


def repair_state_visual_coherence(state_data: dict[str, Any]) -> bool:
    """Repair in-memory state visuals. Returns True when state_data changed."""
    if not isinstance(state_data, dict):
        return False
    scene = state_data.get("current_scene")
    if not isinstance(scene, dict):
        return False

    corpus = visual_context_corpus(state_data)
    repaired_theme = coerce_scene_theme(scene.get("scene_theme"), corpus)
    changed = False
    if scene.get("scene_theme") != repaired_theme:
        scene["scene_theme"] = repaired_theme
        changed = True

    world_maps = state_data.get("world_maps")
    if isinstance(world_maps, dict):
        region_map = world_maps.get("region_map")
        if _strip_incoherent_coastline(region_map, corpus):
            changed = True

    return changed


async def repair_campaign_visual_coherence_for_session(
    session_id: str,
    state_data: dict[str, Any],
    db: AsyncSession | None,
) -> bool:
    if db is None or not isinstance(state_data, dict):
        return False

    from app.services import campaign_dossier_service

    campaign = await campaign_dossier_service.campaign_for_session(session_id, db)
    if campaign is None:
        return False
    dossier = await campaign_dossier_service.get_dossier(campaign.id, db)
    if dossier is None or not isinstance(dossier.gm_dossier, dict):
        return False

    gm_dossier = campaign_dossier_service.sanitize_gm_dossier_map_defaults(
        deepcopy(dossier.gm_dossier)
    )
    region_map = gm_dossier.get("region_map")
    corpus = visual_context_corpus(state_data)
    if not _strip_incoherent_coastline(region_map, corpus):
        return False

    await campaign_dossier_service.update_campaign_maps(
        campaign.id,
        db,
        region_map=region_map,
    )
    return True


async def repair_visual_coherence_for_session(
    session_id: str,
    state_data: dict[str, Any],
    db: AsyncSession | None,
) -> bool:
    state_changed = repair_state_visual_coherence(state_data)
    await repair_campaign_visual_coherence_for_session(session_id, state_data, db)
    return state_changed


def _strip_incoherent_coastline(region_map: Any, corpus: str) -> bool:
    if not isinstance(region_map, dict):
        return False
    decor = region_map.get("decor")
    if not isinstance(decor, dict) or not decor.get("coastline"):
        return False
    if infer_scene_theme(corpus) != "desert":
        return False
    decor.pop("coastline", None)
    return True
