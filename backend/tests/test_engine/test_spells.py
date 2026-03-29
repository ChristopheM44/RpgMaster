"""Tests for engine/spells.py"""
from __future__ import annotations

import random

import pytest

from app.engine.spells import (
    FULL_CASTER_SLOTS,
    HALF_CASTER_SLOTS,
    THIRD_CASTER_SLOTS,
    ConcentrationCheckResult,
    ConcentrationState,
    SpellCastResult,
    SpellSlots,
    cast_spell,
    concentration_check,
    roll_spell_attack,
    spell_attack_bonus,
    spell_save_dc,
    starting_slots,
    upcast_damage,
)
from app.engine.combat import AttackResult


def seeded(seed: int = 42) -> random.Random:
    return random.Random(seed)


# ---------------------------------------------------------------------------
# Spell slot tables
# ---------------------------------------------------------------------------


class TestSlotTables:
    def test_full_caster_level_1_has_2_first_level_slots(self):
        assert FULL_CASTER_SLOTS[1] == {1: 2}

    def test_full_caster_level_5_has_third_level_slots(self):
        slots = FULL_CASTER_SLOTS[5]
        assert slots.get(3, 0) == 2

    def test_full_caster_level_20_has_9th_level_slots(self):
        slots = FULL_CASTER_SLOTS[20]
        assert slots.get(9, 0) == 1

    def test_half_caster_level_1_no_slots(self):
        assert HALF_CASTER_SLOTS[1] == {}

    def test_half_caster_level_2_starts_with_first_level(self):
        assert HALF_CASTER_SLOTS[2] == {1: 2}

    def test_third_caster_level_1_and_2_no_slots(self):
        assert THIRD_CASTER_SLOTS[1] == {}
        assert THIRD_CASTER_SLOTS[2] == {}

    def test_third_caster_level_3_starts(self):
        assert THIRD_CASTER_SLOTS[3] == {1: 2}

    def test_all_tables_have_20_levels(self):
        for table in (FULL_CASTER_SLOTS, HALF_CASTER_SLOTS, THIRD_CASTER_SLOTS):
            assert len(table) == 20
            for lvl in range(1, 21):
                assert lvl in table


class TestStartingSlots:
    def test_full_caster_level_3(self):
        slots = starting_slots("full", 3)
        assert slots == {1: 4, 2: 2}

    def test_half_caster_level_5(self):
        slots = starting_slots("half", 5)
        assert slots[2] == 2

    def test_third_caster_level_7(self):
        slots = starting_slots("third", 7)
        assert slots[2] == 2

    def test_returns_copy_not_reference(self):
        slots_a = starting_slots("full", 1)
        slots_b = starting_slots("full", 1)
        slots_a[1] = 0
        assert slots_b[1] == 2  # unaffected

    def test_invalid_caster_type(self):
        with pytest.raises(ValueError, match="caster_type"):
            starting_slots("warlock", 5)

    def test_invalid_level(self):
        with pytest.raises(ValueError, match="level"):
            starting_slots("full", 0)
        with pytest.raises(ValueError, match="level"):
            starting_slots("full", 21)


# ---------------------------------------------------------------------------
# SpellSlots
# ---------------------------------------------------------------------------


class TestSpellSlots:
    def test_from_table_full_caster_level_3(self):
        slots = SpellSlots.from_table("full", 3)
        assert slots.remaining(1) == 4
        assert slots.remaining(2) == 2
        assert slots.remaining(3) == 0

    def test_has_slot_true(self):
        slots = SpellSlots(slots={1: 2})
        assert slots.has_slot(1) is True

    def test_has_slot_false_when_zero(self):
        slots = SpellSlots(slots={1: 0})
        assert slots.has_slot(1) is False

    def test_has_slot_false_when_missing(self):
        slots = SpellSlots(slots={})
        assert slots.has_slot(3) is False

    def test_use_slot_decrements(self):
        slots = SpellSlots(slots={1: 2})
        slots.use_slot(1)
        assert slots.remaining(1) == 1

    def test_use_slot_raises_when_empty(self):
        slots = SpellSlots(slots={1: 0})
        with pytest.raises(ValueError, match="No spell slots"):
            slots.use_slot(1)

    def test_restore_adds_back(self):
        slots = SpellSlots(slots={1: 0})
        slots.restore(1, 2)
        assert slots.remaining(1) == 2

    def test_snapshot_is_copy(self):
        slots = SpellSlots(slots={1: 3})
        snap = slots.snapshot()
        snap[1] = 0
        assert slots.remaining(1) == 3  # unaffected


# ---------------------------------------------------------------------------
# ConcentrationState
# ---------------------------------------------------------------------------


class TestConcentrationState:
    def test_starts_inactive(self):
        state = ConcentrationState()
        assert state.active is False
        assert state.spell_name == ""

    def test_start_concentration(self):
        state = ConcentrationState()
        state.start("Bless", slot_level=1)
        assert state.active is True
        assert state.spell_name == "Bless"
        assert state.slot_level == 1

    def test_end_concentration(self):
        state = ConcentrationState()
        state.start("Bless", 1)
        state.end()
        assert state.active is False
        assert state.spell_name == ""
        assert state.slot_level == 0

    def test_start_replaces_previous(self):
        state = ConcentrationState()
        state.start("Bless", 1)
        state.start("Hold Person", 2)
        assert state.spell_name == "Hold Person"


# ---------------------------------------------------------------------------
# spell_save_dc / spell_attack_bonus
# ---------------------------------------------------------------------------


class TestSpellDCAndBonus:
    def test_spell_save_dc_formula(self):
        # 8 + 2 (prof) + 3 (INT 16 → mod 3) = 13
        dc = spell_save_dc(caster_ability_score=16, prof_bonus=2)
        assert dc == 13

    def test_spell_save_dc_min_case(self):
        # 8 + 2 + (-1) = 9 (INT 8 → mod -1, level 1 prof +2)
        dc = spell_save_dc(caster_ability_score=8, prof_bonus=2)
        assert dc == 9

    def test_spell_attack_bonus_formula(self):
        # 2 (prof) + 3 (INT 16) = 5
        bonus = spell_attack_bonus(caster_ability_score=16, prof_bonus=2)
        assert bonus == 5


# ---------------------------------------------------------------------------
# roll_spell_attack
# ---------------------------------------------------------------------------


class TestRollSpellAttack:
    def test_returns_attack_result(self):
        result = roll_spell_attack(
            caster_ability_score=16,
            prof_bonus=2,
            target_ac=14,
            rng=seeded(),
        )
        assert isinstance(result, AttackResult)

    def test_uses_correct_bonus(self):
        result = roll_spell_attack(16, 2, 14, rng=seeded())
        # bonus = 2 + 3 = 5
        assert result.attack_bonus == 5

    def test_natural_20_always_hits(self):
        for seed in range(200):
            result = roll_spell_attack(1, 0, 30, rng=random.Random(seed))
            if result.d20_roll == 20:
                assert result.hit is True
                assert result.critical is True
                break

    def test_advantage_two_rolls(self):
        result = roll_spell_attack(14, 2, 15, advantage=True, rng=seeded())
        assert len(result.all_rolls) == 2


# ---------------------------------------------------------------------------
# cast_spell
# ---------------------------------------------------------------------------


class TestCastSpell:
    def _make_slots(self) -> SpellSlots:
        return SpellSlots(slots={1: 2, 2: 1, 3: 1})

    def _make_conc(self) -> ConcentrationState:
        return ConcentrationState()

    def test_basic_cast_consumes_slot(self):
        slots = self._make_slots()
        conc = self._make_conc()
        result = cast_spell(slots, "Magic Missile", 1, 1, False, conc)
        assert isinstance(result, SpellCastResult)
        assert slots.remaining(1) == 1
        assert result.upcasted is False

    def test_upcast_uses_higher_slot(self):
        slots = self._make_slots()
        conc = self._make_conc()
        result = cast_spell(slots, "Magic Missile", 1, 3, False, conc)
        assert result.upcasted is True
        assert result.slot_level == 3
        assert slots.remaining(3) == 0

    def test_cantrip_uses_no_slot(self):
        slots = self._make_slots()
        conc = self._make_conc()
        before = slots.snapshot()
        cast_spell(slots, "Fire Bolt", 0, 0, False, conc)
        assert slots.snapshot() == before

    def test_concentration_ends_previous(self):
        slots = self._make_slots()
        conc = self._make_conc()
        conc.start("Bless", 1)
        result = cast_spell(slots, "Hold Person", 2, 2, True, conc)
        assert conc.spell_name == "Hold Person"
        assert result.previous_concentration == "Bless"

    def test_non_concentration_does_not_end_concentration(self):
        slots = self._make_slots()
        conc = self._make_conc()
        conc.start("Bless", 1)
        cast_spell(slots, "Magic Missile", 1, 1, False, conc)
        assert conc.spell_name == "Bless"  # unaffected

    def test_slot_lower_than_spell_level_raises(self):
        slots = self._make_slots()
        conc = self._make_conc()
        with pytest.raises(ValueError, match="level-2 spell in a level-1 slot"):
            cast_spell(slots, "Hold Person", 2, 1, False, conc)

    def test_no_slots_raises(self):
        slots = SpellSlots(slots={1: 0})
        conc = self._make_conc()
        with pytest.raises(ValueError, match="No spell slots"):
            cast_spell(slots, "Magic Missile", 1, 1, False, conc)

    def test_result_slots_remaining_is_snapshot(self):
        slots = self._make_slots()
        conc = self._make_conc()
        result = cast_spell(slots, "Magic Missile", 1, 1, False, conc)
        assert result.slots_remaining[1] == 1  # started with 2, used 1


# ---------------------------------------------------------------------------
# concentration_check
# ---------------------------------------------------------------------------


class TestConcentrationCheck:
    def test_dc_is_max_10_or_half_damage(self):
        # damage = 14 → DC = 7 → but max(10, 7) = 10
        result = concentration_check(con_score=14, damage_taken=14, level=1, rng=seeded())
        assert result.dc == 10

        # damage = 30 → DC = 15
        result2 = concentration_check(con_score=14, damage_taken=30, level=1, rng=seeded())
        assert result2.dc == 15

    def test_always_dc_10_minimum(self):
        # damage = 1 → half = 0 → max(10, 0) = 10
        result = concentration_check(con_score=14, damage_taken=1, level=1, rng=seeded())
        assert result.dc == 10

    def test_returns_check_result_type(self):
        result = concentration_check(14, 10, 1, rng=seeded())
        assert isinstance(result, ConcentrationCheckResult)
        assert 1 <= result.d20_roll <= 20

    def test_success_set_correctly(self):
        result = concentration_check(14, 10, 1, rng=seeded())
        assert result.success == (result.total >= result.dc)

    def test_proficient_con_adds_bonus(self):
        # Con 12 (mod +1), level 5 (prof +3) = total mod 4
        result = concentration_check(12, 10, 5, proficient=True, rng=seeded())
        assert result.modifier == 4  # +1 CON + +3 prof


# ---------------------------------------------------------------------------
# upcast_damage
# ---------------------------------------------------------------------------


class TestUpcastDamage:
    def test_no_upcast_same_as_normal(self):
        result = upcast_damage("2d6+3", "1d6", spell_level=1, slot_level=1, rng=seeded())
        assert result.notation == "2d6+3"
        assert len(result.rolls) == 2

    def test_upcast_adds_extra_dice(self):
        # Fireball (3d6 base) upcasted from level 3 to level 5 → +2d6
        result = upcast_damage("8d6", "1d6", spell_level=3, slot_level=5, rng=seeded())
        # 8 base dice + 2 extra dice = 10 total dice
        assert len(result.rolls) == 10

    def test_upcast_crit_doubles_all_dice(self):
        # Base: 1d8 (1 die), upcast +1 level → 1 extra die → total 2 dice
        # On crit: all doubled → 4 dice
        result = upcast_damage("1d8", "1d8", spell_level=1, slot_level=2, critical=True, rng=seeded())
        assert len(result.rolls) == 4  # (1 base × 2 crit) + (1 extra × 2 crit)

    def test_upcast_empty_extra_dice_no_extra(self):
        result = upcast_damage("2d6", "", spell_level=1, slot_level=5, rng=seeded())
        assert len(result.rolls) == 2  # no extra dice

    def test_invalid_slot_level_raises(self):
        with pytest.raises(ValueError, match="slot_level"):
            upcast_damage("2d6", "1d6", spell_level=3, slot_level=2, rng=seeded())

    def test_invalid_extra_notation_raises(self):
        with pytest.raises(ValueError, match="extra_dice_per_level"):
            upcast_damage("2d6", "1d6+3", spell_level=1, slot_level=2, rng=seeded())

    def test_total_non_negative(self):
        # 1d4-10 base → always 0; ensure upcast doesn't go negative
        result = upcast_damage("1d4-10", "1d4", spell_level=1, slot_level=3, rng=seeded())
        assert result.total >= 0
