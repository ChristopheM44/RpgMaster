"""Tests for engine/conditions.py"""
from __future__ import annotations

import pytest

from app.engine.conditions import (
    Condition,
    ConditionEffects,
    ExhaustionEffects,
    CONDITION_EFFECTS,
    auto_crits_on_melee,
    auto_fails_dex_save,
    auto_fails_str_save,
    breaks_concentration,
    can_take_actions,
    can_take_bonus_actions,
    can_take_reactions,
    effective_speed,
    exhaustion_effects,
    get_effects,
    has_attack_advantage,
    has_attack_disadvantage,
    is_attacked_with_advantage,
    is_attacked_with_disadvantage,
    resolve_attack_advantage,
    resolve_attack_advantage_vs,
)


# ---------------------------------------------------------------------------
# Condition enum
# ---------------------------------------------------------------------------


class TestConditionEnum:
    def test_all_14_conditions_present(self):
        names = {c.value for c in Condition}
        expected = {
            "blinded", "charmed", "deafened", "frightened", "grappled",
            "incapacitated", "invisible", "paralyzed", "petrified",
            "poisoned", "prone", "restrained", "stunned", "unconscious",
        }
        assert names == expected

    def test_condition_effects_table_has_all_conditions(self):
        for cond in Condition:
            assert cond in CONDITION_EFFECTS, f"Missing: {cond}"


# ---------------------------------------------------------------------------
# get_effects
# ---------------------------------------------------------------------------


class TestGetEffects:
    def test_blinded_gives_attack_disadvantage(self):
        fx = get_effects(Condition.BLINDED)
        assert fx.attack_disadvantage is True

    def test_blinded_attacked_with_advantage(self):
        fx = get_effects(Condition.BLINDED)
        assert fx.attacked_advantage is True

    def test_invisible_gives_attack_advantage(self):
        fx = get_effects(Condition.INVISIBLE)
        assert fx.attack_advantage is True

    def test_invisible_attacked_with_disadvantage(self):
        fx = get_effects(Condition.INVISIBLE)
        assert fx.attacked_disadvantage is True

    def test_paralyzed_auto_crit_melee(self):
        fx = get_effects(Condition.PARALYZED)
        assert fx.auto_crit_melee is True

    def test_paralyzed_fail_str_dex_saves(self):
        fx = get_effects(Condition.PARALYZED)
        assert fx.fail_str_saves is True
        assert fx.fail_dex_saves is True

    def test_paralyzed_no_actions(self):
        fx = get_effects(Condition.PARALYZED)
        assert fx.no_actions is True
        assert fx.no_reactions is True
        assert fx.no_bonus_actions is True

    def test_grappled_speed_zero(self):
        fx = get_effects(Condition.GRAPPLED)
        assert fx.speed_zero is True
        assert fx.no_actions is False  # grappled doesn't prevent actions

    def test_unconscious_breaks_concentration(self):
        fx = get_effects(Condition.UNCONSCIOUS)
        assert fx.breaks_concentration is True

    def test_prone_melee_advantage_ranged_disadvantage(self):
        fx = get_effects(Condition.PRONE)
        assert fx.melee_attacked_advantage is True
        assert fx.ranged_attacked_disadvantage is True
        assert fx.attacked_advantage is False  # NOT all attacks, only melee

    def test_prone_attack_disadvantage(self):
        fx = get_effects(Condition.PRONE)
        assert fx.attack_disadvantage is True

    def test_incapacitated_blocks_all_actions(self):
        fx = get_effects(Condition.INCAPACITATED)
        assert fx.no_actions is True
        assert fx.no_reactions is True
        assert fx.no_bonus_actions is True

    def test_stunned_blocks_all_actions_and_saves(self):
        fx = get_effects(Condition.STUNNED)
        assert fx.no_actions is True
        assert fx.fail_str_saves is True
        assert fx.fail_dex_saves is True
        assert fx.attacked_advantage is True


# ---------------------------------------------------------------------------
# Attack roll advantage helpers
# ---------------------------------------------------------------------------


class TestAttackAdvantageHelpers:
    def test_invisible_attacker_has_advantage(self):
        assert has_attack_advantage({Condition.INVISIBLE}) is True

    def test_blinded_attacker_has_disadvantage(self):
        assert has_attack_disadvantage({Condition.BLINDED}) is True

    def test_no_conditions_no_modifiers(self):
        assert has_attack_advantage(set()) is False
        assert has_attack_disadvantage(set()) is False

    def test_both_adv_and_disadv_cancel_out(self):
        # Invisible (adv) + Blinded (disadv) → normal
        result = resolve_attack_advantage({Condition.INVISIBLE, Condition.BLINDED})
        assert result is None

    def test_only_advantage(self):
        result = resolve_attack_advantage({Condition.INVISIBLE})
        assert result is True

    def test_only_disadvantage(self):
        result = resolve_attack_advantage({Condition.BLINDED})
        assert result is False

    def test_no_conditions_normal_roll(self):
        result = resolve_attack_advantage(set())
        assert result is None


# ---------------------------------------------------------------------------
# Attacked advantage/disadvantage helpers
# ---------------------------------------------------------------------------


class TestAttackedAdvantageHelpers:
    def test_blinded_target_attacked_with_advantage(self):
        assert is_attacked_with_advantage({Condition.BLINDED}) is True

    def test_invisible_target_attacked_with_disadvantage(self):
        assert is_attacked_with_disadvantage({Condition.INVISIBLE}) is True

    def test_prone_melee_advantage(self):
        assert is_attacked_with_advantage({Condition.PRONE}, ranged=False) is True

    def test_prone_ranged_no_advantage(self):
        assert is_attacked_with_advantage({Condition.PRONE}, ranged=True) is False

    def test_prone_ranged_disadvantage(self):
        assert is_attacked_with_disadvantage({Condition.PRONE}, ranged=True) is True

    def test_prone_melee_no_disadvantage(self):
        assert is_attacked_with_disadvantage({Condition.PRONE}, ranged=False) is False

    def test_paralyzed_melee_crit(self):
        assert auto_crits_on_melee({Condition.PARALYZED}) is True

    def test_unconscious_melee_crit(self):
        assert auto_crits_on_melee({Condition.UNCONSCIOUS}) is True

    def test_blinded_no_melee_crit(self):
        assert auto_crits_on_melee({Condition.BLINDED}) is False

    def test_resolve_vs_paralyzed_advantage(self):
        result = resolve_attack_advantage_vs({Condition.PARALYZED})
        assert result is True

    def test_resolve_vs_invisible_disadvantage(self):
        result = resolve_attack_advantage_vs({Condition.INVISIBLE})
        assert result is False


# ---------------------------------------------------------------------------
# Saving throw auto-fail helpers
# ---------------------------------------------------------------------------


class TestAutoFailSaves:
    def test_paralyzed_fails_str_and_dex(self):
        conds = {Condition.PARALYZED}
        assert auto_fails_str_save(conds) is True
        assert auto_fails_dex_save(conds) is True

    def test_stunned_fails_str_and_dex(self):
        conds = {Condition.STUNNED}
        assert auto_fails_str_save(conds) is True
        assert auto_fails_dex_save(conds) is True

    def test_blinded_does_not_auto_fail_saves(self):
        conds = {Condition.BLINDED}
        assert auto_fails_str_save(conds) is False
        assert auto_fails_dex_save(conds) is False


# ---------------------------------------------------------------------------
# Action restriction helpers
# ---------------------------------------------------------------------------


class TestActionRestrictions:
    def test_incapacitated_blocks_everything(self):
        conds = {Condition.INCAPACITATED}
        assert can_take_actions(conds) is False
        assert can_take_reactions(conds) is False
        assert can_take_bonus_actions(conds) is False

    def test_grappled_does_not_block_actions(self):
        conds = {Condition.GRAPPLED}
        assert can_take_actions(conds) is True
        assert can_take_reactions(conds) is True

    def test_no_conditions_full_actions(self):
        assert can_take_actions(set()) is True
        assert can_take_reactions(set()) is True
        assert can_take_bonus_actions(set()) is True


# ---------------------------------------------------------------------------
# Concentration break helper
# ---------------------------------------------------------------------------


class TestBreaksConcentration:
    def test_unconscious_breaks_concentration(self):
        assert breaks_concentration({Condition.UNCONSCIOUS}) is True

    def test_blinded_does_not_break_concentration(self):
        assert breaks_concentration({Condition.BLINDED}) is False

    def test_no_conditions(self):
        assert breaks_concentration(set()) is False


# ---------------------------------------------------------------------------
# Exhaustion
# ---------------------------------------------------------------------------


class TestExhaustion:
    def test_level_0_no_effects(self):
        fx = exhaustion_effects(0)
        assert isinstance(fx, ExhaustionEffects)
        assert fx.ability_check_disadvantage is False
        assert fx.speed_halved is False
        assert fx.attack_and_save_disadvantage is False
        assert fx.max_hp_halved is False
        assert fx.speed_zero is False

    def test_level_1_ability_check_disadvantage(self):
        fx = exhaustion_effects(1)
        assert fx.ability_check_disadvantage is True
        assert fx.speed_halved is False

    def test_level_2_speed_halved(self):
        fx = exhaustion_effects(2)
        assert fx.ability_check_disadvantage is True
        assert fx.speed_halved is True
        assert fx.attack_and_save_disadvantage is False

    def test_level_3_attack_save_disadvantage(self):
        fx = exhaustion_effects(3)
        assert fx.attack_and_save_disadvantage is True

    def test_level_4_max_hp_halved(self):
        fx = exhaustion_effects(4)
        assert fx.max_hp_halved is True

    def test_level_5_speed_zero(self):
        fx = exhaustion_effects(5)
        assert fx.speed_zero is True

    def test_level_6_all_effects(self):
        fx = exhaustion_effects(6)
        assert fx.ability_check_disadvantage is True
        assert fx.speed_halved is True
        assert fx.attack_and_save_disadvantage is True
        assert fx.max_hp_halved is True
        assert fx.speed_zero is True

    def test_invalid_level(self):
        with pytest.raises(ValueError):
            exhaustion_effects(-1)
        with pytest.raises(ValueError):
            exhaustion_effects(7)


# ---------------------------------------------------------------------------
# effective_speed
# ---------------------------------------------------------------------------


class TestEffectiveSpeed:
    def test_no_conditions_full_speed(self):
        assert effective_speed(30, set()) == 30

    def test_grappled_speed_zero(self):
        assert effective_speed(30, {Condition.GRAPPLED}) == 0

    def test_exhaustion_2_halves_speed(self):
        assert effective_speed(30, set(), exhaustion_level=2) == 15

    def test_exhaustion_5_speed_zero(self):
        assert effective_speed(30, set(), exhaustion_level=5) == 0

    def test_condition_overrides_exhaustion_halved(self):
        # Grappled wins over exhaustion 2 halving
        assert effective_speed(30, {Condition.GRAPPLED}, exhaustion_level=2) == 0

    def test_exhaustion_2_odd_speed_floors(self):
        assert effective_speed(35, set(), exhaustion_level=2) == 17  # 35 // 2
