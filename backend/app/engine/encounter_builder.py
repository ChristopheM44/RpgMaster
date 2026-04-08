"""Encounter builder: pure D&D 5.2 SRD encounter logic (no I/O, no async).

XP Thresholds per character per level (SRD 5.2 §Building Combat Encounters):
Easy / Medium / Hard / Deadly
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Optional

# XP thresholds per character per level: (Easy, Medium, Hard, Deadly)
_XP_THRESHOLDS: dict[int, tuple[int, int, int, int]] = {
    1:  (25,   50,   75,   100),
    2:  (50,   100,  150,  200),
    3:  (75,   150,  225,  400),
    4:  (125,  250,  375,  500),
    5:  (250,  500,  750,  1100),
    6:  (300,  600,  900,  1400),
    7:  (350,  750,  1100, 1700),
    8:  (450,  900,  1400, 2100),
    9:  (550,  1100, 1600, 2400),
    10: (600,  1200, 1900, 2800),
}

# XP multipliers by number of monsters: (min_count, max_count, multiplier)
_GROUP_MULTIPLIERS: list[tuple[int, int, float]] = [
    (1,   1,   1.0),
    (2,   2,   1.5),
    (3,   6,   2.0),
    (7,   10,  2.5),
    (11,  14,  3.0),
    (15,  999, 4.0),
]

_DIFFICULTY_INDEX: dict[str, int] = {
    "easy": 0,
    "medium": 1,
    "hard": 2,
    "deadly": 3,
}


@dataclass
class EncounterEntry:
    """One type of monster and how many of them appear in the encounter."""

    monster_id: str
    count: int
    name_fr: str
    cr: float
    xp_each: int
    ac: int
    hp: int
    attack_bonus: int
    damage_notation: str


@dataclass
class BuiltEncounter:
    """Result of building an encounter."""

    entries: list[EncounterEntry] = field(default_factory=list)
    total_xp_raw: int = 0
    total_xp_adjusted: int = 0
    difficulty: str = "medium"
    xp_budget: int = 0


# ---------------------------------------------------------------------------
# Public pure functions
# ---------------------------------------------------------------------------


def get_xp_threshold(level: int, difficulty: str) -> int:
    """XP threshold for one character at given level and difficulty."""
    level = max(1, min(level, 10))
    d_idx = _DIFFICULTY_INDEX.get(difficulty, 1)
    return _XP_THRESHOLDS[level][d_idx]


def get_group_multiplier(monster_count: int) -> float:
    """XP multiplier for a group of *monster_count* monsters."""
    for lo, hi, mult in _GROUP_MULTIPLIERS:
        if lo <= monster_count <= hi:
            return mult
    return 4.0


def calculate_xp_budget(party_levels: list[int], difficulty: str) -> int:
    """Total adjusted XP budget for the encounter given the party."""
    return sum(get_xp_threshold(lvl, difficulty) for lvl in party_levels)


def calculate_adjusted_xp(monster_xp_list: list[int]) -> int:
    """Adjusted encounter XP = raw total × group multiplier."""
    total = sum(monster_xp_list)
    return int(total * get_group_multiplier(len(monster_xp_list)))


def assess_difficulty(party_levels: list[int], monster_xp_list: list[int]) -> str:
    """Return difficulty label for a given party vs a flat list of monster XP values."""
    adjusted = calculate_adjusted_xp(monster_xp_list)
    difficulties = ("easy", "medium", "hard", "deadly")
    thresholds = [calculate_xp_budget(party_levels, d) for d in difficulties]
    if adjusted < thresholds[0]:
        return "trivial"
    if adjusted < thresholds[1]:
        return "easy"
    if adjusted < thresholds[2]:
        return "medium"
    if adjusted < thresholds[3]:
        return "hard"
    return "deadly"


def _first_attack_action(monster: dict[str, Any]) -> dict[str, Any]:
    """Return the first action that has an attack_bonus, or empty dict."""
    for action in monster.get("actions", []):
        if "attack_bonus" in action:
            return action
    return {}


def generate_encounter(
    monsters_data: list[dict[str, Any]],
    party_levels: list[int],
    difficulty: str = "medium",
    rng: Optional[random.Random] = None,
) -> BuiltEncounter:
    """Generate a balanced random encounter for the given party.

    Args:
        monsters_data: Flat list of monster dicts from srd_data/monsters.json.
        party_levels:  One int per party member (their character level).
        difficulty:    Target difficulty label ("easy"|"medium"|"hard"|"deadly").
        rng:           Optional seeded Random for deterministic tests.

    Returns:
        BuiltEncounter with entries and XP accounting.
    """
    if rng is None:
        rng = random.Random()
    if not party_levels:
        party_levels = [1]

    budget = calculate_xp_budget(party_levels, difficulty)
    deadly_budget = calculate_xp_budget(party_levels, "deadly")
    avg_level = sum(party_levels) / len(party_levels)

    # CR range heuristic: monsters roughly matching party level
    max_cr = max(1.0, avg_level * 0.75)
    min_cr = 0.0
    candidates = [m for m in monsters_data if min_cr <= m["cr"] <= max_cr]
    if not candidates:
        # Fallback: just use the cheapest monsters available
        candidates = sorted(monsters_data, key=lambda m: m["xp"])[:4]

    entries: list[EncounterEntry] = []
    xp_accumulated = 0
    attempts = 0

    while xp_accumulated < budget * 0.6 and attempts < 30:
        attempts += 1
        monster = rng.choice(candidates)
        monster_xp = monster["xp"]

        # How many fit in the remaining budget?
        remaining = budget - xp_accumulated
        max_by_budget = max(1, remaining // max(monster_xp, 1))
        max_count = min(max_by_budget, 6)  # never more than 6 of one type
        count = rng.randint(1, max(1, max_count))

        # Reject if adjusted XP would exceed deadly by more than 10%
        probe_xp = [e.xp_each for e in entries for _ in range(e.count)]
        probe_xp.extend([monster_xp] * count)
        if calculate_adjusted_xp(probe_xp) > deadly_budget * 1.1:
            count = max(1, count // 2)
            probe_xp = [e.xp_each for e in entries for _ in range(e.count)]
            probe_xp.extend([monster_xp] * count)
            if calculate_adjusted_xp(probe_xp) > deadly_budget * 1.1:
                continue  # still too much, skip this monster

        first_action = _first_attack_action(monster)
        entries.append(EncounterEntry(
            monster_id=monster["id"],
            count=count,
            name_fr=monster.get("name_fr", monster["name"]),
            cr=monster["cr"],
            xp_each=monster_xp,
            ac=monster["ac"],
            hp=monster["hp"],
            attack_bonus=first_action.get("attack_bonus", 2),
            damage_notation=first_action.get("damage_dice", "1d4"),
        ))
        xp_accumulated += monster_xp * count

        # Cap variety at 3 different types
        if len(entries) >= 3:
            break

    # Fallback: at least one monster
    if not entries:
        m = candidates[0]
        first_action = _first_attack_action(m)
        entries.append(EncounterEntry(
            monster_id=m["id"],
            count=1,
            name_fr=m.get("name_fr", m["name"]),
            cr=m["cr"],
            xp_each=m["xp"],
            ac=m["ac"],
            hp=m["hp"],
            attack_bonus=first_action.get("attack_bonus", 2),
            damage_notation=first_action.get("damage_dice", "1d4"),
        ))

    all_xp_flat = [e.xp_each for e in entries for _ in range(e.count)]
    return BuiltEncounter(
        entries=entries,
        total_xp_raw=sum(all_xp_flat),
        total_xp_adjusted=calculate_adjusted_xp(all_xp_flat),
        difficulty=assess_difficulty(party_levels, all_xp_flat),
        xp_budget=budget,
    )


def expand_to_combatants(
    encounter: BuiltEncounter,
    monsters_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Flatten BuiltEncounter into one combatant dict per monster instance.

    Each dict is ready to be inserted into state_data["combatants"].
    """
    result: list[dict[str, Any]] = []
    for entry in encounter.entries:
        for i in range(entry.count):
            suffix = f"_{i + 1}"
            combatant_id = f"{entry.monster_id}{suffix}"
            display_name = entry.name_fr
            if entry.count > 1:
                display_name = f"{entry.name_fr} {i + 1}"
            result.append({
                "combatant_id": combatant_id,
                "name": display_name,
                "hp": entry.hp,
                "hp_max": entry.hp,
                "is_player": False,
                "is_ai": True,
                "ac": entry.ac,
                "attack_bonus": entry.attack_bonus,
                "damage_notation": entry.damage_notation,
                "cr": entry.cr,
                "xp": entry.xp_each,
            })
    return result
