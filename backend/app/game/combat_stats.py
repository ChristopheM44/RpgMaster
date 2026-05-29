"""Combat stat builders for player combatants.

The websocket combat bootstrap stores a compact combatant map that is later
used by mechanical resolution. Keep the derivation here so combat start and
live equipment sync apply the same weapon/range rules.
"""

from __future__ import annotations

import logging
from typing import Any

from app.engine.ability_checks import ability_modifier, proficiency_bonus
from app.engine.character_creation import get_class_features
from app.engine.equipment import (
    WeaponStats,
    get_weapon,
    is_weapon_proficient,
    weapon_attack_stats,
)

logger = logging.getLogger(__name__)

_WEAPON_CATEGORIES = {"simple", "martial"}
_ABILITY_KEYS = {
    "str": ("str", "strength"),
    "dex": ("dex", "dexterity"),
}


def build_combatant_combat_stats(cdata: dict[str, Any]) -> dict[str, Any]:
    """Build attack, damage, range and speed stats from the equipped weapon.

    If the character class or weapon catalogue entry is unavailable, fall back
    to an unarmed strike instead of making combat startup fail.
    """
    str_score = _ability_score(cdata, "str", 10)
    dex_score = _ability_score(cdata, "dex", 10)
    level = _int_value(cdata.get("level"), 1)
    speed_m = _speed_m(cdata)

    weapon_item = _main_weapon_item(cdata.get("equipment"))
    if weapon_item is None:
        return {**_unarmed_stats(str_score, level), "speed_m": speed_m}

    try:
        class_features = get_class_features(str(cdata.get("char_class") or ""))
        weapon = _weapon_from_item(weapon_item)
        proficiencies = _expanded_proficiencies(class_features.weapon_proficiencies)
        proficient = is_weapon_proficient(weapon, proficiencies)
        attack_stats = weapon_attack_stats(
            weapon,
            str_score,
            dex_score,
            proficient,
            level,
            prefer_dex=True,
        )
    except (TypeError, ValueError, KeyError) as exc:
        logger.warning(
            "Unable to build weapon combat stats for %s: %s",
            cdata.get("name", "unknown combatant"),
            exc,
        )
        return {**_unarmed_stats(str_score, level), "speed_m": speed_m}

    reach_m = 3.0 if "reach" in {str(prop).lower() for prop in weapon.properties} else 1.5
    attack_range_m = float(weapon.range_normal) if weapon.range_normal is not None else reach_m
    return {
        "attack_bonus": int(attack_stats.attack_bonus),
        "damage_notation": attack_stats.damage_notation,
        "reach_m": reach_m,
        "attack_range_m": attack_range_m,
        "speed_m": speed_m,
    }


def _main_weapon_item(equipment: Any) -> dict[str, Any] | None:
    if not isinstance(equipment, list):
        return None
    equipped_weapons = [
        item
        for item in equipment
        if isinstance(item, dict) and item.get("equipped") and _is_weapon_item(item)
    ]
    for item in equipped_weapons:
        slots = item.get("occupied_slots")
        if isinstance(slots, list) and "main_hand" in slots:
            return item
        if item.get("slot") == "main_hand":
            return item
    return equipped_weapons[0] if equipped_weapons else None


def _is_weapon_item(item: dict[str, Any]) -> bool:
    category = str(item.get("category") or "").lower()
    if (
        str(item.get("item_type") or "").lower() == "weapon"
        or category in _WEAPON_CATEGORIES
        or item.get("damage_dice") is not None
    ):
        return True
    for candidate in _weapon_lookup_candidates(item):
        try:
            get_weapon(candidate)
            return True
        except ValueError:
            continue
    return False


def _weapon_from_item(item: dict[str, Any]) -> WeaponStats:
    for candidate in _weapon_lookup_candidates(item):
        try:
            return get_weapon(candidate)
        except ValueError:
            continue

    if item.get("damage_dice"):
        return WeaponStats(
            name=str(item.get("name") or item.get("name_fr") or item.get("id") or "Custom Weapon"),
            category=str(item.get("category") or "simple").lower(),
            damage_dice=str(item["damage_dice"]),
            damage_type=str(item.get("damage_type") or "bludgeoning"),
            properties=[str(prop).lower() for prop in item.get("properties", []) or []],
            range_normal=_optional_float(item.get("range_normal")),
            range_long=_optional_float(item.get("range_long")),
            versatile_dice=(
                str(item.get("versatile_dice")) if item.get("versatile_dice") else None
            ),
            weight=float(item.get("weight_lb", item.get("weight", 0.0)) or 0.0),
            cost_gp=float(item.get("cost_gp", item.get("cost", 0.0)) or 0.0),
        )

    raise ValueError(f"Unknown weapon item: {item.get('id') or item.get('name')}")


def _weapon_lookup_candidates(item: dict[str, Any]) -> list[str]:
    keys = ("weapon_id", "template_id", "srd_id", "base_id", "id", "name")
    candidates: list[str] = []
    for key in keys:
        value = item.get(key)
        if value:
            candidates.append(str(value))
    return candidates


def _expanded_proficiencies(proficiencies: list[str]) -> list[str]:
    expanded: set[str] = set()
    for prof in proficiencies:
        raw = str(prof).lower()
        expanded.add(raw)
        expanded.add(raw.replace("_", " "))
        expanded.add(raw.replace(" ", "_"))
    return sorted(expanded)


def _unarmed_stats(str_score: int, level: int) -> dict[str, Any]:
    str_mod = ability_modifier(str_score)
    attack_bonus = str_mod + proficiency_bonus(level)
    damage_amount = max(1 + str_mod, 1)
    return {
        "attack_bonus": int(attack_bonus),
        "damage_notation": str(damage_amount),
        "reach_m": 1.5,
        "attack_range_m": 1.5,
    }


def _ability_score(cdata: dict[str, Any], ability: str, default: int) -> int:
    for key in _ABILITY_KEYS[ability]:
        if cdata.get(key) is not None:
            return _int_value(cdata.get(key), default)
    scores = cdata.get("ability_scores")
    if isinstance(scores, dict):
        for key in _ABILITY_KEYS[ability]:
            if scores.get(key) is not None:
                return _int_value(scores.get(key), default)
    return default


def _speed_m(cdata: dict[str, Any]) -> float:
    speed = cdata.get("speed_m", cdata.get("speed", 9.0))
    if isinstance(speed, dict):
        speed = speed.get("walk", 9.0)
    return float(speed or 9.0)


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
