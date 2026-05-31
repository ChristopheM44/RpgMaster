"""Stealth and passive Perception helpers for hidden-world events."""
from __future__ import annotations

import random
from typing import Any

from app.engine.ability_checks import (
    Proficiency,
    compute_passive_perception,
    skill_check,
)
from app.engine.dice import roll_dice
from app.game.constants import INACTIVE_STATUSES
from app.game.session_manager import ActiveSession


def resolve_stealth_event(
    active: ActiveSession,
    params: dict[str, Any],
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Resolve a GM-only stealth event against party passive Perception."""
    actor_id = str(params.get("actor_id") or params.get("target") or "").strip()
    actor_kind = str(params.get("actor_kind") or "npc").strip().lower()
    event_type = str(params.get("event_type") or "move_unnoticed").strip().lower()
    actor_data = _actor_data(active.state_data, actor_id)
    actor_name = str(actor_data.get("name") or params.get("actor_name") or actor_id or "Acteur")

    roll_payload = _roll_stealth(actor_data, params, rng)
    observers = party_passive_perceptions(active)
    noticed_by = [
        observer
        for observer in observers
        if observer["passive_perception"] > roll_payload["total"]
    ]
    stealth_succeeded = len(noticed_by) == 0

    max_pp = max((observer["passive_perception"] for observer in observers), default=None)
    summary = _stealth_summary(
        actor_name=actor_name,
        total=roll_payload["total"],
        noticed_by=noticed_by,
        stealth_succeeded=stealth_succeeded,
    )
    return {
        "type": "stealth_event",
        "event_type": event_type,
        "actor_id": actor_id or None,
        "actor_name": actor_name,
        "actor_kind": actor_kind,
        "skill": "stealth",
        "dice_notation": "1d20",
        "rolls": roll_payload["rolls"],
        "d20": roll_payload["d20"],
        "d20_roll": roll_payload["d20"],
        "modifier": roll_payload["modifier"],
        "total": roll_payload["total"],
        "dc": max_pp,
        "success": stealth_succeeded,
        "stealth_succeeded": stealth_succeeded,
        "noticed_by": noticed_by,
        "observers": observers,
        "advantage": roll_payload["advantage"],
        "label": "DEX (Stealth) vs Perception passive",
        "breakdown": roll_payload["breakdown"],
        "summary": summary,
    }


def resolve_hide_action(
    active: ActiveSession,
    actor_id: str | None,
    *,
    advantage: bool | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any] | None:
    """Resolve a player Hide action against active hostile combatants."""
    if not actor_id:
        return None
    actor_data = _actor_data(active.state_data, actor_id)
    if not actor_data:
        return None

    params: dict[str, Any] = {}
    if advantage is not None:
        params["advantage"] = advantage
    roll_payload = _roll_stealth(actor_data, params, rng)
    observers = hostile_passive_perceptions(active, actor_id)
    noticed_by = [
        observer
        for observer in observers
        if observer["passive_perception"] > roll_payload["total"]
    ]
    stealth_succeeded = len(noticed_by) == 0
    max_pp = max((observer["passive_perception"] for observer in observers), default=None)
    actor_name = str(actor_data.get("name") or actor_id)
    summary = _stealth_summary(
        actor_name=actor_name,
        total=roll_payload["total"],
        noticed_by=noticed_by,
        stealth_succeeded=stealth_succeeded,
    )
    return {
        "type": "skill_check",
        "skill": "stealth",
        "dice_notation": "1d20",
        "rolls": roll_payload["rolls"],
        "d20": roll_payload["d20"],
        "d20_roll": roll_payload["d20"],
        "modifier": roll_payload["modifier"],
        "total": roll_payload["total"],
        "dc": max_pp,
        "success": stealth_succeeded,
        "stealth_succeeded": stealth_succeeded,
        "noticed_by": noticed_by,
        "observers": observers,
        "advantage": roll_payload["advantage"],
        "label": "DEX (Stealth)",
        "breakdown": roll_payload["breakdown"],
        "summary": summary,
    }


def party_passive_perceptions(active: ActiveSession) -> list[dict[str, Any]]:
    characters = active.state_data.get("characters", {})
    if not isinstance(characters, dict):
        return []
    observers: list[dict[str, Any]] = []
    for char_id, char_data in characters.items():
        if not isinstance(char_data, dict):
            continue
        observers.append(_observer_payload(str(char_id), char_data))
    return observers


def hostile_passive_perceptions(
    active: ActiveSession,
    actor_id: str | None = None,
) -> list[dict[str, Any]]:
    combatants = active.state_data.get("combatants", {})
    if not isinstance(combatants, dict):
        return []
    observers: list[dict[str, Any]] = []
    for combatant_id, combatant in combatants.items():
        if str(combatant_id) == str(actor_id):
            continue
        if not isinstance(combatant, dict) or combatant.get("is_player"):
            continue
        if str(combatant.get("status", "active")).lower() in INACTIVE_STATUSES:
            continue
        observers.append(_observer_payload(str(combatant_id), combatant))
    return observers


def _actor_data(state_data: dict[str, Any], actor_id: str) -> dict[str, Any]:
    if not actor_id:
        return {}
    for collection_name in ("combatants", "characters", "npc_states"):
        collection = state_data.get(collection_name)
        if isinstance(collection, dict) and isinstance(collection.get(actor_id), dict):
            return collection[actor_id]
    return {}


def _roll_stealth(
    actor_data: dict[str, Any],
    params: dict[str, Any],
    rng: random.Random | None,
) -> dict[str, Any]:
    total_override = _optional_int(params.get("stealth_total_override"))
    if total_override is None:
        total_override = _optional_int(params.get("dc_override"))
    if total_override is not None:
        return {
            "rolls": [],
            "d20": 0,
            "modifier": total_override,
            "total": total_override,
            "advantage": None,
            "breakdown": f"Total furtivité fixé = {total_override}",
        }

    advantage = params.get("advantage") if isinstance(params.get("advantage"), bool) else None
    disadvantage = _has_stealth_disadvantage(actor_data)
    advantage = _combine_advantage(advantage, disadvantage)

    modifier_override = _optional_int(params.get("stealth_modifier"))
    if modifier_override is not None:
        d20, rolls = _roll_d20(advantage, rng)
        total = d20 + modifier_override
        sign = f"+{modifier_override}" if modifier_override >= 0 else str(modifier_override)
        adv_label = " (adv)" if advantage is True else " (dis)" if advantage is False else ""
        return {
            "rolls": rolls,
            "d20": d20,
            "modifier": modifier_override,
            "total": total,
            "advantage": advantage,
            "breakdown": f"{d20}{adv_label} {sign} = {total}",
        }

    score = _ability_score(actor_data, "dex", "dexterity", default=10)
    level = int(actor_data.get("level", 1) or 1)
    proficiency = _skill_proficiency(actor_data, "stealth")
    result = skill_check(score, "stealth", level, proficiency, advantage=advantage, rng=rng)
    return {
        "rolls": result.all_rolls,
        "d20": result.d20_roll,
        "modifier": result.modifier,
        "total": result.total,
        "advantage": result.advantage,
        "breakdown": result.breakdown,
    }


def _observer_payload(observer_id: str, data: dict[str, Any]) -> dict[str, Any]:
    passive = _optional_int(data.get("passive_perception"))
    if passive is None:
        senses = data.get("senses")
        if isinstance(senses, dict):
            passive = _optional_int(senses.get("passive_perception"))
    if passive is None:
        wis = _ability_score(data, "wis", "wisdom", default=10)
        passive = compute_passive_perception(
            wis,
            int(data.get("level", 1) or 1),
            _skill_proficiency(data, "perception"),
        )
    return {
        "id": observer_id,
        "name": str(data.get("name") or observer_id),
        "passive_perception": passive,
    }


def _ability_score(
    data: dict[str, Any],
    short_key: str,
    long_key: str,
    *,
    default: int,
) -> int:
    scores = data.get("ability_scores")
    if isinstance(scores, dict):
        for key in (short_key, long_key):
            value = _optional_int(scores.get(key))
            if value is not None:
                return value
    for key in (short_key, long_key):
        value = _optional_int(data.get(key))
        if value is not None:
            return value
    return default


def _skill_proficiency(data: dict[str, Any], skill: str) -> Proficiency:
    normalized = skill.lower().replace(" ", "_").replace("-", "_")
    raw_expertise = data.get("skill_expertise") or data.get("expertise")
    if isinstance(raw_expertise, list) and normalized in _normalized_list(raw_expertise):
        return Proficiency.EXPERT
    raw_profs = data.get("skill_proficiencies")
    if isinstance(raw_profs, list) and normalized in _normalized_list(raw_profs):
        return Proficiency.PROFICIENT
    return Proficiency.NONE


def _normalized_list(values: list[Any]) -> set[str]:
    return {
        str(value).strip().lower().replace(" ", "_").replace("-", "_")
        for value in values
        if str(value).strip()
    }


def _has_stealth_disadvantage(data: dict[str, Any]) -> bool:
    equipment = data.get("equipment")
    if not isinstance(equipment, list):
        return False
    for item in equipment:
        if not isinstance(item, dict):
            continue
        if item.get("equipped") is False:
            continue
        if item.get("stealth_disadvantage") is True:
            return True
    return False


def _combine_advantage(advantage: bool | None, disadvantage: bool) -> bool | None:
    if advantage is True and disadvantage:
        return None
    if advantage is True:
        return True
    if disadvantage:
        return False
    return advantage


def _roll_d20(
    advantage: bool | None,
    rng: random.Random | None,
) -> tuple[int, list[int]]:
    if advantage is None:
        rolls = roll_dice(20, 1, rng)
        return rolls[0], rolls
    rolls = roll_dice(20, 2, rng)
    return (max(rolls) if advantage else min(rolls)), rolls


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _stealth_summary(
    *,
    actor_name: str,
    total: int,
    noticed_by: list[dict[str, Any]],
    stealth_succeeded: bool,
) -> str:
    if stealth_succeeded:
        return f"{actor_name} passe inaperçu (furtivité {total})."
    names = ", ".join(str(observer["name"]) for observer in noticed_by) or "le groupe"
    return f"{actor_name} est remarqué par {names} (furtivité {total})."
