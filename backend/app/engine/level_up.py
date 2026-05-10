"""Level-up calculations built on existing character creation rules."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.engine.character_creation import get_class_features, hp_at_level
from app.engine.spells import starting_slots

ASI_LEVELS = frozenset({4, 8, 12, 16, 19})


@dataclass
class LevelUpResult:
    old_level: int
    new_level: int
    hp_total_gain: int
    hp_per_level: list[int]
    new_spell_slots: dict[str, dict[str, int]]
    new_hit_dice: dict[str, Any]
    asi_levels_granted: list[int]


def caster_type_for_class(char_class: str) -> str | None:
    return get_class_features(char_class).caster_type


def roll_hp_increase(hit_die: int, con_mod: int, *, average: bool = True) -> int:
    """Return a deterministic average HP increase, minimum 1."""
    if not average:
        raise NotImplementedError("Random HP rolls are not implemented for automated level-up")
    return max(1, (int(hit_die) // 2 + 1) + int(con_mod))


def compute_level_up(
    *,
    char_class: str,
    current_level: int,
    target_level: int,
    con_score: int,
    current_spell_slots: dict[str, Any] | None,
    current_hit_dice: dict[str, Any] | None,
) -> LevelUpResult:
    """Compute all mechanical state changes for a potentially multi-level gain."""
    old_level = max(1, min(20, int(current_level)))
    new_level = max(old_level, min(20, int(target_level)))
    features = get_class_features(char_class)

    hp_per_level: list[int] = []
    previous_hp = hp_at_level(char_class, con_score, old_level)
    for level in range(old_level + 1, new_level + 1):
        next_hp = hp_at_level(char_class, con_score, level)
        hp_per_level.append(max(1, next_hp - previous_hp))
        previous_hp = next_hp
    hp_total_gain = sum(hp_per_level)

    slot_table = _slot_table_for_class(char_class, new_level)
    new_spell_slots = _merge_spell_slots(current_spell_slots or {}, slot_table)

    old_hit_dice = dict(current_hit_dice or {})
    used_hit_dice = max(0, int(old_hit_dice.get("used", 0) or 0))
    new_hit_dice = {
        "die": int(old_hit_dice.get("die") or features.hit_die),
        "total": new_level,
        "used": min(used_hit_dice, new_level),
    }

    asi_levels = [level for level in range(old_level + 1, new_level + 1) if level in ASI_LEVELS]
    return LevelUpResult(
        old_level=old_level,
        new_level=new_level,
        hp_total_gain=hp_total_gain,
        hp_per_level=hp_per_level,
        new_spell_slots=new_spell_slots,
        new_hit_dice=new_hit_dice,
        asi_levels_granted=asi_levels,
    )


def _slot_table_for_class(char_class: str, level: int) -> dict[int, int]:
    caster_type = caster_type_for_class(char_class)
    if not caster_type:
        return {}
    return starting_slots(caster_type, level)


def _merge_spell_slots(
    current_spell_slots: dict[str, Any],
    new_totals: dict[int, int],
) -> dict[str, dict[str, int]]:
    merged: dict[str, dict[str, int]] = {}
    for level, total in new_totals.items():
        key = str(level)
        existing = current_spell_slots.get(key) or current_spell_slots.get(level) or {}
        used = int(existing.get("used", 0) or 0) if isinstance(existing, dict) else 0
        merged[key] = {"total": int(total), "used": min(used, int(total))}
    return merged
