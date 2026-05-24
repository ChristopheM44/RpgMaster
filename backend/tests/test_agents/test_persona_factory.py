"""Tests unitaires pour PersonaFactory.

Couvre :
- Stub NPC instantané (sans LLM)
- Heuristique de behavior_pattern selon le type SRD
- Persona monstre minimale pour mindless / can_speak=False
- Enrichissement NPC via mock LLM : succès, retry, fallback sur stub
- Generation monster : skip LLM pour mindless, retry sur invalide
- Macro Jinja _persona_render avec include_hidden True/False
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.agents.base_agent import _PROMPTS_DIR
from app.agents.persona import (
    MonsterPersona,
    NPCPersona,
    PersonaMotivations,
    PersonaVoice,
)
from app.game.persona_factory import (
    PersonaFactory,
    _heuristic_behavior_pattern,
    _slugify,
)
from app.llm.ollama_client import OllamaClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> OllamaClient:
    return OllamaClient(base_url="http://localhost:11434", model="test")


@pytest.fixture
def factory(client: OllamaClient) -> PersonaFactory:
    return PersonaFactory(client=client)


# ---------------------------------------------------------------------------
# Helpers / heuristiques
# ---------------------------------------------------------------------------


def test_slugify_handles_accents_and_spaces() -> None:
    assert _slugify("Garrik le Taverner") == "garrik_le_taverner"
    assert _slugify("Mère Éline").startswith("m")  # accents normalisés ou préservés
    assert _slugify("") == "unknown"


def test_heuristic_oozes_are_mindless_and_silent() -> None:
    pattern, can_speak = _heuristic_behavior_pattern("gray_ooze", "ooze", None)
    assert pattern == "mindless"
    assert can_speak is False


def test_heuristic_constructs_are_lawful_and_silent() -> None:
    pattern, can_speak = _heuristic_behavior_pattern("iron_golem", "construct", 16)
    assert pattern == "lawful"
    assert can_speak is False


def test_heuristic_beasts_are_predatory_and_silent() -> None:
    pattern, can_speak = _heuristic_behavior_pattern("brown_bear", "beast", 1)
    assert pattern == "predatory"
    assert can_speak is False


def test_heuristic_dragons_are_cunning_and_speaking() -> None:
    pattern, can_speak = _heuristic_behavior_pattern("ancient_red_dragon", "dragon", 24)
    assert pattern == "cunning"
    assert can_speak is True


def test_heuristic_default_is_tactical_speaking() -> None:
    pattern, can_speak = _heuristic_behavior_pattern("bandit", "humanoid", 0.125)
    assert pattern == "tactical"
    assert can_speak is True


# ---------------------------------------------------------------------------
# Stub NPC
# ---------------------------------------------------------------------------


def test_stub_npc_persona_is_instant_and_light(factory: PersonaFactory) -> None:
    stub = factory.stub_npc_persona(
        "Mère Éline", scene_context="Vieille femme à l'entrée du temple"
    )
    assert isinstance(stub, NPCPersona)
    assert stub.importance == "light"
    assert stub.name == "Mère Éline"
    assert "Vieille femme" in stub.short_description


def test_stub_npc_persona_truncates_long_descriptions(factory: PersonaFactory) -> None:
    long_text = "X" * 500
    stub = factory.stub_npc_persona("Bob", scene_context=long_text)
    assert len(stub.short_description) <= 200


# ---------------------------------------------------------------------------
# Monster persona minimale (mindless / fallback)
# ---------------------------------------------------------------------------


def test_minimal_monster_persona_for_ooze() -> None:
    persona = PersonaFactory._build_minimal_monster_persona(
        monster_srd_id="gray_ooze",
        display_name="Vase grise",
        behavior_pattern="mindless",
        can_speak=False,
    )
    assert isinstance(persona, MonsterPersona)
    assert persona.can_speak is False
    assert persona.combat_taunts == []
    assert persona.surrender_threshold is None
    assert persona.behavior_pattern == "mindless"


# ---------------------------------------------------------------------------
# Génération NPC via mock LLM
# ---------------------------------------------------------------------------


VALID_NPC_JSON = json.dumps(
    {
        "id": "mere_eline",
        "name": "Mère Éline",
        "archetype": "oracle",
        "short_description": "Vieille oracle aveugle qui lit l'avenir dans les os.",
        "voice": {
            "gender": "female",
            "age_range": "elder",
            "speech_register": "archaic",
            "pitch": "low",
            "rate": "slow",
            "accent": "noble",
            "timbre": "rauque",
        },
        "motivations": {
            "visible": ["aider les voyageurs"],
            "hidden": ["retrouver son ancien temple"],
            "fears": ["mourir avant la rédemption"],
        },
        "knowledge": {
            "knows": ["l'histoire occulte"],
            "ignores": ["les évènements récents"],
            "rumors": ["un dragon dort sous les ruines"],
        },
        "relationships": [],
        "importance": "rich",
        "persona_type": "npc",
        "attitude_default": "indifferent",
        "secrets": ["A volé une relique"],
        "quest_hooks": ["Demander de l'aide pour le temple"],
        "catchphrases": ["Les os ne mentent jamais."],
    }
)


async def test_enrich_npc_persona_returns_rich_persona_on_success(
    factory: PersonaFactory,
) -> None:
    factory._client.chat = AsyncMock(return_value=VALID_NPC_JSON)  # type: ignore[assignment]
    stub = factory.stub_npc_persona("Mère Éline")
    enriched = await factory.enrich_npc_persona(stub, target_importance="rich")

    assert isinstance(enriched, NPCPersona)
    assert enriched.importance == "rich"
    assert enriched.archetype == "oracle"
    assert "A volé une relique" in enriched.secrets
    factory._client.chat.assert_called_once()


async def test_enrich_npc_persona_retries_then_falls_back_on_invalid_json(
    factory: PersonaFactory,
) -> None:
    factory._client.chat = AsyncMock(  # type: ignore[assignment]
        side_effect=["pas du JSON", "encore du texte libre"]
    )
    stub = factory.stub_npc_persona("Anonyme")
    result = await factory.enrich_npc_persona(stub)

    # 2 tentatives → fallback sur le stub original
    assert factory._client.chat.call_count == 2
    assert result is stub
    assert result.importance == "light"


async def test_enrich_npc_persona_handles_partial_json_then_succeeds(
    factory: PersonaFactory,
) -> None:
    invalid_then_valid = ["{ broken", VALID_NPC_JSON]
    factory._client.chat = AsyncMock(side_effect=invalid_then_valid)  # type: ignore[assignment]
    stub = factory.stub_npc_persona("Mère Éline")
    result = await factory.enrich_npc_persona(stub)

    assert factory._client.chat.call_count == 2
    assert isinstance(result, NPCPersona)
    assert result.archetype == "oracle"


# ---------------------------------------------------------------------------
# Génération monstre — skip LLM pour mindless
# ---------------------------------------------------------------------------


async def test_generate_monster_persona_skips_llm_for_ooze(
    factory: PersonaFactory,
) -> None:
    factory._client.chat = AsyncMock()  # type: ignore[assignment]
    persona = await factory.generate_monster_persona(
        "gray_ooze",
        monster_type="ooze",
        monster_cr=0.5,
    )
    assert persona.can_speak is False
    assert persona.behavior_pattern == "mindless"
    # Aucun appel LLM
    factory._client.chat.assert_not_called()


async def test_generate_monster_persona_skips_llm_for_construct(
    factory: PersonaFactory,
) -> None:
    factory._client.chat = AsyncMock()  # type: ignore[assignment]
    persona = await factory.generate_monster_persona(
        "iron_golem",
        monster_type="construct",
        monster_cr=16,
    )
    assert persona.behavior_pattern == "lawful"
    assert persona.can_speak is False
    factory._client.chat.assert_not_called()


VALID_MONSTER_JSON = json.dumps(
    {
        "id": "vermithrax_dragon",
        "name": "Vermithrax",
        "archetype": "ancient_tyrant",
        "short_description": "Dragon rouge antique.",
        "voice": {
            "gender": "male",
            "age_range": "ancient",
            "speech_register": "archaic",
            "pitch": "very_low",
            "rate": "slow",
        },
        "motivations": {
            "visible": ["défendre son trésor"],
            "hidden": ["récupérer une couronne volée"],
            "fears": ["perdre son trésor"],
        },
        "knowledge": {
            "knows": ["chaque pièce du trésor"],
            "ignores": ["les évènements en surface"],
            "rumors": [],
        },
        "relationships": [],
        "importance": "rich",
        "persona_type": "monster",
        "monster_srd_id": "ancient_red_dragon",
        "behavior_pattern": "cunning",
        "combat_taunts": ["Vous osez défier Vermithrax ?"],
        "surrender_threshold": 0.15,
        "can_speak": True,
    }
)


async def test_generate_monster_persona_calls_llm_for_intelligent(
    factory: PersonaFactory,
) -> None:
    factory._client.chat = AsyncMock(return_value=VALID_MONSTER_JSON)  # type: ignore[assignment]
    persona = await factory.generate_monster_persona(
        "ancient_red_dragon",
        monster_type="dragon",
        monster_cr=24,
        importance="rich",
    )
    assert persona.can_speak is True
    assert persona.behavior_pattern == "cunning"
    assert persona.surrender_threshold == 0.15
    factory._client.chat.assert_called_once()


async def test_generate_monster_persona_falls_back_after_two_invalid_responses(
    factory: PersonaFactory,
) -> None:
    factory._client.chat = AsyncMock(  # type: ignore[assignment]
        side_effect=["invalid 1", "invalid 2"]
    )
    persona = await factory.generate_monster_persona(
        "ancient_red_dragon",
        monster_type="dragon",
        monster_cr=24,
        importance="rich",
    )
    assert factory._client.chat.call_count == 2
    # Fallback déterministe : cunning + can_speak, mais light/minimal
    assert persona.behavior_pattern == "cunning"
    assert persona.importance == "light"
    assert persona.combat_taunts == []


# ---------------------------------------------------------------------------
# Macro Jinja2 _persona_render.j2
# ---------------------------------------------------------------------------


@pytest.fixture
def jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_PROMPTS_DIR)),
        autoescape=select_autoescape([]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _render_npc(env: Environment, persona: NPCPersona, include_hidden: bool) -> str:
    tpl = env.from_string(
        "{% import '_persona_render.j2' as P %}{{ P.render_persona(p, include_hidden=hidden) }}"
    )
    return tpl.render(p=persona, hidden=include_hidden)


def test_macro_render_includes_visible_motivations(jinja_env: Environment) -> None:
    npc = NPCPersona(
        id="garrik",
        name="Garrik",
        archetype="merchant",
        short_description="Tavernier",
        voice=PersonaVoice(gender="male", speech_register="vulgar"),
        motivations=PersonaMotivations(visible=["gagner sa vie"], hidden=["venger sa fille"]),
        secrets=["sait le meurtre"],
    )
    out = _render_npc(jinja_env, npc, include_hidden=False)
    assert "gagner sa vie" in out
    assert "venger sa fille" not in out
    assert "sait le meurtre" not in out


def test_macro_render_exposes_hidden_when_flagged(jinja_env: Environment) -> None:
    npc = NPCPersona(
        id="garrik",
        name="Garrik",
        archetype="merchant",
        short_description="Tavernier",
        voice=PersonaVoice(gender="male", speech_register="vulgar"),
        motivations=PersonaMotivations(visible=["gagner sa vie"], hidden=["venger sa fille"]),
        secrets=["sait le meurtre"],
    )
    out = _render_npc(jinja_env, npc, include_hidden=True)
    assert "gagner sa vie" in out
    assert "venger sa fille" in out
    assert "sait le meurtre" in out


def test_macro_render_monster_includes_taunts_and_threshold(
    jinja_env: Environment,
) -> None:
    monster = MonsterPersona(
        id="verm",
        name="Vermithrax",
        archetype="ancient_tyrant",
        short_description="Dragon antique.",
        monster_srd_id="ancient_red_dragon",
        behavior_pattern="cunning",
        surrender_threshold=0.15,
        combat_taunts=["Misérables fourmis !"],
    )
    tpl = jinja_env.from_string(
        "{% import '_persona_render.j2' as P %}{{ P.render_persona(p, include_hidden=True) }}"
    )
    out = tpl.render(p=monster)
    assert "Misérables fourmis" in out
    assert "15" in out  # surrender threshold percent
    assert "cunning" in out
