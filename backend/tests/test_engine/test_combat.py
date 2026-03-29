"""Tests for engine/combat.py"""
from __future__ import annotations

import random

import pytest

from app.engine.combat import (
    ActionEconomy,
    AttackResult,
    DamageResult,
    DeathSaveResult,
    InitiativeResult,
    new_turn_economy,
    roll_attack,
    roll_damage,
    roll_death_save,
    roll_initiative,
    sort_initiative,
)


def seeded(seed: int = 42) -> random.Random:
    return random.Random(seed)


# ---------------------------------------------------------------------------
# roll_initiative
# ---------------------------------------------------------------------------


class TestRollInitiative:
    def test_returns_initiative_result(self):
        result = roll_initiative(dex_score=14, combatant_id="hero", rng=seeded())
        assert isinstance(result, InitiativeResult)
        assert result.combatant_id == "hero"
        assert result.dex_modifier == 2  # (14 - 10) // 2
        assert result.total == result.d20_roll + 2

    def test_dex_10_zero_modifier(self):
        result = roll_initiative(dex_score=10, rng=seeded())
        assert result.dex_modifier == 0
        assert result.total == result.d20_roll

    def test_low_dex_negative_modifier(self):
        result = roll_initiative(dex_score=8, rng=seeded())
        assert result.dex_modifier == -1
        assert result.total == result.d20_roll - 1

    def test_d20_in_range(self):
        rng = seeded(1)
        for _ in range(100):
            result = roll_initiative(10, rng=rng)
            assert 1 <= result.d20_roll <= 20


class TestSortInitiative:
    def test_highest_total_first(self):
        combatants = [
            InitiativeResult("a", d20_roll=5, dex_modifier=0, total=5),
            InitiativeResult("b", d20_roll=15, dex_modifier=0, total=15),
            InitiativeResult("c", d20_roll=10, dex_modifier=0, total=10),
        ]
        ordered = sort_initiative(combatants)
        assert [r.combatant_id for r in ordered] == ["b", "c", "a"]

    def test_tie_broken_by_dex_modifier(self):
        combatants = [
            InitiativeResult("low_dex", d20_roll=10, dex_modifier=1, total=11),
            InitiativeResult("high_dex", d20_roll=9, dex_modifier=2, total=11),
        ]
        ordered = sort_initiative(combatants)
        assert ordered[0].combatant_id == "high_dex"


# ---------------------------------------------------------------------------
# roll_attack
# ---------------------------------------------------------------------------


class TestRollAttack:
    def test_hit_when_total_gte_ac(self):
        # Seed so d20 = 15; attack_bonus = 5 → total 20 vs AC 18 → hit
        rng = random.Random(0)
        # Consume seed to get deterministic d20 = 15
        # We'll just verify the logic by forcing a known result
        result = roll_attack(attack_bonus=5, target_ac=15, rng=seeded(7))
        assert isinstance(result, AttackResult)
        assert result.hit == (result.d20_roll == 20 or (result.d20_roll != 1 and result.total >= 15))

    def test_natural_20_always_hits(self):
        # Keep trying until we get a nat 20 (use many seeds)
        for seed in range(200):
            rng = random.Random(seed)
            result = roll_attack(attack_bonus=-10, target_ac=30, rng=rng)
            if result.d20_roll == 20:
                assert result.hit is True
                assert result.critical is True
                break

    def test_natural_1_always_misses(self):
        for seed in range(200):
            rng = random.Random(seed)
            result = roll_attack(attack_bonus=20, target_ac=1, rng=rng)
            if result.d20_roll == 1:
                assert result.hit is False
                assert result.fumble is True
                break

    def test_miss_when_total_lt_ac(self):
        # d20=1 by force → miss
        for seed in range(200):
            rng = random.Random(seed)
            result = roll_attack(attack_bonus=0, target_ac=25, rng=rng)
            if result.d20_roll == 1:
                assert result.hit is False
                break

    def test_advantage_uses_two_rolls(self):
        result = roll_attack(1, 15, advantage=True, rng=seeded())
        assert len(result.all_rolls) == 2

    def test_normal_uses_one_roll(self):
        result = roll_attack(1, 15, advantage=None, rng=seeded())
        assert len(result.all_rolls) == 1

    def test_breakdown_contains_vs_ac(self):
        result = roll_attack(3, 14, rng=seeded())
        if not result.critical and not result.fumble:
            assert "AC 14" in result.breakdown

    def test_critical_breakdown(self):
        for seed in range(200):
            rng = random.Random(seed)
            r = roll_attack(0, 10, rng=rng)
            if r.critical:
                assert "CRITICAL" in r.breakdown
                break


# ---------------------------------------------------------------------------
# roll_damage
# ---------------------------------------------------------------------------


class TestRollDamage:
    def test_basic_1d8(self):
        result = roll_damage("1d8", rng=seeded())
        assert isinstance(result, DamageResult)
        assert len(result.rolls) == 1
        assert 1 <= result.rolls[0] <= 8
        assert result.total == result.rolls[0]
        assert not result.critical

    def test_modifier_added(self):
        result = roll_damage("1d6+3", rng=seeded())
        assert result.modifier == 3
        assert result.total == result.rolls[0] + 3

    def test_negative_modifier(self):
        result = roll_damage("1d4-2", rng=seeded(99))
        assert result.modifier == -2

    def test_total_never_below_zero(self):
        # 1d4-10 → always ≤ -6, clamped to 0
        for seed in range(50):
            result = roll_damage("1d4-10", rng=random.Random(seed))
            assert result.total == 0

    def test_critical_doubles_dice(self):
        result = roll_damage("2d6+3", critical=True, rng=seeded())
        assert len(result.rolls) == 4  # 2 × 2 dice
        assert result.modifier == 3
        assert result.critical is True

    def test_critical_does_not_double_modifier(self):
        normal = roll_damage("1d8+5", critical=False, rng=seeded(1))
        crit = roll_damage("1d8+5", critical=True, rng=seeded(1))
        # On crit, 2 dice rolled vs 1 — check modifier stays 5 in both
        assert normal.modifier == crit.modifier == 5

    def test_invalid_notation_raises(self):
        with pytest.raises(ValueError, match="Invalid damage notation"):
            roll_damage("4d6kh3")

    def test_invalid_notation_text_raises(self):
        with pytest.raises(ValueError):
            roll_damage("not_dice")

    @pytest.mark.parametrize("notation", ["1d4", "2d6+3", "1d12-1", "3d8"])
    def test_valid_notations(self, notation):
        result = roll_damage(notation, rng=seeded())
        assert result.total >= 0


# ---------------------------------------------------------------------------
# roll_death_save
# ---------------------------------------------------------------------------


class TestRollDeathSave:
    def test_returns_death_save_result(self):
        result = roll_death_save(rng=seeded())
        assert isinstance(result, DeathSaveResult)
        assert 1 <= result.d20_roll <= 20

    def test_natural_20_is_critical_success(self):
        for seed in range(200):
            result = roll_death_save(rng=random.Random(seed))
            if result.d20_roll == 20:
                assert result.critical_success is True
                assert result.success is True
                break

    def test_natural_1_is_critical_failure(self):
        for seed in range(200):
            result = roll_death_save(rng=random.Random(seed))
            if result.d20_roll == 1:
                assert result.critical_failure is True
                assert result.success is False
                break

    def test_10_or_above_is_success(self):
        # Verify success = (d20 >= 10)
        for seed in range(200):
            result = roll_death_save(rng=random.Random(seed))
            assert result.success == (result.d20_roll >= 10)

    def test_critical_success_implies_success(self):
        for seed in range(500):
            result = roll_death_save(rng=random.Random(seed))
            if result.critical_success:
                assert result.success is True


# ---------------------------------------------------------------------------
# ActionEconomy
# ---------------------------------------------------------------------------


class TestActionEconomy:
    def test_new_turn_full_economy(self):
        eco = new_turn_economy(speed=35)
        assert eco.action is True
        assert eco.bonus_action is True
        assert eco.reaction is True
        assert eco.movement == 35

    def test_use_action(self):
        eco = new_turn_economy()
        assert eco.use_action() is True
        assert eco.action is False
        assert eco.use_action() is False  # already spent

    def test_use_bonus_action(self):
        eco = new_turn_economy()
        assert eco.use_bonus_action() is True
        assert eco.use_bonus_action() is False

    def test_use_reaction(self):
        eco = new_turn_economy()
        assert eco.use_reaction() is True
        assert eco.use_reaction() is False

    def test_spend_movement_partial(self):
        eco = new_turn_economy(speed=30)
        assert eco.spend_movement(10) is True
        assert eco.movement == 20
        assert eco.spend_movement(20) is True
        assert eco.movement == 0

    def test_spend_movement_insufficient(self):
        eco = new_turn_economy(speed=10)
        assert eco.spend_movement(15) is False
        assert eco.movement == 10  # unchanged

    def test_default_speed_30(self):
        eco = new_turn_economy()
        assert eco.movement == 30
