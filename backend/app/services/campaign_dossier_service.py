"""Campaign dossier service — player-safe contracts and private GM dossiers."""
from __future__ import annotations

import html
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Optional

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.campaign_forge_agent import CampaignForgeAgent
from app.models.campaign import Campaign
from app.models.campaign_dossier import CampaignDossier
from app.models.character import Character
from app.security_url import validate_public_http_url

logger = logging.getLogger(__name__)

VALID_STATUSES = {"empty", "drafting", "draft", "validated", "failed"}
SOURCE_MAX_CHARS = 120_000
URL_MAX_BYTES = 2_000_000
_SYNTHESIS_IN_FLIGHT: set[str] = set()


def empty_played_canon() -> dict[str, Any]:
    return {
        "established_facts": [],
        "player_decisions": [],
        "quests": [],
        "npc_relationships": [],
        "revealed_secrets": [],
        "plan_changes": [],
        "rolling_summary": "",
        "chapter_progression": [],
    }


async def get_dossier(campaign_id: str, db: AsyncSession) -> Optional[CampaignDossier]:
    result = await db.execute(
        select(CampaignDossier).where(CampaignDossier.campaign_id == campaign_id)
    )
    return result.scalar_one_or_none()


async def get_or_create_dossier(campaign_id: str, db: AsyncSession) -> CampaignDossier:
    dossier = await get_dossier(campaign_id, db)
    if dossier is not None:
        return dossier
    dossier = CampaignDossier(
        id=str(uuid.uuid4()),
        campaign_id=campaign_id,
        player_contract={},
        gm_dossier={},
        played_canon=empty_played_canon(),
        import_sources=[],
        active_chapter_id="",
        generation_status="empty",
    )
    db.add(dossier)
    await db.flush()
    return dossier


async def import_source(
    campaign_id: str,
    payload: dict[str, Any],
    db: AsyncSession,
) -> dict[str, Any]:
    campaign = await _get_campaign_or_raise(campaign_id, db)
    dossier = await get_or_create_dossier(campaign.id, db)

    kind = str(payload.get("kind") or "").strip()
    if kind not in {"url", "text", "file_text"}:
        raise ValueError("kind must be one of: url, text, file_text")

    title = str(payload.get("title") or payload.get("filename") or "Source importée").strip()
    url = str(payload.get("url") or "").strip()
    filename = str(payload.get("filename") or "").strip()
    content = str(payload.get("content") or "")

    if kind == "url":
        if not url:
            raise ValueError("url is required for URL imports")
        title = title if title != "Source importée" else url
        content = await _fetch_url_text(url)
    elif not content.strip():
        raise ValueError("content is required for text imports")

    source = {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "title": title[:180],
        "url": url or None,
        "filename": filename or None,
        "content": _clip(content, SOURCE_MAX_CHARS),
        "created_at": datetime.utcnow().isoformat(),
    }
    sources = list(dossier.import_sources or [])
    sources.append(source)
    dossier.import_sources = sources
    if dossier.generation_status == "empty":
        dossier.generation_status = "draft"

    await db.commit()
    await db.refresh(dossier)
    return _source_metadata(source, len(sources))


async def forge_draft(
    campaign_id: str,
    brief: dict[str, Any],
    options: dict[str, Any],
    db: AsyncSession,
    agent: Optional[CampaignForgeAgent] = None,
) -> CampaignDossier:
    campaign = await _get_campaign_or_raise(campaign_id, db)
    dossier = await get_or_create_dossier(campaign.id, db)
    dossier.generation_status = "drafting"
    await db.flush()

    campaign_data = {"id": campaign.id, "name": campaign.name, "description": campaign.description}
    sources_for_agent = [
        {k: v for k, v in source.items() if k in {"kind", "title", "url", "filename", "content"}}
        for source in list(dossier.import_sources or [])
    ]

    try:
        forge_agent = agent or CampaignForgeAgent()
        generated = await forge_agent.forge_dossier(
            campaign=campaign_data,
            brief=brief,
            options=options,
            import_sources=sources_for_agent,
        )
    except Exception as exc:
        logger.warning("Campaign forge failed, using deterministic fallback: %s", exc)
        generated = _fallback_dossier(campaign, brief, options, dossier.import_sources or [])

    contract = sanitize_player_contract(
        generated.get("player_contract", {}),
        campaign,
        brief=brief,
    )
    gm_dossier = sanitize_gm_dossier(
        generated.get("gm_dossier", {}),
        campaign,
        contract,
    )
    played_canon = sanitize_played_canon(generated.get("played_canon", {}))
    active_chapter_id = str(generated.get("active_chapter_id") or "").strip()
    if not active_chapter_id:
        active_chapter_id = _first_chapter_id(contract, gm_dossier)

    dossier.player_contract = contract
    dossier.gm_dossier = gm_dossier
    dossier.played_canon = played_canon
    dossier.active_chapter_id = active_chapter_id
    dossier.generation_status = "draft"

    await db.commit()
    await db.refresh(dossier)
    return dossier


async def validate_contract(
    campaign_id: str,
    contract_payload: dict[str, Any],
    db: AsyncSession,
) -> CampaignDossier:
    campaign = await _get_campaign_or_raise(campaign_id, db)
    dossier = await get_or_create_dossier(campaign.id, db)
    contract = sanitize_player_contract(
        contract_payload or dossier.player_contract or {},
        campaign,
        brief={},
    )
    dossier.player_contract = contract
    if not dossier.gm_dossier:
        dossier.gm_dossier = sanitize_gm_dossier({}, campaign, contract)
    if not dossier.played_canon:
        dossier.played_canon = empty_played_canon()
    dossier.active_chapter_id = dossier.active_chapter_id or _first_chapter_id(
        contract,
        dossier.gm_dossier,
    )
    dossier.generation_status = "validated"
    await db.commit()
    await db.refresh(dossier)
    return dossier


async def scenario_view(campaign_id: str, db: AsyncSession) -> dict[str, Any]:
    campaign = await _get_campaign_or_raise(campaign_id, db)
    dossier = await get_dossier(campaign.id, db)
    if dossier is None:
        contract = sanitize_player_contract({}, campaign, brief={})
        return {
            "campaign_id": campaign.id,
            "generation_status": "empty",
            "player_contract": contract,
            "timeline": contract["visible_chapters"],
            "current_chapter": contract["visible_chapters"][0],
            "known_objectives": contract["known_objectives"],
            "quests": [],
            "played_summary": "",
        }

    contract = sanitize_player_contract(dossier.player_contract or {}, campaign, brief={})
    canon = sanitize_played_canon(dossier.played_canon or {})
    timeline = _apply_chapter_progress(contract["visible_chapters"], canon)
    current = _current_public_chapter(timeline, dossier.active_chapter_id)
    return {
        "campaign_id": campaign.id,
        "generation_status": dossier.generation_status,
        "player_contract": {**contract, "visible_chapters": timeline},
        "timeline": timeline,
        "current_chapter": current,
        "known_objectives": contract.get("known_objectives", []),
        "quests": _public_quests(canon, dossier.gm_dossier or {}),
        "played_summary": canon.get("rolling_summary") or contract.get("played_summary") or "",
    }


async def gm_dossier_view(campaign_id: str, db: AsyncSession) -> dict[str, Any]:
    campaign = await _get_campaign_or_raise(campaign_id, db)
    dossier = await get_dossier(campaign.id, db)
    if dossier is None:
        contract = sanitize_player_contract({}, campaign, brief={})
        return {
            "campaign_id": campaign.id,
            "generation_status": "empty",
            "active_chapter_id": "",
            "gm_dossier": sanitize_gm_dossier({}, campaign, contract),
        }

    contract = sanitize_player_contract(dossier.player_contract or {}, campaign, brief={})
    return {
        "campaign_id": campaign.id,
        "generation_status": dossier.generation_status,
        "active_chapter_id": dossier.active_chapter_id,
        "gm_dossier": sanitize_gm_dossier(dossier.gm_dossier or {}, campaign, contract),
    }


async def public_summary(campaign: Campaign, db: AsyncSession) -> dict[str, Any]:
    dossier = await get_dossier(campaign.id, db)
    character_count = await _current_session_character_count(campaign, db)
    if dossier is None:
        return _summary_from_contract(campaign, None, character_count=character_count)
    return _summary_from_contract(campaign, dossier, character_count=character_count)


async def synthesize_canon(
    campaign_id: str,
    game_state: dict[str, Any],
    recent_messages: list[dict[str, Any]],
    db: AsyncSession,
    agent: Optional[CampaignForgeAgent] = None,
) -> CampaignDossier:
    campaign = await _get_campaign_or_raise(campaign_id, db)
    dossier = await get_or_create_dossier(campaign.id, db)
    current_canon = sanitize_played_canon(dossier.played_canon or {})
    try:
        forge_agent = agent or CampaignForgeAgent()
        next_canon = await forge_agent.synthesize_canon(
            player_contract=dossier.player_contract or {},
            gm_dossier=dossier.gm_dossier or {},
            played_canon=current_canon,
            game_state=game_state or {},
            recent_messages=recent_messages or [],
        )
    except Exception as exc:
        logger.warning("Campaign canon synthesis failed, using deterministic merge: %s", exc)
        next_canon = _fallback_canon(current_canon, game_state or {}, recent_messages or [])

    canon = sanitize_played_canon(next_canon)
    dossier.played_canon = canon
    contract = sanitize_player_contract(dossier.player_contract or {}, campaign, brief={})
    if canon.get("rolling_summary"):
        contract["played_summary"] = canon["rolling_summary"]
    contract["visible_chapters"] = _apply_chapter_progress(contract["visible_chapters"], canon)
    dossier.player_contract = contract

    await db.commit()
    await db.refresh(dossier)
    return dossier


async def synthesize_canon_for_session(
    session_id: str,
    game_state: dict[str, Any],
    recent_messages: list[dict[str, Any]],
    db: AsyncSession,
) -> Optional[CampaignDossier]:
    campaign = await campaign_for_session(session_id, db)
    if campaign is None:
        return None
    key = campaign.id
    if key in _SYNTHESIS_IN_FLIGHT:
        return await get_dossier(campaign.id, db)
    _SYNTHESIS_IN_FLIGHT.add(key)
    try:
        dossier = await synthesize_canon(campaign.id, game_state, recent_messages, db)
        context = game_state.get("campaign_context")
        if isinstance(context, dict):
            context["played_canon"] = dossier.played_canon
            context["player_contract"]["played_summary"] = (
                dossier.player_contract or {}
            ).get("played_summary", "")
        return dossier
    finally:
        _SYNTHESIS_IN_FLIGHT.discard(key)


async def campaign_for_session(session_id: str, db: AsyncSession) -> Optional[Campaign]:
    result = await db.execute(select(Campaign).order_by(Campaign.created_at.desc()))
    for campaign in result.scalars().all():
        if session_id in (campaign.session_ids or []):
            return campaign
    return None


async def compile_campaign_context_for_session(
    session_id: str,
    db: AsyncSession,
) -> Optional[dict[str, Any]]:
    campaign = await campaign_for_session(session_id, db)
    if campaign is None:
        return None
    dossier = await get_dossier(campaign.id, db)
    if dossier is None or dossier.generation_status != "validated":
        return None

    contract = sanitize_player_contract(dossier.player_contract or {}, campaign, brief={})
    canon = sanitize_played_canon(dossier.played_canon or {})
    active_chapter = _active_chapter_for_context(
        dossier.gm_dossier or {},
        contract,
        dossier.active_chapter_id,
    )
    characters = await _session_characters(session_id, db)

    return {
        "campaign_id": campaign.id,
        "player_contract": contract,
        "active_chapter": active_chapter,
        "played_canon": canon,
        "known_quests": _public_quests(canon, dossier.gm_dossier or {}),
        "continuity": {
            "played_summary": canon.get("rolling_summary") or contract.get("played_summary") or "",
            "established_facts": canon.get("established_facts", []),
            "player_decisions": canon.get("player_decisions", []),
            "revealed_secrets": canon.get("revealed_secrets", []),
            "plan_changes": canon.get("plan_changes", []),
        },
        "party_hooks": [
            {
                "character_id": c.id,
                "name": c.name,
                "class": c.char_class,
                "background": c.background,
            }
            for c in characters
        ],
    }


def response_for_draft(dossier: CampaignDossier) -> dict[str, Any]:
    return {
        "campaign_id": dossier.campaign_id,
        "generation_status": dossier.generation_status,
        "player_contract": dossier.player_contract or {},
        "active_chapter_id": dossier.active_chapter_id,
    }


def source_count_response(dossier: CampaignDossier) -> dict[str, Any]:
    return {
        "campaign_id": dossier.campaign_id,
        "generation_status": dossier.generation_status,
        "source_count": len(dossier.import_sources or []),
    }


def sanitize_player_contract(
    data: dict[str, Any],
    campaign: Campaign,
    brief: dict[str, Any],
) -> dict[str, Any]:
    title = _text(
        data.get("title") or brief.get("title") or brief.get("name") or campaign.name,
        100,
    )
    pitch = _text(
        data.get("pitch_public") or brief.get("pitch_public") or brief.get("pitch")
        or campaign.description or "Une nouvelle chronique attend d'être jouée.",
        700,
    )
    tones = _string_list(data.get("tones") or brief.get("tones") or brief.get("tonalities"), 5)
    duration = _text(data.get("duration") or brief.get("duration") or "3-5 sessions", 80)
    hook = _text(data.get("hook") or brief.get("hook") or pitch, 450)
    chapters = _sanitize_visible_chapters(data.get("visible_chapters"), title)
    objectives = _string_list(data.get("known_objectives") or brief.get("known_objectives"), 8)
    if not objectives:
        objectives = ["Découvrir ce qui menace la région."]
    return {
        "title": title,
        "pitch_public": pitch,
        "tones": tones,
        "duration": duration,
        "hook": hook,
        "visible_chapters": chapters,
        "known_objectives": objectives,
        "played_summary": _text(data.get("played_summary") or "", 1200),
    }


def sanitize_gm_dossier(
    data: dict[str, Any],
    campaign: Campaign,
    contract: dict[str, Any],
) -> dict[str, Any]:
    chapters = data.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        chapters = [
            {
                "id": ch.get("id", f"chapter_{i + 1}"),
                "title": ch.get("title", f"Chapitre {i + 1}"),
                "state": ch.get("state", "planned"),
                "objective": "Faire émerger la situation par les choix des joueurs.",
                "stakes": contract.get("hook", ""),
                "initial_state": ch.get("summary", ""),
                "key_locations": [],
                "involved_npcs": [],
                "clues": [],
                "secrets": [],
                "complications": [],
                "possible_exits": [],
                "indicative_dcs": [],
                "possible_srd_encounters": [],
            }
            for i, ch in enumerate(contract.get("visible_chapters", []))
        ]
    return {
        "narrative_arc": _text(data.get("narrative_arc") or campaign.description, 2000),
        "chapters": [_sanitize_private_chapter(ch, i) for i, ch in enumerate(chapters)],
        "important_npcs": _generic_list(data.get("important_npcs")),
        "locations": _generic_list(data.get("locations")),
        "factions": _generic_list(data.get("factions")),
        "secrets": _generic_list(data.get("secrets")),
        "revelations": _generic_list(data.get("revelations")),
        "fronts": _generic_list(data.get("fronts")),
        "quests": _generic_list(data.get("quests")),
        "complications": _generic_list(data.get("complications")),
        "clues": _generic_list(data.get("clues")),
        "light_mechanics": _generic_list(data.get("light_mechanics")),
    }


def sanitize_played_canon(data: dict[str, Any]) -> dict[str, Any]:
    canon = empty_played_canon()
    if not isinstance(data, dict):
        return canon
    for key in (
        "established_facts",
        "player_decisions",
        "quests",
        "npc_relationships",
        "revealed_secrets",
        "plan_changes",
        "chapter_progression",
    ):
        canon[key] = _generic_list(data.get(key))
    canon["rolling_summary"] = _text(data.get("rolling_summary") or "", 2000)
    return canon


async def _get_campaign_or_raise(campaign_id: str, db: AsyncSession) -> Campaign:
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise KeyError(f"Campaign {campaign_id} not found")
    return campaign


async def _session_characters(session_id: str, db: AsyncSession) -> list[Character]:
    result = await db.execute(select(Character).where(Character.session_id == session_id))
    return list(result.scalars().all())


async def _fetch_url_text(url: str) -> str:
    safe_url = await validate_public_http_url(url)
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
        response = await client.get(safe_url)
        if response.is_redirect or 300 <= response.status_code < 400:
            raise ValueError("URL redirects are not allowed.")
        response.raise_for_status()
        raw = response.content[:URL_MAX_BYTES]
    text = raw.decode(response.encoding or "utf-8", errors="replace")
    return _strip_html(text)


def _strip_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _fallback_dossier(
    campaign: Campaign,
    brief: dict[str, Any],
    options: dict[str, Any],
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    title = _text(brief.get("title") or brief.get("name") or campaign.name, 100)
    pitch = _text(
        brief.get("pitch_public") or brief.get("pitch") or campaign.description
        or "Une menace ancienne remue dans l'ombre.",
        700,
    )
    tones = _string_list(brief.get("tones") or brief.get("tonalities") or options.get("tones"), 5)
    if not tones:
        tones = ["Mystère", "Exploration"]
    duration = _text(brief.get("duration") or options.get("duration") or "3-5 sessions", 80)
    public_hook = _text(brief.get("hook") or pitch, 450)
    if sources:
        first = sources[0]
        public_hook = _text(first.get("title") or public_hook, 450)
    chapters = [
        {
            "id": "chapter_1",
            "num": "I",
            "title": "L'appel de l'aventure",
            "state": "active",
            "sessions": 0,
            "summary": public_hook,
        },
        {
            "id": "chapter_2",
            "num": "II",
            "title": "La piste s'épaissit",
            "state": "planned",
            "sessions": 0,
            "summary": "Les premières réponses ouvrent plusieurs chemins.",
        },
        {
            "id": "chapter_3",
            "num": "III",
            "title": "Le choix décisif",
            "state": "planned",
            "sessions": 0,
            "summary": "La campagne se conclura selon les décisions du groupe.",
        },
    ]
    return {
        "player_contract": {
            "title": title,
            "pitch_public": pitch,
            "tones": tones,
            "duration": duration,
            "hook": public_hook,
            "visible_chapters": chapters,
            "known_objectives": ["Suivre l'accroche et établir les premières alliances."],
            "played_summary": "",
        },
        "gm_dossier": {
            "narrative_arc": pitch,
            "chapters": [
                {
                    "id": ch["id"],
                    "title": ch["title"],
                    "state": ch["state"],
                    "objective": "Présenter une situation ouverte et laisser le groupe choisir.",
                    "stakes": public_hook,
                    "initial_state": ch["summary"],
                    "key_locations": [],
                    "involved_npcs": [],
                    "clues": [],
                    "secrets": ["À définir selon les choix de jeu."],
                    "complications": [],
                    "possible_exits": [],
                    "indicative_dcs": [{"label": "Lire la situation", "ability": "wis", "dc": 13}],
                    "possible_srd_encounters": ["bandit"],
                }
                for ch in chapters
            ],
            "important_npcs": [],
            "locations": [],
            "factions": [],
            "secrets": [],
            "revelations": [],
            "fronts": [],
            "quests": [],
            "complications": [],
            "clues": [],
            "light_mechanics": [],
        },
        "played_canon": empty_played_canon(),
        "active_chapter_id": "chapter_1",
    }


def _fallback_canon(
    canon: dict[str, Any],
    game_state: dict[str, Any],
    recent_messages: list[dict[str, Any]],
) -> dict[str, Any]:
    merged = sanitize_played_canon(canon)
    event = game_state.get("canon_event") if isinstance(game_state, dict) else None
    if isinstance(event, dict):
        _append_unique(merged["established_facts"], event.get("established_fact"))
        _append_unique(merged["player_decisions"], event.get("player_decision"))
        _append_unique(merged["plan_changes"], event.get("plan_change"))
        _append_unique(merged["revealed_secrets"], event.get("revealed_secret"))
        if event.get("rolling_summary"):
            merged["rolling_summary"] = _text(event["rolling_summary"], 2000)
    if game_state.get("quests"):
        merged["quests"] = _generic_list(game_state.get("quests"))
    if not merged["rolling_summary"] and recent_messages:
        last = recent_messages[-1]
        merged["rolling_summary"] = _text(last.get("content") or last.get("text") or "", 500)
    return merged


def _summary_from_contract(
    campaign: Campaign,
    dossier: Optional[CampaignDossier],
    character_count: Optional[int] = None,
) -> dict[str, Any]:
    if dossier is None:
        contract = sanitize_player_contract({}, campaign, brief={})
        status = "empty"
        canon = empty_played_canon()
    else:
        contract = sanitize_player_contract(dossier.player_contract or {}, campaign, brief={})
        status = dossier.generation_status
        canon = sanitize_played_canon(dossier.played_canon or {})
    chapters = _apply_chapter_progress(contract.get("visible_chapters", []), canon)
    current = _current_public_chapter(chapters, dossier.active_chapter_id if dossier else "")
    total = len(chapters)
    done = len([ch for ch in chapters if ch.get("state") == "done"])
    quests = _public_quests(canon, dossier.gm_dossier if dossier else {})
    return {
        "tagline": contract.get("pitch_public") or campaign.description,
        "generation_status": status,
        "active_chapter": current,
        "progress": {"done": done, "total": max(total, 1)},
        "counts": {
            "sessions": len(campaign.session_ids or []),
            "characters": (
                character_count
                if character_count is not None
                else len(campaign.character_ids or [])
            ),
            "quests_active": len([q for q in quests if q.get("status", "active") == "active"]),
            "quests_done": len([q for q in quests if q.get("status") == "completed"]),
            "chronicle_entries": len(canon.get("npc_relationships", []))
            + len(canon.get("established_facts", [])),
            "npcs": len((dossier.gm_dossier or {}).get("important_npcs", [])) if dossier else 0,
            "places": len((dossier.gm_dossier or {}).get("locations", [])) if dossier else 0,
        },
    }


def _current_session_id(campaign: Campaign) -> Optional[str]:
    session_ids = list(campaign.session_ids or [])
    if not session_ids:
        return None
    index = campaign.current_session_index
    if 0 <= index < len(session_ids):
        return session_ids[index]
    return session_ids[-1]


async def _current_session_character_count(campaign: Campaign, db: AsyncSession) -> Optional[int]:
    session_id = _current_session_id(campaign)
    if session_id is None:
        return None
    result = await db.execute(
        select(func.count(Character.id)).where(Character.session_id == session_id)
    )
    return int(result.scalar_one())


def _current_public_chapter(
    chapters: list[dict[str, Any]],
    active_chapter_id: str,
) -> dict[str, Any]:
    if not chapters:
        return {}
    for chapter in chapters:
        if chapter.get("id") == active_chapter_id:
            return chapter
    active = next((ch for ch in chapters if ch.get("state") == "active"), None)
    return active or chapters[0]


def _active_chapter_for_context(
    gm_dossier: dict[str, Any],
    contract: dict[str, Any],
    active_chapter_id: str,
) -> dict[str, Any]:
    chapters = gm_dossier.get("chapters") if isinstance(gm_dossier, dict) else []
    chapter = None
    if isinstance(chapters, list):
        chapter = next((ch for ch in chapters if ch.get("id") == active_chapter_id), None)
        chapter = chapter or next((ch for ch in chapters if ch.get("state") == "active"), None)
    if not isinstance(chapter, dict):
        chapter = _current_public_chapter(contract.get("visible_chapters", []), active_chapter_id)
    allowed = {
        "id",
        "title",
        "state",
        "objective",
        "stakes",
        "initial_state",
        "key_locations",
        "involved_npcs",
        "clues",
        "complications",
        "possible_exits",
        "indicative_dcs",
        "possible_srd_encounters",
    }
    return {key: value for key, value in chapter.items() if key in allowed}


def _public_quests(canon: dict[str, Any], gm_dossier: dict[str, Any]) -> list[dict[str, Any]]:
    quests = canon.get("quests") if isinstance(canon, dict) else []
    if quests:
        return _generic_list(quests)
    gm_quests = gm_dossier.get("quests") if isinstance(gm_dossier, dict) else []
    out = []
    for i, quest in enumerate(_generic_list(gm_quests)):
        if isinstance(quest, dict) and quest.get("public"):
            out.append(
                {
                    "id": quest.get("id") or f"quest_{i + 1}",
                    "title": quest.get("title") or "Quête",
                    "summary": quest.get("summary") or "",
                    "status": quest.get("status") or "active",
                }
            )
    return out


def _apply_chapter_progress(
    chapters: list[dict[str, Any]],
    canon: dict[str, Any],
) -> list[dict[str, Any]]:
    progress = {}
    for item in canon.get("chapter_progression", []):
        if isinstance(item, dict) and item.get("id"):
            progress[item["id"]] = item
    out = []
    for chapter in chapters:
        updated = dict(chapter)
        if chapter.get("id") in progress:
            patch = progress[chapter["id"]]
            for key in ("state", "sessions", "summary"):
                if key in patch:
                    updated[key] = patch[key]
        out.append(updated)
    return out


def _first_chapter_id(contract: dict[str, Any], gm_dossier: dict[str, Any]) -> str:
    for chapter in contract.get("visible_chapters", []):
        if chapter.get("state") == "active" and chapter.get("id"):
            return str(chapter["id"])
    for chapter in contract.get("visible_chapters", []):
        if chapter.get("id"):
            return str(chapter["id"])
    for chapter in gm_dossier.get("chapters", []):
        if isinstance(chapter, dict) and chapter.get("id"):
            return str(chapter["id"])
    return "chapter_1"


def _sanitize_visible_chapters(value: Any, title: str) -> list[dict[str, Any]]:
    raw = value if isinstance(value, list) and value else []
    if not raw:
        raw = [
            {
                "id": "chapter_1",
                "num": "I",
                "title": "Prologue",
                "state": "active",
                "sessions": 0,
                "summary": f"Premiers pas dans {title}.",
            }
        ]
    chapters = []
    for i, chapter in enumerate(raw[:12]):
        if not isinstance(chapter, dict):
            continue
        state = str(chapter.get("state") or ("active" if i == 0 else "planned")).lower()
        if state not in {"done", "active", "planned"}:
            state = "planned"
        chapters.append(
            {
                "id": _text(chapter.get("id") or f"chapter_{i + 1}", 80),
                "num": _text(chapter.get("num") or _roman(i + 1), 12),
                "title": _text(chapter.get("title") or f"Chapitre {i + 1}", 120),
                "state": state,
                "sessions": int(chapter.get("sessions") or 0),
                "summary": _text(chapter.get("summary") or "", 450),
            }
        )
    return chapters or _sanitize_visible_chapters([], title)


def _sanitize_private_chapter(chapter: Any, index: int) -> dict[str, Any]:
    data = chapter if isinstance(chapter, dict) else {}
    state = str(data.get("state") or ("active" if index == 0 else "planned")).lower()
    if state not in {"done", "active", "planned"}:
        state = "planned"
    return {
        "id": _text(data.get("id") or f"chapter_{index + 1}", 80),
        "title": _text(data.get("title") or f"Chapitre {index + 1}", 120),
        "state": state,
        "objective": _text(data.get("objective") or "", 700),
        "stakes": _text(data.get("stakes") or "", 700),
        "initial_state": _text(data.get("initial_state") or "", 900),
        "key_locations": _generic_list(data.get("key_locations")),
        "involved_npcs": _generic_list(data.get("involved_npcs")),
        "clues": _generic_list(data.get("clues")),
        "secrets": _generic_list(data.get("secrets")),
        "complications": _generic_list(data.get("complications")),
        "possible_exits": _generic_list(data.get("possible_exits")),
        "indicative_dcs": _generic_list(data.get("indicative_dcs")),
        "possible_srd_encounters": _string_list(data.get("possible_srd_encounters"), 12),
    }


def _source_metadata(source: dict[str, Any], source_count: int) -> dict[str, Any]:
    return {
        "source": {
            "id": source["id"],
            "kind": source["kind"],
            "title": source["title"],
            "url": source.get("url"),
            "filename": source.get("filename"),
            "created_at": source["created_at"],
        },
        "source_count": source_count,
    }


def _text(value: Any, max_len: int) -> str:
    if value is None:
        return ""
    return _clip(str(value).strip(), max_len)


def _clip(value: str, max_len: int) -> str:
    return value if len(value) <= max_len else value[: max_len - 1].rstrip() + "…"


def _string_list(value: Any, max_items: int = 20) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        text = _text(item, 160)
        if text:
            out.append(text)
        if len(out) >= max_items:
            break
    return out


def _generic_list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    return value[:50]


def _append_unique(items: list[Any], value: Any) -> None:
    if not value:
        return
    if value not in items:
        items.append(value)


def _roman(value: int) -> str:
    numerals = [
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    ]
    remaining = max(1, min(value, 12))
    out = ""
    for num, label in numerals:
        while remaining >= num:
            out += label
            remaining -= num
    return out
