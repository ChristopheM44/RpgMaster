"""Combat orchestration handlers and helpers used by the game WebSocket facade."""
from __future__ import annotations

import asyncio
import logging
import random
import re
from copy import deepcopy
from typing import Any, Callable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ws_payloads import (
    build_combat_start_payload,
    build_session_state_payload,
    character_snapshot,
    compute_ac_from_equipment,
    format_monster_actions,
    monster_color,
    monster_token_for_combatant,
)
from app.api.ws_schemas import PlayerActionMessage
from app.db.database import async_session
from app.engine.loot import loot_for_encounter
from app.engine.tactical_grid import GridPosition, initialize_positions
from app.engine.xp import level_from_xp
from app.game.action_resolver import ActionResolver
from app.game.combat_stats import build_combatant_combat_stats
from app.game.constants import INACTIVE_STATUSES
from app.game.event_bus import EventType, event_bus
from app.game.runtime import session_manager
from app.game.state_sync import sync_character_state
from app.game.tactical_combat import apply_tactical_move, calculate_reachable_cells, grid_position_for
from app.game.turn_manager import CombatantInfo
from app.models.character import Character
from app.models.session import SessionStatus
from app.services.encounter_service import encounter_service
from app.services.local_map_service import element_grid_cells
from app.services.level_up_service import level_up_service
from app.services.message_service import load_recent_messages, persist_narration
from app.game.social_resolution import (
    _is_combat_social_text as is_combat_social_text,
    _SOCIAL_COMBAT_MARKERS as SOCIAL_COMBAT_MARKERS,
)
from app.api.ws_handlers.ai_control import handle_ai_turns as handle_ai_combat_turns
from app.api.ws_handlers.encounter_intro import (
    execute_intro_scene_layout,
    generate_encounter_intro,
    is_async_callable,
    is_unhelpful_intro,
    pause_at_encounter_start,
    should_pause_for_encounter_intro,
)
from app.api.ws_handlers.session import sync_ai_control_from_db

logger = logging.getLogger(__name__)
action_resolver = ActionResolver()

TURN_BOUND_COMBAT_ACTIONS = {
    "attack",
    "cast_spell",
    "death_save",
    "disengage",
    "dash",
    "dodge",
    "end_turn",
    "equip",
    "free_text",
    "hide",
    "move",
    "shove",
    "stabilize",
    "use_item",
    "wait",
}

_ENCOUNTER_END_ACTION_TYPES = {
    "scene_layout",
    "journal_update",
    "quest_add",
    "chronicle_add",
    "xp_grant",
    "currency_grant",
    "currency_spend",
    "loot_grant",
    "item_remove",
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


def normalized_phrase(text: Optional[str]) -> str:
    if not text:
        return ""
    normalized = text.casefold().replace("’", "'")
    return re.sub(r"\s+", " ", normalized)


def active_npc_ids(active: Any) -> list[str]:
    combatants: dict[str, Any] = active.state_data.get("combatants", {})
    result: list[str] = []
    for cid, cdata in combatants.items():
        if not isinstance(cdata, dict) or cdata.get("is_player", True):
            continue
        status = str(cdata.get("status", "active")).lower()
        try:
            hp = int(cdata.get("hp", 1))
        except (TypeError, ValueError):
            hp = 1
        if hp > 0 and status not in INACTIVE_STATUSES:
            result.append(cid)
    return result


def combat_target_id(action: PlayerActionMessage, active: Any) -> Optional[str]:
    if action.target_id:
        return action.target_id
    if action.action_type != "free_text" or not is_combat_social_text(action.content):
        return None
    active_npcs = active_npc_ids(active)
    return active_npcs[0] if len(active_npcs) == 1 else None


async def reject_out_of_turn_action(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    *,
    event_bus: Any,
    source: str = "ws_game",
) -> bool:
    if action.action_type not in TURN_BOUND_COMBAT_ACTIONS or not action.character_id:
        return False
    current = active.turn_manager.current_turn
    if current is None:
        return False
    if action.action_type == "end_turn" and current.is_ai_controlled:
        return False
    if action.character_id == current.combatant_id:
        return False

    await event_bus.publish_to_session(
        session_id,
        EventType.ERROR,
        {
            "message": (
                f"Ce n'est pas le tour de ce personnage. "
                f"Tour actuel : {current.name}."
            )
        },
        source=source,
    )
    return True


def combat_end_reason_from_removed(removed: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status", "defeated")) for item in removed}
    if not statuses:
        return "victory"
    if statuses == {"surrendered"}:
        return "surrender"
    if statuses == {"fled"}:
        return "fled"
    if statuses & {"surrendered", "fled"}:
        return "resolved"
    return "victory"


def combat_end_text(reason: str) -> str:
    if reason == "surrender":
        return "Le dernier adversaire se rend. Le combat prend fin et le calme revient."
    if reason == "fled":
        return "Les derniers adversaires prennent la fuite. Le combat prend fin."
    if reason == "resolved":
        return "La menace est neutralisée. Le combat prend fin."
    return "Victoire ! Tous les ennemis ont été vaincus. Le calme revient."


def npc_removed_text(name: str, status: str) -> str:
    if status == "surrendered":
        return f"{name} se rend et quitte l'initiative."
    if status == "fled":
        return f"{name} fuit le combat !"
    return f"{name} a été vaincu !"


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
        for key in ("monster_id", "species", "cr", "xp"):
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

    total_monster_xp = sum(
        _safe_int(enemy.get("xp"), 0)
        for group in (enemies_defeated, enemies_fled, enemies_surrendered)
        for enemy in group
    )
    total_cr = sum(
        float(enemy.get("cr") or 0)
        for group in (enemies_defeated, enemies_fled, enemies_surrendered)
        for enemy in group
    )

    return {
        "outcome": "partial" if enemies_unresolved else "victory",
        "party": party,
        "enemies_defeated": enemies_defeated,
        "enemies_fled": enemies_fled,
        "enemies_surrendered": enemies_surrendered,
        "enemies_unresolved": enemies_unresolved,
        "total_enemies": total_enemies,
        "total_monster_xp": total_monster_xp,
        "total_cr": total_cr,
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
                "Le combat a laisse ici un corps, des armes tombees et des traces visibles."
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
    aftermath_enemies.extend(("fled", enemy) for enemy in combat_summary.get("enemies_fled", []))
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
        "cell_size_m": base_scene.get("cell_size_m") or grid_config.get("cell_size_m") or 1.5,
        "terrain": base_scene.get("terrain") or "battlefield_aftermath",
        "pois": pois,
        "exits": deepcopy(base_scene.get("exits", []) or []),
        "party_positions": party_positions,
    }


def _suggested_xp(combat_summary: dict[str, Any]) -> dict[str, Any]:
    party_size = max(1, len(combat_summary.get("party") or []))
    total_xp = int(combat_summary.get("total_monster_xp") or 0)
    per_character = total_xp // party_size if total_xp > 0 else 0
    return {
        "target": "party",
        "amount_per_character": per_character,
        "total_monster_xp": total_xp,
        "party_size": party_size,
    }


def _suggested_loot(combat_summary: dict[str, Any]) -> dict[str, Any]:
    rng_seed = repr(
        (
            combat_summary.get("battlefield_location"),
            combat_summary.get("round_number"),
            combat_summary.get("total_monster_xp"),
            combat_summary.get("total_cr"),
        )
    )
    loot = loot_for_encounter(
        total_cr=float(combat_summary.get("total_cr") or 0),
        monster_xp=int(combat_summary.get("total_monster_xp") or 0),
        difficulty="medium",
        rng=random.Random(rng_seed),
    )
    return loot.as_dict()


def _campaign_custom_monsters(active: Any) -> list[dict[str, Any]]:
    context = active.state_data.get("campaign_context")
    if not isinstance(context, dict):
        return []
    custom_monsters = context.get("custom_monsters")
    if not isinstance(custom_monsters, list):
        return []
    return [item for item in custom_monsters if isinstance(item, dict)]


def _build_session_state_payload(session_id: str) -> dict[str, Any]:
    return build_session_state_payload(session_id, session_manager.get_session(session_id))


def _build_combat_start_payload(active: Any) -> dict[str, Any]:
    return build_combat_start_payload(active, encounter_service)


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


async def _handle_level_up_phase_if_needed(
    session_id: str,
    active: Any,
    db: AsyncSession,
) -> bool:
    query = db.execute(select(Character).where(Character.session_id == session_id))
    if not hasattr(query, "__await__"):
        return False
    result = await query
    characters = list(result.scalars().all())
    eligible = [
        char
        for char in characters
        if level_from_xp(int(getattr(char, "xp", 0) or 0)) > int(char.level or 1)
    ]
    if not eligible:
        return False

    await _transition_active_phase(session_id, active, db, SessionStatus.LEVEL_UP)
    await event_bus.publish_to_session(
        session_id,
        EventType.PHASE_CHANGE,
        {"phase": SessionStatus.LEVEL_UP.value},
        source="ws_game",
    )

    leveled_names: list[str] = []
    for char in eligible:
        applied = await level_up_service.level_up_character(
            session_id=session_id,
            character_id=char.id,
            db=db,
            active=active,
        )
        if applied.applied:
            leveled_names.append(f"{applied.character.name} niveau {applied.result.new_level}")

    if leveled_names:
        await event_bus.publish_to_session(
            session_id,
            EventType.NARRATION,
            {
                "text": "Montée de niveau : " + ", ".join(leveled_names) + ".",
                "speaker": "Maître du Jeu",
            },
            source="ws_game",
        )

    await _transition_active_phase(session_id, active, db, SessionStatus.EXPLORATION)
    await event_bus.publish_to_session(
        session_id,
        EventType.PHASE_CHANGE,
        {"phase": SessionStatus.EXPLORATION.value},
        source="ws_game",
    )
    return True


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
    db: AsyncSession,
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
        db=db,
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
    from app.api import ws_game
    gm_agent = getattr(ws_game.action_resolver, "_gm", None)
    run_end = getattr(gm_agent, "run_encounter_end", None)
    if not callable(run_end) or not is_async_callable(run_end):
        return None, False

    response: Any = None
    suggested_xp = _suggested_xp(combat_summary)
    suggested_loot = _suggested_loot(combat_summary)
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
            suggested_loot=suggested_loot,
            suggested_xp=suggested_xp,
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

    scene_applied = await _execute_encounter_end_actions(session_id, active, db, response)
    narration = getattr(response, "narration", "")
    if is_unhelpful_intro(narration):
        return None, scene_applied
    return str(narration).strip(), scene_applied


async def _publish_action_economy(
    session_id: str,
    combatant_id: str,
    action_economy: Any,
    active: Any | None = None,
) -> None:
    payload: dict[str, Any] = {
        "combatant_id": combatant_id,
        "action_economy": getattr(action_economy, "__dict__", action_economy),
    }
    if active is not None:
        reachable = calculate_reachable_cells(active, combatant_id)
        if reachable is not None:
            payload["reachable_cells"] = reachable
    await event_bus.publish_to_session(
        session_id,
        EventType.ACTION_ECONOMY_CHANGED,
        payload,
        source="ws_game",
    )


# ---------------------------------------------------------------------------
# Core exported combat actions
# ---------------------------------------------------------------------------


async def auto_death_save(
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


async def cleanup_inactive_npcs(session_id: str, active: Any) -> list[dict[str, Any]]:
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
                {"text": npc_removed_text(name, status), "speaker": "Maître du Jeu"},
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
                (idx for idx, item in enumerate(resolved_npcs) if item.get("combatant_id") == cid),
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


async def handle_combat_end(
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
    active.state_data.pop("encounter_monsters", None)
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

    leveled_up = await _handle_level_up_phase_if_needed(session_id, active, db)
    if not leveled_up:
        await _transition_active_phase(session_id, active, db, SessionStatus.EXPLORATION)
        await event_bus.publish_to_session(
            session_id,
            EventType.PHASE_CHANGE,
            {"phase": SessionStatus.EXPLORATION.value},
            source="ws_game",
        )

    victory_text = aftermath_text or combat_end_text(reason)
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


async def handle_start_combat(
    session_id: str,
    active: Any,
    db: AsyncSession,
    encounter_id: Optional[str] = None,
    *,
    force: bool = False,
) -> None:
    """Spawn an encounter, roll initiative, and start combat."""
    if active.phase == SessionStatus.COMBAT:
        logger.warning(
            "handle_start_combat: combat déjà en cours pour session=%s — ignoré.",
            session_id,
        )
        return

    from app.api import ws_game
    await ws_game._sync_ai_control_from_db(session_id, active, db)

    characters_data: dict[str, Any] = active.state_data.get("characters", {})
    party_levels = [int(c.get("level", 1)) for c in characters_data.values()]
    if not party_levels:
        party_levels = [1]

    intro_text: Optional[str] = None
    built = None

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
            candidate = encounter_service.build_from_monster_ids(
                monster_ids,
                custom_monsters=_campaign_custom_monsters(active),
            )
            if candidate.entries:
                built = candidate
            else:
                logger.warning(
                    "handle_start_combat: aucun monster_id valide dans pending_encounter %s, fallback.",
                    monster_ids,
                )

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

    encounter_monsters = dict(getattr(built, "monsters_by_id", {}) or {})
    npc_combatants = encounter_service.expand(built)

    combatants_list: list[CombatantInfo] = []
    combatants_info: dict[str, Any] = {}

    for char_id, cdata in characters_data.items():
        dex = int(cdata.get("dex", 10))
        dex_mod = (dex - 10) // 2
        combat_stats = build_combatant_combat_stats(cdata)
        combatants_list.append(
            CombatantInfo(
                combatant_id=char_id,
                name=cdata["name"],
                dex_score=dex,
                is_player=True,
                speed=float(combat_stats.get("speed_m", 9.0)),
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
            "ac": compute_ac_from_equipment(char_equipment, dex_mod),
            **combat_stats,
        }

    npc_names: list[str] = []
    for npc in npc_combatants:
        cid = npc["combatant_id"]
        encounter_service._ensure_loaded()
        monster_id_base = "_".join(cid.rsplit("_", 1)[:-1]) if "_" in cid else cid
        monster_data = encounter_monsters.get(
            monster_id_base
        ) or encounter_service._monsters_by_id.get(monster_id_base, {})
        first_action = next(
            (a for a in monster_data.get("actions", []) if a.get("attack_bonus") is not None),
            {},
        )
        first_action_type = str(first_action.get("type") or "").lower()
        first_action_range = first_action.get("range_m")
        if isinstance(first_action_range, list):
            first_action_range = first_action_range[0] if first_action_range else None
        attack_range_m = (
            first_action_range
            if first_action_type in {"ranged_attack", "melee_or_ranged_attack"}
            and isinstance(first_action_range, (int, float))
            else first_action.get("reach_m", 1.5)
        )
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
            "base_srd_id": monster_data.get("base_srd_id"),
            "ac": npc["ac"],
            "attack_bonus": npc["attack_bonus"],
            "damage_notation": npc["damage_notation"],
            "speed_m": (monster_data.get("speed") or {}).get("walk", 9.0),
            "reach_m": first_action.get("reach_m", 1.5),
            "attack_range_m": attack_range_m,
            "species": monster_data.get("type"),
            "cr": monster_data.get("cr"),
            "xp": monster_data.get("xp", npc.get("xp", 0)),
            "ability_scores": monster_data.get("ability_scores", {}),
            "actions": format_monster_actions(monster_data.get("actions", [])),
            "traits": monster_data.get("traits", []),
            "damage_resistances": monster_data.get("damage_resistances", []),
            "damage_immunities": monster_data.get("damage_immunities", []),
            "damage_vulnerabilities": monster_data.get("damage_vulnerabilities", []),
            "condition_immunities": monster_data.get("condition_immunities", []),
            "description": monster_data.get("description"),
            "color": monster_color(monster_data.get("type")),
            "token": monster_token_for_combatant(
                monster_data.get("name_fr") or monster_data.get("name") or npc["name"],
                cid,
                npc["name"],
            ),
        }
        npc_names.append(npc["name"])

    from app.game.ai_player_manager import register_ai_player

    for char_id, cdata in characters_data.items():
        register_ai_player(active, char_id, cdata)

    active.turn_manager.setup_combat(combatants_list)
    active.state_data["combatants"] = combatants_info
    if encounter_monsters:
        active.state_data["encounter_monsters"] = encounter_monsters
    else:
        active.state_data.pop("encounter_monsters", None)

    scene = active.state_data.get("current_scene") or {}
    grid_cols = int(scene.get("cols", 12))
    grid_rows = int(scene.get("rows", 12))
    cell_size_m = float(scene.get("cell_size_m", 1.5))
    scene_theme = scene.get("scene_theme") or scene.get("terrain") or "forest"
    exploration_positions = scene.get("party_positions") or {}

    player_ids = [cid for cid, c in combatants_info.items() if c["is_player"]]
    npc_ids = [cid for cid, c in combatants_info.items() if not c["is_player"]]

    grid_positions = initialize_positions(
        player_ids,
        npc_ids,
        grid_cols,
        grid_rows,
        exploration_positions=exploration_positions,
    )
    active.state_data["grid_positions"] = {
        cid: pos.to_dict() for cid, pos in grid_positions.items()
    }

    grid_decor = active.state_data.get("grid_decoration") or {}
    obstacles_list = list(grid_decor.get("obstacles", []))
    difficult_list = list(grid_decor.get("difficult", []))

    for poi in scene.get("pois", []):
        kind = str(poi.get("kind", "")).lower()
        pos = poi.get("position")
        if isinstance(pos, dict) and "col" in pos and "row" in pos:
            if kind == "cover" and pos not in obstacles_list:
                obstacles_list.append(pos)
            elif kind == "hazard" and pos not in difficult_list:
                difficult_list.append(pos)

    for element in scene.get("elements", []):
        if not isinstance(element, dict):
            continue
        element_kind = str(element.get("kind") or "").lower()
        cells = element_grid_cells(element, grid_cols, grid_rows)
        if element_kind == "hazard":
            for cell in cells:
                if cell not in difficult_list:
                    difficult_list.append(cell)
            continue
        if element.get("blocks_movement") or element_kind in {"cover", "furniture"}:
            for cell in cells:
                if cell not in obstacles_list:
                    obstacles_list.append(cell)

    active.state_data["grid_decoration"] = {
        "obstacles": obstacles_list,
        "difficult": difficult_list,
        "zones": grid_decor.get("zones", []),
    }

    active.state_data["grid_config"] = {
        "cols": grid_cols,
        "rows": grid_rows,
        "cell_size_m": cell_size_m,
        "scene_theme": scene_theme,
    }

    if should_generate_intro:
        from app.api import ws_game
        generated_intro = await ws_game._generate_encounter_intro(
            session_id,
            active,
            db,
            combatants_info,
        )
        if generated_intro:
            intro_text = generated_intro
            start_mode = active.state_data.pop("_encounter_intro_start_mode", None)
            should_pause = start_mode == "pause" or (
                start_mode is None and should_pause_for_encounter_intro(generated_intro)
            )
            if not force and should_pause:
                await pause_at_encounter_start(
                    session_id,
                    active,
                    db,
                    pending,
                    generated_intro,
                    session_manager=session_manager,
                    event_bus=event_bus,
                    session_state_payload=lambda: ws_game._build_session_state_payload(session_id),
                    persist_narration=persist_narration,
                )
                return

    active.phase = SessionStatus.COMBAT
    active.round_number = 1
    active.mark_dirty()
    await session_manager.save_state(session_id, db)

    await event_bus.publish_to_session(
        session_id,
        EventType.PHASE_CHANGE,
        {"phase": SessionStatus.COMBAT.value},
        source="ws_game",
    )

    from app.api import ws_game
    await event_bus.publish_to_session(
        session_id,
        "combat_start",
        ws_game._build_combat_start_payload(active),
        source="ws_game",
    )

    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        ws_game._build_session_state_payload(session_id),
        source="ws_game",
    )

    if not intro_text:
        enemy_list = ", ".join(npc_names) if npc_names else "des ennemis"
        verb = "surgissent" if len(npc_names) > 1 else "surgit"
        intro_text = (
            f"{enemy_list} {verb} devant vous ! L'initiative est lancée — le combat commence !"
        )
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": intro_text, "speaker": "Maître du Jeu"},
        source="ws_game",
    )
    await ws_game.persist_narration(session_id, intro_text, "Maître du Jeu", db)

    first = active.turn_manager.current_turn
    if first:
        if first.is_ai_controlled:
            await ws_game._handle_ai_turns(session_id, active, db)
        else:
            await event_bus.publish_to_session(
                session_id,
                EventType.TURN_START,
                {"combatant_id": first.combatant_id, "combatant_name": first.name},
                source="ws_game",
            )


async def handle_end_turn(session_id: str, active: Any, db: AsyncSession) -> None:
    """Advance to the next combatant's turn; end combat if all NPCs are down."""
    if not active.turn_manager._order:
        return

    await sync_ai_control_from_db(session_id, active, db)

    removed_npcs = await cleanup_inactive_npcs(session_id, active)

    if active.turn_manager.all_npcs_removed():
        await handle_combat_end(
            session_id,
            active,
            db,
            reason=combat_end_reason_from_removed(removed_npcs),
            removed_npcs=removed_npcs,
        )
        return

    next_entry = active.turn_manager.next_turn()
    active.turn_number += 1
    active.round_number = active.turn_manager.round_number
    active.mark_dirty()
    await session_manager.save_state(session_id, db)

    if next_entry and next_entry.is_ai_controlled:
        await handle_ai_turns(session_id, active, db)
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


async def handle_ai_turns(session_id: str, active: Any, db: AsyncSession) -> None:
    """Trigger all consecutive AI-controlled turns, then emit TURN_START for the next human."""
    from app.api import ws_game
    await handle_ai_combat_turns(
        session_id,
        active,
        db,
        event_bus=event_bus,
        action_resolver=ws_game.action_resolver,
        session_manager=session_manager,
        session_state_payload=lambda: _build_session_state_payload(session_id),
        cleanup_inactive_npcs=cleanup_inactive_npcs,
        handle_combat_end=handle_combat_end,
        combat_end_reason_from_removed=combat_end_reason_from_removed,
        auto_death_save=auto_death_save,
    )


async def handle_reset_combat(session_id: str, active: Any, db: AsyncSession) -> None:
    """Test utility: exit combat, restore full HP, return to exploration."""
    active.turn_manager.reset()
    active.phase = SessionStatus.EXPLORATION
    active.state_data.pop("combatants", None)
    active.state_data.pop("grid_positions", None)
    active.state_data.pop("grid_config", None)
    active.state_data.pop("grid_decoration", None)
    active.state_data.pop("pending_encounter", None)
    active.state_data.pop("encounter_monsters", None)
    active.state_data["phase"] = SessionStatus.EXPLORATION.value

    characters_data: dict[str, Any] = active.state_data.get("characters", {})
    for cdata in characters_data.values():
        cdata["hp"] = cdata.get("hp_max", cdata.get("hp", 10))

    result = await db.execute(select(Character).where(Character.session_id == session_id))
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


async def handle_flee(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    """Make a player character flee the combat if they are standing on an exit tile."""
    if active.phase != SessionStatus.COMBAT:
        return

    char_id = action.character_id
    if not char_id:
        return

    combatants: dict[str, Any] = active.state_data.setdefault("combatants", {})
    if char_id not in combatants:
        return

    cdata = combatants[char_id]
    name = cdata.get("name", char_id)

    pos = grid_position_for(active.state_data, char_id)
    if not pos:
        return

    scene = active.state_data.get("current_scene") or {}
    exits = scene.get("exits", [])
    on_exit = False
    exit_label = "la sortie"

    for exit_data in exits:
        exit_pos = exit_data.get("position")
        if isinstance(exit_pos, dict) and "col" in exit_pos and "row" in exit_pos:
            if int(exit_pos["col"]) == pos.col and int(exit_pos["row"]) == pos.row:
                on_exit = True
                exit_label = exit_data.get("label") or exit_data.get("id") or exit_label
                break

    if not on_exit:
        logger.warning(
            "handle_flee: Le personnage '%s' a tenté de fuir mais n'est pas sur une case de sortie (pos=%s).",
            name,
            pos,
        )
        return

    cdata["status"] = "fled"

    grid_positions = active.state_data.setdefault("grid_positions", {})
    grid_positions.pop(char_id, None)

    active.turn_manager.remove_combatant(char_id)
    active.mark_dirty()

    await event_bus.publish_to_session(
        session_id,
        EventType.COMBATANT_STATUS_CHANGED,
        {
            "combatant_id": char_id,
            "combatant_name": name,
            "status": "fled",
            "reason": "escaped",
        },
        source="ws_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.COMBATANT_REMOVED,
        {
            "combatant_id": char_id,
            "combatant_name": name,
            "status": "fled",
        },
        source="ws_game",
    )

    flee_text = f"{name} s'enfuit de la bataille par {exit_label} !"
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": flee_text, "speaker": "Maître du Jeu"},
        source="ws_game",
    )
    await persist_narration(session_id, flee_text, "Maître du Jeu", db)

    active_pcs = [
        cid for cid, c in combatants.items()
        if c.get("is_player") and c.get("status") == "active"
    ]

    if not active_pcs:
        await handle_combat_end(
            session_id,
            active,
            db,
            reason="fled",
        )
        return

    current = active.turn_manager.current_turn
    if current is None or current.combatant_id == char_id:
        await handle_end_turn(session_id, active, db)
    else:
        await event_bus.publish_to_session(
            session_id,
            EventType.SESSION_STATE,
            _build_session_state_payload(session_id),
            source="ws_game",
        )


async def handle_dash(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    del db
    current = active.turn_manager.current_turn
    if current is None or current.combatant_id != action.character_id:
        return
    economy = current.action_economy
    if not economy.use_action():
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "Action déjà utilisée ce tour."},
            source="ws_game",
        )
        return
    economy.movement += economy.movement_max
    economy.has_dashed = True
    active.mark_dirty()
    await _publish_action_economy(session_id, current.combatant_id, economy, active)


async def handle_disengage(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    del db
    current = active.turn_manager.current_turn
    if current is None or current.combatant_id != action.character_id:
        return
    economy = current.action_economy
    if not economy.use_action():
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "Action déjà utilisée ce tour."},
            source="ws_game",
        )
        return
    economy.has_disengaged = True
    active.mark_dirty()
    await _publish_action_economy(session_id, current.combatant_id, economy, active)


async def handle_move(
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

    from_pos = active.state_data.get("grid_positions", {}).get(mover_id)
    if from_pos is None:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "Position de départ introuvable."},
            source="ws_game",
        )
        return

    to_pos = GridPosition(col=target_col, row=target_row)

    combatants_info: dict[str, Any] = active.state_data.get("combatants", {})
    mover_data = combatants_info.get(mover_id, {})
    current = active.turn_manager.current_turn
    turn_economy = (
        current.action_economy if current is not None and current.combatant_id == mover_id else None
    )
    speed_m = float(
        turn_economy.movement if turn_economy is not None else mover_data.get("speed_m", 9.0)
    )

    move_result = await apply_tactical_move(
        session_id=session_id,
        active=active,
        mover_id=mover_id,
        destination=to_pos,
        event_bus=event_bus,
        movement_m=speed_m,
        source="ws_game",
    )
    if not move_result.valid:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": f"Déplacement invalide : {move_result.reason}"},
            source="ws_game",
        )
        return

    if turn_economy is not None and not turn_economy.spend_movement(move_result.movement_used_m):
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "Mouvement insuffisant pour ce déplacement."},
            source="ws_game",
        )
        return

    await event_bus.publish_to_session(
        session_id,
        EventType.COMBATANT_MOVED,
        {
            "combatant_id": mover_id,
            "position": (move_result.final_position or to_pos).to_dict(),
            "movement_used_m": move_result.movement_used_m,
            "path": [step.to_dict() for step in move_result.path],
            "interrupted": move_result.interrupted,
            "reason": move_result.reason,
        },
        source="ws_game",
    )
    if turn_economy is not None:
        await _publish_action_economy(session_id, mover_id, turn_economy, active)


async def handle_toggle_ai_control(
    session_id: str,
    character_id: Optional[str],
    next_is_ai: bool,
    db: AsyncSession,
) -> None:
    """Toggle a character between human and AI control during a live session."""
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

    chars_data: dict[str, Any] = active.state_data.setdefault("characters", {})
    cdata = chars_data.setdefault(character_id, {})
    cdata["is_ai"] = next_is_ai
    cdata.setdefault("name", char.name)

    combatants_info: dict[str, Any] = active.state_data.get("combatants", {})
    if character_id in combatants_info:
        combatants_info[character_id]["is_ai"] = next_is_ai

    for entry in active.turn_manager._order:
        if entry.combatant_id == character_id:
            entry.is_ai_controlled = next_is_ai
            break

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

    current = active.turn_manager.current_turn
    if next_is_ai and current and current.combatant_id == character_id:
        if active.phase == SessionStatus.COMBAT:
            await handle_ai_turns(session_id, active, db)
        else:
            from app.game.ai_player_manager import AIPlayerManager
            from app.api import ws_game

            try:
                await AIPlayerManager().run_exploration_reactions(
                    session_id, active, ws_game.action_resolver, trigger_character_id=None, db=db
                )
                await ws_game._consume_pending_combat_transition(
                    session_id,
                    active,
                    db,
                    force=active.phase == SessionStatus.ENCOUNTER_START,
                )
            except Exception as exc:
                logger.error("toggle_ai_control: exploration reactions failed: %s", exc)


async def handle_trigger_ai_reactions(
    session_id: str,
    db: AsyncSession,
    trigger_character_id: Optional[str] = None,
) -> None:
    """Manual fallback: let AI companions react without a preceding human action."""
    active = session_manager.get_session(session_id)
    if active is None:
        return

    if active.phase == SessionStatus.COMBAT:
        current = active.turn_manager.current_turn
        if current is None or not current.is_ai_controlled:
            return
        await handle_ai_turns(session_id, active, db)
        return

    if not active.ai_players:
        return

    from app.game.ai_player_manager import AIPlayerManager
    from app.api import ws_game

    await AIPlayerManager().run_exploration_reactions(
        session_id,
        active,
        ws_game.action_resolver,
        trigger_character_id=trigger_character_id,
        db=db,
    )
    await ws_game._consume_pending_combat_transition(
        session_id,
        active,
        db,
        force=active.phase == SessionStatus.ENCOUNTER_START,
    )


async def consume_pending_combat_transition(
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

    await handle_start_combat(
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
