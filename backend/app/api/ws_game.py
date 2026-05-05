"""WebSocket endpoint for real-time game communication.

Protocol summary
----------------

Client → Server (JSON):

    {"type": "join",   "character_id": "<id>"}
    {"type": "action", "action_type": "free_text|attack|end_turn|start_combat|take_rest",
                       "content": "Je cherche des pièges",
                       "target_id": "<id|null>"}
    {"type": "ping"}

Server → Client (JSON):

    {"event_type": "session_state", "session_id": "...", "payload": {...}, "timestamp": "..."}
    {"event_type": "narration",     "session_id": "...", "payload": {"text": "..."}, ...}
    {"event_type": "roll_result",   "session_id": "...", "payload": {...}, ...}
    {"event_type": "turn_start",    "session_id": "...", "payload": {"combatant_id": "..."}, ...}
    {"event_type": "phase_change",  "session_id": "...", "payload": {"phase": "..."}, ...}
    {"event_type": "combat_start",  "session_id": "...", "payload": {"combatants": [...]}, ...}
    {"event_type": "hp_changed", "session_id": "...", "payload": {"combatant_id": "...", "hp": 0}}

    {"event_type": "error",         "session_id": "...", "payload": {"message": "..."}, ...}
    {"event_type": "pong"}

Connection lifecycle
--------------------
1. Client connects: session is opened/loaded from DB, client receives ``session_state``.
2. Client sends ``join`` with its character_id → ``player_joined`` broadcast.
3. Client sends ``action`` messages → dispatched to the game layer → results broadcast.
4. Client disconnects: ``player_left`` broadcast, session closed if no more clients.
"""
from __future__ import annotations

import asyncio
import logging
import re
from copy import deepcopy
from typing import Any, Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.connection_manager import ConnectionManager
from app.api.ws_handlers.ai_control import handle_ai_turns as handle_ai_combat_turns
from app.api.ws_handlers.combat import (
    active_npc_ids,
    combat_end_reason_from_removed,
    combat_end_text,
    combat_target_id,
    is_combat_social_text,
    npc_removed_text,
    reject_out_of_turn_action,
)
from app.api.ws_handlers.encounter_intro import (
    execute_intro_scene_layout,
    generate_encounter_intro,
    is_async_callable,
    is_unhelpful_intro,
    normalized_phrase,
    pause_at_encounter_start,
    should_pause_for_encounter_intro,
)
from app.api.ws_handlers.lifecycle import (
    VALIDATION_ERROR_MESSAGE,
    character_belongs_to_session,
    send_ws_error,
)
from app.api.ws_payloads import (
    build_combat_start_payload,
    build_session_state_payload,
    character_snapshot,
    compute_ac_from_equipment,
    format_monster_actions,
    monster_base_id,
    monster_color,
    monster_instance_number,
    monster_token,
    monster_token_for_combatant,
)
from app.api.ws_schemas import (
    JoinMessage,
    PingMessage,
    PlayerActionMessage,
    ToggleAiControlMessage,
    TriggerAiReactionsMessage,
)
from app.config import settings
from app.db.database import get_db
from app.engine.tactical_grid import GridPosition, initialize_positions, validate_move
from app.game.action_resolver import ActionResolver
from app.game.async_tasks import create_logged_task
from app.game.combat_triggers import prime_combat_from_aggressive_action
from app.game.constants import INACTIVE_STATUSES
from app.game.event_bus import EventType, GameEvent, event_bus
from app.game.runtime import rest_service, session_manager
from app.game.turn_manager import CombatantInfo
from app.llm.budget import is_sober_mode
from app.models.character import Character
from app.models.session import SessionStatus
from app.security import websocket_has_valid_access_token
from app.services.encounter_service import encounter_service
from app.services.equipment_service import (
    CharacterNotFoundError,
    EquipmentService,
    ItemNotFoundError,
)
from app.services.message_service import load_recent_messages, persist_narration
from app.services.rest_service import RestServiceError, normalize_character_hit_dice

logger = logging.getLogger(__name__)

router = APIRouter()

action_resolver = ActionResolver()
equipment_service = EquipmentService()

# Module-level singleton
connection_manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Relay task
# ---------------------------------------------------------------------------


async def _relay_events(websocket: WebSocket, queue: asyncio.Queue) -> None:
    """Background coroutine: forward events from *queue* to *websocket*."""
    try:
        while True:
            event: GameEvent = await queue.get()
            payload = event.model_dump(mode="json")
            await websocket.send_json(payload)
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.debug("Relay task ended: %s", exc)


# ---------------------------------------------------------------------------
# Session state payload builder
# ---------------------------------------------------------------------------


def _build_session_state_payload(session_id: str) -> dict[str, Any]:
    return build_session_state_payload(session_id, session_manager.get_session(session_id))


# ---------------------------------------------------------------------------
# Combat helpers
# ---------------------------------------------------------------------------


_compute_ac_from_equipment = compute_ac_from_equipment
_monster_base_id = monster_base_id
_monster_instance_number = monster_instance_number
_monster_token = monster_token
_monster_token_for_combatant = monster_token_for_combatant
_monster_color = monster_color
_format_monster_actions = format_monster_actions
_character_snapshot = character_snapshot


async def _sync_ai_control_from_db(
    session_id: str,
    active: Any,
    db: AsyncSession,
) -> bool:
    """Reconcile live AI-control flags with the Character table.

    Character control can be changed from REST screens before or during a live
    session. The combat engine relies on the persisted game snapshot and the
    TurnManager, so this keeps those copies aligned with the DB source of truth.
    """
    result = await db.execute(select(Character).where(Character.session_id == session_id))
    characters = result.scalars().all()
    if not characters:
        return False

    from app.game.ai_player_manager import register_ai_player, unregister_ai_player

    changed = False
    chars_data: dict[str, Any] = active.state_data.setdefault("characters", {})
    combatants_info: dict[str, Any] = active.state_data.get("combatants", {})

    for char in characters:
        if char.id not in chars_data:
            chars_data[char.id] = _character_snapshot(char)
            changed = True
        cdata = chars_data[char.id]
        if cdata.get("is_ai") != char.is_ai:
            cdata["is_ai"] = char.is_ai
            changed = True
        cdata.setdefault("name", char.name)
        cdata.setdefault("hit_dice", dict(normalize_character_hit_dice(char)))
        cdata.setdefault("personality", dict(char.personality or {}))

        if char.id in combatants_info and combatants_info[char.id].get("is_ai") != char.is_ai:
            combatants_info[char.id]["is_ai"] = char.is_ai
            changed = True

        for entry in active.turn_manager._order:
            if entry.combatant_id == char.id:
                if entry.is_ai_controlled != char.is_ai:
                    entry.is_ai_controlled = char.is_ai
                    changed = True
                break

        if char.is_ai:
            before = len(active.ai_players)
            register_ai_player(active, char.id, cdata)
            changed = changed or len(active.ai_players) != before
        else:
            had_agent = char.id in active.ai_players
            unregister_ai_player(active, char.id)
            changed = changed or had_agent

    if changed:
        active.mark_dirty()
        await session_manager.save_state(session_id, db)

    return changed


def _build_combat_start_payload(active: Any) -> dict[str, Any]:
    return build_combat_start_payload(active, encounter_service)


_is_unhelpful_intro = is_unhelpful_intro
_is_async_callable = is_async_callable
_normalized_phrase = normalized_phrase
_should_pause_for_encounter_intro = should_pause_for_encounter_intro


async def _generate_encounter_intro(
    session_id: str,
    active: Any,
    db: AsyncSession,
    combatants_info: dict[str, Any],
) -> Optional[str]:
    return await generate_encounter_intro(
        session_id,
        active,
        db,
        combatants_info,
        gm_agent=getattr(action_resolver, "_gm", None),
        event_bus=event_bus,
        load_recent_messages=load_recent_messages,
    )


async def _execute_intro_scene_layout(
    session_id: str,
    active: Any,
    response: Any,
) -> None:
    await execute_intro_scene_layout(session_id, active, response, event_bus=event_bus)


_ENCOUNTER_END_ACTION_TYPES = {
    "scene_layout",
    "journal_update",
    "quest_add",
    "chronicle_add",
}

_HOSTILE_POI_MARKERS = {
    "hostile",
    "enemy",
    "enemies",
    "ennemi",
    "ennemis",
    "monster",
    "monstre",
    "adversaire",
    "foe",
    "goblin",
    "gobelin",
    "hobgoblin",
    "orc",
    "skeleton",
    "squelette",
    "zombie",
    "wolf",
    "loup",
    "spider",
    "araignee",
    "bandit",
    "cultist",
    "cultiste",
    "bugbear",
    "zhentarim",
}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _summary_position(position: Any) -> Optional[dict[str, int]]:
    if not isinstance(position, dict):
        return None
    if "col" in position or "row" in position:
        return {
            "col": _safe_int(position.get("col"), 0),
            "row": _safe_int(position.get("row"), 0),
        }
    if "x" in position or "y" in position:
        return {
            "col": _safe_int(position.get("x"), 0),
            "row": _safe_int(position.get("y"), 0),
        }
    return None


def _dedupe_removed_npcs(*groups: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for group in groups:
        for entry in group or []:
            if not isinstance(entry, dict):
                continue
            combatant_id = entry.get("combatant_id") or entry.get("id")
            if not combatant_id:
                continue
            by_id[str(combatant_id)] = {**by_id.get(str(combatant_id), {}), **entry}
    return list(by_id.values())


def _build_combat_summary(
    active: Any,
    removed_npcs: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Build a compact, structured combat outcome before combat state cleanup."""
    state_data: dict[str, Any] = active.state_data
    combatants: dict[str, Any] = state_data.get("combatants", {})
    grid_positions: dict[str, Any] = state_data.get("grid_positions", {})
    previous_scene = deepcopy(state_data.get("current_scene"))
    all_removed = _dedupe_removed_npcs(
        state_data.get("resolved_npcs"),
        removed_npcs,
    )
    removed_by_id = {
        str(item.get("combatant_id") or item.get("id")): item
        for item in all_removed
        if item.get("combatant_id") or item.get("id")
    }

    party: list[dict[str, Any]] = []
    enemies_defeated: list[dict[str, Any]] = []
    enemies_fled: list[dict[str, Any]] = []
    enemies_surrendered: list[dict[str, Any]] = []
    enemies_unresolved: list[dict[str, Any]] = []

    for combatant_id, info in combatants.items():
        removed = removed_by_id.get(str(combatant_id), {})
        is_player = bool(info.get("is_player", False))
        hp = _safe_int(info.get("hp"), 0)
        raw_status = removed.get("status", info.get("status", "active"))
        status = str(raw_status or "active").lower()
        if not is_player and hp <= 0 and status == "active":
            status = "defeated"

        entry = {
            "id": combatant_id,
            "name": info.get("name", combatant_id),
            "hp": hp,
            "hp_max": info.get("hp_max"),
            "status": status,
            "is_player": is_player,
            "position": (
                _summary_position(removed.get("position"))
                or _summary_position(grid_positions.get(combatant_id))
            ),
        }
        for key in ("monster_id", "species", "cr"):
            if info.get(key) is not None:
                entry[key] = info.get(key)

        if is_player:
            party.append(entry)
        elif status == "fled":
            enemies_fled.append(entry)
        elif status == "surrendered":
            enemies_surrendered.append(entry)
        elif status == "defeated":
            enemies_defeated.append(entry)
        else:
            enemies_unresolved.append(entry)

    journal = state_data.get("adventure_journal") or {}
    battlefield_location = (
        journal.get("location_place")
        or journal.get("location_region")
        or (previous_scene or {}).get("terrain")
        or "lieu actuel"
    )
    total_enemies = (
        len(enemies_defeated)
        + len(enemies_fled)
        + len(enemies_surrendered)
        + len(enemies_unresolved)
    )

    return {
        "outcome": "partial" if enemies_unresolved else "victory",
        "party": party,
        "enemies_defeated": enemies_defeated,
        "enemies_fled": enemies_fled,
        "enemies_surrendered": enemies_surrendered,
        "enemies_unresolved": enemies_unresolved,
        "total_enemies": total_enemies,
        "battlefield_location": battlefield_location,
        "round_number": getattr(active, "round_number", 0),
        "grid_config": deepcopy(state_data.get("grid_config") or {}),
        "previous_scene": previous_scene,
    }


def _is_hostile_scene_poi(poi: Any) -> bool:
    if not isinstance(poi, dict):
        return False
    searchable = " ".join(
        str(poi.get(key, ""))
        for key in ("id", "name", "kind", "icon", "description", "action_hint")
    ).casefold()
    normalized = re.sub(r"[^a-z0-9àâäéèêëîïôöùûüç_-]+", " ", searchable)
    tokens = set(normalized.replace("_", " ").replace("-", " ").split())
    return bool(tokens & _HOSTILE_POI_MARKERS)


def _position_for_aftermath(
    entry: dict[str, Any],
    *,
    cols: int,
    rows: int,
    fallback_index: int,
) -> dict[str, int]:
    position = _summary_position(entry.get("position"))
    if position is None:
        position = {
            "col": 1 + (fallback_index % max(cols - 2, 1)),
            "row": min(rows - 2, 1 + (fallback_index // max(cols - 2, 1))),
        }
    return {
        "col": max(0, min(cols - 1, position["col"])),
        "row": max(0, min(rows - 1, position["row"])),
    }


def _fallback_poi_for_enemy(
    enemy: dict[str, Any],
    *,
    status: str,
    index: int,
    cols: int,
    rows: int,
) -> dict[str, Any]:
    safe_id = re.sub(r"[^a-zA-Z0-9_]+", "_", str(enemy.get("id") or f"enemy_{index}"))
    name = str(enemy.get("name") or "Adversaire")
    position = _position_for_aftermath(enemy, cols=cols, rows=rows, fallback_index=index)

    if status == "defeated":
        return {
            "id": f"aftermath_{safe_id}",
            "name": f"Restes de {name}",
            "kind": "corpse",
            "icon": "ruins",
            "position": position,
            "description": (
                "Le combat a laisse ici un corps, des armes tombees "
                "et des traces visibles."
            ),
            "action_hint": "Examiner les restes ou recuperer ce qui peut servir.",
        }
    if status == "surrendered":
        return {
            "id": f"aftermath_{safe_id}",
            "name": f"Armes deposees de {name}",
            "kind": "clue",
            "icon": "clue",
            "position": position,
            "description": "Une arme ou un signe de reddition marque la fin de l'affrontement.",
            "action_hint": "Observer ce que l'adversaire a abandonne.",
        }
    return {
        "id": f"aftermath_{safe_id}",
        "name": f"Trace de fuite de {name}",
        "kind": "clue",
        "icon": "clue",
        "position": position,
        "description": "Des marques pressees indiquent une retraite dans la confusion.",
        "action_hint": "Chercher ou suivre la piste.",
    }


def _build_fallback_aftermath_scene(
    previous_scene: Any,
    combat_summary: dict[str, Any],
) -> dict[str, Any]:
    """Build a deterministic post-combat exploration scene when the LLM cannot."""
    base_scene = deepcopy(previous_scene) if isinstance(previous_scene, dict) else {}
    grid_config = combat_summary.get("grid_config") or {}
    cols = _safe_int(base_scene.get("cols") or grid_config.get("cols"), 8)
    rows = _safe_int(base_scene.get("rows") or grid_config.get("rows"), 8)
    cols = max(3, min(cols, 24))
    rows = max(3, min(rows, 24))

    pois = [
        deepcopy(poi)
        for poi in base_scene.get("pois", []) or []
        if isinstance(poi, dict) and not _is_hostile_scene_poi(poi)
    ]

    aftermath_enemies: list[tuple[str, dict[str, Any]]] = []
    aftermath_enemies.extend(
        ("defeated", enemy) for enemy in combat_summary.get("enemies_defeated", [])
    )
    aftermath_enemies.extend(
        ("surrendered", enemy) for enemy in combat_summary.get("enemies_surrendered", [])
    )
    aftermath_enemies.extend(
        ("fled", enemy) for enemy in combat_summary.get("enemies_fled", [])
    )
    aftermath_enemies.extend(
        ("unresolved", enemy) for enemy in combat_summary.get("enemies_unresolved", [])
    )

    for index, (status, enemy) in enumerate(aftermath_enemies, start=1):
        if isinstance(enemy, dict):
            pois.append(
                _fallback_poi_for_enemy(
                    enemy,
                    status=status,
                    index=index,
                    cols=cols,
                    rows=rows,
                )
            )

    party_positions = deepcopy(base_scene.get("party_positions") or {})
    if not party_positions:
        party_positions = {
            str(member["id"]): member["position"]
            for member in combat_summary.get("party", [])
            if isinstance(member, dict) and member.get("id") and member.get("position")
        }

    return {
        "cols": cols,
        "rows": rows,
        "cell_size_m": base_scene.get("cell_size_m")
        or grid_config.get("cell_size_m")
        or 1.5,
        "terrain": base_scene.get("terrain") or "battlefield_aftermath",
        "pois": pois,
        "exits": deepcopy(base_scene.get("exits", []) or []),
        "party_positions": party_positions,
    }


async def _apply_fallback_aftermath_scene(
    session_id: str,
    active: Any,
    combat_summary: dict[str, Any],
) -> bool:
    from app.agents.schemas import GMAction, GMResponse
    from app.game.gm_response_executor import GMResponseExecutor

    previous_scene = combat_summary.get("previous_scene")
    fallback_scene = _build_fallback_aftermath_scene(previous_scene, combat_summary)
    before_scene = deepcopy(active.state_data.get("current_scene"))
    await GMResponseExecutor(event_bus, source="ws_game").execute_gm_response(
        GMResponse(
            narration="",
            actions=[GMAction(type="scene_layout", params=fallback_scene)],
        ),
        active,
        session_id=session_id,
    )
    return active.state_data.get("current_scene") != before_scene


async def _execute_encounter_end_actions(
    session_id: str,
    active: Any,
    response: Any,
) -> bool:
    from app.agents.schemas import GMResponse
    from app.game.gm_response_executor import GMResponseExecutor

    safe_actions: list[Any] = []
    scene_action_seen = False
    for action in getattr(response, "actions", []) or []:
        action_type = str(getattr(action, "type", "") or "").lower()
        if action_type not in _ENCOUNTER_END_ACTION_TYPES:
            logger.warning(
                "Action GM post-combat ignoree car interdite : %s",
                action_type or "<vide>",
            )
            continue
        if action_type == "scene_layout":
            if scene_action_seen:
                logger.warning("scene_layout post-combat supplementaire ignore.")
                continue
            scene_action_seen = True
        safe_actions.append(action)

    if not safe_actions:
        return False

    before_scene = deepcopy(active.state_data.get("current_scene"))
    safe_response = GMResponse(narration="", actions=safe_actions)
    await GMResponseExecutor(event_bus, source="ws_game").execute_gm_response(
        safe_response,
        active,
        session_id=session_id,
    )
    return scene_action_seen and active.state_data.get("current_scene") != before_scene


async def _generate_encounter_end(
    session_id: str,
    active: Any,
    db: AsyncSession,
    combat_summary: dict[str, Any],
) -> tuple[Optional[str], bool]:
    """Ask the GM for one post-combat narration and safe scene updates."""
    gm_agent = getattr(action_resolver, "_gm", None)
    run_end = getattr(gm_agent, "run_encounter_end", None)
    if not callable(run_end) or not _is_async_callable(run_end):
        return None, False

    response: Any = None
    await event_bus.publish_to_session(
        session_id,
        EventType.AI_THINKING,
        {"agent_kind": "gm", "thinking": True},
        source="ws_game",
    )
    try:
        recent_messages = await load_recent_messages(session_id, db)
        response = await run_end(
            game_state={**active.state_data, "phase": SessionStatus.ENCOUNTER_END.value},
            combat_summary=combat_summary,
            messages=recent_messages,
        )
    except Exception as exc:
        logger.warning("_generate_encounter_end: aftermath LLM ignore : %s", exc)
        return None, False
    finally:
        await event_bus.publish_to_session(
            session_id,
            EventType.AI_THINKING,
            {"agent_kind": "gm", "thinking": False},
            source="ws_game",
        )

    scene_applied = await _execute_encounter_end_actions(session_id, active, response)
    narration = getattr(response, "narration", "")
    if _is_unhelpful_intro(narration):
        return None, scene_applied
    return str(narration).strip(), scene_applied


async def _pause_at_encounter_start(
    session_id: str,
    active: Any,
    db: AsyncSession,
    pending: dict[str, Any] | None,
    intro_text: str,
) -> None:
    await pause_at_encounter_start(
        session_id,
        active,
        db,
        pending,
        intro_text,
        session_manager=session_manager,
        event_bus=event_bus,
        session_state_payload=lambda: _build_session_state_payload(session_id),
        persist_narration=persist_narration,
    )


_is_combat_social_text = is_combat_social_text
_active_npc_ids = active_npc_ids
_combat_target_id = combat_target_id


async def _reject_out_of_turn_action(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
) -> bool:
    return await reject_out_of_turn_action(
        session_id,
        action,
        active,
        event_bus=event_bus,
    )


async def _auto_death_save(
    session_id: str,
    combatant_id: str,
    name: str,
    active: Any,
) -> None:
    """Auto-roule un jet de sauvegarde contre la mort pour un compagnon IA à 0 PV."""
    from app.engine.combat import roll_death_save  # noqa: PLC0415

    result = roll_death_save()
    combatants: dict[str, Any] = active.state_data.setdefault("combatants", {})
    cdata = combatants.get(combatant_id, {})
    ds: dict[str, Any] = cdata.setdefault(
        "death_saves",
        {"successes": 0, "failures": 0, "stable": False},
    )

    if result.critical_success:
        cdata["hp"] = 1
        ds["stable"] = True
        conds = list(cdata.get("conditions", []))
        if "inconscient" in conds:
            conds.remove("inconscient")
            cdata["conditions"] = conds
        active.mark_dirty()
        await event_bus.publish_to_session(
            session_id,
            EventType.HP_CHANGED,
            {"combatant_id": combatant_id, "hp": 1, "delta": 1},
            source="ws_game",
        )
        narr = (
            f"{name} réussit son jet de sauvegarde avec un 20 naturel "
            "et reprend conscience avec 1 PV !"
        )
    elif result.critical_failure:
        ds["failures"] = min(3, ds.get("failures", 0) + 2)
        active.mark_dirty()
        narr = f"{name} rate son jet de sauvegarde avec un 1 naturel — 2 échecs !"
    elif result.success:
        ds["successes"] = min(3, ds.get("successes", 0) + 1)
        if ds["successes"] >= 3:
            ds["stable"] = True
        active.mark_dirty()
        narr = (
            f"{name} réussit son jet de sauvegarde contre la mort "
            f"({result.d20_roll}) [{ds['successes']}/3 succès]."
        )
    else:
        ds["failures"] = min(3, ds.get("failures", 0) + 1)
        active.mark_dirty()
        narr = (
            f"{name} rate son jet de sauvegarde contre la mort "
            f"({result.d20_roll}) [{ds['failures']}/3 échecs]."
        )

    if ds.get("failures", 0) >= 3 and not ds.get("stable"):
        cdata["dead"] = True
        active.mark_dirty()
        narr = f"{name} est mort(e) — 3 échecs aux jets de sauvegarde."

    await event_bus.publish_to_session(
        session_id,
        EventType.ROLL_RESULT,
        {
            "dice_notation": "1d20",
            "rolls": [result.d20_roll],
            "total": result.d20_roll,
            "modifier": 0,
            "label": f"Jet de sauvegarde — {name}",
            "success": result.success,
        },
        source="ws_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": narr, "speaker": "Maître du Jeu"},
        source="ws_game",
    )


_combat_end_reason_from_removed = combat_end_reason_from_removed
_combat_end_text = combat_end_text


async def _cleanup_inactive_npcs(session_id: str, active: Any) -> list[dict[str, Any]]:
    """Remove defeated, surrendered, or fled NPCs from initiative and grid state."""
    combatants: dict[str, Any] = active.state_data.get("combatants", {})
    grid_positions: dict[str, Any] = active.state_data.get("grid_positions", {})
    removed_entries: list[dict[str, Any]] = []

    for cid, cdata in list(combatants.items()):
        if cdata.get("is_player", True):
            continue

        status = str(cdata.get("status", "active")).lower()
        try:
            hp = int(cdata.get("hp", 1))
        except (TypeError, ValueError):
            hp = 1

        if hp <= 0 and status == "active":
            status = "defeated"
            cdata["status"] = status
            await event_bus.publish_to_session(
                session_id,
                EventType.COMBATANT_STATUS_CHANGED,
                {
                    "combatant_id": cid,
                    "combatant_name": cdata.get("name", cid),
                    "status": status,
                    "reason": "hp_zero",
                },
                source="ws_game",
            )

        if status not in INACTIVE_STATUSES:
            continue

        removed = active.turn_manager.remove_combatant(cid)
        if removed:
            name = cdata.get("name", cid)
            position = _summary_position(grid_positions.pop(cid, None))
            await event_bus.publish_to_session(
                session_id,
                EventType.NARRATION,
                {"text": _npc_removed_text(name, status), "speaker": "Maître du Jeu"},
                source="ws_game",
            )
            await event_bus.publish_to_session(
                session_id,
                EventType.COMBATANT_REMOVED,
                {
                    "combatant_id": cid,
                    "combatant_name": name,
                    "status": status,
                },
                source="ws_game",
            )
            removed_entry = {
                "combatant_id": cid,
                "name": name,
                "status": status,
                "position": position,
            }
            removed_entries.append(removed_entry)
            resolved_npcs = active.state_data.setdefault("resolved_npcs", [])
            existing_idx = next(
                (
                    idx for idx, item in enumerate(resolved_npcs)
                    if item.get("combatant_id") == cid
                ),
                -1,
            )
            if existing_idx >= 0:
                resolved_npcs[existing_idx] = {
                    **resolved_npcs[existing_idx],
                    **removed_entry,
                }
            else:
                resolved_npcs.append(removed_entry)
            active.mark_dirty()

    return removed_entries


_npc_removed_text = npc_removed_text


async def _transition_active_phase(
    session_id: str,
    active: Any,
    db: AsyncSession,
    target: SessionStatus,
) -> None:
    active.game_loop.validate_transition(active.phase, target)
    active.phase = target
    active.state_data["phase"] = target.value
    active.mark_dirty()
    await session_manager.save_state(session_id, db)


async def _handle_combat_end(
    session_id: str,
    active: Any,
    db: AsyncSession,
    reason: str = "victory",
    removed_npcs: Optional[list[dict[str, Any]]] = None,
) -> None:
    """Wrap up combat through ENCOUNTER_END, then return to EXPLORATION."""
    combat_summary = _build_combat_summary(active, removed_npcs)
    if combat_summary.get("enemies_unresolved") and reason == "victory":
        reason = "resolved"

    active.turn_manager.reset()
    active.state_data.pop("combatants", None)
    active.state_data.pop("grid_positions", None)
    active.state_data.pop("grid_config", None)
    active.state_data.pop("grid_decoration", None)
    active.state_data.pop("pending_encounter", None)
    active.state_data.pop("resolved_npcs", None)
    active.mark_dirty()
    await _transition_active_phase(session_id, active, db, SessionStatus.ENCOUNTER_END)

    await event_bus.publish_to_session(
        session_id,
        EventType.COMBAT_END,
        {"reason": reason},
        source="ws_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.PHASE_CHANGE,
        {"phase": SessionStatus.ENCOUNTER_END.value},
        source="ws_game",
    )

    aftermath_text, scene_applied = await _generate_encounter_end(
        session_id,
        active,
        db,
        combat_summary,
    )
    if not scene_applied:
        await _apply_fallback_aftermath_scene(session_id, active, combat_summary)

    await _transition_active_phase(session_id, active, db, SessionStatus.EXPLORATION)
    await event_bus.publish_to_session(
        session_id,
        EventType.PHASE_CHANGE,
        {"phase": SessionStatus.EXPLORATION.value},
        source="ws_game",
    )

    victory_text = aftermath_text or _combat_end_text(reason)
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": victory_text, "speaker": "Maître du Jeu"},
        source="ws_game",
    )
    await persist_narration(session_id, victory_text, "Maître du Jeu", db)
    try:
        from app.services import campaign_dossier_service

        await campaign_dossier_service.synthesize_canon_for_session(
            session_id,
            active.state_data,
            [{"speaker": "Maître du Jeu", "content": victory_text}],
            db,
        )
    except Exception as exc:
        logger.warning("Synthèse canon campagne après combat ignorée : %s", exc)
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        _build_session_state_payload(session_id),
        source="ws_game",
    )


# ---------------------------------------------------------------------------
# Special action handlers
# ---------------------------------------------------------------------------


async def _handle_start_combat(
    session_id: str,
    active: Any,
    db: AsyncSession,
    encounter_id: Optional[str] = None,
    *,
    force: bool = False,
) -> None:
    """Spawn an encounter, roll initiative, and start combat.

    If encounter_id is provided, load that pre-built encounter.
    Otherwise generate a dynamic encounter adapted to the party's levels.
    """
    # Garde d'idempotence : un combat déjà en cours ne doit jamais être
    # "re-démarré" (double-trigger possible si flag consommé deux fois ou
    # si le joueur clique sur le bouton pendant qu'une transition auto arrive).
    if active.phase == SessionStatus.COMBAT:
        logger.warning(
            "_handle_start_combat: combat déjà en cours pour session=%s — ignoré.",
            session_id,
        )
        return

    await _sync_ai_control_from_db(session_id, active, db)

    # Resolve party levels from characters in state_data
    characters_data: dict[str, Any] = active.state_data.get("characters", {})
    party_levels = [int(c.get("level", 1)) for c in characters_data.values()]
    if not party_levels:
        party_levels = [1]

    # Build (or generate) the encounter
    intro_text: Optional[str] = None
    built = None

    # 1. Priorité : encounter déclaré par le GM via encounter_setup
    pending = active.state_data.pop("pending_encounter", None)
    intro_already_played = bool(pending and pending.get("intro_played"))
    should_generate_intro = pending is not None and not intro_already_played
    if pending:
        monster_ids = pending.get("monster_ids", [])
        intro_text = (
            "Les armes se lèvent. L'initiative est lancée — le combat commence !"
            if intro_already_played
            else pending.get("context") or None
        )
        if monster_ids:
            candidate = encounter_service.build_from_monster_ids(monster_ids)
            if candidate.entries:
                built = candidate
            else:
                logger.warning(
                    "_handle_start_combat: aucun monster_id valide dans pending_encounter"
                    " %s, fallback.",
                    monster_ids,
                )

    # 2. Fallback : preset ou génération dynamique
    if built is None:
        if encounter_id:
            built = encounter_service.build_from_preset(encounter_id)
            preset = encounter_service.get_preset(encounter_id)
            intro_text = preset.get("intro_text") if preset else None
            if built is None:
                built = encounter_service.generate(party_levels)
        else:
            preset = encounter_service.pick_preset_for_party(party_levels)
            if preset:
                intro_text = preset.get("intro_text")
                built = encounter_service.build_from_preset(preset["id"])
            else:
                built = encounter_service.generate(party_levels)

    npc_combatants = encounter_service.expand(built)

    # Build player combatant maps
    combatants_list: list[CombatantInfo] = []
    combatants_info: dict[str, Any] = {}

    for char_id, cdata in characters_data.items():
        dex = int(cdata.get("dex", 10))
        dex_mod = (dex - 10) // 2
        combatants_list.append(
            CombatantInfo(
                combatant_id=char_id,
                name=cdata["name"],
                dex_score=dex,
                is_player=True,
                is_ai_controlled=bool(cdata.get("is_ai", False)),
            )
        )
        char_equipment = cdata.get("equipment", [])
        combatants_info[char_id] = {
            "name": cdata["name"],
            "hp": int(cdata.get("hp", 10)),
            "hp_max": int(cdata.get("hp_max", 10)),
            "is_player": True,
            "is_ai": bool(cdata.get("is_ai", False)),
            "status": "active",
            "ac": _compute_ac_from_equipment(char_equipment, dex_mod),
            "attack_bonus": 3,
            "damage_notation": "1d6+2",
        }

    # Add NPC combatants from the built encounter
    npc_names: list[str] = []
    for npc in npc_combatants:
        cid = npc["combatant_id"]
        encounter_service._ensure_loaded()
        monster_id_base = "_".join(cid.rsplit("_", 1)[:-1]) if "_" in cid else cid
        monster_data = encounter_service._monsters_by_id.get(monster_id_base, {})
        dex = int(monster_data.get("ability_scores", {}).get("dexterity", 10))
        combatants_list.append(
            CombatantInfo(
                combatant_id=cid,
                name=npc["name"],
                dex_score=dex,
                is_player=False,
                is_ai_controlled=True,
            )
        )
        combatants_info[cid] = {
            "name": npc["name"],
            "hp": npc["hp"],
            "hp_max": npc["hp_max"],
            "is_player": False,
            "is_ai": True,
            "status": "active",
            "monster_id": monster_id_base,
            "ac": npc["ac"],
            "attack_bonus": npc["attack_bonus"],
            "damage_notation": npc["damage_notation"],
            "species": monster_data.get("type"),
            "cr": monster_data.get("cr"),
            "ability_scores": monster_data.get("ability_scores", {}),
            "actions": _format_monster_actions(monster_data.get("actions", [])),
            "color": _monster_color(monster_data.get("type")),
            "token": _monster_token_for_combatant(
                monster_data.get("name_fr")
                or monster_data.get("name")
                or npc["name"],
                cid,
                npc["name"],
            ),
        }
        npc_names.append(npc["name"])

    # Enregistrer les PlayerAgent pour les compagnons IA (personnages avec is_ai=True).
    # Idempotent : ne recrée pas les agents déjà présents (déjà restaurés par open_session).
    from app.game.ai_player_manager import register_ai_player
    for char_id, cdata in characters_data.items():
        register_ai_player(active, char_id, cdata)

    # Roll initiative and set up TurnManager
    active.turn_manager.setup_combat(combatants_list)
    active.state_data["combatants"] = combatants_info

    # Initialize tactical grid positions
    player_ids = [cid for cid, c in combatants_info.items() if c["is_player"]]
    npc_ids = [cid for cid, c in combatants_info.items() if not c["is_player"]]
    grid_cols, grid_rows = 10, 8
    grid_positions = initialize_positions(player_ids, npc_ids, grid_cols, grid_rows)
    active.state_data["grid_positions"] = {
        cid: pos.to_dict() for cid, pos in grid_positions.items()
    }
    active.state_data["grid_config"] = {
        "cols": grid_cols, "rows": grid_rows, "cell_size_m": 1.5
    }

    if should_generate_intro:
        generated_intro = await _generate_encounter_intro(
            session_id,
            active,
            db,
            combatants_info,
        )
        if generated_intro:
            intro_text = generated_intro
            start_mode = active.state_data.pop("_encounter_intro_start_mode", None)
            should_pause = start_mode == "pause" or (
                start_mode is None and _should_pause_for_encounter_intro(generated_intro)
            )
            if not force and should_pause:
                await _pause_at_encounter_start(
                    session_id,
                    active,
                    db,
                    pending,
                    generated_intro,
                )
                return

    active.phase = SessionStatus.COMBAT
    active.round_number = 1
    active.mark_dirty()
    await session_manager.save_state(session_id, db)

    # Broadcast phase change
    await event_bus.publish_to_session(
        session_id,
        EventType.PHASE_CHANGE,
        {"phase": SessionStatus.COMBAT.value},
        source="ws_game",
    )

    # Broadcast full combatant list for the combat UI.
    await event_bus.publish_to_session(
        session_id,
        "combat_start",
        _build_combat_start_payload(active),
        source="ws_game",
    )

    # Updated session state (includes new turn order)
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        _build_session_state_payload(session_id),
        source="ws_game",
    )

    # Narration d'introduction
    if not intro_text:
        enemy_list = ", ".join(npc_names) if npc_names else "des ennemis"
        verb = "surgissent" if len(npc_names) > 1 else "surgit"
        intro_text = (
            f"{enemy_list} {verb} devant vous ! "
            "L'initiative est lancée — le combat commence !"
        )
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": intro_text, "speaker": "Maître du Jeu"},
        source="ws_game",
    )
    await persist_narration(session_id, intro_text, "Maître du Jeu", db)

    # Announce first turn (or trigger AI turns if monster goes first)
    first = active.turn_manager.current_turn
    if first:
        if first.is_ai_controlled:
            await _handle_ai_turns(session_id, active, db)
        else:
            await event_bus.publish_to_session(
                session_id,
                EventType.TURN_START,
                {"combatant_id": first.combatant_id, "combatant_name": first.name},
                source="ws_game",
            )


async def _handle_end_turn(session_id: str, active: Any, db: AsyncSession) -> None:
    """Advance to the next combatant's turn; end combat if all NPCs are down."""
    if not active.turn_manager._order:
        return

    await _sync_ai_control_from_db(session_id, active, db)

    # Remove defeated, surrendered, or fled NPCs before advancing.
    removed_npcs = await _cleanup_inactive_npcs(session_id, active)

    if active.turn_manager.all_npcs_removed():
        await _handle_combat_end(
            session_id,
            active,
            db,
            reason=_combat_end_reason_from_removed(removed_npcs),
            removed_npcs=removed_npcs,
        )
        return

    next_entry = active.turn_manager.next_turn()
    active.turn_number += 1
    active.round_number = active.turn_manager.round_number
    active.mark_dirty()
    await session_manager.save_state(session_id, db)

    if next_entry and next_entry.is_ai_controlled:
        # Next combatant is AI: delegate to _handle_ai_turns (emits TURN_START + SESSION_STATE)
        await _handle_ai_turns(session_id, active, db)
        return

    if next_entry:
        await event_bus.publish_to_session(
            session_id,
            EventType.TURN_START,
            {"combatant_id": next_entry.combatant_id, "combatant_name": next_entry.name},
            source="ws_game",
        )

    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        _build_session_state_payload(session_id),
        source="ws_game",
    )


async def _handle_ai_turns(session_id: str, active: Any, db: AsyncSession) -> None:
    """Trigger all consecutive AI-controlled turns, then emit TURN_START for the next human."""
    await handle_ai_combat_turns(
        session_id,
        active,
        db,
        event_bus=event_bus,
        action_resolver=action_resolver,
        session_manager=session_manager,
        session_state_payload=lambda: _build_session_state_payload(session_id),
        cleanup_inactive_npcs=_cleanup_inactive_npcs,
        handle_combat_end=_handle_combat_end,
        combat_end_reason_from_removed=_combat_end_reason_from_removed,
        auto_death_save=_auto_death_save,
    )


async def _handle_reset_combat(session_id: str, active: Any, db: AsyncSession) -> None:
    """Test utility: exit combat, restore full HP, return to exploration."""
    active.turn_manager.reset()
    active.phase = SessionStatus.EXPLORATION
    active.state_data.pop("combatants", None)
    active.state_data.pop("grid_positions", None)
    active.state_data.pop("grid_config", None)
    active.state_data.pop("grid_decoration", None)
    active.state_data.pop("pending_encounter", None)
    active.state_data["phase"] = SessionStatus.EXPLORATION.value

    # Restore HP in characters snapshot
    characters_data: dict[str, Any] = active.state_data.get("characters", {})
    for cdata in characters_data.values():
        cdata["hp"] = cdata.get("hp_max", cdata.get("hp", 10))

    # Persist to DB
    result = await db.execute(
        select(Character).where(Character.session_id == session_id)
    )
    chars = result.scalars().all()
    for char in chars:
        char.hp_current = char.hp_max
    await db.commit()

    active.mark_dirty()
    await session_manager.save_state(session_id, db)

    await event_bus.publish_to_session(
        session_id,
        EventType.COMBAT_END,
        {"reason": "manual_reset"},
        source="ws_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.PHASE_CHANGE,
        {"phase": SessionStatus.EXPLORATION.value},
        source="ws_game",
    )
    reset_text = "[TEST] Combat annulé. Points de vie restaurés. Retour en exploration."
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": reset_text, "speaker": "Maître du Jeu"},
        source="ws_game",
    )
    await persist_narration(session_id, reset_text, "Maître du Jeu", db)
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        _build_session_state_payload(session_id),
        source="ws_game",
    )


async def _handle_equip_item(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    """Équipe ou retire un objet (toggle) pendant une session active."""
    item_id = action.item_id
    character_id = action.character_id
    if not item_id or not character_id:
        await event_bus.publish_to_session(
            session_id, EventType.ERROR,
            {"message": "item_id et character_id requis pour équiper un objet."},
            source="ws_game",
        )
        return

    try:
        result = await equipment_service.equip_item(
            character_id=character_id,
            item_id=item_id,
            db=db,
            active=active,
        )
    except CharacterNotFoundError:
        await event_bus.publish_to_session(
            session_id, EventType.ERROR,
            {"message": "Personnage introuvable."},
            source="ws_game",
        )
        return
    except ItemNotFoundError:
        await event_bus.publish_to_session(
            session_id, EventType.ERROR,
            {"message": f"Objet '{item_id}' introuvable dans l'inventaire."},
            source="ws_game",
        )
        return

    await event_bus.publish_to_session(
        session_id, EventType.EQUIPMENT_UPDATED,
        {"character_id": character_id, "equipment": result.equipment},
        source="ws_game",
    )
    await event_bus.publish_to_session(
        session_id, EventType.NARRATION,
        {"text": result.narration, "speaker": "Maître du Jeu"},
        source="ws_game",
    )


async def _handle_use_item(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    """Utilise un objet consommable pendant une session (potion = soin)."""
    item_id = action.item_id
    character_id = action.character_id
    if not item_id or not character_id:
        await event_bus.publish_to_session(
            session_id, EventType.ERROR,
            {"message": "item_id et character_id requis pour utiliser un objet."},
            source="ws_game",
        )
        return

    try:
        result = await equipment_service.use_item(
            character_id=character_id,
            item_id=item_id,
            db=db,
            active=active,
        )
    except CharacterNotFoundError:
        await event_bus.publish_to_session(
            session_id, EventType.ERROR,
            {"message": "Personnage introuvable."},
            source="ws_game",
        )
        return
    except ItemNotFoundError:
        await event_bus.publish_to_session(
            session_id, EventType.ERROR,
            {"message": f"Objet '{item_id}' introuvable dans l'inventaire."},
            source="ws_game",
        )
        return

    if result.hp is not None:
        await event_bus.publish_to_session(
            session_id, EventType.HP_CHANGED,
            {"combatant_id": character_id, "delta": result.hp_delta, "hp": result.hp},
            source="ws_game",
        )

    await event_bus.publish_to_session(
        session_id, EventType.EQUIPMENT_UPDATED,
        {"character_id": character_id, "equipment": result.equipment},
        source="ws_game",
    )

    await event_bus.publish_to_session(
        session_id, EventType.NARRATION,
        {"text": result.narration, "speaker": "Maître du Jeu"},
        source="ws_game",
    )


async def _handle_drop_item(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    """Retire définitivement un objet de l'inventaire."""
    item_id = action.item_id
    character_id = action.character_id
    if not item_id or not character_id:
        await event_bus.publish_to_session(
            session_id, EventType.ERROR,
            {"message": "item_id et character_id requis pour lâcher un objet."},
            source="ws_game",
        )
        return

    try:
        result = await equipment_service.drop_item(
            character_id=character_id,
            item_id=item_id,
            db=db,
            active=active,
        )
    except CharacterNotFoundError:
        await event_bus.publish_to_session(
            session_id, EventType.ERROR,
            {"message": "Personnage introuvable."},
            source="ws_game",
        )
        return
    except ItemNotFoundError:
        return

    await event_bus.publish_to_session(
        session_id, EventType.EQUIPMENT_UPDATED,
        {"character_id": character_id, "equipment": result.equipment},
        source="ws_game",
    )
    await event_bus.publish_to_session(
        session_id, EventType.NARRATION,
        {"text": result.narration, "speaker": "Maître du Jeu"},
        source="ws_game",
    )


async def _handle_take_rest(session_id: str, active: Any, db: AsyncSession) -> None:
    """Long rest: restore full HP, spell slots and hit dice."""
    await rest_service.long_rest(
        session_id=session_id,
        active=active,
        db=db,
        session_state_payload=lambda: _build_session_state_payload(session_id),
    )


async def _handle_short_rest(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    """Short rest: spend hit dice chosen by the player."""
    try:
        await rest_service.short_rest(
            session_id=session_id,
            active=active,
            db=db,
            hit_dice_spend=action.hit_dice_spend or {},
            session_state_payload=lambda: _build_session_state_payload(session_id),
        )
    except RestServiceError as exc:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": str(exc)},
            source="ws_game",
        )


async def _handle_move(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    """Handle a movement action: validate, update position, broadcast."""
    if not action.content or "," not in action.content:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "Format de déplacement invalide. Attendu: 'col,row'"},
            source="ws_game",
        )
        return

    try:
        parts = action.content.split(",")
        target_col = int(parts[0].strip())
        target_row = int(parts[1].strip())
    except (ValueError, IndexError):
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "Coordonnées de déplacement invalides."},
            source="ws_game",
        )
        return

    mover_id = action.character_id
    if not mover_id:
        return

    grid_positions: dict[str, Any] = active.state_data.get("grid_positions", {})
    grid_config: dict[str, Any] = active.state_data.get("grid_config", {"cols": 10, "rows": 8})
    grid_cols = int(grid_config.get("cols", 10))
    grid_rows = int(grid_config.get("rows", 8))

    from_data = grid_positions.get(mover_id)
    if from_data is None:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "Position de départ introuvable."},
            source="ws_game",
        )
        return

    from_pos = GridPosition.from_dict(from_data)
    to_pos = GridPosition(col=target_col, row=target_row)

    # Get mover's speed from characters data
    combatants_info: dict[str, Any] = active.state_data.get("combatants", {})
    mover_data = combatants_info.get(mover_id, {})
    speed_m = float(mover_data.get("speed_m", 9.0))

    # Occupied positions (excluding mover)
    occupied = [
        GridPosition.from_dict(v)
        for cid, v in grid_positions.items()
        if cid != mover_id
    ]

    valid, reason = validate_move(from_pos, to_pos, speed_m, grid_cols, grid_rows, occupied)
    if not valid:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": f"Déplacement invalide : {reason}"},
            source="ws_game",
        )
        return

    from app.engine.tactical_grid import distance_m as grid_distance_m
    dist = grid_distance_m(from_pos, to_pos)

    # Update position in state
    grid_positions[mover_id] = to_pos.to_dict()
    active.mark_dirty()

    await event_bus.publish_to_session(
        session_id,
        EventType.COMBATANT_MOVED,
        {
            "combatant_id": mover_id,
            "position": to_pos.to_dict(),
            "movement_used_m": dist,
        },
        source="ws_game",
    )


# ---------------------------------------------------------------------------
# Welcome narration (join en exploration)
# ---------------------------------------------------------------------------


async def _send_welcome_narration(session_id: str, active: Any, db: AsyncSession) -> None:
    """Demande au GMAgent de décrire la scène courante quand un joueur rejoint en exploration."""
    # Guard d'idempotence : atomique en asyncio (pas d'await avant cette ligne)
    if active.state_data.get("welcome_narration_sent"):
        return
    active.state_data["welcome_narration_sent"] = True

    try:
        await event_bus.publish_to_session(
            session_id,
            EventType.AI_THINKING,
            {"agent_kind": "gm", "thinking": True},
            source="ws_game",
        )
        gm_response = await action_resolver._gm.narrate(
            game_state=active.state_data,
            player_action=None,
        )
        welcome_text = gm_response.narration if gm_response else (
            "Bienvenue dans l'aventure ! Décrivez votre action pour commencer."
        )
    except Exception as exc:
        logger.warning("_send_welcome_narration: GMAgent failed: %s", exc)
        welcome_text = "Bienvenue dans l'aventure ! Décrivez votre action pour commencer."
    finally:
        await event_bus.publish_to_session(
            session_id,
            EventType.AI_THINKING,
            {"agent_kind": "gm", "thinking": False},
            source="ws_game",
        )

    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": welcome_text, "speaker": "Maître du Jeu"},
        source="ws_game",
    )
    await persist_narration(session_id, welcome_text, "Maître du Jeu", db)


# ---------------------------------------------------------------------------
# AI control toggle / manual reactions
# ---------------------------------------------------------------------------


async def _handle_toggle_ai_control(
    session_id: str,
    character_id: Optional[str],
    next_is_ai: bool,
    db: AsyncSession,
) -> None:
    """Toggle a character between human and AI control during a live session.

    - Persists ``Character.is_ai`` in DB.
    - Updates the in-memory snapshot (``state_data["characters"]``).
    - Mutates the matching ``TurnEntry.is_ai_controlled`` in the turn order.
    - Registers or unregisters the ``PlayerAgent`` accordingly.
    - Broadcasts ``SESSION_STATE``.
    - If the current turn belongs to the toggled character and it became AI,
      triggers the AI turn loop (combat only) or the exploration reactions.
    """
    if not character_id:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "toggle_ai_control: character_id requis."},
            source="ws_game",
        )
        return

    active = session_manager.get_session(session_id)
    if active is None:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": f"Session '{session_id}' inactive."},
            source="ws_game",
        )
        return

    # --- DB update -------------------------------------------------------
    result = await db.execute(select(Character).where(Character.id == character_id))
    char = result.scalar_one_or_none()
    if char is None:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": f"Personnage '{character_id}' introuvable."},
            source="ws_game",
        )
        return
    char.is_ai = next_is_ai
    await db.commit()

    # --- In-memory state snapshot ---------------------------------------
    chars_data: dict[str, Any] = active.state_data.setdefault("characters", {})
    cdata = chars_data.setdefault(character_id, {})
    cdata["is_ai"] = next_is_ai
    cdata.setdefault("name", char.name)

    # Combatants map (used in combat)
    combatants_info: dict[str, Any] = active.state_data.get("combatants", {})
    if character_id in combatants_info:
        combatants_info[character_id]["is_ai"] = next_is_ai

    # --- TurnManager ----------------------------------------------------
    for entry in active.turn_manager._order:
        if entry.combatant_id == character_id:
            entry.is_ai_controlled = next_is_ai
            break

    # --- PlayerAgent registry ------------------------------------------
    from app.game.ai_player_manager import register_ai_player, unregister_ai_player
    if next_is_ai:
        register_ai_player(active, character_id, cdata)
    else:
        unregister_ai_player(active, character_id)

    active.mark_dirty()
    await session_manager.save_state(session_id, db)

    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        _build_session_state_payload(session_id),
        source="ws_game",
    )

    # --- If the toggled character is currently up, hand over to AI -----
    current = active.turn_manager.current_turn
    if next_is_ai and current and current.combatant_id == character_id:
        if active.phase == SessionStatus.COMBAT:
            await _handle_ai_turns(session_id, active, db)
        else:
            from app.game.ai_player_manager import AIPlayerManager
            try:
                if is_sober_mode():
                    await AIPlayerManager().run_party_reaction_batch(
                        session_id,
                        active,
                        "Le groupe sollicite l'avis des compagnons.",
                        trigger_character_id=None,
                        db=db,
                    )
                else:
                    await AIPlayerManager().run_exploration_reactions(
                        session_id, active, action_resolver, trigger_character_id=None, db=db
                    )
                await _consume_pending_combat_transition(
                    session_id,
                    active,
                    db,
                    force=active.phase == SessionStatus.ENCOUNTER_START,
                )
            except Exception as exc:
                logger.error("toggle_ai_control: exploration reactions failed: %s", exc)


async def _handle_trigger_ai_reactions(
    session_id: str,
    db: AsyncSession,
    trigger_character_id: Optional[str] = None,
) -> None:
    """Manual fallback: let AI companions react without a preceding human action."""
    active = session_manager.get_session(session_id)
    if active is None:
        return

    if active.phase == SessionStatus.COMBAT:
        # In combat, only makes sense when the current turn is AI.
        current = active.turn_manager.current_turn
        if current is None or not current.is_ai_controlled:
            return
        await _handle_ai_turns(session_id, active, db)
        return

    if not active.ai_players:
        return

    # Exploration: let each AI companion react once.
    from app.game.ai_player_manager import AIPlayerManager
    if is_sober_mode():
        await AIPlayerManager().run_party_reaction_batch(
            session_id,
            active,
            "Le groupe sollicite l'avis des compagnons.",
            trigger_character_id=trigger_character_id,
            db=db,
        )
    else:
        await AIPlayerManager().run_exploration_reactions(
            session_id,
            active,
            action_resolver,
            trigger_character_id=trigger_character_id,
            db=db,
        )
    await _consume_pending_combat_transition(
        session_id,
        active,
        db,
        force=active.phase == SessionStatus.ENCOUNTER_START,
    )


async def _consume_pending_combat_transition(
    session_id: str,
    active: Any,
    db: AsyncSession,
    *,
    force: bool,
) -> bool:
    """Consume a pending COMBAT transition only after combat handling succeeds."""
    pending_transition = active.state_data.get("pending_phase_transition")
    if pending_transition != "COMBAT" or active.phase == SessionStatus.COMBAT:
        return False

    await _handle_start_combat(
        session_id,
        active,
        db,
        encounter_id=None,
        force=force,
    )
    active.state_data.pop("pending_phase_transition", None)
    active.mark_dirty()
    await session_manager.save_state(session_id, db)
    return True


# ---------------------------------------------------------------------------
# Action dispatcher
# ---------------------------------------------------------------------------


async def _dispatch_action(
    session_id: str,
    action: PlayerActionMessage,
    db: AsyncSession,
) -> None:
    """Process a player action through the full pipeline and broadcast results."""
    active = session_manager.get_session(session_id)
    if active is None:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": f"Session '{session_id}' is not active."},
            source="ws_game",
        )
        return

    if (
        active.phase in (SessionStatus.EXPLORATION, SessionStatus.ENCOUNTER_START)
        and prime_combat_from_aggressive_action(
            active,
            action_type=action.action_type,
            content=action.content,
            target_id=action.target_id,
        )
    ):
        await _consume_pending_combat_transition(session_id, active, db, force=True)
        return

    if active.phase == SessionStatus.COMBAT:
        await _sync_ai_control_from_db(session_id, active, db)
        current = active.turn_manager.current_turn
        if (
            action.action_type == "end_turn"
            and current is not None
            and current.is_ai_controlled
        ):
            await _handle_ai_turns(session_id, active, db)
            return
        if await _reject_out_of_turn_action(session_id, action, active):
            return

    # ----------------------------------------------------------------
    # Guard : un joueur inconscient ne peut pas attaquer ni lancer de sort
    # ----------------------------------------------------------------
    if action.action_type in ("attack", "cast_spell") and action.character_id:
        _combatants = active.state_data.get("combatants", {})
        _cdata = _combatants.get(action.character_id, {})
        if int(_cdata.get("hp", 1)) == 0:
            await event_bus.publish_to_session(
                session_id,
                EventType.NARRATION,
                {
                    "text": (
                        "Vous êtes inconscient(e) — effectuez votre jet de sauvegarde "
                        "contre la mort."
                    ),
                    "speaker": "Maître du Jeu",
                },
                source="ws_game",
            )
            return

    # ----------------------------------------------------------------
    # Route special action types directly (bypass GM agent)
    # ----------------------------------------------------------------
    if action.action_type == "move":
        await _handle_move(session_id, action, active, db)
        return

    if action.action_type == "end_turn":
        await _handle_end_turn(session_id, active, db)
        return

    if action.action_type == "start_combat":
        # Optional: client may pass encounter_id in content to trigger a preset
        encounter_id: Optional[str] = action.content if action.content else None
        await _handle_start_combat(
            session_id,
            active,
            db,
            encounter_id=encounter_id,
            force=True,
        )
        return

    if action.action_type in ("take_rest", "long_rest"):
        await _handle_take_rest(session_id, active, db)
        return

    if action.action_type == "short_rest":
        await _handle_short_rest(session_id, action, active, db)
        return

    if action.action_type == "reset_combat":
        await _handle_reset_combat(session_id, active, db)
        return

    if action.action_type == "equip":
        await _handle_equip_item(session_id, action, active, db)
        return

    if action.action_type == "use_item":
        await _handle_use_item(session_id, action, active, db)
        return

    if action.action_type == "drop_item":
        await _handle_drop_item(session_id, action, active, db)
        return

    # ----------------------------------------------------------------
    # Normal action: exploration scene flow or combat pipeline.
    # ----------------------------------------------------------------
    if active.phase != SessionStatus.COMBAT:
        from app.services.narrative_flow_service import NarrativeFlowService

        await NarrativeFlowService().handle_exploration_action(
            session_id=session_id,
            action=action,
            active=active,
            action_resolver=action_resolver,
            db=db,
        )

        if await _consume_pending_combat_transition(
                session_id,
                active,
                db,
                force=active.phase == SessionStatus.ENCOUNTER_START,
        ):
            return

        active.turn_number += 1
        active.mark_dirty()
        await session_manager.save_state(session_id, db)
        await event_bus.publish_to_session(
            session_id,
            EventType.TURN_END,
            {"turn_number": active.turn_number},
            source="ws_game",
        )
        return

    await action_resolver.resolve(
        session_id=session_id,
        action_type=action.action_type,
        content=action.content,
        character_id=action.character_id,
        target_id=_combat_target_id(action, active) or action.target_id,
        active=active,
        db=db,
        spell_id=action.spell_id,
        slot_level=action.slot_level,
    )

    if await _consume_pending_combat_transition(
            session_id,
            active,
            db,
            force=True,
    ):
        return

    # After resolution: check for inactive NPC combatants
    if active.phase == SessionStatus.COMBAT:
        removed_npcs = await _cleanup_inactive_npcs(session_id, active)
        if active.turn_manager.all_npcs_removed():
            await _handle_combat_end(
                session_id,
                active,
                db,
                reason=_combat_end_reason_from_removed(removed_npcs),
                removed_npcs=removed_npcs,
            )
            return
        # Auto-advance turn: one action = end of turn
        await _handle_end_turn(session_id, active, db)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/ws/game/{session_id}")
async def game_websocket(
    websocket: WebSocket,
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Main WebSocket endpoint for real-time game communication."""
    if not websocket_has_valid_access_token(websocket):
        await websocket.close(code=4401)
        return

    await websocket.accept()

    # ------------------------------------------------------------------
    # 1. Open / load session
    # ------------------------------------------------------------------
    try:
        await session_manager.open_session(session_id, db)
    except KeyError:
        await websocket.send_json({
            "event_type": EventType.ERROR,
            "session_id": session_id,
            "payload": {"message": f"Session '{session_id}' not found."},
        })
        await websocket.close(code=4404)
        return

    # ------------------------------------------------------------------
    # 2. Register connection and subscribe to event bus
    # ------------------------------------------------------------------
    connection_manager.connect(session_id, websocket)
    queue = event_bus.subscribe(session_id, maxsize=settings.ws_event_queue_size)

    relay_task = create_logged_task(_relay_events(websocket, queue), "ws_game.relay_events")

    # ------------------------------------------------------------------
    # 3. Send initial session state
    # ------------------------------------------------------------------
    await websocket.send_json({
        "event_type": EventType.SESSION_STATE,
        "session_id": session_id,
        "payload": _build_session_state_payload(session_id),
    })

    character_id: Optional[str] = None

    try:
        # ----------------------------------------------------------------
        # 4. Receive loop
        # ----------------------------------------------------------------
        while True:
            try:
                raw = await websocket.receive_json()
            except Exception:
                break
            if not isinstance(raw, dict):
                await websocket.send_json({
                    "event_type": EventType.ERROR,
                    "session_id": session_id,
                    "payload": {"message": "Message WebSocket invalide."},
                })
                continue

            msg_type = raw.get("type", "")

            # --- ping ---------------------------------------------------
            if msg_type == "ping":
                try:
                    PingMessage(**raw)
                except ValidationError:
                    await send_ws_error(websocket, session_id, VALIDATION_ERROR_MESSAGE)
                    continue
                await websocket.send_json({"event_type": "pong"})
                continue

            # --- join ---------------------------------------------------
            if msg_type == "join":
                try:
                    join = JoinMessage(**raw)
                except ValidationError:
                    await send_ws_error(websocket, session_id, VALIDATION_ERROR_MESSAGE)
                    continue

                async with session_manager.session_lock(session_id):
                    character_id = join.character_id
                    if not await character_belongs_to_session(session_id, character_id, db):
                        character_id = None
                        await send_ws_error(
                            websocket,
                            session_id,
                            "Personnage introuvable dans cette session.",
                        )
                        continue
                    await event_bus.publish_to_session(
                        session_id,
                        EventType.PLAYER_JOINED,
                        {"character_id": character_id},
                        source="ws_game",
                    )
                    logger.info(
                        "Player joined session %s with character %s.",
                        session_id,
                        character_id,
                    )

                    # Si la session est déjà en exploration, le MJ décrit la scène
                    active_on_join = session_manager.get_session(session_id)
                    if active_on_join:
                        await _sync_ai_control_from_db(session_id, active_on_join, db)
                    if active_on_join and active_on_join.phase == SessionStatus.EXPLORATION:
                        await _send_welcome_narration(session_id, active_on_join, db)
                    elif active_on_join and active_on_join.phase == SessionStatus.COMBAT:
                        # Rejouer l'état de combat pour ce client qui se (re)connecte
                        await websocket.send_json({
                            "event_type": "combat_start",
                            "session_id": session_id,
                            "payload": _build_combat_start_payload(active_on_join),
                        })
                        current = active_on_join.turn_manager.current_turn
                        if current:
                            await websocket.send_json({
                                "event_type": EventType.TURN_START,
                                "session_id": session_id,
                                "payload": {
                                    "combatant_id": current.combatant_id,
                                    "combatant_name": current.name,
                                },
                            })
                            if current.is_ai_controlled:
                                await _handle_ai_turns(session_id, active_on_join, db)
                continue

            # --- action -------------------------------------------------
            if msg_type == "action":
                try:
                    action = PlayerActionMessage(**raw)
                except ValidationError:
                    await send_ws_error(websocket, session_id, VALIDATION_ERROR_MESSAGE)
                    continue

                try:
                    async with session_manager.session_lock(session_id):
                        await _dispatch_action(session_id, action, db)
                except Exception as exc:
                    logger.error("Unhandled error in _dispatch_action: %s", exc, exc_info=True)
                    await event_bus.publish_to_session(
                        session_id,
                        EventType.ERROR,
                        {"message": "Une erreur interne s'est produite. Réessayez."},
                        source="ws_game",
                    )
                continue

            # --- toggle_ai_control --------------------------------------
            if msg_type == "toggle_ai_control":
                try:
                    msg = ToggleAiControlMessage(**raw)
                    async with session_manager.session_lock(session_id):
                        await _handle_toggle_ai_control(
                            session_id,
                            character_id=msg.character_id,
                            next_is_ai=msg.is_ai,
                            db=db,
                        )
                except ValidationError:
                    await send_ws_error(websocket, session_id, VALIDATION_ERROR_MESSAGE)
                except Exception as exc:
                    logger.error(
                        "Unhandled error in toggle_ai_control: %s", exc, exc_info=True
                    )
                    await event_bus.publish_to_session(
                        session_id,
                        EventType.ERROR,
                        {"message": f"Erreur toggle IA : {exc}"},
                        source="ws_game",
                    )
                continue

            # --- trigger_ai_reactions -----------------------------------
            if msg_type == "trigger_ai_reactions":
                try:
                    msg = TriggerAiReactionsMessage(**raw)
                    async with session_manager.session_lock(session_id):
                        await _handle_trigger_ai_reactions(
                            session_id,
                            db,
                            trigger_character_id=msg.character_id,
                        )
                except ValidationError:
                    await send_ws_error(websocket, session_id, VALIDATION_ERROR_MESSAGE)
                except Exception as exc:
                    logger.error(
                        "Unhandled error in trigger_ai_reactions: %s", exc, exc_info=True
                    )
                    await event_bus.publish_to_session(
                        session_id,
                        EventType.ERROR,
                        {"message": f"Erreur déclenchement IA : {exc}"},
                        source="ws_game",
                    )
                continue

            # --- unknown type -------------------------------------------
            await websocket.send_json({
                "event_type": EventType.ERROR,
                "session_id": session_id,
                "payload": {"message": f"Unknown message type: '{msg_type}'."},
            })

    except WebSocketDisconnect:
        pass
    finally:
        # ----------------------------------------------------------------
        # 5. Cleanup
        # ----------------------------------------------------------------
        relay_task.cancel()
        await asyncio.gather(relay_task, return_exceptions=True)

        event_bus.unsubscribe(session_id, queue)
        connection_manager.disconnect(session_id, websocket)

        if character_id:
            await event_bus.publish_to_session(
                session_id,
                EventType.PLAYER_LEFT,
                {"character_id": character_id},
                source="ws_game",
            )

        if connection_manager.connection_count(session_id) == 0:
            try:
                async with session_manager.session_lock(session_id):
                    await session_manager.close_session(session_id, db)
            except Exception as exc:
                logger.warning(
                    "Error closing session %s on last disconnect: %s", session_id, exc
                )

        logger.info("WS closed: session=%s character=%s", session_id, character_id)
