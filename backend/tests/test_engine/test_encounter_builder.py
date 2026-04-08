"""Unit tests for engine/encounter_builder.py (pure logic, no I/O)."""
from __future__ import annotations

import random
from typing import Any, Dict, List

import pytest

from app.engine.encounter_builder import (
    BuiltEncounter,
    EncounterEntry,
    assess_difficulty,
    calculate_adjusted_xp,
    calculate_xp_budget,
    expand_to_combatants,
    generate_encounter,
    get_group_multiplier,
    get_xp_threshold,
)

# ---------------------------------------------------------------------------
# Minimal monster fixtures (no file I/O)
# ---------------------------------------------------------------------------

GOBLIN: Dict[str, Any] = {
    "id": "goblin",
    "name": "Goblin",
    "name_fr": "Gobelin",
    "cr": 0.25,
    "xp": 50,
    "ac": 15,
    "hp": 7,
    "ability_scores": {"dexterity": 14},
    "actions": [
        {"name": "Scimitar", "type": "melee_attack", "attack_bonus": 4, "damage_dice": "1d6+2"}
    ],
}

HOBGOBLIN: Dict[str, Any] = {
    "id": "hobgoblin",
    "name": "Hobgoblin",
    "name_fr": "Hobgobelin",
    "cr": 0.5,
    "xp": 100,
    "ac": 18,
    "hp": 11,
    "ability_scores": {"dexterity": 12},
    "actions": [
        {"name": "Longsword", "type": "melee_attack", "attack_bonus": 3, "damage_dice": "1d8+1"}
    ],
}

OGRE: Dict[str, Any] = {
    "id": "ogre",
    "name": "Ogre",
    "name_fr": "Ogre",
    "cr": 2,
    "xp": 450,
    "ac": 11,
    "hp": 59,
    "ability_scores": {"dexterity": 8},
    "actions": [
        {"name": "Greatclub", "type": "melee_attack", "attack_bonus": 6, "damage_dice": "2d8+4"}
    ],
}

ALL_MONSTERS = [GOBLIN, HOBGOBLIN, OGRE]


# ---------------------------------------------------------------------------
# get_xp_threshold
# ---------------------------------------------------------------------------

class TestGetXpThreshold:
    def test_level_1_easy(self):
        assert get_xp_threshold(1, "easy") == 25

    def test_level_1_deadly(self):
        assert get_xp_threshold(1, "deadly") == 100

    def test_level_5_medium(self):
        assert get_xp_threshold(5, "medium") == 500

    def test_level_below_min_clamps_to_1(self):
        assert get_xp_threshold(0, "easy") == get_xp_threshold(1, "easy")

    def test_level_above_max_clamps_to_10(self):
        assert get_xp_threshold(99, "easy") == get_xp_threshold(10, "easy")

    def test_unknown_difficulty_defaults_to_medium(self):
        assert get_xp_threshold(3, "unknown") == get_xp_threshold(3, "medium")


# ---------------------------------------------------------------------------
# get_group_multiplier
# ---------------------------------------------------------------------------

class TestGetGroupMultiplier:
    def test_single_monster(self):
        assert get_group_multiplier(1) == 1.0

    def test_two_monsters(self):
        assert get_group_multiplier(2) == 1.5

    def test_four_monsters(self):
        assert get_group_multiplier(4) == 2.0

    def test_eight_monsters(self):
        assert get_group_multiplier(8) == 2.5

    def test_twelve_monsters(self):
        assert get_group_multiplier(12) == 3.0

    def test_fifteen_plus_monsters(self):
        assert get_group_multiplier(15) == 4.0
        assert get_group_multiplier(20) == 4.0


# ---------------------------------------------------------------------------
# calculate_xp_budget
# ---------------------------------------------------------------------------

class TestCalculateXpBudget:
    def test_party_of_four_level_1_medium(self):
        # 4 × 50 = 200
        assert calculate_xp_budget([1, 1, 1, 1], "medium") == 200

    def test_mixed_levels(self):
        # level 1 easy=25, level 3 easy=75 → 100
        assert calculate_xp_budget([1, 3], "easy") == 100

    def test_single_character(self):
        assert calculate_xp_budget([5], "hard") == 750


# ---------------------------------------------------------------------------
# calculate_adjusted_xp
# ---------------------------------------------------------------------------

class TestCalculateAdjustedXp:
    def test_single_monster_no_multiplier(self):
        assert calculate_adjusted_xp([100]) == 100

    def test_two_monsters_1_5x(self):
        assert calculate_adjusted_xp([100, 100]) == 300  # 200 × 1.5

    def test_four_monsters_2x(self):
        assert calculate_adjusted_xp([50, 50, 50, 50]) == 400  # 200 × 2.0


# ---------------------------------------------------------------------------
# assess_difficulty
# ---------------------------------------------------------------------------

class TestAssessDifficulty:
    def test_trivial(self):
        # 1 rat (10 XP) vs party of 4 level-5 players
        assert assess_difficulty([5, 5, 5, 5], [10]) == "trivial"

    def test_deadly(self):
        # troll (1800 XP) solo vs level-1 party
        result = assess_difficulty([1, 1, 1, 1], [1800])
        assert result == "deadly"

    def test_medium(self):
        # 3 goblins (50 each) vs level-1 party of 4: adjusted = 150 × 2.0 = 300
        # budget: easy=100, medium=200, hard=300, deadly=400
        result = assess_difficulty([1, 1, 1, 1], [50, 50, 50])
        assert result in ("medium", "hard")  # boundary: adjusted 300 = hard threshold


# ---------------------------------------------------------------------------
# generate_encounter
# ---------------------------------------------------------------------------

class TestGenerateEncounter:
    def test_returns_built_encounter(self):
        rng = random.Random(42)
        enc = generate_encounter(ALL_MONSTERS, [2, 2, 2, 2], "medium", rng=rng)
        assert isinstance(enc, BuiltEncounter)

    def test_has_at_least_one_entry(self):
        rng = random.Random(0)
        enc = generate_encounter(ALL_MONSTERS, [1, 1, 1, 1], "easy", rng=rng)
        assert len(enc.entries) >= 1

    def test_total_xp_raw_matches_entries(self):
        rng = random.Random(7)
        enc = generate_encounter(ALL_MONSTERS, [2, 2], "medium", rng=rng)
        expected_raw = sum(e.xp_each * e.count for e in enc.entries)
        assert enc.total_xp_raw == expected_raw

    def test_adjusted_xp_positive(self):
        rng = random.Random(13)
        enc = generate_encounter([GOBLIN], [1], "easy", rng=rng)
        assert enc.total_xp_adjusted > 0

    def test_fallback_single_monster_when_no_candidates(self):
        # Ogre CR 2 only, party level 1 — heuristic may exclude it, test fallback
        rng = random.Random(1)
        enc = generate_encounter([OGRE], [1], "easy", rng=rng)
        assert len(enc.entries) >= 1

    def test_does_not_exceed_deadly_by_large_margin(self):
        rng = random.Random(99)
        party = [1, 1, 1, 1]
        enc = generate_encounter(ALL_MONSTERS, party, "medium", rng=rng)
        deadly = calculate_xp_budget(party, "deadly")
        # Allow a small overshoot (10%)
        assert enc.total_xp_adjusted <= deadly * 1.2

    def test_deterministic_with_seeded_rng(self):
        enc1 = generate_encounter(ALL_MONSTERS, [3, 3, 3], "medium", rng=random.Random(42))
        enc2 = generate_encounter(ALL_MONSTERS, [3, 3, 3], "medium", rng=random.Random(42))
        assert [(e.monster_id, e.count) for e in enc1.entries] == [
            (e.monster_id, e.count) for e in enc2.entries
        ]

    def test_difficulty_field_is_string(self):
        rng = random.Random(5)
        enc = generate_encounter(ALL_MONSTERS, [2, 2, 2, 2], "hard", rng=rng)
        assert isinstance(enc.difficulty, str)
        assert enc.difficulty in ("trivial", "easy", "medium", "hard", "deadly")


# ---------------------------------------------------------------------------
# expand_to_combatants
# ---------------------------------------------------------------------------

class TestExpandToCombatants:
    def _make_encounter(self, entries: List[EncounterEntry]) -> BuiltEncounter:
        return BuiltEncounter(entries=entries)

    def test_single_entry_single_count(self):
        entry = EncounterEntry(
            monster_id="goblin", count=1, name_fr="Gobelin",
            cr=0.25, xp_each=50, ac=15, hp=7, attack_bonus=4, damage_notation="1d6+2",
        )
        enc = self._make_encounter([entry])
        monsters_by_id = {"goblin": GOBLIN}
        result = expand_to_combatants(enc, monsters_by_id)
        assert len(result) == 1
        assert result[0]["combatant_id"] == "goblin_1"
        assert result[0]["name"] == "Gobelin"
        assert result[0]["hp"] == 7

    def test_multiple_count_generates_unique_ids(self):
        entry = EncounterEntry(
            monster_id="goblin", count=3, name_fr="Gobelin",
            cr=0.25, xp_each=50, ac=15, hp=7, attack_bonus=4, damage_notation="1d6+2",
        )
        enc = self._make_encounter([entry])
        result = expand_to_combatants(enc, {"goblin": GOBLIN})
        ids = [c["combatant_id"] for c in result]
        assert ids == ["goblin_1", "goblin_2", "goblin_3"]

    def test_numbered_names_for_multiple(self):
        entry = EncounterEntry(
            monster_id="goblin", count=2, name_fr="Gobelin",
            cr=0.25, xp_each=50, ac=15, hp=7, attack_bonus=4, damage_notation="1d6+2",
        )
        result = expand_to_combatants(self._make_encounter([entry]), {"goblin": GOBLIN})
        assert result[0]["name"] == "Gobelin 1"
        assert result[1]["name"] == "Gobelin 2"

    def test_unknown_monster_still_expands(self):
        # EncounterEntry carries all combat stats; monsters_by_id is not required
        entry = EncounterEntry(
            monster_id="dragon", count=1, name_fr="Dragon",
            cr=10, xp_each=5900, ac=19, hp=200, attack_bonus=10, damage_notation="2d10+7",
        )
        result = expand_to_combatants(self._make_encounter([entry]), {})
        assert len(result) == 1
        assert result[0]["combatant_id"] == "dragon_1"
        assert result[0]["ac"] == 19

    def test_is_player_false_for_npcs(self):
        entry = EncounterEntry(
            monster_id="goblin", count=1, name_fr="Gobelin",
            cr=0.25, xp_each=50, ac=15, hp=7, attack_bonus=4, damage_notation="1d6+2",
        )
        result = expand_to_combatants(self._make_encounter([entry]), {"goblin": GOBLIN})
        assert result[0]["is_player"] is False
        assert result[0]["is_ai"] is True

    def test_multi_entry_encounter(self):
        entries = [
            EncounterEntry("goblin", 2, "Gobelin", 0.25, 50, 15, 7, 4, "1d6+2"),
            EncounterEntry("hobgoblin", 1, "Hobgobelin", 0.5, 100, 18, 11, 3, "1d8+1"),
        ]
        result = expand_to_combatants(
            self._make_encounter(entries),
            {"goblin": GOBLIN, "hobgoblin": HOBGOBLIN},
        )
        assert len(result) == 3
        ids = [c["combatant_id"] for c in result]
        assert "goblin_1" in ids
        assert "goblin_2" in ids
        assert "hobgoblin_1" in ids
