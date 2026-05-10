"""Payload builders shared by the game WebSocket facade."""
from __future__ import annotations

import re
from typing import Any

from app.game.constants import ARMOR_CATEGORIES, MONSTER_TYPE_COLORS
from app.engine.xp import xp_to_next_level
from app.models.character import Character
from app.services.encounter_service import encounter_service
from app.services.rest_service import normalize_character_hit_dice


def build_session_state_payload(
    session_id: str,
    active: Any | None,
) -> dict[str, Any]:
    """Build the ``session_state`` event payload from an active session."""
    if active is None:
        return {"session_id": session_id, "phase": "unknown"}

    turn_data = active.turn_manager.to_dict()

    def _map_entry(entry: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": entry.get("combatant_id", ""),
            "name": entry.get("name", ""),
            "initiative": entry.get("initiative_total", 0),
            "is_ai": entry.get("is_ai_controlled", False),
            "is_ai_controlled": entry.get("is_ai_controlled", False),
            "is_player": entry.get("is_player", True),
        }

    default_journal = {
        "location_region": None,
        "location_place": None,
        "time_of_day": "morning",
        "day_number": 1,
        "calendar_date": None,
        "weather": None,
    }

    payload = {
        "session_id": session_id,
        "phase": active.phase.value,
        "turn_number": active.turn_number,
        "round_number": active.round_number,
        "turn_order": [_map_entry(entry) for entry in turn_data.get("order", [])],
        "current_turn_index": turn_data.get("index", 0),
        "valid_transitions": [
            status.value for status in active.game_loop.get_valid_transitions(active.phase)
        ],
        "adventure_journal": active.state_data.get("adventure_journal", default_journal),
        "quests": active.state_data.get("quests", []),
        "chronicle": active.state_data.get("chronicle", []),
        "current_scene": active.state_data.get("current_scene"),
    }
    if active.phase.value == "combat":
        payload.update(build_combat_start_payload(active))
    return payload


async def build_session_state_payload_enriched(
    session_id: str,
    active: Any | None,
    db: Any,
) -> dict[str, Any]:
    """Build session state plus campaign-level map data when a DB session is available."""
    payload = build_session_state_payload(session_id, active)
    try:
        from app.services import campaign_dossier_service

        payload.update(
            await campaign_dossier_service.campaign_maps_for_session(
                session_id,
                db,
                active.state_data if active is not None else None,
            )
        )
    except Exception:
        payload.setdefault("region_map", None)
        payload.setdefault("city_maps", {})
        payload.setdefault("active_city_id", None)
    return payload


def compute_ac_from_equipment(equipment: list, dex_mod: int) -> int:
    """Calcule l'AC à partir de l'équipement équipé."""
    armor = next(
        (
            item for item in equipment
            if item.get("equipped") and item.get("category") in ARMOR_CATEGORIES
        ),
        None,
    )
    shield = next(
        (
            item for item in equipment
            if item.get("equipped") and item.get("category") == "shield"
        ),
        None,
    )
    shield_bonus = 2 if shield else 0

    if armor and isinstance(armor.get("base_ac"), int):
        dex_cap = armor.get("dex_cap")
        dex_applied = dex_mod if dex_cap is None else min(dex_mod, int(dex_cap))
        return armor["base_ac"] + dex_applied + shield_bonus

    return 10 + dex_mod + shield_bonus


def monster_base_id(combatant_id: str) -> str:
    return "_".join(combatant_id.rsplit("_", 1)[:-1]) if "_" in combatant_id else combatant_id


def monster_instance_number(combatant_id: str, display_name: str = "") -> int:
    """Return the stable encounter instance number carried by id/name."""
    for value, pattern in (
        (combatant_id, r"_(\d+)$"),
        (display_name, r"\b(\d+)$"),
    ):
        match = re.search(pattern, value or "")
        if match:
            return max(1, int(match.group(1)))
    return 1


def monster_token(name: str, count: int) -> str:
    letters = "".join(part[0] for part in name.replace("-", " ").split() if part)
    prefix = (letters or name[:1] or "?").upper()[:2]
    return f"{prefix}{count}"


def monster_token_for_combatant(
    monster_name: str,
    combatant_id: str,
    display_name: str,
) -> str:
    return monster_token(
        monster_name,
        monster_instance_number(combatant_id, display_name),
    )


def monster_color(monster_type: str | None) -> str:
    return MONSTER_TYPE_COLORS.get((monster_type or "").lower(), "#b45309")


def format_monster_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    formatted: list[dict[str, Any]] = []
    for action in actions:
        formatted.append({
            "name": action.get("name_fr") or action.get("name") or "Action",
            "attack_bonus": action.get("attack_bonus"),
            "damage_dice": action.get("damage_dice"),
            "description": action.get("description") or action.get("description_fr"),
        })
    return formatted


def character_snapshot(char: Character) -> dict[str, Any]:
    """Build the in-memory character snapshot used by game/combat state."""
    hit_dice = normalize_character_hit_dice(char)
    return {
        "name": char.name,
        "hp": char.hp_current,
        "hp_max": char.hp_max,
        "xp": int(getattr(char, "xp", 0)),
        "gp": int(getattr(char, "gp", 0)),
        "sp": int(getattr(char, "sp", 0)),
        "cp": int(getattr(char, "cp", 0)),
        "xp_to_next_level": xp_to_next_level(
            int(getattr(char, "xp", 0)),
            int(getattr(char, "level", 1)),
        ),
        "is_ai": char.is_ai,
        "level": char.level,
        "ability_scores": dict(char.ability_scores),
        "skill_proficiencies": list(char.proficiencies.get("skills", [])),
        "save_proficiencies": list(char.proficiencies.get("saving_throws", [])),
        "spell_slots": dict(char.spell_slots or {}),
        "known_spells": list(char.known_spells or []),
        "dex": int(char.ability_scores.get("dex", 10)),
        "str": int(char.ability_scores.get("str", 10)),
        "equipment": list(char.equipment or []),
        "hit_dice": dict(hit_dice),
        "personality": dict(char.personality or {}),
        "pending_asi": bool((char.personality or {}).get("pending_asi", False)),
    }


def build_combat_start_payload(
    active: Any,
    encounter_catalog: Any = encounter_service,
) -> dict[str, Any]:
    """Build the frontend combat-start payload from active combat state."""
    combatants_info: dict[str, Any] = active.state_data.get("combatants", {})
    grid_cfg: dict[str, Any] = active.state_data.get(
        "grid_config", {"cols": 10, "rows": 8, "cell_size_m": 1.5}
    )
    grid_positions: dict[str, Any] = active.state_data.get("grid_positions", {})
    turn_data = active.turn_manager.to_dict()
    current_idx = turn_data.get("index", 0)

    encounter_catalog._ensure_loaded()

    combat_combatants = []
    for idx, entry in enumerate(turn_data.get("order", [])):
        cid = entry.get("combatant_id", "")
        info = combatants_info.get(cid, {})
        is_player = bool(info.get("is_player", entry.get("is_player", True)))
        is_ai_controlled = bool(entry.get("is_ai_controlled", False)) if is_player else False
        payload = {
            "id": cid,
            "name": entry.get("name") or info.get("name", ""),
            "initiative": entry.get("initiative_total", 0),
            "hp_current": info.get("hp", 0),
            "hp_max": info.get("hp_max", 0),
            "kind": "pc" if is_player else "monster",
            "is_ai": entry.get("is_ai_controlled", False) if is_player else True,
            "is_ai_controlled": is_ai_controlled,
            "conditions": info.get("conditions", []),
            "status": info.get("status", "active"),
            "is_active": (idx == current_idx),
            "position": grid_positions.get(cid, {"col": 0, "row": 0}),
            "death_saves": info.get("death_saves"),
            "ac": info.get("ac", 10),
            "attack_bonus": info.get("attack_bonus"),
            "damage_notation": info.get("damage_notation"),
            "action_economy": entry.get("action_economy"),
        }
        if not is_player:
            base_id = info.get("monster_id") or monster_base_id(cid)
            monster_data = encounter_catalog._monsters_by_id.get(base_id, {})
            monster_name = (
                monster_data.get("name_fr")
                or monster_data.get("name")
                or payload["name"]
            )
            payload.update({
                "species": monster_data.get("type"),
                "cr": monster_data.get("cr"),
                "token": info.get("token")
                or monster_token_for_combatant(monster_name, cid, str(payload["name"])),
                "color": info.get("color") or monster_color(monster_data.get("type")),
                "ability_scores": monster_data.get("ability_scores", {}),
                "actions": format_monster_actions(monster_data.get("actions", [])),
                "description": monster_data.get("description") or monster_data.get("alignment"),
            })
        combat_combatants.append(payload)

    return {
        "combatants": combat_combatants,
        "grid_config": grid_cfg,
        "grid_decoration": active.state_data.get("grid_decoration"),
    }
