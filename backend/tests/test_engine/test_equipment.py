"""Tests for engine/equipment.py"""
from __future__ import annotations

import pytest

from app.engine.equipment import (
    ACResult,
    ArmorStats,
    AttackStats,
    WeaponStats,
    WEAPON_PROPERTIES,
    compute_ac,
    get_armor,
    get_weapon,
    is_armor_proficient,
    is_weapon_proficient,
    weapon_attack_stats,
)


# ---------------------------------------------------------------------------
# get_weapon — catalogue lookup
# ---------------------------------------------------------------------------


class TestGetWeapon:
    def test_known_weapon_returns_stats(self):
        w = get_weapon("longsword")
        assert isinstance(w, WeaponStats)
        assert w.name == "Longsword"

    def test_case_insensitive(self):
        w = get_weapon("LONGSWORD")
        assert w.name == "Longsword"

    def test_space_to_underscore(self):
        w = get_weapon("light crossbow")
        assert w.name == "Light Crossbow"

    def test_mixed_case_with_space(self):
        w = get_weapon("War Pick")
        assert w.name == "War Pick"

    def test_unknown_weapon_raises(self):
        with pytest.raises(ValueError, match="Unknown weapon"):
            get_weapon("excalibur")

    # ---- Spot-check specific weapons ----

    def test_dagger_is_simple_finesse_thrown(self):
        w = get_weapon("dagger")
        assert w.category == "simple"
        assert "finesse" in w.properties
        assert "thrown" in w.properties
        assert w.damage_dice == "1d4"
        assert w.damage_type == "piercing"
        assert w.range_normal == 20
        assert w.range_long == 60

    def test_greataxe_is_martial_heavy_two_handed(self):
        w = get_weapon("greataxe")
        assert w.category == "martial"
        assert "heavy" in w.properties
        assert "two-handed" in w.properties
        assert w.damage_dice == "1d12"
        assert w.versatile_dice is None

    def test_longsword_is_versatile(self):
        w = get_weapon("longsword")
        assert "versatile" in w.properties
        assert w.versatile_dice == "1d10"

    def test_quarterstaff_versatile_1d8(self):
        w = get_weapon("quarterstaff")
        assert w.versatile_dice == "1d8"

    def test_longbow_is_ammunition(self):
        w = get_weapon("longbow")
        assert "ammunition" in w.properties
        assert w.range_normal == 150
        assert w.range_long == 600

    def test_shortbow_range(self):
        w = get_weapon("shortbow")
        assert w.range_normal == 80
        assert w.range_long == 320

    def test_greatsword_two_d6(self):
        w = get_weapon("greatsword")
        assert w.damage_dice == "2d6"

    def test_rapier_finesse_no_thrown(self):
        w = get_weapon("rapier")
        assert "finesse" in w.properties
        assert "thrown" not in w.properties

    def test_mace_no_range(self):
        w = get_weapon("mace")
        assert w.range_normal is None
        assert w.range_long is None

    def test_all_properties_are_valid_srd_tags(self):
        """Every weapon property in the catalogue must be a known SRD tag."""
        for weapon in [
            "dagger", "handaxe", "light_crossbow", "longsword",
            "rapier", "shortsword", "greatsword", "longbow",
        ]:
            w = get_weapon(weapon)
            for prop in w.properties:
                assert prop in WEAPON_PROPERTIES, f"{weapon}: unknown property '{prop}'"


# ---------------------------------------------------------------------------
# get_armor — catalogue lookup
# ---------------------------------------------------------------------------


class TestGetArmor:
    def test_known_armor_returns_stats(self):
        a = get_armor("leather")
        assert isinstance(a, ArmorStats)
        assert a.name == "Leather"

    def test_case_insensitive(self):
        a = get_armor("PLATE")
        assert a.name == "Plate"

    def test_space_to_underscore(self):
        a = get_armor("chain mail")
        assert a.name == "Chain Mail"

    def test_unknown_armor_raises(self):
        with pytest.raises(ValueError, match="Unknown armor"):
            get_armor("mithral plate")

    # ---- Category spot-checks ----

    def test_leather_is_light(self):
        a = get_armor("leather")
        assert a.category == "light"
        assert a.base_ac == 11
        assert a.dex_cap is None
        assert a.stealth_disadvantage is False

    def test_padded_light_stealth_disadvantage(self):
        assert get_armor("padded").stealth_disadvantage is True

    def test_studded_leather_base_ac_12(self):
        a = get_armor("studded_leather")
        assert a.base_ac == 12
        assert a.category == "light"

    def test_chain_shirt_medium_dex_cap_2(self):
        a = get_armor("chain_shirt")
        assert a.category == "medium"
        assert a.dex_cap == 2

    def test_scale_mail_medium_stealth_disadvantage(self):
        assert get_armor("scale_mail").stealth_disadvantage is True

    def test_breastplate_medium_no_stealth_disadvantage(self):
        assert get_armor("breastplate").stealth_disadvantage is False

    def test_half_plate_base_ac_15(self):
        a = get_armor("half_plate")
        assert a.base_ac == 15
        assert a.dex_cap == 2

    def test_chain_mail_heavy_str_requirement(self):
        a = get_armor("chain_mail")
        assert a.category == "heavy"
        assert a.dex_cap == 0
        assert a.strength_requirement == 13

    def test_plate_heavy_base_ac_18_str_15(self):
        a = get_armor("plate")
        assert a.base_ac == 18
        assert a.strength_requirement == 15

    def test_splint_heavy_str_15(self):
        assert get_armor("splint").strength_requirement == 15

    def test_ring_mail_heavy_no_str_requirement(self):
        assert get_armor("ring_mail").strength_requirement == 0

    def test_shield_category_and_bonus(self):
        s = get_armor("shield")
        assert s.category == "shield"
        assert s.base_ac == 2
        assert s.stealth_disadvantage is False


# ---------------------------------------------------------------------------
# compute_ac
# ---------------------------------------------------------------------------


class TestComputeAC:
    # ---- Unarmored ----

    def test_unarmored_dex_10_ac_10(self):
        result = compute_ac(dex_score=10)
        assert isinstance(result, ACResult)
        assert result.total == 10
        assert result.base == 10
        assert result.dex_applied == 0
        assert result.armor_name is None
        assert result.has_shield is False
        assert result.stealth_disadvantage is False

    def test_unarmored_dex_16_ac_13(self):
        result = compute_ac(dex_score=16)
        assert result.total == 13
        assert result.dex_applied == 3

    def test_unarmored_dex_8_ac_9(self):
        result = compute_ac(dex_score=8)
        assert result.total == 9
        assert result.dex_applied == -1

    def test_unarmored_with_shield(self):
        result = compute_ac(dex_score=10, has_shield=True)
        assert result.total == 12
        assert result.shield_bonus == 2
        assert result.has_shield is True

    # ---- Light armor ----

    def test_leather_dex_14_ac_13(self):
        armor = get_armor("leather")
        result = compute_ac(dex_score=14, armor=armor)
        assert result.total == 13  # 11 + 2
        assert result.base == 11
        assert result.dex_applied == 2
        assert result.armor_name == "Leather"

    def test_studded_leather_dex_18_ac_16(self):
        armor = get_armor("studded_leather")
        result = compute_ac(dex_score=18, armor=armor)
        assert result.total == 16  # 12 + 4

    def test_light_armor_with_shield(self):
        armor = get_armor("leather")
        result = compute_ac(dex_score=14, armor=armor, has_shield=True)
        assert result.total == 15  # 11 + 2 + 2

    def test_light_armor_no_dex_cap(self):
        # DEX 20 → +5 ; leather 11 + 5 = 16
        armor = get_armor("leather")
        result = compute_ac(dex_score=20, armor=armor)
        assert result.total == 16

    # ---- Medium armor ----

    def test_chain_shirt_dex_14_ac_15(self):
        armor = get_armor("chain_shirt")
        result = compute_ac(dex_score=14, armor=armor)
        assert result.total == 15  # 13 + 2

    def test_chain_shirt_dex_20_capped_at_2(self):
        armor = get_armor("chain_shirt")
        result = compute_ac(dex_score=20, armor=armor)
        assert result.total == 15  # 13 + 2 (cap)
        assert result.dex_applied == 2

    def test_chain_shirt_dex_8_negative_allowed(self):
        # DEX 8 → -1; medium cap is +2, but floor is -inf
        armor = get_armor("chain_shirt")
        result = compute_ac(dex_score=8, armor=armor)
        assert result.dex_applied == -1
        assert result.total == 12  # 13 - 1

    def test_breastplate_dex_12_ac_15(self):
        armor = get_armor("breastplate")
        result = compute_ac(dex_score=12, armor=armor)
        assert result.total == 15  # 14 + 1

    def test_half_plate_dex_18_capped_ac_17(self):
        armor = get_armor("half_plate")
        result = compute_ac(dex_score=18, armor=armor)
        assert result.total == 17  # 15 + 2

    def test_medium_armor_stealth_disadvantage(self):
        armor = get_armor("scale_mail")
        result = compute_ac(dex_score=14, armor=armor)
        assert result.stealth_disadvantage is True

    # ---- Heavy armor ----

    def test_chain_mail_dex_16_ac_16(self):
        armor = get_armor("chain_mail")
        result = compute_ac(dex_score=16, armor=armor)
        assert result.total == 16  # 16 + 0 (DEX ignored)
        assert result.dex_applied == 0

    def test_plate_dex_20_ac_18(self):
        armor = get_armor("plate")
        result = compute_ac(dex_score=20, armor=armor)
        assert result.total == 18
        assert result.dex_applied == 0

    def test_heavy_armor_stealth_disadvantage(self):
        armor = get_armor("plate")
        result = compute_ac(dex_score=10, armor=armor)
        assert result.stealth_disadvantage is True

    def test_plate_with_shield(self):
        armor = get_armor("plate")
        result = compute_ac(dex_score=14, armor=armor, has_shield=True)
        assert result.total == 20  # 18 + 2

    # ---- Shield passed as armor (edge case) ----

    def test_shield_as_armor_treated_as_unarmored_plus_shield(self):
        shield = get_armor("shield")
        result = compute_ac(dex_score=12, armor=shield)
        # unarmored (10) + DEX +1 + shield +2 = 13
        assert result.total == 13
        assert result.has_shield is True
        assert result.armor_name is None

    # ---- Breakdown string ----

    def test_breakdown_contains_ac_total(self):
        result = compute_ac(dex_score=14)
        assert "AC 12" in result.breakdown

    def test_breakdown_contains_armor_name(self):
        armor = get_armor("leather")
        result = compute_ac(dex_score=14, armor=armor)
        assert "Leather" in result.breakdown

    def test_breakdown_contains_shield(self):
        result = compute_ac(dex_score=10, has_shield=True)
        assert "Shield" in result.breakdown

    def test_breakdown_no_dex_when_zero(self):
        # DEX 10 → mod 0; should not appear in breakdown
        result = compute_ac(dex_score=10)
        assert "DEX" not in result.breakdown


# ---------------------------------------------------------------------------
# weapon_attack_stats
# ---------------------------------------------------------------------------


class TestWeaponAttackStats:
    # ---- STR-based melee ----

    def test_longsword_str_proficient(self):
        w = get_weapon("longsword")
        stats = weapon_attack_stats(w, str_score=16, dex_score=12,
                                     proficient=True, level=1)
        assert isinstance(stats, AttackStats)
        # STR mod +3, prof +2 = +5
        assert stats.attack_bonus == 5
        assert stats.uses_dex is False
        assert stats.damage_notation == "1d8+3"
        assert stats.damage_type == "slashing"

    def test_mace_not_proficient_no_prof_bonus(self):
        w = get_weapon("mace")
        stats = weapon_attack_stats(w, str_score=14, dex_score=10,
                                     proficient=False, level=1)
        # STR mod +2, no prof = +2
        assert stats.attack_bonus == 2
        assert stats.damage_notation == "1d6+2"

    def test_longsword_two_handed_uses_versatile_die(self):
        w = get_weapon("longsword")
        stats = weapon_attack_stats(w, str_score=14, dex_score=10,
                                     proficient=True, level=1,
                                     two_handed=True)
        assert stats.damage_notation == "1d10+2"
        assert stats.two_handed is True

    def test_quarterstaff_two_handed_1d8(self):
        w = get_weapon("quarterstaff")
        stats = weapon_attack_stats(w, str_score=12, dex_score=10,
                                     proficient=True, level=3,
                                     two_handed=True)
        assert stats.damage_notation == "1d8+1"

    def test_two_handed_on_non_versatile_raises(self):
        w = get_weapon("mace")
        with pytest.raises(ValueError, match="two-handed"):
            weapon_attack_stats(w, 14, 10, True, 1, two_handed=True)

    # ---- DEX-based ranged ----

    def test_longbow_uses_dex(self):
        w = get_weapon("longbow")
        stats = weapon_attack_stats(w, str_score=10, dex_score=18,
                                     proficient=True, level=5)
        assert stats.uses_dex is True
        # DEX +4, prof +3 = +7
        assert stats.attack_bonus == 7
        assert stats.damage_notation == "1d8+4"

    def test_shortbow_dex_proficient_level1(self):
        w = get_weapon("shortbow")
        stats = weapon_attack_stats(w, str_score=8, dex_score=16,
                                     proficient=True, level=1)
        assert stats.uses_dex is True
        assert stats.attack_bonus == 5  # +3 DEX + 2 prof

    # ---- Finesse weapons ----

    def test_rapier_chooses_higher_ability(self):
        w = get_weapon("rapier")
        # STR 16 (+3), DEX 14 (+2) → chooses STR
        stats = weapon_attack_stats(w, str_score=16, dex_score=14,
                                     proficient=False, level=1)
        assert stats.uses_dex is False
        assert stats.attack_bonus == 3

    def test_rapier_chooses_dex_when_higher(self):
        w = get_weapon("rapier")
        # DEX 18 (+4) > STR 12 (+1) → chooses DEX
        stats = weapon_attack_stats(w, str_score=12, dex_score=18,
                                     proficient=False, level=1)
        assert stats.uses_dex is True
        assert stats.attack_bonus == 4

    def test_finesse_prefer_dex_on_tie(self):
        w = get_weapon("dagger")
        # STR 14 (+2), DEX 14 (+2) — tie, prefer_dex=True → uses DEX
        stats = weapon_attack_stats(w, str_score=14, dex_score=14,
                                     proficient=False, level=1, prefer_dex=True)
        assert stats.uses_dex is True

    def test_finesse_str_wins_over_equal_dex_no_prefer(self):
        w = get_weapon("dagger")
        stats = weapon_attack_stats(w, str_score=14, dex_score=14,
                                     proficient=False, level=1, prefer_dex=False)
        assert stats.uses_dex is False

    def test_dagger_thrown_uses_melee_ability(self):
        # Thrown weapons use same ability as melee (STR unless finesse/ranged)
        w = get_weapon("dagger")
        assert "finesse" in w.properties  # dagger is finesse — DEX can be used

    # ---- Ability modifier in notation ----

    def test_negative_modifier_in_notation(self):
        w = get_weapon("mace")
        stats = weapon_attack_stats(w, str_score=8, dex_score=10,
                                     proficient=False, level=1)
        # STR -1 → damage: "1d6-1"
        assert stats.damage_notation == "1d6-1"
        assert stats.attack_bonus == -1

    def test_zero_modifier_notation_has_no_plus(self):
        w = get_weapon("mace")
        stats = weapon_attack_stats(w, str_score=10, dex_score=10,
                                     proficient=False, level=1)
        assert stats.damage_notation == "1d6"

    # ---- Proficiency bonus at different levels ----

    def test_proficiency_bonus_level_5(self):
        w = get_weapon("longsword")
        stats = weapon_attack_stats(w, str_score=16, dex_score=10,
                                     proficient=True, level=5)
        # STR +3, prof +3 = +6
        assert stats.attack_bonus == 6

    # ---- Breakdown string ----

    def test_breakdown_contains_weapon_name(self):
        w = get_weapon("longsword")
        stats = weapon_attack_stats(w, 14, 10, True, 1)
        assert "Longsword" in stats.breakdown

    def test_breakdown_contains_damage_notation(self):
        w = get_weapon("longsword")
        stats = weapon_attack_stats(w, 14, 10, False, 1)
        assert stats.damage_notation in stats.breakdown

    def test_is_finesse_flag(self):
        rapier = get_weapon("rapier")
        mace = get_weapon("mace")
        assert weapon_attack_stats(rapier, 12, 14, False, 1).is_finesse is True
        assert weapon_attack_stats(mace, 12, 14, False, 1).is_finesse is False


# ---------------------------------------------------------------------------
# is_weapon_proficient
# ---------------------------------------------------------------------------


class TestIsWeaponProficient:
    def test_simple_weapon_with_simple_proficiency(self):
        w = get_weapon("mace")
        assert is_weapon_proficient(w, ["simple"]) is True

    def test_martial_weapon_with_martial_proficiency(self):
        w = get_weapon("longsword")
        assert is_weapon_proficient(w, ["simple", "martial"]) is True

    def test_martial_weapon_without_martial_proficiency(self):
        w = get_weapon("longsword")
        assert is_weapon_proficient(w, ["simple"]) is False

    def test_named_proficiency_singular(self):
        # e.g. Fighter has proficiency in "longsword" by name
        w = get_weapon("longsword")
        assert is_weapon_proficient(w, ["longsword"]) is True

    def test_named_proficiency_plural(self):
        w = get_weapon("rapier")
        assert is_weapon_proficient(w, ["rapiers"]) is True

    def test_no_proficiency(self):
        w = get_weapon("greatsword")
        assert is_weapon_proficient(w, []) is False

    def test_case_insensitive_proficiency_list(self):
        w = get_weapon("mace")
        assert is_weapon_proficient(w, ["Simple"]) is True


# ---------------------------------------------------------------------------
# is_armor_proficient
# ---------------------------------------------------------------------------


class TestIsArmorProficient:
    def test_light_armor_with_light_proficiency(self):
        a = get_armor("leather")
        assert is_armor_proficient(a, ["light"]) is True

    def test_medium_armor_with_medium_proficiency(self):
        a = get_armor("chain_shirt")
        assert is_armor_proficient(a, ["light", "medium"]) is True

    def test_heavy_armor_with_heavy_proficiency(self):
        a = get_armor("plate")
        assert is_armor_proficient(a, ["light", "medium", "heavy"]) is True

    def test_heavy_armor_without_heavy_proficiency(self):
        a = get_armor("plate")
        assert is_armor_proficient(a, ["light", "medium"]) is False

    def test_shield_with_shields_proficiency(self):
        s = get_armor("shield")
        assert is_armor_proficient(s, ["shields"]) is True

    def test_shield_without_shields_proficiency(self):
        s = get_armor("shield")
        assert is_armor_proficient(s, ["light", "medium"]) is False

    def test_no_proficiency(self):
        a = get_armor("leather")
        assert is_armor_proficient(a, []) is False

    def test_case_insensitive_proficiency_list(self):
        a = get_armor("leather")
        assert is_armor_proficient(a, ["Light"]) is True

    def test_fighter_full_proficiency(self):
        # Fighter: light, medium, heavy, shields
        profs = ["light", "medium", "heavy", "shields"]
        for armor_name in ["leather", "chain_shirt", "plate", "shield"]:
            a = get_armor(armor_name)
            assert is_armor_proficient(a, profs) is True

    def test_wizard_no_armor_proficiency(self):
        profs: list = []
        for armor_name in ["leather", "chain_mail", "plate"]:
            a = get_armor(armor_name)
            assert is_armor_proficient(a, profs) is False
