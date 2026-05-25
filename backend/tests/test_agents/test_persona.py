"""Tests unitaires pour les schémas Persona polymorphes.

Couvre :
- Construction valide de NPCPersona, MonsterPersona, CompanionPersona
- Validators : traits inconnus rejetés, relationships cappées à 10
- Adapter CompanionPersona.from_player_personality
- Polymorphisme via persona_from_dict
- Migration legacy via stub_npc_persona_from_legacy
"""

from __future__ import annotations

import pytest

from app.agents.persona import (
    MAX_RELATIONSHIPS,
    BasePersona,
    CompanionPersona,
    MonsterPersona,
    NPCPersona,
    PersonaKnowledge,
    PersonaMotivations,
    PersonaRelationship,
    PersonaVoice,
    persona_from_dict,
    stub_npc_persona_from_legacy,
)
from app.agents.schemas import PlayerPersonality

# ---------------------------------------------------------------------------
# Construction et défauts
# ---------------------------------------------------------------------------


def test_npc_persona_minimal_construction() -> None:
    npc = NPCPersona(
        id="garrik",
        name="Garrik",
        archetype="merchant",
        short_description="Tavernier rude.",
    )
    assert npc.persona_type == "npc"
    assert npc.attitude_default == "indifferent"
    assert npc.secrets == []
    assert npc.voice.gender == "neutral"


def test_monster_persona_requires_srd_id() -> None:
    with pytest.raises(ValueError):
        MonsterPersona(
            id="x",
            name="X",
            archetype="x",
            short_description="x",
            behavior_pattern="predatory",
        )  # type: ignore[call-arg]


def test_monster_persona_can_be_mindless_and_silent() -> None:
    ooze = MonsterPersona(
        id="ooze_1",
        name="Vase grise",
        archetype="ooze",
        short_description="Acide mouvant.",
        monster_srd_id="gray_ooze",
        behavior_pattern="mindless",
        can_speak=False,
    )
    assert ooze.can_speak is False
    assert ooze.combat_taunts == []
    assert ooze.surrender_threshold is None


def test_companion_persona_extends_player_personality() -> None:
    comp = CompanionPersona(
        id="lyra_1",
        name="Lyra",
        archetype="cleric",
        short_description="Clerc de la lumière.",
        traits=["noble", "protective"],
        speech_style="formal",
        bond_to_party="Doit la vie au héros",
        fears_in_combat=["feu"],
    )
    assert comp.persona_type == "companion"
    assert comp.traits == ["noble", "protective"]
    assert comp.bond_to_party == "Doit la vie au héros"


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def test_companion_persona_rejects_unknown_traits() -> None:
    with pytest.raises(ValueError, match="Unknown traits"):
        CompanionPersona(
            id="x",
            name="X",
            archetype="x",
            short_description="x",
            traits=["evil", "brave"],
        )


def test_base_persona_caps_relationships_to_max() -> None:
    rels = [
        PersonaRelationship(
            target_id=f"t{i}",
            target_name=f"T{i}",
            intensity=(i % 5) + 1,
        )
        for i in range(15)
    ]
    npc = NPCPersona(
        id="x",
        name="X",
        archetype="x",
        short_description="x",
        relationships=rels,
    )
    assert len(npc.relationships) == MAX_RELATIONSHIPS
    # Le cap garde les relations les plus intenses
    assert all(r.intensity >= 1 for r in npc.relationships)
    assert npc.relationships[0].intensity >= npc.relationships[-1].intensity


def test_persona_relationship_intensity_bounds() -> None:
    with pytest.raises(ValueError):
        PersonaRelationship(target_id="t", target_name="T", intensity=6)
    with pytest.raises(ValueError):
        PersonaRelationship(target_id="t", target_name="T", intensity=0)


def test_monster_surrender_threshold_bounds() -> None:
    with pytest.raises(ValueError):
        MonsterPersona(
            id="x",
            name="X",
            archetype="x",
            short_description="x",
            monster_srd_id="srd",
            behavior_pattern="tactical",
            surrender_threshold=1.5,
        )


# ---------------------------------------------------------------------------
# Adapter PlayerPersonality → CompanionPersona
# ---------------------------------------------------------------------------


def test_from_player_personality_preserves_fields() -> None:
    pp = PlayerPersonality(
        traits=["brave", "cautious"],
        backstory_hook="Orphelin du Nord",
        speech_style="gruff",
    )
    adapted = CompanionPersona.from_player_personality(pp, character_id="hero_3", name="Bran")
    assert adapted.id == "hero_3"
    assert adapted.name == "Bran"
    assert adapted.traits == ["brave", "cautious"]
    assert adapted.backstory_hook == "Orphelin du Nord"
    assert adapted.speech_style == "gruff"
    assert adapted.importance == "light"


def test_from_player_personality_with_empty_traits() -> None:
    pp = PlayerPersonality()
    adapted = CompanionPersona.from_player_personality(pp, character_id="x", name="Nameless")
    assert adapted.traits == []
    assert adapted.short_description.startswith("Nameless")


# ---------------------------------------------------------------------------
# Polymorphisme et sérialisation
# ---------------------------------------------------------------------------


def test_persona_from_dict_dispatches_to_correct_class() -> None:
    npc_dump = NPCPersona(id="a", name="A", archetype="x", short_description="x").model_dump()
    monster_dump = MonsterPersona(
        id="b",
        name="B",
        archetype="x",
        short_description="x",
        monster_srd_id="srd",
        behavior_pattern="tactical",
    ).model_dump()
    comp_dump = CompanionPersona(
        id="c", name="C", archetype="x", short_description="x", traits=["brave"]
    ).model_dump()

    assert isinstance(persona_from_dict(npc_dump), NPCPersona)
    assert isinstance(persona_from_dict(monster_dump), MonsterPersona)
    assert isinstance(persona_from_dict(comp_dump), CompanionPersona)


def test_persona_from_dict_falls_back_to_base_when_type_unknown() -> None:
    raw = {
        "id": "x",
        "name": "X",
        "archetype": "x",
        "short_description": "x",
        "persona_type": "alien",
    }
    persona = persona_from_dict(raw)
    assert isinstance(persona, BasePersona)
    assert persona.persona_type == "alien"


def test_persona_round_trip_through_json() -> None:
    original = NPCPersona(
        id="garrik",
        name="Garrik",
        archetype="merchant",
        short_description="Tavernier.",
        voice=PersonaVoice(gender="male", speech_register="vulgar"),
        motivations=PersonaMotivations(visible=["argent"], hidden=["vengeance"]),
        knowledge=PersonaKnowledge(knows=["le meurtre"], ignores=["la magie"]),
        secrets=["sait qui a tué le shérif"],
    )
    restored = persona_from_dict(original.model_dump(mode="json"))
    assert isinstance(restored, NPCPersona)
    assert restored.secrets == ["sait qui a tué le shérif"]
    assert restored.voice.speech_register == "vulgar"
    assert restored.motivations.hidden == ["vengeance"]


# ---------------------------------------------------------------------------
# Migration legacy
# ---------------------------------------------------------------------------


def test_stub_from_legacy_creates_light_npc() -> None:
    stub = stub_npc_persona_from_legacy("Mère Eline", "Vieille femme énigmatique")
    assert isinstance(stub, NPCPersona)
    assert stub.importance == "light"
    assert stub.name == "Mère Eline"
    assert "Vieille femme" in stub.short_description


def test_stub_from_legacy_handles_empty_hint() -> None:
    stub = stub_npc_persona_from_legacy("Bob")
    assert stub.name == "Bob"
    assert "Bob" in stub.short_description


# ---------------------------------------------------------------------------
# Helpers de sanitisation côté campaign_dossier_service
# ---------------------------------------------------------------------------


def test_empty_played_canon_includes_npc_personas() -> None:
    from app.services.campaign_dossier_service import empty_played_canon

    canon = empty_played_canon()
    assert "npc_personas" in canon
    assert canon["npc_personas"] == {}
    assert canon["granted_unique_items"] == []


def test_sanitize_played_canon_preserves_valid_personas() -> None:
    from app.services.campaign_dossier_service import sanitize_played_canon

    canon = sanitize_played_canon(
        {
            "npc_personas": {
                "garrik": {
                    "id": "garrik",
                    "name": "Garrik",
                    "archetype": "merchant",
                    "short_description": "Tavernier",
                    "persona_type": "npc",
                }
            }
        }
    )
    assert "garrik" in canon["npc_personas"]
    assert canon["npc_personas"]["garrik"]["name"] == "Garrik"


def test_sanitize_played_canon_drops_invalid_payloads() -> None:
    from app.services.campaign_dossier_service import sanitize_played_canon

    canon = sanitize_played_canon({"npc_personas": {"broken": {"foo": "bar"}}})
    assert "broken" not in canon["npc_personas"]


def test_sanitize_npc_personas_accepts_mix_of_new_and_legacy() -> None:
    from app.services.campaign_dossier_service import _sanitize_npc_personas

    items = [
        {
            "id": "garrik",
            "name": "Garrik",
            "archetype": "merchant",
            "short_description": "X",
            "persona_type": "npc",
        },
        {"name": "Old Tom", "role": "guide"},  # legacy format → coerced
        {"unrelated": "garbage"},  # no name/id → dropped
    ]
    result = _sanitize_npc_personas(items)
    assert len(result) == 2
    names = {item["name"] for item in result}
    assert "Garrik" in names
    assert "Old Tom" in names


def test_sanitize_monster_personas_filters_by_type() -> None:
    from app.services.campaign_dossier_service import _sanitize_monster_personas

    items = [
        {
            "id": "verm",
            "name": "Vermithrax",
            "archetype": "dragon",
            "short_description": "X",
            "monster_srd_id": "red_dragon",
            "behavior_pattern": "cunning",
            "persona_type": "monster",
        },
        {
            "id": "x",
            "name": "X",
            "archetype": "x",
            "short_description": "X",
            "persona_type": "npc",  # wrong type → dropped
        },
    ]
    result = _sanitize_monster_personas(items)
    assert len(result) == 1
    assert result[0]["behavior_pattern"] == "cunning"


def test_sanitize_gm_dossier_includes_bestiary_and_companion_seeds() -> None:
    from app.models.campaign import Campaign
    from app.services.campaign_dossier_service import sanitize_gm_dossier

    campaign = Campaign(
        id="cmp1",
        name="Test",
        description="Une campagne de test",
        starting_level=1,
    )
    dossier = sanitize_gm_dossier({}, campaign, contract={"visible_chapters": []})
    assert "bestiary" in dossier
    assert "companion_seeds" in dossier
    assert "items" in dossier
    assert "custom_monsters" in dossier
    assert dossier["bestiary"] == []
    assert dossier["companion_seeds"] == []
    assert dossier["items"] == []
    assert dossier["custom_monsters"] == []


# ---------------------------------------------------------------------------
# Pipeline forge → sanitize : préservation des personas complètes
# ---------------------------------------------------------------------------


def test_sanitize_gm_dossier_preserves_rich_npc_persona_from_forge() -> None:
    """Une NPCPersona complète depuis le forge LLM doit traverser intacte."""
    from app.models.campaign import Campaign
    from app.services.campaign_dossier_service import sanitize_gm_dossier

    campaign = Campaign(id="cmp1", name="T", description="T", starting_level=1)
    forge_output = {
        "important_npcs": [
            {
                "id": "mere_eline",
                "name": "Mère Éline",
                "archetype": "oracle",
                "short_description": "Vieille oracle aveugle.",
                "voice": {
                    "gender": "female",
                    "age_range": "elder",
                    "speech_register": "archaic",
                    "pitch": "low",
                    "rate": "slow",
                },
                "motivations": {
                    "visible": ["aider les voyageurs"],
                    "hidden": ["retrouver son ancien temple"],
                    "fears": ["mourir avant la rédemption"],
                },
                "knowledge": {
                    "knows": ["l'histoire occulte"],
                    "ignores": ["la cour"],
                    "rumors": [],
                },
                "importance": "rich",
                "persona_type": "npc",
                "attitude_default": "indifferent",
                "secrets": ["A volé une relique"],
                "quest_hooks": ["Demander de l'aide pour le temple"],
                "catchphrases": ["Les os ne mentent jamais."],
            }
        ]
    }
    dossier = sanitize_gm_dossier(
        forge_output, campaign, contract={"visible_chapters": []}
    )
    npcs = dossier["important_npcs"]
    assert len(npcs) == 1
    persona = npcs[0]
    assert persona["importance"] == "rich"
    assert persona["voice"]["speech_register"] == "archaic"
    assert "A volé une relique" in persona["secrets"]
    assert "retrouver son ancien temple" in persona["motivations"]["hidden"]


def test_sanitize_gm_dossier_preserves_bestiary_monster_persona() -> None:
    """Un bestiary entry au format MonsterPersona doit traverser intact."""
    from app.models.campaign import Campaign
    from app.services.campaign_dossier_service import sanitize_gm_dossier

    campaign = Campaign(id="cmp1", name="T", description="T", starting_level=1)
    forge_output = {
        "bestiary": [
            {
                "id": "vermithrax",
                "name": "Vermithrax",
                "archetype": "ancient_tyrant",
                "short_description": "Dragon rouge antique.",
                "monster_srd_id": "ancient_red_dragon",
                "behavior_pattern": "cunning",
                "combat_taunts": ["Misérables fourmis !"],
                "surrender_threshold": 0.15,
                "can_speak": True,
                "importance": "rich",
                "persona_type": "monster",
            }
        ]
    }
    dossier = sanitize_gm_dossier(
        forge_output, campaign, contract={"visible_chapters": []}
    )
    bestiary = dossier["bestiary"]
    assert len(bestiary) == 1
    assert bestiary[0]["behavior_pattern"] == "cunning"
    assert bestiary[0]["surrender_threshold"] == 0.15
    assert "Misérables fourmis !" in bestiary[0]["combat_taunts"]


def test_sanitize_gm_dossier_preserves_custom_items_and_monsters() -> None:
    from app.models.campaign import Campaign
    from app.services.campaign_dossier_service import sanitize_gm_dossier

    campaign = Campaign(id="cmp1", name="T", description="T", starting_level=1)
    forge_output = {
        "chapters": [
            {
                "id": "chapter_1",
                "title": "Cendres",
                "possible_srd_encounters": ["skeleton"],
                "possible_custom_encounters": ["squelette-enflamme"],
            }
        ],
        "items": [
            {
                "id": "lame-de-braise",
                "template_id": "lame-de-braise",
                "name": "Ember Blade",
                "name_fr": "Lame de braise",
                "category": "martial",
                "item_type": "weapon",
                "damage_dice": "1d8",
                "damage_type": "slashing",
                "weight_lb": 3,
                "cost_gp": 250,
                "unique": True,
            },
            {"id": "broken", "item_type": "weapon"},
        ],
        "custom_monsters": [
            {
                "id": "squelette-enflamme",
                "base_srd_id": "skeleton",
                "name": "Flaming Skeleton",
                "name_fr": "Squelette enflammé",
                "stat_overrides": {
                    "hp": 18,
                    "ac": 14,
                    "damage_dice": "1d6+2",
                    "damage_type": "fire",
                    "damage_immunities": ["fire"],
                },
            },
            {"id": "bad", "name": "Bad"},
        ],
        "light_mechanics": [{"id": "rest_variant"}],
    }

    dossier = sanitize_gm_dossier(
        forge_output,
        campaign,
        contract={"visible_chapters": [{"id": "chapter_1", "title": "Cendres"}]},
    )

    assert len(dossier["items"]) == 1
    item = dossier["items"][0]
    assert item["id"] == "lame_de_braise"
    assert item["damage_dice"] == "1d8"
    assert item["unique"] is True
    assert len(dossier["custom_monsters"]) == 1
    custom = dossier["custom_monsters"][0]
    assert custom["id"] == "squelette_enflamme"
    assert custom["base_srd_id"] == "skeleton"
    assert custom["stat_overrides"]["damage_immunities"] == ["fire"]
    assert dossier["chapters"][0]["possible_custom_encounters"] == ["squelette_enflamme"]
    assert dossier["light_mechanics"] == [{"id": "rest_variant"}]


def test_chapter_custom_encounter_mapping_is_merged() -> None:
    from app.services.campaign_dossier_service import _merge_chapter_custom_encounters

    chapters = [{"id": "chapter_1"}, {"id": "chapter_2", "possible_custom_encounters": ["old"]}]
    merged = _merge_chapter_custom_encounters(
        chapters,
        {"chapter_1": ["squelette-enflamme"], "chapter_2": ["old", "new-beast"]},
    )

    assert merged[0]["possible_custom_encounters"] == ["squelette_enflamme"]
    assert merged[1]["possible_custom_encounters"] == ["old", "new_beast"]


def test_sanitize_gm_dossier_coerces_legacy_npc_dict() -> None:
    """Un ancien format `important_npcs: [{"name": "Bram"}]` doit être migré."""
    from app.models.campaign import Campaign
    from app.services.campaign_dossier_service import sanitize_gm_dossier

    campaign = Campaign(id="cmp1", name="T", description="T", starting_level=1)
    forge_output = {
        "important_npcs": [
            {"name": "Bram", "role": "informateur", "description": "Témoin furtif"},
            {"name": "Garrik"},
        ]
    }
    dossier = sanitize_gm_dossier(
        forge_output, campaign, contract={"visible_chapters": []}
    )
    npcs = dossier["important_npcs"]
    assert len(npcs) == 2
    bram = next(n for n in npcs if n["name"] == "Bram")
    assert bram["importance"] == "light"
    assert bram["archetype"] == "informateur"
    assert bram["persona_type"] == "npc"
    # Le champ "role" disparaît mais "Témoin furtif" est préservé dans short_description
    assert "Témoin furtif" in bram["short_description"]
