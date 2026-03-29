"""Tests for engine/character_creation.py"""
from __future__ import annotations

import pytest

from app.engine.ability_checks import Ability
from app.engine.character_creation import (
    POINT_BUY_BUDGET,
    POINT_BUY_COST,
    VALID_CLASSES,
    VALID_SPECIES,
    AbilityScores,
    CharacterBlueprint,
    ClassFeatures,
    SpeciesTraits,
    build_character,
    get_class_features,
    get_species_traits,
    hp_at_level,
    point_buy_cost,
    validate_point_buy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _standard_base() -> AbilityScores:
    """Standard array equivalent: 15, 14, 13, 12, 10, 8 — costs exactly 27 pts."""
    return AbilityScores(
        strength=15,
        dexterity=14,
        constitution=13,
        intelligence=12,
        wisdom=10,
        charisma=8,
    )


def _all_tens() -> AbilityScores:
    """All 10s — costs 2 × 6 = 12 points (under budget)."""
    return AbilityScores(
        strength=10, dexterity=10, constitution=10,
        intelligence=10, wisdom=10, charisma=10,
    )


# ---------------------------------------------------------------------------
# Point buy cost table
# ---------------------------------------------------------------------------


class TestPointBuyCostTable:
    def test_budget_constant(self):
        assert POINT_BUY_BUDGET == 27

    def test_cost_8_is_0(self):
        assert point_buy_cost(8) == 0

    def test_cost_9_is_1(self):
        assert point_buy_cost(9) == 1

    def test_cost_13_is_5(self):
        assert point_buy_cost(13) == 5

    def test_cost_14_is_7(self):
        # Non-linear jump: 13→14 costs 2 extra points
        assert point_buy_cost(14) == 7

    def test_cost_15_is_9(self):
        assert point_buy_cost(15) == 9

    def test_table_has_8_entries(self):
        assert len(POINT_BUY_COST) == 8

    def test_score_7_raises(self):
        with pytest.raises(ValueError, match="8"):
            point_buy_cost(7)

    def test_score_16_raises(self):
        with pytest.raises(ValueError, match="15"):
            point_buy_cost(16)

    def test_score_0_raises(self):
        with pytest.raises(ValueError):
            point_buy_cost(0)


# ---------------------------------------------------------------------------
# validate_point_buy
# ---------------------------------------------------------------------------


class TestValidatePointBuy:
    def test_standard_array_costs_27(self):
        scores = _standard_base().as_dict()
        total = validate_point_buy(scores)
        assert total == 27

    def test_all_eights_costs_0(self):
        scores = {a.value: 8 for a in Ability}
        total = validate_point_buy(scores)
        assert total == 0

    def test_under_budget_is_valid(self):
        # All 10s → 2×6 = 12 points — under budget, still valid
        scores = _all_tens().as_dict()
        total = validate_point_buy(scores)
        assert total == 12

    def test_over_budget_raises(self):
        # All 15s → 9×6 = 54 points
        scores = {a.value: 15 for a in Ability}
        with pytest.raises(ValueError, match="budget"):
            validate_point_buy(scores)

    def test_score_out_of_range_raises(self):
        scores = _standard_base().as_dict()
        scores["strength"] = 16  # valid final score, but not a valid base
        with pytest.raises(ValueError):
            validate_point_buy(scores)

    def test_missing_ability_raises(self):
        scores = {a.value: 10 for a in Ability}
        del scores["charisma"]
        with pytest.raises(ValueError, match="missing"):
            validate_point_buy(scores)

    def test_extra_ability_raises(self):
        scores = {a.value: 10 for a in Ability}
        scores["luck"] = 10
        with pytest.raises(ValueError, match="extra"):
            validate_point_buy(scores)

    def test_case_insensitive_keys(self):
        scores = {a.value.upper(): 10 for a in Ability}
        # Should work — keys are lowered internally
        total = validate_point_buy(scores)
        assert total == 12


# ---------------------------------------------------------------------------
# AbilityScores
# ---------------------------------------------------------------------------


class TestAbilityScores:
    def test_get_returns_correct_score(self):
        s = AbilityScores(strength=16, dexterity=14, constitution=12,
                          intelligence=10, wisdom=8, charisma=13)
        assert s.get(Ability.STR) == 16
        assert s.get(Ability.DEX) == 14
        assert s.get(Ability.CON) == 12
        assert s.get(Ability.INT) == 10
        assert s.get(Ability.WIS) == 8
        assert s.get(Ability.CHA) == 13

    def test_modifier_returns_correct_modifier(self):
        s = AbilityScores(strength=16, dexterity=14, constitution=12,
                          intelligence=10, wisdom=8, charisma=13)
        assert s.modifier(Ability.STR) == 3    # (16-10)//2
        assert s.modifier(Ability.DEX) == 2
        assert s.modifier(Ability.CON) == 1
        assert s.modifier(Ability.INT) == 0
        assert s.modifier(Ability.WIS) == -1
        assert s.modifier(Ability.CHA) == 1

    def test_apply_bonuses_adds_values(self):
        s = AbilityScores(strength=10, dexterity=10, constitution=10,
                          intelligence=10, wisdom=10, charisma=10)
        s2 = s.apply_bonuses({"dexterity": 2, "intelligence": 1})
        assert s2.dexterity == 12
        assert s2.intelligence == 11
        assert s2.strength == 10  # unchanged

    def test_apply_bonuses_caps_at_20(self):
        s = AbilityScores(strength=19, dexterity=10, constitution=10,
                          intelligence=10, wisdom=10, charisma=10)
        s2 = s.apply_bonuses({"strength": 5})
        assert s2.strength == 20  # capped, not 24

    def test_apply_bonuses_returns_new_instance(self):
        s = _all_tens()
        s2 = s.apply_bonuses({"strength": 2})
        assert s.strength == 10  # original unchanged
        assert s2.strength == 12

    def test_apply_bonuses_invalid_ability_raises(self):
        s = _all_tens()
        with pytest.raises(ValueError, match="Unknown ability"):
            s.apply_bonuses({"luck": 2})

    def test_as_dict_has_6_entries(self):
        d = _all_tens().as_dict()
        assert len(d) == 6
        assert all(v == 10 for v in d.values())

    def test_as_dict_keys_match_ability_values(self):
        d = _all_tens().as_dict()
        expected = {a.value for a in Ability}
        assert set(d.keys()) == expected


# ---------------------------------------------------------------------------
# Species traits
# ---------------------------------------------------------------------------


class TestSpeciesTraits:
    def test_all_valid_species_defined(self):
        for species in VALID_SPECIES:
            traits = get_species_traits(species)
            assert isinstance(traits, SpeciesTraits)

    def test_invalid_species_raises(self):
        with pytest.raises(ValueError, match="species"):
            get_species_traits("halfling")

    def test_human_plus_one_all_abilities(self):
        traits = get_species_traits("human")
        for ability in Ability:
            assert traits.ability_bonuses.get(ability.value, 0) == 1

    def test_human_speed_30(self):
        assert get_species_traits("human").speed == 30

    def test_human_no_darkvision(self):
        assert get_species_traits("human").darkvision_ft == 0

    def test_elf_dex_bonus_2(self):
        traits = get_species_traits("elf")
        assert traits.ability_bonuses["dexterity"] == 2

    def test_elf_int_bonus_1(self):
        traits = get_species_traits("elf")
        assert traits.ability_bonuses["intelligence"] == 1

    def test_elf_darkvision_60(self):
        assert get_species_traits("elf").darkvision_ft == 60

    def test_elf_perception_proficiency(self):
        assert "perception" in get_species_traits("elf").skill_proficiencies

    def test_elf_fey_ancestry_in_traits(self):
        assert "Fey Ancestry" in get_species_traits("elf").traits

    def test_elf_speed_30(self):
        assert get_species_traits("elf").speed == 30

    def test_dwarf_con_bonus_2(self):
        traits = get_species_traits("dwarf")
        assert traits.ability_bonuses["constitution"] == 2

    def test_dwarf_str_bonus_2(self):
        traits = get_species_traits("dwarf")
        assert traits.ability_bonuses["strength"] == 2

    def test_dwarf_darkvision_60(self):
        assert get_species_traits("dwarf").darkvision_ft == 60

    def test_dwarf_speed_25(self):
        assert get_species_traits("dwarf").speed == 25

    def test_dwarf_dwarven_resilience(self):
        assert "Dwarven Resilience" in get_species_traits("dwarf").traits

    def test_case_insensitive_lookup(self):
        assert get_species_traits("ELF").name == "Elf"
        assert get_species_traits("Human").name == "Human"

    def test_all_species_have_common_language(self):
        for species in VALID_SPECIES:
            assert "common" in get_species_traits(species).languages

    def test_all_species_medium_size(self):
        for species in VALID_SPECIES:
            assert get_species_traits(species).size == "Medium"


# ---------------------------------------------------------------------------
# Class features
# ---------------------------------------------------------------------------


class TestClassFeatures:
    def test_all_valid_classes_defined(self):
        for cls in VALID_CLASSES:
            features = get_class_features(cls)
            assert isinstance(features, ClassFeatures)

    def test_invalid_class_raises(self):
        with pytest.raises(ValueError, match="class"):
            get_class_features("barbarian")

    def test_fighter_hit_die_10(self):
        assert get_class_features("fighter").hit_die == 10

    def test_fighter_saves_str_con(self):
        saves = get_class_features("fighter").saving_throw_proficiencies
        assert "strength" in saves
        assert "constitution" in saves

    def test_fighter_2_skill_choices(self):
        assert get_class_features("fighter").num_skill_choices == 2

    def test_fighter_no_spellcasting(self):
        f = get_class_features("fighter")
        assert f.spellcasting_ability is None
        assert f.caster_type is None

    def test_fighter_heavy_armor_proficiency(self):
        assert "heavy" in get_class_features("fighter").armor_proficiencies

    def test_fighter_second_wind_feature(self):
        assert "Second Wind" in get_class_features("fighter").level_1_features

    def test_wizard_hit_die_6(self):
        assert get_class_features("wizard").hit_die == 6

    def test_wizard_saves_int_wis(self):
        saves = get_class_features("wizard").saving_throw_proficiencies
        assert "intelligence" in saves
        assert "wisdom" in saves

    def test_wizard_full_caster_int(self):
        w = get_class_features("wizard")
        assert w.spellcasting_ability == "intelligence"
        assert w.caster_type == "full"

    def test_wizard_no_armor_proficiency(self):
        assert get_class_features("wizard").armor_proficiencies == []

    def test_wizard_arcane_recovery_feature(self):
        assert "Arcane Recovery" in get_class_features("wizard").level_1_features

    def test_rogue_hit_die_8(self):
        assert get_class_features("rogue").hit_die == 8

    def test_rogue_4_skill_choices(self):
        assert get_class_features("rogue").num_skill_choices == 4

    def test_rogue_saves_dex_int(self):
        saves = get_class_features("rogue").saving_throw_proficiencies
        assert "dexterity" in saves
        assert "intelligence" in saves

    def test_rogue_sneak_attack_feature(self):
        features = get_class_features("rogue").level_1_features
        assert any("Sneak Attack" in f for f in features)

    def test_rogue_no_spellcasting(self):
        r = get_class_features("rogue")
        assert r.spellcasting_ability is None
        assert r.caster_type is None

    def test_cleric_hit_die_8(self):
        assert get_class_features("cleric").hit_die == 8

    def test_cleric_saves_wis_cha(self):
        saves = get_class_features("cleric").saving_throw_proficiencies
        assert "wisdom" in saves
        assert "charisma" in saves

    def test_cleric_full_caster_wis(self):
        c = get_class_features("cleric")
        assert c.spellcasting_ability == "wisdom"
        assert c.caster_type == "full"

    def test_cleric_divine_domain_feature(self):
        assert "Divine Domain" in get_class_features("cleric").level_1_features

    def test_case_insensitive_lookup(self):
        assert get_class_features("FIGHTER").name == "Fighter"
        assert get_class_features("Wizard").name == "Wizard"


# ---------------------------------------------------------------------------
# HP at level
# ---------------------------------------------------------------------------


class TestHpAtLevel:
    def test_fighter_level_1_con14(self):
        # d10 + 2 = 12
        assert hp_at_level("fighter", con_score=14, level=1) == 12

    def test_fighter_level_2_con14(self):
        # Level 1: 10+2=12 | Level 2: +(5+1+2)=8 → 12+8=20
        # avg per level for d10 = 10//2+1 = 6
        # 12 + (6 + 2) = 20
        assert hp_at_level("fighter", con_score=14, level=2) == 20

    def test_wizard_level_1_con10(self):
        # d6 + 0 = 6
        assert hp_at_level("wizard", con_score=10, level=1) == 6

    def test_wizard_level_1_con16(self):
        # d6 + 3 = 9
        assert hp_at_level("wizard", con_score=16, level=1) == 9

    def test_rogue_level_1_con10(self):
        # d8 + 0 = 8
        assert hp_at_level("rogue", con_score=10, level=1) == 8

    def test_cleric_level_1_con12(self):
        # d8 + 1 = 9
        assert hp_at_level("cleric", con_score=12, level=1) == 9

    def test_minimum_hp_is_1(self):
        # d6 + (-5) = 1 (CON 1 → mod -5)
        hp = hp_at_level("wizard", con_score=1, level=1)
        assert hp == 1

    def test_level_0_raises(self):
        with pytest.raises(ValueError, match="Level"):
            hp_at_level("fighter", con_score=10, level=0)

    def test_level_21_raises(self):
        with pytest.raises(ValueError, match="Level"):
            hp_at_level("fighter", con_score=10, level=21)

    def test_level_20_fighter_reasonable_hp(self):
        # Fighter d10, CON 20 (+5): 10+5 + 19*(6+5) = 15 + 209 = 224
        hp = hp_at_level("fighter", con_score=20, level=20)
        assert hp > 100  # obviously more than 100 at level 20 with good CON

    def test_higher_level_more_hp(self):
        hp1 = hp_at_level("rogue", con_score=12, level=1)
        hp5 = hp_at_level("rogue", con_score=12, level=5)
        assert hp5 > hp1

    def test_d10_average_per_level(self):
        # d10 // 2 + 1 = 6; level 3 fighter CON 10:
        # L1: 10+0=10 | L2: +(6+0)=6 | L3: +(6+0)=6 → total 22
        assert hp_at_level("fighter", con_score=10, level=3) == 22


# ---------------------------------------------------------------------------
# Build character
# ---------------------------------------------------------------------------


class TestBuildCharacter:
    def test_returns_blueprint_instance(self):
        char = build_character("Aric", "human", "fighter", _standard_base())
        assert isinstance(char, CharacterBlueprint)

    def test_name_and_class_stored(self):
        char = build_character("Lyra", "elf", "wizard", _standard_base())
        assert char.name == "Lyra"
        assert char.character_class == "wizard"
        assert char.species == "elf"

    def test_species_bonuses_applied_to_final_scores(self):
        # Elf: +2 DEX, +1 INT
        base = AbilityScores(strength=10, dexterity=14, constitution=10,
                             intelligence=12, wisdom=10, charisma=8)
        char = build_character("Sylvan", "elf", "wizard", base,
                               validate_scores=False)
        assert char.final_scores.dexterity == 16  # 14 + 2
        assert char.final_scores.intelligence == 13  # 12 + 1
        assert char.final_scores.strength == 10  # unchanged

    def test_base_scores_unchanged(self):
        base = _standard_base()
        char = build_character("Human", "human", "fighter", base)
        # base_scores should still be the original values
        assert char.base_scores.strength == 15
        assert char.base_scores.charisma == 8

    def test_proficiency_bonus_is_2_at_level_1(self):
        char = build_character("Test", "dwarf", "cleric", _standard_base())
        assert char.proficiency_bonus == 2

    def test_level_stored(self):
        char = build_character("Hero", "human", "fighter", _standard_base(), level=3)
        assert char.level == 3

    def test_max_hp_uses_final_con(self):
        # Dwarf: +2 CON. Base CON=13 (mod+1), final CON=15 (mod+2)
        # Cleric d8: 8 + 2 = 10
        base = AbilityScores(strength=15, dexterity=10, constitution=13,
                             intelligence=10, wisdom=14, charisma=8)
        char = build_character("Thordak", "dwarf", "cleric", base)
        assert char.max_hp == 10  # d8 + CON mod +2

    def test_validate_scores_catches_over_budget(self):
        over_budget = AbilityScores(
            strength=15, dexterity=15, constitution=15,
            intelligence=15, wisdom=15, charisma=15,
        )
        with pytest.raises(ValueError, match="budget"):
            build_character("Cheater", "human", "fighter", over_budget,
                            validate_scores=True)

    def test_validate_scores_false_skips_budget_check(self):
        over_budget = AbilityScores(
            strength=15, dexterity=15, constitution=15,
            intelligence=15, wisdom=15, charisma=15,
        )
        # Should not raise
        char = build_character("Powerful", "human", "fighter", over_budget,
                               validate_scores=False)
        assert char is not None

    def test_species_traits_attached(self):
        char = build_character("Gimli", "dwarf", "fighter", _standard_base())
        assert char.species_traits.name == "Dwarf"
        assert char.species_traits.darkvision_ft == 60

    def test_class_features_attached(self):
        char = build_character("Legolas", "elf", "rogue", _standard_base())
        assert char.class_features.name == "Rogue"
        assert char.class_features.num_skill_choices == 4

    def test_elf_perception_in_species_proficiencies(self):
        char = build_character("Aria", "elf", "wizard", _standard_base())
        assert "perception" in char.species_traits.skill_proficiencies

    def test_all_species_and_classes_combinable(self):
        for species in VALID_SPECIES:
            for cls in VALID_CLASSES:
                char = build_character("Test", species, cls, _all_tens(),
                                       validate_scores=False)
                assert char.max_hp >= 1
