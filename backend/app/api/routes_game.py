from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import GMAction, GMResponse
from app.api.ws_payloads import (
    build_session_state_payload,
    build_session_state_payload_enriched,
    character_snapshot,
)
from app.db.database import get_db
from app.game.event_bus import EventType, event_bus
from app.game.gm_response_executor import GMResponseExecutor
from app.game.runtime import session_manager
from app.game.turn_manager import CombatantInfo
from app.models.character import Character
from app.models.game_state import GameState
from app.models.message import Message
from app.models.save_slot import SaveSlot
from app.models.session import Session, SessionStatus

router = APIRouter()


class StartGameBody(BaseModel):
    adventure_script: Optional[str] = None
    auto_generate: bool = False


class SaveSlotCreate(BaseModel):
    name: str


_STOPWORDS = {
    "le",
    "la",
    "les",
    "de",
    "du",
    "des",
    "un",
    "une",
    "et",
    "a",
    "au",
    "aux",
}


def _build_session_state_payload(session_id: str) -> dict:
    return build_session_state_payload(session_id, session_manager.get_session(session_id))


async def _build_session_state_payload_with_maps(session_id: str, db: AsyncSession) -> dict:
    return await build_session_state_payload_enriched(
        session_id,
        session_manager.get_session(session_id),
        db,
    )


def _campaign_opening_text(campaign_context: dict[str, Any]) -> str:
    contract = campaign_context.get("player_contract", {})
    if not isinstance(contract, dict):
        contract = {}
    chapter = campaign_context.get("active_chapter", {})
    if not isinstance(chapter, dict):
        chapter = {}

    title = str(contract.get("title") or "l'aventure").strip()
    hook = str(
        contract.get("hook")
        or contract.get("pitch_public")
        or chapter.get("initial_state")
        or ""
    ).strip()
    objectives = contract.get("known_objectives")
    objective = ""
    if isinstance(objectives, list) and objectives:
        objective = str(objectives[0]).strip()
    stakes = str(chapter.get("stakes") or "").strip()

    location = _opening_location_name(campaign_context)
    parts = [
        f"La première scène jouable de {title} s'ouvre à {location}.",
        "Le groupe est présent, libre de questionner la situation avant de s'engager.",
    ]
    if hook:
        parts.append(hook)
    if stakes and stakes not in hook:
        parts.append(stakes)
    if objective:
        parts.append(f"Un cap possible se dessine : {objective}.")
    parts.append(
        "Vous pouvez parler aux personnes présentes, examiner les indices du lieu, "
        "chercher une autre source d'information ou prendre la route. Que faites-vous ?"
    )
    return " ".join(part for part in parts if part)


def _free_opening_text(
    active: Any,
    script: Optional[str] = None,
    auto_generate: bool = False,
) -> str:
    party = _party_names(active)
    if script:
        return (
            f"{party} prend place dans la première scène du scénario proposé. "
            f"{script.strip()} "
            "Avant que quoi que ce soit soit décidé à votre place, le lieu offre "
            "plusieurs prises : "
            "observer, discuter, chercher une autre piste ou partir explorer. Que faites-vous ?"
        )
    if auto_generate:
        return (
            f"{party} se retrouve au cœur d'une situation encore ouverte : une rumeur pressante, "
            "un lieu à inspecter et plusieurs interlocuteurs possibles attendent vos choix. "
            "Rien n'est encore joué ; par où commencez-vous ?"
        )
    return (
        f"{party} se tient dans un lieu de départ encore calme, juste avant que "
        "l'aventure ne prenne forme. "
        "Autour de vous, un repère à examiner, des environs à parcourir et la "
        "possibilité de chercher des informations. "
        "Que faites-vous ?"
    )


def _opening_location_name(campaign_context: Optional[dict[str, Any]]) -> str:
    if not isinstance(campaign_context, dict):
        return "un lieu de départ"
    chapter = campaign_context.get("active_chapter", {})
    if not isinstance(chapter, dict):
        chapter = {}
    key_locations = chapter.get("key_locations")
    if isinstance(key_locations, list):
        for location in key_locations:
            text = str(location).strip()
            if text:
                return text
    initial_state = str(chapter.get("initial_state") or "").strip()
    if initial_state:
        sentence = initial_state.split(".")[0].strip()
        if 0 < len(sentence) <= 80:
            return sentence
    return "un lieu de départ"


def _opening_objective(campaign_context: Optional[dict[str, Any]]) -> str:
    if not isinstance(campaign_context, dict):
        return ""
    contract = campaign_context.get("player_contract", {})
    if not isinstance(contract, dict):
        return ""
    objectives = contract.get("known_objectives")
    if isinstance(objectives, list) and objectives:
        return str(objectives[0]).strip()
    return ""


def _opening_npcs(campaign_context: Optional[dict[str, Any]]) -> list[str]:
    if not isinstance(campaign_context, dict):
        return []
    chapter = campaign_context.get("active_chapter", {})
    if not isinstance(chapter, dict):
        return []
    involved = chapter.get("involved_npcs")
    if not isinstance(involved, list):
        return []
    return [str(name).strip() for name in involved if str(name).strip()][:2]


def _party_names(active: Any) -> str:
    characters = active.state_data.get("characters", {})
    if not isinstance(characters, dict) or not characters:
        return "Le groupe"
    names = [
        str(data.get("name") or char_id)
        for char_id, data in characters.items()
        if isinstance(data, dict)
    ]
    if not names:
        return "Le groupe"
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" et {names[-1]}"


def _safe_id(value: str, fallback: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value.casefold())
    ascii_text = "".join(ch for ch in ascii_text if not unicodedata.combining(ch))
    normalized = re.sub(r"[^a-z0-9_]+", "_", ascii_text).strip("_")
    parts = [part for part in normalized.split("_") if part and part not in _STOPWORDS]
    return "_".join(parts[:4]) or fallback


def _region_kind_for_location(location: str) -> str:
    normalized = location.casefold()
    if any(word in normalized for word in ("ville", "cité", "cite", "port", "village")):
        return "settlement"
    if any(word in normalized for word in ("route", "carrefour", "croisée", "croisee")):
        return "crossroads"
    if any(word in normalized for word in ("ruine", "mine", "temple", "tombe", "donjon")):
        return "ruin"
    return "landmark"


def _party_positions(active: Any) -> dict[str, dict[str, int]]:
    characters = active.state_data.get("characters", {})
    if not isinstance(characters, dict):
        return {}
    positions: dict[str, dict[str, int]] = {}
    for index, char_id in enumerate(characters):
        positions[str(char_id)] = {"col": 1 + index % 3, "row": 4 + index // 3}
    return positions


def _opening_response(
    active: Any,
    *,
    campaign_context: Optional[dict[str, Any]] = None,
    script: Optional[str] = None,
    auto_generate: bool = False,
) -> GMResponse:
    location = _opening_location_name(campaign_context)
    objective = _opening_objective(campaign_context)
    location_id = _safe_id(location, "lieu_depart")
    objective_id = _safe_id(objective, "objectif_rumeur") if objective else ""
    if objective_id == location_id:
        objective_id = ""
    region_kind = _region_kind_for_location(location)
    narration = (
        _campaign_opening_text(campaign_context)
        if campaign_context is not None
        else _free_opening_text(active, script, auto_generate)
    )

    pois: list[dict[str, Any]] = [
        {
            "id": "situation_initiale",
            "name": "Situation immédiate",
            "kind": "clue",
            "position": {"col": 3, "row": 3},
            "icon": "clue",
            "description": "Les premiers détails concrets de la scène.",
            "action_hint": "Observer avant de décider.",
            "interactions": [
                {
                    "label": "Examiner",
                    "intent": "examine",
                    "prompt": "J'examine la situation immédiate et les détails du lieu.",
                }
            ],
        },
        {
            "id": "source_information",
            "name": "Source d'information",
            "kind": "clue",
            "position": {"col": 5, "row": 3},
            "icon": "poi",
            "description": "Une piste sociale ou matérielle à interroger.",
            "action_hint": "Chercher une autre version des faits.",
            "interactions": [
                {
                    "label": "Se renseigner",
                    "intent": "search",
                    "prompt": "Je cherche une autre source d'information dans les environs.",
                }
            ],
        },
    ]
    for index, npc_name in enumerate(_opening_npcs(campaign_context)):
        npc_id = _safe_id(npc_name, f"npc_{index + 1}")
        pois.append({
            "id": npc_id,
            "name": npc_name,
            "kind": "npc",
            "position": {"col": 4 + index, "row": 5},
            "icon": "npc",
            "description": "Personne présente dans la scène d'ouverture.",
            "action_hint": "Lui parler ou négocier avant d'agir.",
            "interactions": [
                {
                    "label": "Parler",
                    "intent": "talk",
                    "prompt": f"Je m'approche de {npc_name} et lui adresse la parole.",
                }
            ],
        })

    exits = [
        {
            "id": "explorer_environs",
            "label": "Explorer les environs",
            "position": {"col": 7, "row": 4},
            "leads_to": "environs",
            "description": "Quitter le point de départ pour observer le terrain proche.",
        },
        {
            "id": "chercher_contacts",
            "label": "Chercher d'autres contacts",
            "position": {"col": 0, "row": 3},
            "leads_to": "contacts",
            "description": "Trouver une autre source d'information ou une aide différente.",
        },
    ]
    if objective:
        exits.append({
            "id": "prendre_route_objectif",
            "label": "Prendre la route",
            "position": {"col": 7, "row": 6},
            "leads_to": objective_id or "objectif",
            "description": f"Se diriger vers : {objective}",
        })

    actions = [
        GMAction(
            type="journal_update",
            params={
                "location_region": location,
                "location_place": location,
                "time_of_day": "morning",
                "day_number": 1,
            },
        ),
        GMAction(
            type="scene_layout",
            params={
                "scene_id": f"scene_{location_id}",
                "cols": 8,
                "rows": 8,
                "cell_size_m": 1.5,
                "terrain": region_kind,
                "pois": pois[:5],
                "exits": exits[:3],
                "party_positions": _party_positions(active),
            },
        ),
        GMAction(
            type="region_map_update",
            params={
                "name": "Carte de campagne",
                "current_node_id": location_id,
                "nodes_upsert": [
                    {
                        "id": location_id,
                        "name": location,
                        "kind": region_kind,
                        "position": {"x": 45, "y": 58},
                        "status": "current",
                        "description": "Point de départ joué en scène.",
                    },
                    *(
                        [{
                            "id": objective_id,
                            "name": objective,
                            "kind": "landmark",
                            "position": {"x": 62, "y": 42},
                            "status": "rumored",
                            "description": "Destination ou piste connue, non encore vérifiée.",
                        }]
                        if objective_id
                        else []
                    ),
                ],
                "nodes_remove": [],
                "edges_upsert": (
                    [{
                        "id": f"route_{location_id}_{objective_id}",
                        "from": location_id,
                        "to": objective_id,
                        "kind": "path",
                        "travel_hint": "Trajet à confirmer par les choix du groupe.",
                    }]
                    if objective_id
                    else []
                ),
                "edges_remove": [],
            },
        ),
    ]
    if region_kind == "settlement":
        actions.append(
            GMAction(
                type="city_map_update",
                params={
                    "city_id": location_id,
                    "region_node_id": location_id,
                    "name": location,
                    "current_node_id": "point_depart",
                    "nodes_upsert": [
                        {
                            "id": "point_depart",
                            "name": "Point de départ",
                            "kind": "square",
                            "position": {"x": 45, "y": 58},
                            "status": "current",
                        },
                        {
                            "id": "contacts",
                            "name": "Contacts et rumeurs",
                            "kind": "district",
                            "position": {"x": 28, "y": 48},
                            "status": "known",
                        },
                        {
                            "id": "sortie",
                            "name": "Route de sortie",
                            "kind": "gate",
                            "position": {"x": 70, "y": 60},
                            "status": "known",
                        },
                    ],
                    "nodes_remove": [],
                    "edges_upsert": [
                        {
                            "id": "rue_depart_contacts",
                            "from": "point_depart",
                            "to": "contacts",
                            "kind": "street",
                        },
                        {
                            "id": "rue_depart_sortie",
                            "from": "point_depart",
                            "to": "sortie",
                            "kind": "street",
                        },
                    ],
                    "edges_remove": [],
                },
            )
        )
    return GMResponse(narration=narration, actions=actions, mood="neutral")


def _seed_campaign_opening_quest(
    active: Any,
    campaign_context: dict[str, Any],
) -> bool:
    contract = campaign_context.get("player_contract", {})
    if not isinstance(contract, dict):
        contract = {}
    objectives = contract.get("known_objectives")
    objective = ""
    if isinstance(objectives, list) and objectives:
        objective = str(objectives[0]).strip()
    summary = str(contract.get("hook") or contract.get("pitch_public") or objective).strip()
    if not summary and not objective:
        return False

    quests = active.state_data.setdefault("quests", [])
    if not isinstance(quests, list):
        quests = []
        active.state_data["quests"] = quests

    quest_id = "campaign_opening"
    quest_entry = {
        "id": quest_id,
        "category": "principale",
        "title": objective or str(contract.get("title") or "Suivre l'accroche"),
        "summary": summary or objective,
        "urgency": None,
        "status": "active",
    }
    idx = next((i for i, quest in enumerate(quests) if quest.get("id") == quest_id), -1)
    if idx >= 0:
        quests[idx] = {**quests[idx], **quest_entry}
    else:
        quests.append(quest_entry)
    return True


async def _send_campaign_opening_narration(
    session_id: str,
    active: Any,
    campaign_context: dict[str, Any],
    db: AsyncSession,
) -> None:
    response = _opening_response(active, campaign_context=campaign_context)
    await _publish_opening_scene(
        session_id,
        active,
        db,
        response,
        quest_changed=_seed_campaign_opening_quest(active, campaign_context),
    )


async def _send_free_opening_narration(
    session_id: str,
    active: Any,
    db: AsyncSession,
    *,
    script: Optional[str] = None,
    auto_generate: bool = False,
) -> None:
    response = _opening_response(active, script=script, auto_generate=auto_generate)
    await _publish_opening_scene(session_id, active, db, response, quest_changed=False)


async def _publish_opening_scene(
    session_id: str,
    active: Any,
    db: AsyncSession,
    response: GMResponse,
    *,
    quest_changed: bool,
) -> None:
    from app.services.message_service import persist_narration

    executor = GMResponseExecutor(event_bus, source="routes_game")
    await executor.execute_gm_response(response, active, db, session_id=session_id)

    active.state_data["welcome_narration_sent"] = True
    active.mark_dirty()
    await session_manager.save_state(session_id, db)

    if quest_changed:
        await event_bus.publish_to_session(
            session_id,
            EventType.QUEST_UPDATED,
            {"quests": list(active.state_data.get("quests", []))},
            source="routes_game",
        )
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        await _build_session_state_payload_with_maps(session_id, db),
        source="routes_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {
            "text": response.narration,
            "speaker": "Maître du Jeu",
            "speaker_kind": "gm",
            "entry_kind": "narration",
        },
        source="routes_game",
    )
    await persist_narration(session_id, response.narration, "Maître du Jeu", db)


@router.get("/{session_id}/state")
async def get_game_state(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get current game state."""
    active = session_manager.get_session(session_id)
    if active:
        return await _build_session_state_payload_with_maps(session_id, db)

    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    payload = await build_session_state_payload_enriched(session_id, None, db)
    payload["phase"] = session.status.value
    return payload


@router.post("/{session_id}/start")
async def start_game(
    session_id: str,
    body: StartGameBody = Body(default_factory=StartGameBody),
    db: AsyncSession = Depends(get_db),
):
    """Start a game session — transition to EXPLORATION and set up participants."""
    try:
        active = await session_manager.open_session(session_id, db)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    # Already past character creation — idempotent
    if active.phase not in (SessionStatus.LOBBY, SessionStatus.CHARACTER_CREATION):
        return {
            "status": "already_started",
            "phase": active.phase.value,
            "session_id": session_id,
        }

    # Load characters for this session
    result = await db.execute(
        select(Character).where(Character.session_id == session_id)
    )
    characters = result.scalars().all()

    if not characters:
        raise HTTPException(
            status_code=400,
            detail="Aucun personnage dans cette session. Créez un personnage d'abord.",
        )

    # Force-transition to EXPLORATION (bypasses strict state-machine validation)
    active.phase = SessionStatus.EXPLORATION

    # Set up TurnManager for exploration (round-robin)
    participants = [
        CombatantInfo(
            combatant_id=c.id,
            name=c.name,
            dex_score=int(c.ability_scores.get("dex", 10)),
            is_player=True,
            is_ai_controlled=c.is_ai,
        )
        for c in characters
    ]
    active.turn_manager.setup_exploration(participants)

    # Store character snapshots in state_data for later combat use
    active.state_data["characters"] = {
        c.id: character_snapshot(c)
        for c in characters
    }

    # Seed world-state slices (idempotent — setdefault preserves existing saves)
    active.state_data.setdefault("adventure_journal", {
        "location_region": None,
        "location_place": None,
        "time_of_day": "morning",
        "day_number": 1,
        "calendar_date": None,
        "weather": None,
    })
    active.state_data.setdefault("quests", [])
    active.state_data.setdefault("chronicle", [])
    active.state_data.setdefault(
        "world_maps",
        {"region_map": None, "city_maps": {}, "active_city_id": None},
    )

    from app.services import campaign_dossier_service

    campaign_context = await campaign_dossier_service.compile_campaign_context_for_session(
        session_id,
        db,
    )
    if campaign_context is not None:
        active.state_data["campaign_context"] = campaign_context
    else:
        active.state_data.pop("campaign_context", None)

    # Store adventure context for the GM agent
    if body.adventure_script:
        active.state_data["adventure_script"] = body.adventure_script
    if body.auto_generate:
        active.state_data["auto_generate_adventure"] = True
    active.mark_dirty()
    await session_manager.save_state(session_id, db)

    # Notify any already-connected WebSocket clients
    await event_bus.publish_to_session(
        session_id,
        EventType.PHASE_CHANGE,
        {"phase": SessionStatus.EXPLORATION.value},
        source="routes_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        await _build_session_state_payload_with_maps(session_id, db),
        source="routes_game",
    )

    if body.adventure_script:
        await _send_free_opening_narration(
            session_id,
            active,
            db,
            script=body.adventure_script,
        )
    elif campaign_context is not None:
        await _send_campaign_opening_narration(
            session_id,
            active,
            campaign_context,
            db,
        )
    elif body.auto_generate:
        await _send_free_opening_narration(
            session_id,
            active,
            db,
            auto_generate=True,
        )
    else:
        await _send_free_opening_narration(
            session_id,
            active,
            db,
        )

    return {
        "status": "ok",
        "phase": active.phase.value,
        "session_id": session_id,
        "characters": len(characters),
    }


# ─── Save / Load ──────────────────────────────────────────────────────────────


@router.post("/{session_id}/saves")
async def create_save(
    session_id: str,
    body: SaveSlotCreate,
    db: AsyncSession = Depends(get_db),
):
    """Creer un point de sauvegarde nomme pour la session."""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Le nom de la sauvegarde est requis.")

    # Verifier que la session existe
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session introuvable.")

    # Obtenir l'etat courant (depuis la memoire ou la DB)
    active = session_manager.get_session(session_id)
    if active:
        phase_val = active.phase.value
        turn_number = active.turn_number
        round_number = active.round_number
        state_data = dict(active.state_data)
        # Snapshot TurnManager dans state_data
        state_data["turn_manager"] = active.turn_manager.to_dict()
        state_data["phase"] = phase_val
    else:
        gs_result = await db.execute(
            select(GameState).where(GameState.session_id == session_id)
        )
        gs = gs_result.scalar_one_or_none()
        phase_val = session.status.value
        turn_number = gs.turn_number if gs else 0
        round_number = gs.round_number if gs else 0
        state_data = dict(gs.state_data) if gs else {}

    # Snapshot de tous les personnages
    chars_result = await db.execute(
        select(Character).where(Character.session_id == session_id)
    )
    characters = chars_result.scalars().all()
    characters_snapshot = [
        {
            "id": c.id,
            "name": c.name,
            "player_name": c.player_name,
            "is_ai": c.is_ai,
            "species": c.species,
            "char_class": c.char_class,
            "level": c.level,
            "background": c.background,
            "ability_scores": c.ability_scores,
            "hp_current": c.hp_current,
            "hp_max": c.hp_max,
            "hp_temp": c.hp_temp,
            "equipment": c.equipment,
            "spell_slots": c.spell_slots,
            "hit_dice": c.hit_dice,
            "known_spells": c.known_spells,
            "conditions": c.conditions,
            "proficiencies": c.proficiencies,
            "personality": c.personality,
        }
        for c in characters
    ]

    save_slot = SaveSlot(
        id=str(uuid.uuid4()),
        session_id=session_id,
        name=name,
        phase=phase_val,
        turn_number=turn_number,
        round_number=round_number,
        state_data=state_data,
        characters_snapshot=characters_snapshot,
    )
    db.add(save_slot)
    await db.commit()
    await db.refresh(save_slot)

    return {
        "id": save_slot.id,
        "session_id": save_slot.session_id,
        "name": save_slot.name,
        "phase": save_slot.phase,
        "turn_number": save_slot.turn_number,
        "round_number": save_slot.round_number,
        "characters_count": len(characters_snapshot),
        "created_at": save_slot.created_at.isoformat(),
    }


@router.get("/{session_id}/saves")
async def list_saves(session_id: str, db: AsyncSession = Depends(get_db)):
    """Lister toutes les sauvegardes d'une session."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Session introuvable.")

    saves_result = await db.execute(
        select(SaveSlot)
        .where(SaveSlot.session_id == session_id)
        .order_by(SaveSlot.created_at.desc())
    )
    saves = saves_result.scalars().all()

    return {
        "saves": [
            {
                "id": s.id,
                "session_id": s.session_id,
                "name": s.name,
                "phase": s.phase,
                "turn_number": s.turn_number,
                "round_number": s.round_number,
                "characters_count": len(s.characters_snapshot),
                "created_at": s.created_at.isoformat(),
            }
            for s in saves
        ],
        "total": len(saves),
    }


@router.delete("/{session_id}/saves/{save_id}", status_code=204)
async def delete_save(session_id: str, save_id: str, db: AsyncSession = Depends(get_db)):
    """Supprimer une sauvegarde."""
    result = await db.execute(
        select(SaveSlot).where(
            SaveSlot.id == save_id, SaveSlot.session_id == session_id
        )
    )
    save = result.scalar_one_or_none()
    if save is None:
        raise HTTPException(status_code=404, detail="Sauvegarde introuvable.")

    await db.delete(save)
    await db.commit()


@router.post("/{session_id}/saves/{save_id}/load")
async def load_save(session_id: str, save_id: str, db: AsyncSession = Depends(get_db)):
    """Restaurer la session a partir d'une sauvegarde."""
    result = await db.execute(
        select(SaveSlot).where(
            SaveSlot.id == save_id, SaveSlot.session_id == session_id
        )
    )
    save = result.scalar_one_or_none()
    if save is None:
        raise HTTPException(status_code=404, detail="Sauvegarde introuvable.")

    # Verifier que la session existe
    sess_result = await db.execute(select(Session).where(Session.id == session_id))
    session = sess_result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session introuvable.")

    # Restaurer SessionStatus
    try:
        target_status = SessionStatus(save.phase)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Phase invalide : {save.phase!r}")

    session.status = target_status

    # Restaurer GameState
    gs_result = await db.execute(
        select(GameState).where(GameState.session_id == session_id)
    )
    gs = gs_result.scalar_one_or_none()
    if gs is None:
        gs = GameState(session_id=session_id)
        db.add(gs)

    gs.state_data = save.state_data
    gs.turn_number = save.turn_number
    gs.round_number = save.round_number

    # Restaurer les personnages depuis le snapshot
    chars_result = await db.execute(
        select(Character).where(Character.session_id == session_id)
    )
    existing_chars = {c.id: c for c in chars_result.scalars().all()}

    for snap in save.characters_snapshot:
        char = existing_chars.get(snap["id"])
        if char is None:
            continue
        char.hp_current = snap["hp_current"]
        char.hp_max = snap["hp_max"]
        char.hp_temp = snap["hp_temp"]
        char.level = snap["level"]
        char.ability_scores = snap["ability_scores"]
        char.equipment = snap["equipment"]
        char.spell_slots = snap["spell_slots"]
        char.hit_dice = snap.get("hit_dice", char.hit_dice or {})
        char.known_spells = snap["known_spells"]
        char.conditions = snap["conditions"]
        char.proficiencies = snap["proficiencies"]

    await db.commit()

    # Si la session est active en memoire, la recharger
    if session_manager.is_active(session_id):
        await session_manager.close_session(session_id, db)
    await session_manager.open_session(session_id, db)

    # Notifier les clients connectes
    await event_bus.publish_to_session(
        session_id,
        EventType.PHASE_CHANGE,
        {"phase": save.phase},
        source="routes_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        await _build_session_state_payload_with_maps(session_id, db),
        source="routes_game",
    )

    return {
        "status": "ok",
        "save_id": save_id,
        "phase": save.phase,
        "session_id": session_id,
    }


# ─── Historique narratif ──────────────────────────────────────────────────────


@router.get("/{session_id}/history")
async def get_history(
    session_id: str,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Retourner les derniers messages narratifs pour restaurer le journal."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Session introuvable.")

    msgs_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = list(msgs_result.scalars().all())
    messages.reverse()

    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role.value,
                "speaker": m.speaker,
                "message_type": m.message_type.value,
                "content": m.content,
                "metadata": m.metadata_,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "total": len(messages),
    }
