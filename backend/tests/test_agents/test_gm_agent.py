from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.context_manager import ContextManager
from app.agents.gm_agent import _FALLBACK_NARRATION, GMAgent
from app.agents.schemas import AgentContext, GMResponse
from app.llm.ollama_client import OllamaClient, OllamaError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def gm_agent() -> GMAgent:
    """GMAgent avec un OllamaClient factice (pas de connexion réelle)."""
    client = OllamaClient(base_url="http://localhost:11434", model="test")
    return GMAgent(client=client)


def _valid_gm_json(**overrides) -> str:
    """Retourne une réponse JSON valide du MJ."""
    data = {
        "narration": "Vous entrez dans une forêt sombre et silencieuse.",
        "actions": [],
        "mood": "mysterious",
        "inner_reasoning": "Le joueur explore.",
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


def test_outcome_prompt_requires_fail_forward() -> None:
    prompt = (
        Path(__file__).parents[2]
        / "app"
        / "agents"
        / "prompts"
        / "gm_narrate_outcome.txt"
    ).read_text(encoding="utf-8")

    assert "ÉCHEC fait quand même avancer la scène" in prompt
    assert "tu n'entends rien" in prompt


# ---------------------------------------------------------------------------
# narrate()
# ---------------------------------------------------------------------------


async def test_narrate_success(gm_agent: GMAgent) -> None:
    """narrate() parse correctement une réponse JSON valide."""
    with patch.object(gm_agent._client, "chat", new=AsyncMock(return_value=_valid_gm_json())):
        response = await gm_agent.narrate(
            game_state={"phase": "EXPLORATION"},
            player_action="Je regarde autour de moi.",
        )

    assert isinstance(response, GMResponse)
    assert "forêt" in response.narration
    assert response.mood == "mysterious"
    assert response.actions == []


async def test_narrate_with_actions(gm_agent: GMAgent) -> None:
    """narrate() parse les actions mécaniques correctement."""
    payload = _valid_gm_json(
        actions=[
            {"type": "roll_request", "target": "player_1", "params": {"ability": "dexterity"}}
        ]
    )
    with patch.object(gm_agent._client, "chat", new=AsyncMock(return_value=payload)):
        response = await gm_agent.narrate(game_state={})

    assert len(response.actions) == 1
    assert response.actions[0].type == "roll_request"
    assert response.actions[0].target == "player_1"
    assert response.actions[0].params["ability"] == "dexterity"


async def test_narrate_without_player_action(gm_agent: GMAgent) -> None:
    """narrate() fonctionne sans player_action (None)."""
    with patch.object(gm_agent._client, "chat", new=AsyncMock(return_value=_valid_gm_json())):
        response = await gm_agent.narrate(game_state={})

    assert response.narration != ""


async def test_narrate_injects_scene_anchor_in_prompt(gm_agent: GMAgent) -> None:
    """L'ancrage de scène apparaît textuellement dans le prompt envoyé au LLM."""
    captured: dict[str, Any] = {}

    async def _capture(**kwargs):
        captured["messages"] = kwargs.get("messages", [])
        return _valid_gm_json()

    with patch.object(gm_agent._client, "chat", new=_capture):
        await gm_agent.narrate(
            game_state={
                "adventure_journal": {
                    "location_place": "Goldenthrone",
                    "location_region": "Chult",
                    "time_of_day": "morning",
                    "day_number": 1,
                    "weather": "Chaleur humide",
                },
                "current_scene": {"terrain": "settlement"},
            },
            player_action="Je m'approche de Syndra Silvane.",
        )

    user_prompt = captured["messages"][-1]["content"]
    assert "ANCRAGE DE SCÈNE" in user_prompt
    assert "Goldenthrone" in user_prompt
    assert "morning" in user_prompt
    assert "Chaleur humide" in user_prompt
    assert user_prompt.index("ANCRAGE DE SCÈNE") < user_prompt.index("ÉTAT DU JEU")


async def test_narrate_anchor_handles_empty_state(gm_agent: GMAgent) -> None:
    """L'ancrage est tolérant à un game_state vide (campagne free)."""
    captured: dict[str, Any] = {}

    async def _capture(**kwargs):
        captured["messages"] = kwargs.get("messages", [])
        return _valid_gm_json()

    with patch.object(gm_agent._client, "chat", new=_capture):
        await gm_agent.narrate(game_state={}, player_action="Je regarde.")

    prompt = captured["messages"][-1]["content"]
    assert "lieu non précisé" in prompt
    assert "morning" in prompt


def test_extract_scene_anchor_uses_chapter_location_fallback_only() -> None:
    """Le chapitre peut fournir le lieu, mais pas l'ambiance de scène."""
    from app.agents.gm_agent import _extract_scene_anchor

    anchor = _extract_scene_anchor({
        "campaign_context": {
            "active_chapter": {
                "key_locations": ["Goldenthrone"],
                "initial_state": "L'archmage Syndra Silvane se consume lentement.",
            }
        }
    })
    assert anchor["location_place"] == "Goldenthrone"
    assert anchor["scene_brief"] == ""
    assert anchor["time_of_day"] == "morning"
    assert anchor["location_venue"] is None


def test_extract_scene_anchor_uses_current_scene_description() -> None:
    """L'ambiance établie vient de current_scene.description."""
    from app.agents.gm_agent import _extract_scene_anchor

    anchor = _extract_scene_anchor({
        "adventure_journal": {"location_place": "Port Nyanzaru"},
        "campaign_context": {
            "active_chapter": {
                "initial_state": "Wakanga engage le groupe ailleurs.",
            }
        },
        "current_scene": {
            "description": "Azaka observe la salle commune depuis le comptoir.",
        },
    })

    assert anchor["scene_brief"] == "Azaka observe la salle commune depuis le comptoir."


def test_extract_scene_anchor_uses_opening_scene_location_fallback() -> None:
    """opening_scene peut fournir le lieu physique avant le premier journal_update."""
    from app.agents.gm_agent import _extract_scene_anchor

    anchor = _extract_scene_anchor({
        "campaign_context": {
            "active_chapter": {
                "key_locations": ["Goldenthrone"],
                "opening_scene": {
                    "region": "Chult",
                    "place": "Port Nyanzaru",
                    "venue": "Auberge du Poisson Grillé",
                    "time_of_day": "dusk",
                    "weather": "Chaleur humide",
                },
            }
        }
    })

    assert anchor["location_region"] == "Chult"
    assert anchor["location_place"] == "Port Nyanzaru"
    assert anchor["location_venue"] == "Auberge du Poisson Grillé"
    assert anchor["time_of_day"] == "dusk"
    assert anchor["weather"] == "Chaleur humide"


def test_extract_scene_anchor_uses_location_venue() -> None:
    """location_venue est extrait du journal et ajouté à l'ancre."""
    from app.agents.gm_agent import _extract_scene_anchor

    anchor = _extract_scene_anchor({
        "adventure_journal": {
            "location_place": "Port Nyanzaru",
            "location_venue": "Auberge du Poisson Grillé",
            "time_of_day": "morning",
            "day_number": 1,
        },
    })

    assert anchor["location_venue"] == "Auberge du Poisson Grillé"
    assert anchor["location_place"] == "Port Nyanzaru"


def test_extract_scene_anchor_computes_npc_presence() -> None:
    """L'ancre catégorise les PNJs en présents/absents selon leur last_location."""
    from app.agents.gm_agent import _extract_scene_anchor

    anchor = _extract_scene_anchor({
        "adventure_journal": {
            "location_place": "Port Nyanzaru",
            "location_venue": "Auberge du Poisson Grillé",
        },
        "current_scene": {
            "scene_id": "scene_auberge",
            "terrain": "tavern",
            "pois": [
                {
                    "id": "azaka",
                    "name": "Azaka",
                    "kind": "npc",
                    "icon": "npc",
                    "position": {"col": 3, "row": 3},
                    "description": "La tenancière.",
                }
            ],
        },
        "npc_states": {
            "azaka": {
                "name": "Azaka",
                "attitude": "indifferent",
                "last_location": "scene_auberge",
            },
            "wakanga": {
                "name": "Wakanga O'tamu",
                "attitude": "friendly",
                "last_location": "scene_palais",
            },
        },
    })

    present_names = [n["name"] for n in anchor["present_npcs"]]
    absent_names = [n["name"] for n in anchor["absent_npcs"]]

    assert "Azaka" in present_names
    assert "Wakanga O'tamu" in absent_names


async def test_narrate_injects_npc_presence_in_anchor(gm_agent: GMAgent) -> None:
    """Le bloc PRÉSENCE DES PNJ apparaît dans le prompt avec les PNJs catégorisés."""
    captured: dict[str, Any] = {}

    async def _capture(**kwargs):
        captured["messages"] = kwargs.get("messages", [])
        return _valid_gm_json()

    with patch.object(gm_agent._client, "chat", new=_capture):
        await gm_agent.narrate(
            game_state={
                "adventure_journal": {
                    "location_place": "Port Nyanzaru",
                    "location_venue": "Auberge du Poisson Grillé",
                    "time_of_day": "morning",
                    "day_number": 1,
                },
                "current_scene": {
                    "scene_id": "scene_auberge",
                    "terrain": "tavern",
                    "pois": [
                        {
                            "id": "azaka",
                            "name": "Azaka",
                            "kind": "npc",
                            "icon": "npc",
                            "position": {"col": 3, "row": 3},
                            "description": "La tenancière.",
                        }
                    ],
                },
                "npc_states": {
                    "azaka": {
                        "name": "Azaka",
                        "attitude": "indifferent",
                        "last_location": "scene_auberge",
                    },
                    "wakanga": {
                        "name": "Wakanga O'tamu",
                        "attitude": "friendly",
                        "last_location": "scene_palais",
                    },
                },
            },
            player_action="Je m'approche de Wakanga.",
        )

    user_prompt = captured["messages"][-1]["content"]
    assert "PRÉSENCE DES PNJ" in user_prompt
    assert "Azaka" in user_prompt
    assert "Wakanga O'tamu" in user_prompt
    assert "ABSENTS" in user_prompt


# ---------------------------------------------------------------------------
# run_combat_turn()
# ---------------------------------------------------------------------------


async def test_run_combat_turn_success(gm_agent: GMAgent) -> None:
    """run_combat_turn() retourne une GMResponse cohérente."""
    payload = _valid_gm_json(
        narration="L'épée s'abat sur le gobelin !",
        mood="tense",
        actions=[
            {
                "type": "damage_apply",
                "target": "goblin_1",
                "params": {"amount": 8, "type": "slashing"},
            }
        ],
    )
    with patch.object(gm_agent._client, "chat", new=AsyncMock(return_value=payload)):
        response = await gm_agent.run_combat_turn(
            game_state={"phase": "COMBAT", "round": 1},
            player_action="J'attaque le gobelin.",
            roll_results={"attack": {"hit": True, "total": 17}, "damage": {"total": 8}},
        )

    assert "gobelin" in response.narration
    assert response.mood == "tense"
    assert response.actions[0].type == "damage_apply"


async def test_run_combat_turn_with_context_manager(gm_agent: GMAgent) -> None:
    """run_combat_turn() intègre le ContextManager dans les messages."""
    cm = ContextManager(max_messages=5)
    cm.add_message("gm", "MJ", "Le combat commence !")
    cm.add_message("player", "Aria", "Je dégaine mon épée.")

    captured_messages: list = []

    async def capture(**kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        return _valid_gm_json()

    with patch.object(gm_agent._client, "chat", new=capture):
        await gm_agent.run_combat_turn(
            game_state={},
            context_manager=cm,
        )

    # system + 2 messages contexte + 1 user prompt
    assert len(captured_messages) >= 4
    assert captured_messages[0]["role"] == "system"


async def test_run_encounter_intro(gm_agent: GMAgent) -> None:
    """run_encounter_intro() produit une GMResponse sans action mécanique."""
    payload = _valid_gm_json(
        narration=(
            "Le brasero dévoile trois bandits autour d'une table renversée. "
            "Le plus grand lève son arbalète : « Reculez ou videz vos bourses. »"
        ),
        mood="tense",
        actions=[],
    )
    with patch.object(gm_agent._client, "chat", new=AsyncMock(return_value=payload)):
        response = await gm_agent.run_encounter_intro(
            game_state={"phase": "ENCOUNTER_START"},
            combatants=[
                {"id": "bandit_1", "name": "Bandit", "hp": 11, "monster_id": "bandit"},
            ],
            messages=[],
        )

    assert isinstance(response, GMResponse)
    assert "«" in response.narration
    assert response.actions == []
    assert response.mood == "tense"


async def test_run_encounter_end(gm_agent: GMAgent) -> None:
    """run_encounter_end() produit une narration post-combat structurée."""
    payload = _valid_gm_json(
        narration="Le silence revient sur les quais, seulement troublé par le clapotis noir.",
        mood="dramatic",
        actions=[
            {
                "type": "scene_layout",
                "target": None,
                "params": {
                    "cols": 6,
                    "rows": 6,
                    "terrain": "dock_aftermath",
                    "pois": [],
                    "exits": [],
                    "party_positions": {},
                },
            }
        ],
    )
    with patch.object(gm_agent._client, "chat", new=AsyncMock(return_value=payload)):
        response = await gm_agent.run_encounter_end(
            game_state={"phase": "encounter_end"},
            combat_summary={
                "enemies_defeated": [{"id": "bandit_1", "name": "Bandit"}],
                "enemies_unresolved": [],
                "previous_scene": {"terrain": "dock"},
            },
            messages=[],
        )

    assert isinstance(response, GMResponse)
    assert "silence" in response.narration
    assert response.actions[0].type == "scene_layout"
    assert response.mood == "dramatic"


# ---------------------------------------------------------------------------
# run_npc_dialogue()
# ---------------------------------------------------------------------------


async def test_run_npc_dialogue(gm_agent: GMAgent) -> None:
    """run_npc_dialogue() génère la réponse d'un PNJ."""
    payload = _valid_gm_json(
        narration="L'aubergiste fronce les sourcils. « On ne sert pas les elfes ici », grogne-t-il."
    )
    with patch.object(gm_agent._client, "chat", new=AsyncMock(return_value=payload)):
        response = await gm_agent.run_npc_dialogue(
            npc_name="Gareth l'Aubergiste",
            npc_personality="Méfiant, rancunier, ancien soldat",
            player_message="Avez-vous une chambre pour la nuit ?",
        )

    assert "aubergiste" in response.narration.lower()


async def test_run_npc_dialogue_injects_scene_anchor(gm_agent: GMAgent) -> None:
    """Le prompt PNJ reçoit le même ancrage de scène que la narration MJ."""
    captured: dict[str, object] = {}

    async def _capture(**kwargs):
        captured["messages"] = kwargs.get("messages", [])
        return _valid_gm_json(narration="Syndra acquiesce. « Posez vos questions. »")

    with patch.object(gm_agent._client, "chat", new=_capture):
        await gm_agent.run_npc_dialogue(
            npc_name="Syndra Silvane",
            npc_personality="Patronne malade, pressée mais courtoise",
            player_message="Je m'approche de Syndra Silvane.",
            game_state={
                "adventure_journal": {
                    "location_place": "Port Nyanzaru",
                    "location_venue": "Résidence de Wakanga O'tamu, Goldenthrone",
                    "time_of_day": "morning",
                    "day_number": 1,
                },
                "current_scene": {
                    "scene_id": "scene_wakanga",
                    "description": "Syndra et Wakanga reçoivent le groupe dans une salle privée.",
                    "pois": [
                        {
                            "id": "syndra_silvane",
                            "name": "Syndra Silvane",
                            "kind": "npc",
                            "icon": "npc",
                        }
                    ],
                },
                "npc_states": {
                    "syndra_silvane": {
                        "name": "Syndra Silvane",
                        "last_location": "scene_wakanga",
                    },
                    "azaka": {
                        "name": "Azaka Stormfang",
                        "last_location": "scene_auberge",
                    },
                },
            },
        )

    prompt = captured["messages"][-1]["content"]
    assert "ANCRAGE DE SCÈNE" in prompt
    assert "Résidence de Wakanga O'tamu" in prompt
    assert "PNJ présents" in prompt
    assert "Syndra Silvane" in prompt
    assert "PNJ absents" in prompt
    assert "Azaka Stormfang" in prompt
    assert "Ne répète pas tout le briefing" in prompt


# ---------------------------------------------------------------------------
# Fallback et robustesse
# ---------------------------------------------------------------------------


async def test_narrate_fallback_on_ollama_error(gm_agent: GMAgent) -> None:
    """narrate() retourne la narration de fallback si Ollama est injoignable."""
    with patch.object(
        gm_agent._client,
        "chat",
        new=AsyncMock(side_effect=OllamaError("Connection refused")),
    ):
        response = await gm_agent.narrate(game_state={})

    assert response.narration == _FALLBACK_NARRATION
    assert response.actions == []


async def test_narrate_fallback_on_non_json_response(gm_agent: GMAgent) -> None:
    """narrate() évite d'afficher une sortie brute non JSON."""
    with patch.object(
        gm_agent._client,
        "chat",
        new=AsyncMock(return_value="Je ne suis pas du JSON. Oops."),
    ):
        response = await gm_agent.narrate(game_state={})

    assert response.narration == _FALLBACK_NARRATION


async def test_narrate_broken_json_extracts_only_narration(gm_agent: GMAgent) -> None:
    """Le fallback ne doit pas afficher les morceaux JSON après actions."""
    raw = '{"narration": "Salut.", "actions": [{"type":'
    with patch.object(gm_agent._client, "chat", new=AsyncMock(return_value=raw)):
        response = await gm_agent.narrate(game_state={})

    assert response.narration == "Salut."
    assert "actions" not in response.narration


async def test_narrate_handles_json_in_markdown_block(gm_agent: GMAgent) -> None:
    """narrate() extrait le JSON d'un bloc markdown si le LLM en génère un."""
    raw = "Voici ma réponse:\n```json\n" + _valid_gm_json() + "\n```"
    with patch.object(gm_agent._client, "chat", new=AsyncMock(return_value=raw)):
        response = await gm_agent.narrate(game_state={})

    assert "forêt" in response.narration


async def test_narrate_missing_narration_field(gm_agent: GMAgent) -> None:
    """narrate() gère une réponse JSON sans le champ 'narration'."""
    payload = json.dumps({"actions": [], "mood": "neutral"})
    with patch.object(gm_agent._client, "chat", new=AsyncMock(return_value=payload)):
        response = await gm_agent.narrate(game_state={})

    # Pas d'exception, retourne quelque chose
    assert isinstance(response, GMResponse)


async def test_narrate_actions_with_missing_fields(gm_agent: GMAgent) -> None:
    """narrate() ignore les actions malformées sans planter."""
    payload = json.dumps({
        "narration": "test",
        "actions": [
            {"type": "roll_request"},  # pas de target ni params -> valeurs par défaut
            "not_a_dict",  # filtré
        ],
        "mood": "neutral",
    })
    with patch.object(gm_agent._client, "chat", new=AsyncMock(return_value=payload)):
        response = await gm_agent.narrate(game_state={})

    assert len(response.actions) == 1
    assert response.actions[0].target is None
    assert response.actions[0].params == {}


# ---------------------------------------------------------------------------
# think() — interface BaseAgent
# ---------------------------------------------------------------------------


async def test_think_delegates_to_narrate_in_exploration(gm_agent: GMAgent) -> None:
    """think() délègue à narrate() pour la phase EXPLORATION."""
    with patch.object(gm_agent._client, "chat", new=AsyncMock(return_value=_valid_gm_json())):
        context = AgentContext(
            session_id="sess_1",
            game_phase="EXPLORATION",
            player_action="Je regarde la carte.",
            game_state={},
        )
        response = await gm_agent.think(context)

    assert "forêt" in response.content


async def test_think_passes_roll_results_to_exploration_narrate(gm_agent: GMAgent) -> None:
    gm_agent.narrate = AsyncMock(return_value=GMResponse(narration="Azaka accepte.", actions=[]))
    context = AgentContext(
        session_id="sess_1",
        game_phase="EXPLORATION",
        player_action="Je demande à Azaka d'être notre guide.",
        game_state={},
        roll_results={"type": "skill_check", "success": True, "total": 19},
    )

    response = await gm_agent.think(context)

    assert response.content == "Azaka accepte."
    gm_agent.narrate.assert_awaited_once()
    assert gm_agent.narrate.await_args.kwargs["roll_results"] == {
        "type": "skill_check",
        "success": True,
        "total": 19,
    }


async def test_think_delegates_to_combat_in_combat(gm_agent: GMAgent) -> None:
    """think() délègue à run_combat_turn() pour la phase COMBAT."""
    combat_payload = _valid_gm_json(narration="Le combat fait rage !")
    with patch.object(gm_agent._client, "chat", new=AsyncMock(return_value=combat_payload)):
        context = AgentContext(
            session_id="sess_1",
            game_phase="COMBAT",
            player_action="J'attaque.",
            game_state={},
        )
        response = await gm_agent.think(context)

    assert "combat" in response.content.lower()
