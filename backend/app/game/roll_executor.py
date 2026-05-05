"""Shared execution for GM-requested ability, skill and saving throws."""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.game.session_manager import ActiveSession

logger = logging.getLogger(__name__)


def execute_roll_request(
    params: dict[str, Any],
    fallback_actor_id: Optional[str],
    active: ActiveSession,
) -> Optional[dict[str, Any]]:
    """Execute a GM ``roll_request`` and return a ROLL_RESULT-ready payload."""
    from app.engine.ability_checks import (
        SKILL_ABILITY,
        Ability,
        Proficiency,
        ability_check,
        saving_throw,
        skill_check,
    )

    ability_long_map: dict[str, str] = {
        "strength": "str",
        "dexterity": "dex",
        "constitution": "con",
        "intelligence": "int",
        "wisdom": "wis",
        "charisma": "cha",
    }
    ability_enum_map = {a.value: a for a in Ability}

    skill_name = str(params.get("skill", "")).lower().replace(" ", "_").replace("-", "_")
    ability_str = str(params.get("ability", "")).lower()
    check_type = params.get("type", "check")
    dc = params.get("dc")
    target_id = params.get("target") or fallback_actor_id

    characters = active.state_data.get("characters", {})
    combatants = active.state_data.get("combatants", {})
    char_data = characters.get(target_id) or combatants.get(target_id)
    if char_data is None and characters:
        char_data = next(iter(characters.values()))
    if not char_data:
        logger.warning("roll_request: personnage '%s' introuvable dans state_data", target_id)
        return None

    ab_scores: dict[str, int] = char_data.get("ability_scores") or {
        "str": int(char_data.get("str", 10)),
        "dex": int(char_data.get("dex", 10)),
        "con": 10,
        "int": 10,
        "wis": 10,
        "cha": 10,
    }
    level = int(char_data.get("level", 1))
    skill_profs = list(char_data.get("skill_proficiencies", []))
    save_profs = list(char_data.get("save_proficiencies", []))

    ability_short: Optional[str] = (
        ability_long_map.get(ability_str, ability_str[:3] if ability_str else None)
        if ability_str
        else None
    )
    long_from_short = {v: k for k, v in ability_long_map.items()}

    try:
        if check_type == "save":
            long_ab = long_from_short.get(ability_short or "", ability_str or "wisdom")
            ability_enum = ability_enum_map.get(long_ab, Ability.WIS)
            score = ab_scores.get(ability_short or "wis", 10)
            result = saving_throw(score, ability_enum, level, long_ab in save_profs, dc)
        elif skill_name and skill_name in SKILL_ABILITY:
            gov = SKILL_ABILITY[skill_name]
            ab_key = gov.value[:3]
            score = ab_scores.get(ab_key, 10)
            prof = Proficiency.PROFICIENT if skill_name in skill_profs else Proficiency.NONE
            result = skill_check(score, skill_name, level, prof, dc)
        else:
            long_ab = long_from_short.get(ability_short or "", ability_str or "wisdom")
            ability_enum = ability_enum_map.get(long_ab, Ability.WIS)
            score = ab_scores.get(ability_short or "wis", 10)
            result = ability_check(score, dc, ability=ability_enum)
    except Exception as exc:
        logger.error("roll_request: calcul du jet echoue : %s", exc)
        return None

    payload = {
        "dice_notation": "1d20",
        "rolls": result.all_rolls,
        "d20": result.d20_roll,
        "modifier": result.modifier,
        "total": result.total,
        "dc": result.dc,
        "success": result.success,
        "label": result.label,
        "breakdown": result.breakdown,
        "character_id": target_id,
        "character_name": char_data.get("name", target_id or ""),
    }
    if params.get("social_target"):
        payload["social_target_id"] = params.get("social_target")
    return payload
