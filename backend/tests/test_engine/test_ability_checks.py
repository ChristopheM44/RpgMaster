"""Tests for engine/ability_checks.py"""
from __future__ import annotations

import random

import pytest

from app.engine.ability_checks import (
    Ability,
    CheckResult,
    Proficiency,
    ability_check,
    ability_modifier,
    proficiency_bonus,
    saving_throw,
    skill_check,
)


def seeded(seed: int = 42) -> random.Random:
    return random.Random(seed)


# ---------------------------------------------------------------------------
# ability_modifier
# ---------------------------------------------------------------------------

class TestAbilityModifier:
    @pytest.mark.parametrize("score,expected", [
        (1, -5), (3, -4), (8, -1), (9, -1),
        (10, 0), (11, 0), (12, 1), (13, 1),
        (16, 3), (18, 4), (20, 5), (30, 10),
    ])
    def test_values(self, score, expected):
        assert ability_modifier(score) == expected


# ---------------------------------------------------------------------------
# proficiency_bonus
# ---------------------------------------------------------------------------

class TestProficiencyBonus:
    @pytest.mark.parametrize("level,expected", [
        (1, 2), (4, 2), (5, 3), (8, 3),
        (9, 4), (12, 4), (13, 5), (16, 5),
        (17, 6), (20, 6),
    ])
    def test_values(self, level, expected):
        assert proficiency_bonus(level) == expected

    def test_level_zero_raises(self):
        with pytest.raises(ValueError):
            proficiency_bonus(0)

    def test_level_21_raises(self):
        with pytest.raises(ValueError):
            proficiency_bonus(21)


# ---------------------------------------------------------------------------
# ability_check
# ---------------------------------------------------------------------------

class TestAbilityCheck:
    def test_total_equals_roll_plus_modifier(self):
        r = ability_check(score=14, rng=seeded())  # mod = +2
        assert r.total == r.d20_roll + 2

    def test_success_when_total_meets_dc(self):
        # Force a known roll: seed 42, d20 → deterministic
        rng = random.Random(42)
        # Just check the logic: success iff total >= dc
        r = ability_check(score=10, dc=10, rng=rng)
        assert r.success == (r.total >= 10)

    def test_no_dc_success_is_none(self):
        r = ability_check(score=10, rng=seeded())
        assert r.success is None
        assert r.dc is None

    def test_advantage_two_rolls(self):
        r = ability_check(score=10, advantage=True, rng=seeded())
        assert len(r.all_rolls) == 2
        assert r.d20_roll == max(r.all_rolls)
        assert r.advantage is True

    def test_disadvantage_two_rolls(self):
        r = ability_check(score=10, advantage=False, rng=seeded())
        assert len(r.all_rolls) == 2
        assert r.d20_roll == min(r.all_rolls)
        assert r.advantage is False

    def test_critical_hit(self):
        # Patch to force 20
        rng = random.Random.__new__(random.Random)
        rng.randint = lambda a, b: 20
        r = ability_check(score=10, rng=rng)
        assert r.critical_hit is True
        assert r.critical_fail is False

    def test_critical_fail(self):
        rng = random.Random.__new__(random.Random)
        rng.randint = lambda a, b: 1
        r = ability_check(score=10, dc=5, rng=rng)
        assert r.critical_fail is True
        assert r.critical_hit is False

    def test_breakdown_string_contains_total(self):
        r = ability_check(score=10, dc=12, rng=seeded())
        assert str(r.total) in r.breakdown


# ---------------------------------------------------------------------------
# skill_check
# ---------------------------------------------------------------------------

class TestSkillCheck:
    def test_no_proficiency_uses_ability_mod_only(self):
        rng = seeded(1)
        r = skill_check(score=14, skill="stealth", level=1,
                        proficiency=Proficiency.NONE, rng=rng)
        expected_mod = ability_modifier(14)  # +2
        assert r.modifier == expected_mod
        assert r.total == r.d20_roll + expected_mod

    def test_proficient_adds_prof_bonus(self):
        rng = seeded(1)
        r = skill_check(score=14, skill="stealth", level=5,
                        proficiency=Proficiency.PROFICIENT, rng=rng)
        # mod=+2, prof=+3 at level 5
        assert r.modifier == 2 + 3

    def test_expert_doubles_prof(self):
        rng = seeded(1)
        r = skill_check(score=10, skill="perception", level=5,
                        proficiency=Proficiency.EXPERT, rng=rng)
        # mod=0, prof=3, expert=6
        assert r.modifier == 6

    def test_half_proficiency(self):
        rng = seeded(1)
        r = skill_check(score=10, skill="arcana", level=5,
                        proficiency=Proficiency.HALF, rng=rng)
        # prof=3, half=1 (floor)
        assert r.modifier == 0 + (3 // 2)

    def test_unknown_skill_raises(self):
        with pytest.raises(ValueError, match="Unknown skill"):
            skill_check(score=10, skill="cooking", level=1)

    def test_label_includes_skill_name(self):
        r = skill_check(score=10, skill="stealth", level=1, rng=seeded())
        assert "Stealth" in r.label

    def test_success_flag(self):
        # Use a very low DC to ensure success with any roll
        r = skill_check(score=20, skill="athletics", level=5,
                        proficiency=Proficiency.PROFICIENT, dc=1, rng=seeded())
        assert r.success is True

    def test_failure_flag(self):
        # Use impossible DC
        r = skill_check(score=8, skill="athletics", level=1,
                        proficiency=Proficiency.NONE, dc=30, rng=seeded())
        assert r.success is False

    def test_skill_name_with_space(self):
        # "animal handling" should resolve to "animal_handling"
        r = skill_check(score=12, skill="animal handling", level=1, rng=seeded())
        assert r is not None


# ---------------------------------------------------------------------------
# saving_throw
# ---------------------------------------------------------------------------

class TestSavingThrow:
    def test_not_proficient_uses_mod_only(self):
        r = saving_throw(score=14, ability=Ability.DEX, level=1,
                         proficient=False, rng=seeded())
        assert r.modifier == ability_modifier(14)

    def test_proficient_adds_bonus(self):
        r = saving_throw(score=14, ability=Ability.CON, level=5,
                         proficient=True, rng=seeded())
        assert r.modifier == ability_modifier(14) + proficiency_bonus(5)

    def test_label(self):
        r = saving_throw(score=10, ability=Ability.WIS, level=1, rng=seeded())
        assert "WIS" in r.label
        assert "Save" in r.label

    def test_success_against_dc(self):
        r = saving_throw(score=20, ability=Ability.STR, level=5,
                         proficient=True, dc=1, rng=seeded())
        assert r.success is True

    def test_advantage(self):
        r = saving_throw(score=10, ability=Ability.DEX, level=1,
                         advantage=True, rng=seeded())
        assert len(r.all_rolls) == 2
        assert r.d20_roll == max(r.all_rolls)

    def test_breakdown_contains_dc(self):
        r = saving_throw(score=10, ability=Ability.INT, level=1, dc=15, rng=seeded())
        assert "DC 15" in r.breakdown
