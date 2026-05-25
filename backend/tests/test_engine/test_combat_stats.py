from __future__ import annotations

from app.game.combat_stats import build_combatant_combat_stats


def _character_with_weapon(weapon: dict, **overrides) -> dict:
    data = {
        "name": "Shade",
        "char_class": "rogue",
        "level": 1,
        "ability_scores": {"str": 8, "dex": 16},
        "equipment": [
            {
                **weapon,
                "equipped": True,
                "occupied_slots": weapon.get("occupied_slots", ["main_hand"]),
            }
        ],
    }
    data.update(overrides)
    return data


def test_shortbow_uses_catalogue_range() -> None:
    stats = build_combatant_combat_stats(_character_with_weapon({"id": "shortbow"}))

    assert stats["attack_bonus"] == 5
    assert stats["damage_notation"] == "1d6+3"
    assert stats["reach_m"] == 1.5
    assert stats["attack_range_m"] == 24.0


def test_longbow_uses_catalogue_range() -> None:
    stats = build_combatant_combat_stats(
        _character_with_weapon(
            {"id": "longbow"},
            char_class="fighter",
            ability_scores={"str": 10, "dex": 18},
        )
    )

    assert stats["attack_bonus"] == 6
    assert stats["attack_range_m"] == 45.0


def test_thrown_weapons_use_normal_range() -> None:
    dagger = build_combatant_combat_stats(_character_with_weapon({"id": "dagger"}))
    javelin = build_combatant_combat_stats(
        _character_with_weapon(
            {"id": "javelin"},
            char_class="fighter",
            ability_scores={"str": 16, "dex": 10},
        )
    )

    assert dagger["attack_bonus"] == 5
    assert dagger["damage_notation"] == "1d4+3"
    assert dagger["attack_range_m"] == 6.0
    assert javelin["attack_bonus"] == 5
    assert javelin["damage_notation"] == "1d6+3"
    assert javelin["attack_range_m"] == 9.0


def test_melee_and_reach_weapons_use_reach() -> None:
    longsword = build_combatant_combat_stats(
        _character_with_weapon(
            {"id": "longsword"},
            char_class="fighter",
            ability_scores={"str": 16, "dex": 10},
        )
    )
    reach_weapon = build_combatant_combat_stats(
        _character_with_weapon(
            {
                "id": "custom_glaive",
                "item_type": "weapon",
                "category": "martial",
                "damage_dice": "1d10",
                "damage_type": "slashing",
                "properties": ["reach", "two-handed"],
            },
            char_class="fighter",
            ability_scores={"str": 16, "dex": 10},
        )
    )

    assert longsword["attack_range_m"] == 1.5
    assert reach_weapon["reach_m"] == 3.0
    assert reach_weapon["attack_range_m"] == 3.0


def test_unarmed_and_unknown_class_fallbacks_are_valid() -> None:
    unarmed = build_combatant_combat_stats(
        {
            "name": "Brawler",
            "char_class": "fighter",
            "level": 1,
            "ability_scores": {"str": 14, "dex": 10},
            "equipment": [],
        }
    )
    unknown_class = build_combatant_combat_stats(
        _character_with_weapon(
            {"id": "longbow"},
            char_class="paladin_king",
            ability_scores={"str": 14, "dex": 18},
        )
    )

    assert unarmed["attack_bonus"] == 4
    assert unarmed["damage_notation"] == "3"
    assert unknown_class["attack_bonus"] == 4
    assert unknown_class["damage_notation"] == "3"
    assert unknown_class["attack_range_m"] == 1.5


def test_non_proficient_weapon_omits_proficiency_bonus() -> None:
    stats = build_combatant_combat_stats(
        _character_with_weapon(
            {"id": "longsword"},
            char_class="wizard",
            ability_scores={"str": 14, "dex": 10},
        )
    )

    assert stats["attack_bonus"] == 2
    assert stats["damage_notation"] == "1d8+2"
