"""Tests unitaires pour PlayerAgent (Sprint 5).

Couvre :
- Génération de description de personnalité (_describe_personality)
- validate_action : attaque valide, sorts sans emplacement, objet absent, personnage KO
- decide_action : succès LLM, action_type invalide → fallback, erreur LLM → wait
- roleplay : succès LLM
- think() : délègue selon la phase de jeu
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.player_agent import (
    _FALLBACK_ACTION,
    PlayerAgent,
    _describe_personality,
)
from app.agents.schemas import AgentContext, PlayerActionChoice, PlayerPersonality
from app.llm.ollama_client import OllamaClient, OllamaError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> OllamaClient:
    return OllamaClient(base_url="http://localhost:11434", model="test")


@pytest.fixture
def brave_agent(client: OllamaClient) -> PlayerAgent:
    return PlayerAgent(
        character_id="thorin_1",
        character_name="Thorin",
        personality=PlayerPersonality(traits=["brave", "noble"]),
        client=client,
    )


@pytest.fixture
def arcane_agent(client: OllamaClient) -> PlayerAgent:
    return PlayerAgent(
        character_id="elara_1",
        character_name="Elara",
        personality=PlayerPersonality(
            traits=["arcane", "cautious"],
            backstory_hook="Cherche à retrouver son grimoire volé",
            speech_style="formal",
        ),
        client=client,
    )


def _game_state(**overrides) -> dict:
    base = {
        "characters": {
            "thorin_1": {
                "current_hp": 20,
                "max_hp": 30,
                "spell_slots": {},
                "inventory": [{"name": "Potion de soin"}],
            },
            "elara_1": {
                "current_hp": 10,
                "max_hp": 12,
                "spell_slots": {"1": 2, "2": 1},
                "inventory": [],
            },
        }
    }
    base.update(overrides)
    return base


def _valid_action_json(**overrides) -> str:
    data = {
        "action_type": "attack",
        "action_description": "Frappe avec son marteau de guerre",
        "target": "goblin_1",
        "params": {"weapon": "marteau de guerre"},
        "roleplay_text": "Thorin charge avec un cri de guerre !",
        "inner_reasoning": "Le gobelin est la cible prioritaire.",
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


# ---------------------------------------------------------------------------
# _describe_personality
# ---------------------------------------------------------------------------


def test_describe_personality_single_trait() -> None:
    p = PlayerPersonality(traits=["brave"])
    desc = _describe_personality(p)
    assert "BRAVE" in desc
    assert "ennemis" in desc


def test_describe_personality_multiple_traits() -> None:
    p = PlayerPersonality(traits=["brave", "noble"])
    desc = _describe_personality(p)
    assert "BRAVE" in desc
    assert "NOBLE" in desc


def test_describe_personality_with_backstory_and_style() -> None:
    p = PlayerPersonality(
        traits=["arcane"],
        backstory_hook="A perdu sa famille dans une guerre",
        speech_style="gruff",
    )
    desc = _describe_personality(p)
    assert "ARCANE" in desc
    assert "famille" in desc
    assert "gruff" in desc


def test_describe_personality_empty_traits() -> None:
    p = PlayerPersonality(traits=[])
    desc = _describe_personality(p)
    assert "équilibrée" in desc


def test_describe_personality_unknown_trait() -> None:
    p = PlayerPersonality(traits=["unknown_trait"])
    desc = _describe_personality(p)
    # Unknown trait is ignored, falls back to balanced description
    assert "équilibrée" in desc


# ---------------------------------------------------------------------------
# validate_action
# ---------------------------------------------------------------------------


def test_validate_action_valid_attack(brave_agent: PlayerAgent) -> None:
    action = PlayerActionChoice(
        action_type="attack",
        action_description="Attaque au corps à corps",
        roleplay_text="Thorin frappe !",
    )
    is_valid, reason = brave_agent.validate_action(action, _game_state())
    assert is_valid
    assert reason == "ok"


def test_validate_action_unknown_type(brave_agent: PlayerAgent) -> None:
    action = PlayerActionChoice(
        action_type="fly",  # not in PLAYER_ACTION_TYPES
        action_description="Vol magique",
        roleplay_text="Thorin s'envole.",
    )
    is_valid, reason = brave_agent.validate_action(action, _game_state())
    assert not is_valid
    assert "inconnu" in reason


def test_validate_action_cast_spell_no_slots(arcane_agent: PlayerAgent) -> None:
    state = _game_state()
    state["characters"]["elara_1"]["spell_slots"] = {"1": 0, "2": 0}
    action = PlayerActionChoice(
        action_type="cast_spell",
        action_description="Lance un sort",
        params={"spell_name": "Boule de feu"},
        roleplay_text="Elara invoque les flammes.",
    )
    is_valid, reason = arcane_agent.validate_action(action, state)
    assert not is_valid
    assert "emplacements" in reason


def test_validate_action_cast_spell_has_slots(arcane_agent: PlayerAgent) -> None:
    action = PlayerActionChoice(
        action_type="cast_spell",
        action_description="Lance un sort",
        params={"spell_name": "Projectile magique"},
        roleplay_text="Elara projette des dards de force.",
    )
    is_valid, reason = arcane_agent.validate_action(action, _game_state())
    assert is_valid


def test_validate_action_cast_spell_structured_slots(arcane_agent: PlayerAgent) -> None:
    state = _game_state()
    state["characters"]["elara_1"]["spell_slots"] = {"1": {"total": 2, "used": 1}}
    action = PlayerActionChoice(
        action_type="cast_spell",
        action_description="Lance un sort",
        params={"spell_name": "Projectile magique"},
        roleplay_text="Elara projette des dards de force.",
    )
    is_valid, reason = arcane_agent.validate_action(action, state)
    assert is_valid, reason


def test_validate_action_cast_spell_missing_spell_name(arcane_agent: PlayerAgent) -> None:
    action = PlayerActionChoice(
        action_type="cast_spell",
        action_description="Lance un sort",
        roleplay_text="Elara lance quelque chose.",
    )
    is_valid, reason = arcane_agent.validate_action(action, _game_state())
    assert not is_valid
    assert "spell_name" in reason


def test_validate_action_use_item_in_inventory(brave_agent: PlayerAgent) -> None:
    action = PlayerActionChoice(
        action_type="use_item",
        action_description="Utilise une potion",
        params={"item_name": "Potion de soin"},
        roleplay_text="Thorin boit la potion.",
    )
    is_valid, _ = brave_agent.validate_action(action, _game_state())
    assert is_valid


def test_validate_action_use_item_not_in_inventory(brave_agent: PlayerAgent) -> None:
    action = PlayerActionChoice(
        action_type="use_item",
        action_description="Utilise une potion",
        params={"item_name": "Élixir de force"},
        roleplay_text="Thorin cherche l'élixir.",
    )
    is_valid, reason = brave_agent.validate_action(action, _game_state())
    assert not is_valid
    assert "inventaire" in reason


def test_validate_action_use_item_missing_item_name(brave_agent: PlayerAgent) -> None:
    action = PlayerActionChoice(
        action_type="use_item",
        action_description="Utilise un objet",
        roleplay_text="Thorin fouille son sac.",
    )
    is_valid, reason = brave_agent.validate_action(action, _game_state())
    assert not is_valid
    assert "item_name" in reason


def test_validate_action_unconscious_blocks_attack(brave_agent: PlayerAgent) -> None:
    state = _game_state()
    state["characters"]["thorin_1"]["current_hp"] = 0
    action = PlayerActionChoice(
        action_type="attack",
        action_description="Attaque",
        roleplay_text="Thorin tente de frapper.",
    )
    is_valid, reason = brave_agent.validate_action(action, state)
    assert not is_valid
    assert "inconscient" in reason


def test_validate_action_wait_allowed_when_unconscious(brave_agent: PlayerAgent) -> None:
    state = _game_state()
    state["characters"]["thorin_1"]["current_hp"] = 0
    action = PlayerActionChoice(
        action_type="wait",
        action_description="Attend",
        roleplay_text="(immobile)",
    )
    is_valid, _ = brave_agent.validate_action(action, state)
    assert is_valid


# ---------------------------------------------------------------------------
# decide_action
# ---------------------------------------------------------------------------


async def test_decide_action_success(brave_agent: PlayerAgent) -> None:
    """decide_action() parse correctement une réponse JSON valide."""
    with patch.object(
        brave_agent._client,
        "chat",
        new=AsyncMock(return_value=_valid_action_json()),
    ):
        action = await brave_agent.decide_action(game_state=_game_state())

    assert isinstance(action, PlayerActionChoice)
    assert action.action_type == "attack"
    assert action.target == "goblin_1"
    assert "Thorin" in action.roleplay_text


async def test_decide_action_normalizes_named_target(brave_agent: PlayerAgent) -> None:
    """Une cible nommée en JSON est convertie vers l'id du combattant."""
    state = _game_state(
        phase="COMBAT",
        combatants={
            "thorin_1": {"name": "Thorin", "hp": 20, "is_player": True},
            "goblin_2": {"name": "Gobelin 2", "hp": 5, "is_player": False},
        },
    )
    payload = _valid_action_json(target="Gobelin 2")
    with patch.object(brave_agent._client, "chat", new=AsyncMock(return_value=payload)):
        action = await brave_agent.decide_action(game_state=state)

    assert action.action_type == "attack"
    assert action.target == "goblin_2"


async def test_decide_action_invalid_action_type_falls_back_to_wait(
    brave_agent: PlayerAgent,
) -> None:
    """Si le LLM retourne un action_type inconnu, l'agent utilise 'wait'."""
    payload = _valid_action_json(action_type="fly")
    with patch.object(brave_agent._client, "chat", new=AsyncMock(return_value=payload)):
        action = await brave_agent.decide_action(game_state=_game_state())

    assert action.action_type == "wait"


async def test_decide_action_llm_error_returns_fallback(brave_agent: PlayerAgent) -> None:
    """Si Ollama est injoignable, decide_action() retourne l'action de fallback."""
    with patch.object(
        brave_agent._client,
        "chat",
        new=AsyncMock(side_effect=OllamaError("Connection refused")),
    ):
        action = await brave_agent.decide_action(game_state=_game_state())

    assert action.action_type == "wait"
    assert action.llm_error is not None
    assert "Connection refused" in action.llm_error


async def test_decide_action_non_json_response_uses_raw_text(brave_agent: PlayerAgent) -> None:
    """Si le LLM ne retourne pas de JSON, le texte brut sert de roleplay_text."""
    with patch.object(
        brave_agent._client, "chat", new=AsyncMock(return_value="Je fonce vers l'ennemi !")
    ):
        action = await brave_agent.decide_action(game_state=_game_state())

    assert action.action_type == "dodge"
    assert "fonce" in action.roleplay_text


async def test_decide_action_repairs_non_json_response(brave_agent: PlayerAgent) -> None:
    """Si le LLM répond en prose puis répare en JSON, l'action réparée est utilisée."""
    repaired = _valid_action_json(
        action_type="attack",
        action_description="Attaque le gobelin le plus proche",
        roleplay_text="Thorin transforme son élan en coup de marteau.",
    )
    with patch.object(
        brave_agent._client,
        "chat",
        new=AsyncMock(side_effect=["Je charge le gobelin avec mon marteau !", repaired]),
    ):
        action = await brave_agent.decide_action(game_state=_game_state())

    assert action.action_type == "attack"
    assert action.llm_error is None
    assert "marteau" in action.roleplay_text


async def test_decide_action_recovers_truncated_json_response(brave_agent: PlayerAgent) -> None:
    """Si le JSON est tronqué après des champs utiles, l'agent récupère l'action."""
    raw = (
        '{\n'
        '  "action_type": "talk",\n'
        '  "action_description": "Avertir les compagnons",\n'
        '  "target": "Aria",\n'
        '  "params": {},\n'
        '  "roleplay_text": "Thorin lève son bouclier et prévient le groupe'
    )
    with patch.object(
        brave_agent._client,
        "chat",
        new=AsyncMock(side_effect=[raw, "réparation impossible"]),
    ):
        action = await brave_agent.decide_action(game_state=_game_state())

    assert action.action_type == "talk"
    assert action.target == "Aria"
    assert "Thorin" in action.roleplay_text
    assert action.roleplay_text.endswith(".")
    assert "prévient le groupe" not in action.roleplay_text


async def test_decide_action_recovers_labeled_text_response(brave_agent: PlayerAgent) -> None:
    """Les réponses semi-structurées sans JSON restent exploitables."""
    raw = (
        "action_type: talk\n"
        "action_description: Prévenir les alliés\n"
        "target: Aria\n"
        "roleplay_text: Thorin lève la main pour faire signe au groupe.\n"
        "inner_reasoning: Mieux vaut avertir tout le monde."
    )
    with patch.object(
        brave_agent._client,
        "chat",
        new=AsyncMock(side_effect=[raw, "réparation impossible"]),
    ):
        action = await brave_agent.decide_action(game_state=_game_state())

    assert action.action_type == "talk"
    assert action.target == "Aria"
    assert "Thorin" in action.roleplay_text


async def test_decide_action_recovers_plain_combat_prose_with_target(
    brave_agent: PlayerAgent,
) -> None:
    """Une prose de combat sans JSON est convertie en action mécanique."""
    state = _game_state(
        phase="COMBAT",
        combatants={
            "thorin_1": {"name": "Thorin", "hp": 20, "is_player": True},
            "goblin_1": {"name": "Gobelin 1", "hp": 7, "is_player": False},
            "goblin_2": {"name": "Gobelin 2", "hp": 5, "is_player": False},
        },
    )
    raw = "Thorin frappe Gobelin 2 de son marteau en criant de tenir bon !"
    with patch.object(
        brave_agent._client,
        "chat",
        new=AsyncMock(side_effect=[raw, "réparation impossible"]),
    ):
        action = await brave_agent.decide_action(game_state=state)

    assert action.action_type == "attack"
    assert action.target == "goblin_2"
    assert "marteau" in action.roleplay_text
    assert action.llm_error is None


async def test_decide_action_uses_default_combat_action_on_empty_llm_response(
    brave_agent: PlayerAgent,
) -> None:
    """Même une réponse vide/ellipsis déclenche une action de combat utile."""
    state = _game_state(
        phase="COMBAT",
        combatants={
            "thorin_1": {"name": "Thorin", "hp": 20, "is_player": True},
            "goblin_1": {"name": "Gobelin 1", "hp": 7, "is_player": False},
            "goblin_2": {"name": "Gobelin 2", "hp": 3, "is_player": False},
        },
    )
    with patch.object(brave_agent._client, "chat", new=AsyncMock(return_value="…")):
        action = await brave_agent.decide_action(game_state=state)

    assert action.action_type == "attack"
    assert action.target == "goblin_2"
    assert "Thorin" in action.roleplay_text
    assert action.llm_error is None


# ---------------------------------------------------------------------------
# roleplay
# ---------------------------------------------------------------------------


async def test_roleplay_success(brave_agent: PlayerAgent) -> None:
    """roleplay() parse correctement une réponse JSON valide."""
    payload = _valid_action_json(
        action_type="talk",
        action_description="Parle à l'aubergiste",
        target="aubergiste",
        roleplay_text="Thorin commande une chope de bière d'un geste brusque.",
    )
    chat = AsyncMock(return_value=payload)
    with patch.object(brave_agent._client, "chat", new=chat):
        action = await brave_agent.roleplay(
            game_state=_game_state(),
            scene_context="Le groupe arrive dans une taverne animée.",
        )

    assert action.action_type == "talk"
    assert "bière" in action.roleplay_text
    prompt = chat.await_args.kwargs["messages"][-1]["content"]
    assert "Ta réaction doit faire avancer la scène" in prompt
    assert "question utile" in prompt
    assert "Évite les commentaires purement atmosphériques" in prompt


async def test_respond_to_player_prompt_requests_actionable_dialogue(
    brave_agent: PlayerAgent,
) -> None:
    """Le dialogue compagnon demande un angle concret, pas une phrase d'ambiance."""
    payload = _valid_action_json(
        action_type="talk",
        action_description="Propose de questionner le contact",
        target=None,
        roleplay_text="Thorin désigne le comptoir. « Je peux parler au tavernier. »",
    )
    chat = AsyncMock(return_value=payload)
    with patch.object(brave_agent._client, "chat", new=chat):
        action = await brave_agent.respond_to_player(
            game_state=_game_state(),
            player_message="Thorin, tu en penses quoi ?",
        )

    assert action.action_type == "talk"
    assert "tavernier" in action.roleplay_text
    prompt = chat.await_args.kwargs["messages"][-1]["content"]
    assert "Ta réponse doit avoir une prise jouable" in prompt
    assert "Même avec action_type = \"talk\"" in prompt
    assert "Évite les simples commentaires d'ambiance" in prompt


# ---------------------------------------------------------------------------
# think() — interface BaseAgent
# ---------------------------------------------------------------------------


async def test_think_combat_phase_delegates_to_decide_action(
    brave_agent: PlayerAgent,
) -> None:
    """think() délègue à decide_action() en phase COMBAT."""
    with patch.object(
        brave_agent, "decide_action", new=AsyncMock(return_value=_FALLBACK_ACTION)
    ) as mock_decide, patch.object(
        brave_agent, "roleplay", new=AsyncMock(return_value=_FALLBACK_ACTION)
    ) as mock_roleplay:
        context = AgentContext(
            session_id="s1",
            game_phase="COMBAT",
            game_state={"available_actions": ["attack", "dodge"]},
        )
        await brave_agent.think(context)

    mock_decide.assert_called_once()
    mock_roleplay.assert_not_called()


async def test_think_exploration_phase_delegates_to_roleplay(
    brave_agent: PlayerAgent,
) -> None:
    """think() délègue à roleplay() en phase EXPLORATION."""
    with patch.object(
        brave_agent, "decide_action", new=AsyncMock(return_value=_FALLBACK_ACTION)
    ) as mock_decide, patch.object(
        brave_agent, "roleplay", new=AsyncMock(return_value=_FALLBACK_ACTION)
    ) as mock_roleplay:
        context = AgentContext(
            session_id="s1",
            game_phase="EXPLORATION",
            game_state={},
        )
        await brave_agent.think(context)

    mock_roleplay.assert_called_once()
    mock_decide.assert_not_called()


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


def test_player_agent_properties(brave_agent: PlayerAgent) -> None:
    assert brave_agent.character_id == "thorin_1"
    assert brave_agent.character_name == "Thorin"
    assert "brave" in brave_agent.personality.traits
