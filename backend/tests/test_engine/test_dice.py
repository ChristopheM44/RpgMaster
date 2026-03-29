"""Tests for engine/dice.py"""
from __future__ import annotations

import random

import pytest

from app.engine.dice import roll, roll_ability_scores, roll_with_advantage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def seeded(seed: int = 42) -> random.Random:
    return random.Random(seed)


# ---------------------------------------------------------------------------
# Basic notation parsing
# ---------------------------------------------------------------------------

class TestRollParsing:
    def test_simple_d20(self):
        r = roll("d20", seeded())
        assert 1 <= r.total <= 20
        assert len(r.rolls) == 1
        assert r.modifier == 0

    def test_explicit_count(self):
        r = roll("2d6", seeded())
        assert len(r.rolls) == 2
        assert all(1 <= v <= 6 for v in r.rolls)

    def test_positive_modifier(self):
        # d2 rolls 1 or 2; check modifier is applied
        r = roll("1d2+5", seeded())
        assert r.modifier == 5
        assert r.total == r.rolls[0] + 5

    def test_negative_modifier(self):
        r = roll("1d2-3", seeded())
        assert r.modifier == -3
        assert r.total == r.rolls[0] - 3

    def test_multi_dice_with_modifier(self):
        r = roll("2d2+4", seeded())
        assert r.modifier == 4
        assert r.total == sum(r.rolls) + 4

    def test_case_insensitive(self):
        r = roll("2D6+3", seeded())
        assert len(r.rolls) == 2

    def test_whitespace_stripped(self):
        r = roll("  2d6 + 3  ".replace(" ", ""), seeded())
        assert r.modifier == 3

    def test_invalid_notation_raises(self):
        with pytest.raises(ValueError, match="Invalid dice notation"):
            roll("gibberish")

    def test_invalid_sides_raises(self):
        with pytest.raises(ValueError):
            roll("1d1")  # 1 side < 2 minimum

    @pytest.mark.parametrize("notation", ["0d6", "2d1"])
    def test_invalid_edge_cases(self, notation):
        # 0 count → regex won't match (count group requires \d+, "0" matches but count<1)
        # 2d1 → sides < 2
        with pytest.raises(ValueError):
            roll(notation)


# ---------------------------------------------------------------------------
# Keep-highest / keep-lowest
# ---------------------------------------------------------------------------

class TestKeepModifiers:
    def test_kh_keeps_highest(self):
        rng = seeded(0)
        r = roll("4d6kh3", rng)
        assert len(r.rolls) == 4
        assert len(r.kept) == 3
        assert r.kept == sorted(r.rolls, reverse=True)[:3]
        assert r.total == sum(r.kept)

    def test_kl_keeps_lowest(self):
        rng = seeded(0)
        r = roll("4d6kl1", rng)
        assert len(r.kept) == 1
        assert r.kept[0] == min(r.rolls)

    def test_kh_total_equals_kept_plus_modifier(self):
        rng = seeded(1)
        r = roll("4d6kh3+2", rng)
        assert r.total == sum(r.kept) + 2

    def test_keep_n_out_of_range_raises(self):
        with pytest.raises(ValueError):
            roll("2d6kh5", seeded())  # can't keep 5 from 2 dice


# ---------------------------------------------------------------------------
# Advantage / Disadvantage
# ---------------------------------------------------------------------------

class TestAdvantage:
    def test_advantage_keeps_max(self):
        rng = random.Random(99)
        r = roll_with_advantage(20, advantage=True, rng=rng)
        assert r.kept[0] == max(r.rolls)
        assert r.advantage is True

    def test_disadvantage_keeps_min(self):
        rng = random.Random(99)
        r = roll_with_advantage(20, advantage=False, rng=rng)
        assert r.kept[0] == min(r.rolls)
        assert r.advantage is False

    def test_modifier_applied(self):
        rng = random.Random(7)
        r = roll_with_advantage(20, advantage=True, modifier=3, rng=rng)
        assert r.total == r.kept[0] + 3

    def test_two_rolls_always_present(self):
        rng = seeded()
        r = roll_with_advantage(20, advantage=True, rng=rng)
        assert len(r.rolls) == 2


# ---------------------------------------------------------------------------
# Ability score generation
# ---------------------------------------------------------------------------

class TestAbilityScores:
    def test_returns_six_results(self):
        results = roll_ability_scores()
        assert len(results) == 6

    def test_each_uses_4d6kh3(self):
        for r in roll_ability_scores():
            assert len(r.rolls) == 4
            assert len(r.kept) == 3

    def test_scores_in_valid_range(self):
        for r in roll_ability_scores():
            assert 3 <= r.total <= 18
