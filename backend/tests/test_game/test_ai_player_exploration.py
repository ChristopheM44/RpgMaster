"""Tests pour les compagnons IA en exploration + reprise mi-combat.

Couvre :
1. run_exploration_reactions() — chaque compagnon IA réagit une fois hors combat
2. rebuild_ai_players() — les agents sont restaurés après un redémarrage backend
3. Reprise mid-combat — après open_session, ai_players est peuplé avant le 1er tour IA
4. toggle_ai_control WS message — via TestClient
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.player_agent import PlayerAgent
from app.agents.schemas import PlayerActionChoice, PlayerPersonality
from app.game.ai_player_manager import AIPlayerManager, rebuild_ai_players
from app.game.session_manager import ActiveSession
from app.game.turn_manager import TurnEntry
from app.models.character import Character
from app.models.session import Session, SessionStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _roleplay_json(character_name: str) -> str:
    import json

    return json.dumps(
        {
            "action_type": "talk",
            "action_description": f"{character_name} propose de questionner le contact visible.",
            "target": None,
            "params": {},
            "roleplay_text": (
                f"{character_name} désigne le contact visible. "
                "« Commençons par lui poser des questions précises. »"
            ),
            "inner_reasoning": "Faire avancer la scène par une prise d'information.",
        },
        ensure_ascii=False,
    )


def _attack_roleplay_json(character_name: str) -> str:
    import json

    return json.dumps(
        {
            "action_type": "attack",
            "action_description": f"{character_name} attaque la menace la plus proche.",
            "target": None,
            "params": {},
            "roleplay_text": f"{character_name} dégaine et se jette dans la mêlée.",
            "inner_reasoning": "La situation bascule en combat.",
        },
        ensure_ascii=False,
    )


def _make_exploration_session() -> ActiveSession:
    """ActiveSession en EXPLORATION avec 1 joueur humain + 1 compagnon IA."""
    state: dict[str, Any] = {
        "phase": "EXPLORATION",
        "characters": {
            "human_1": {
                "name": "Aria",
                "is_ai": False,
                "hp": 30,
                "hp_max": 30,
                "personality": ["brave"],
            },
            "ai_1": {
                "name": "Thorin",
                "is_ai": True,
                "hp": 28,
                "hp_max": 28,
                "personality": ["noble"],
            },
        },
    }
    active = ActiveSession(
        session_id="expl_session",
        phase=SessionStatus.EXPLORATION,
        state_data=state,
    )
    active.turn_manager._order = [
        TurnEntry("human_1", "Aria", 0, True, False),
        TurnEntry("ai_1", "Thorin", 0, True, True),
    ]
    return active


# ---------------------------------------------------------------------------
# 1. run_exploration_reactions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exploration_reactions_calls_roleplay_for_ai() -> None:
    """run_exploration_reactions() déclenche le roleplay du compagnon IA.

    Pour un action 'talk', le MJ n'est PAS appelé (pas d'arbitrage nécessaire).
    """
    active = _make_exploration_session()

    thorin_agent = PlayerAgent(
        character_id="ai_1",
        character_name="Thorin",
        personality=PlayerPersonality(traits=["noble"]),
        client=MagicMock(),
    )
    active.ai_players["ai_1"] = thorin_agent

    with patch.object(
        thorin_agent._client, "chat", new=AsyncMock(return_value=_roleplay_json("Thorin"))
    ):
        resolver = MagicMock()
        resolver.resolve = AsyncMock()

        publish = AsyncMock()
        with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=publish):
            ai_manager = AIPlayerManager()
            reacted, responses = await ai_manager.run_exploration_reactions(
                "expl_session", active, resolver, trigger_character_id="human_1"
            )

    assert reacted == 1
    # talk action → MJ non appelé
    resolver.resolve.assert_not_called()
    thinking_flags = [
        call.args[2]["thinking"]
        for call in publish.await_args_list
        if call.args[1] == "ai_thinking"
    ]
    assert thinking_flags == [True, False]
    dialogue_calls = [call for call in publish.await_args_list if call.args[1] == "dialogue"]
    expected_text = (
        "Thorin désigne le contact visible. « Commençons par lui poser des questions précises. »"
    )
    expected_visible_text = (
        "désigne le contact visible. « Commençons par lui poser des questions précises. »"
    )
    assert dialogue_calls[-1].args[2]["text"] == expected_visible_text
    assert dialogue_calls[-1].args[2]["speaker_id"] == "ai_1"
    assert dialogue_calls[-1].args[2]["speaker_kind"] == "companion"
    assert dialogue_calls[-1].args[2]["entry_kind"] == "dialogue"
    assert dialogue_calls[-1].args[2]["scene_id"]
    assert responses == [{"speaker": "Thorin", "text": expected_text}]


@pytest.mark.asyncio
async def test_companion_talk_addressing_present_npc_calls_npc_dialogue_once() -> None:
    """Un compagnon qui pose une vraie question à un PNJ déclenche sa réponse.

    La chaîne s'arrête ensuite : pas de deuxième compagnon automatique dans le
    même passage.
    """
    active = _make_exploration_session()
    active.state_data["current_scene"] = {
        "scene_id": "scene_goldenthrone",
        "pois": [
            {
                "id": "syndra_silvane",
                "name": "Syndra Silvane",
                "kind": "npc",
                "icon": "npc",
            }
        ],
    }
    active.state_data["characters"]["ai_1"]["name"] = "Shade"
    active.turn_manager._order.append(TurnEntry("ai_2", "Elara", 0, True, True))

    shade = MagicMock()
    shade.character_name = "Shade"
    shade.roleplay = AsyncMock(
        return_value=PlayerActionChoice(
            action_type="talk",
            action_description="Interroge Syndra.",
            target="Syndra Silvane",
            roleplay_text=(
                "Shade incline la tête vers l'archimage. "
                "« Archimage, avez-vous une piste plus précise ? »"
            ),
        )
    )
    elara = MagicMock()
    elara.character_name = "Elara"
    elara.roleplay = AsyncMock(
        return_value=PlayerActionChoice(
            action_type="talk",
            action_description="Ajoute un doute.",
            roleplay_text="Elara observe en silence.",
        )
    )
    active.ai_players = {"ai_1": shade, "ai_2": elara}

    resolver = MagicMock()
    resolver.resolve = AsyncMock()
    resolver.resolve_npc_dialogue = AsyncMock()

    with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=AsyncMock()):
        reacted, _ = await AIPlayerManager().run_exploration_reactions(
            "expl_session",
            active,
            resolver,
            trigger_character_id="human_1",
            max_reactors=2,
        )

    assert reacted == 1
    resolver.resolve.assert_not_called()
    resolver.resolve_npc_dialogue.assert_awaited_once()
    assert resolver.resolve_npc_dialogue.await_args.kwargs["character_id"] == "ai_1"
    assert resolver.resolve_npc_dialogue.await_args.kwargs["target_id"] == "syndra_silvane"
    assert "Archimage" in resolver.resolve_npc_dialogue.await_args.kwargs["content"]
    elara.roleplay.assert_not_called()


@pytest.mark.asyncio
async def test_companion_talk_merely_mentioning_npc_does_not_call_npc_dialogue() -> None:
    active = _make_exploration_session()
    active.state_data["current_scene"] = {
        "scene_id": "scene_goldenthrone",
        "pois": [
            {
                "id": "syndra_silvane",
                "name": "Syndra Silvane",
                "kind": "npc",
                "icon": "npc",
            }
        ],
    }
    ai_agent = MagicMock()
    ai_agent.character_name = "Shade"
    ai_agent.roleplay = AsyncMock(
        return_value=PlayerActionChoice(
            action_type="talk",
            action_description="Commente la scène.",
            target=None,
            roleplay_text="Syndra cache-t-elle quelque chose ? Restons attentifs.",
        )
    )
    active.ai_players["ai_1"] = ai_agent

    resolver = MagicMock()
    resolver.resolve = AsyncMock()
    resolver.resolve_npc_dialogue = AsyncMock()

    with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=AsyncMock()):
        reacted, _ = await AIPlayerManager().run_exploration_reactions(
            "expl_session",
            active,
            resolver,
            trigger_character_id="human_1",
        )

    assert reacted == 1
    resolver.resolve.assert_not_called()
    resolver.resolve_npc_dialogue.assert_not_called()


@pytest.mark.asyncio
async def test_companion_environmental_spell_is_arbitrated_with_first_person_visible_text() -> None:
    active = _make_exploration_session()
    active.state_data["current_scene"] = {
        "scene_id": "oasis_corrompue",
        "pois": [
            {
                "id": "eau_noire",
                "name": "Eau noire",
                "kind": "hazard",
                "icon": "trap-danger",
            }
        ],
    }
    ai_agent = MagicMock()
    ai_agent.character_name = "Thorin"
    ai_agent.roleplay = AsyncMock(
        return_value=PlayerActionChoice(
            action_type="cast_spell",
            action_description="lance un trait de feu vers l'eau noire",
            target="eau_noire",
            params={"spell_id": "fire_bolt", "slot_level": 0},
            roleplay_text="Je tends la main vers l'eau noire et je canalise une flamme précise.",
        )
    )
    active.ai_players["ai_1"] = ai_agent

    resolver = MagicMock()
    resolver.resolve = AsyncMock()
    publish = AsyncMock()

    with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=publish):
        reacted, responses = await AIPlayerManager().run_exploration_reactions(
            "expl_session",
            active,
            resolver,
            trigger_character_id="human_1",
        )

    assert reacted == 1
    action_calls = [
        call for call in publish.await_args_list if call.args[2].get("entry_kind") == "action"
    ]
    assert action_calls[-1].args[2]["text"].startswith("Je tends la main")
    assert responses == [
        {
            "speaker": "Thorin",
            "text": "Je tends la main vers l'eau noire et je canalise une flamme précise.",
        }
    ]
    resolver.resolve.assert_awaited_once()
    kwargs = resolver.resolve.await_args.kwargs
    assert kwargs["action_type"] == "cast_spell"
    assert kwargs["target_id"] == "eau_noire"
    assert kwargs["spell_id"] == "fire_bolt"
    assert kwargs["slot_level"] == 0
    assert kwargs["display_text"].startswith("Je tends la main")
    assert kwargs["content"].startswith("Thorin lance un trait de feu")


@pytest.mark.asyncio
async def test_exploration_reactions_hide_unplayed_campaign_context_from_ai() -> None:
    active = _make_exploration_session()
    active.state_data["_gm_prompt_context"] = {"global_secrets": ["SECRET_CHAPITRE"]}
    active.state_data["campaign_context"] = {
        "player_contract": {
            "hook": "Une amie se meurt d'une malédiction liée à Omu.",
            "known_objectives": ["Trouver Omu."],
        },
        "active_chapter": {
            "clues": ["La piste mène à Omu."],
            "complications": ["La malédiction empire."],
        },
        "played_canon": {
            "established_facts": [],
            "player_decisions": [],
            "revealed_secrets": [],
            "rolling_summary": "",
        },
    }
    captured_state: dict[str, Any] = {}
    ai_agent = MagicMock()
    ai_agent.character_name = "Thorin"

    async def capture_roleplay(**kwargs):
        captured_state.update(kwargs["game_state"])
        return PlayerActionChoice(
            action_type="talk",
            action_description="Réagit.",
            roleplay_text="Thorin reste prudent.",
        )

    ai_agent.roleplay = AsyncMock(side_effect=capture_roleplay)
    active.ai_players["ai_1"] = ai_agent
    resolver = MagicMock()
    resolver.resolve = AsyncMock()

    with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=AsyncMock()):
        reacted, _ = await AIPlayerManager().run_exploration_reactions(
            "expl_session",
            active,
            resolver,
            trigger_character_id="human_1",
        )

    assert reacted == 1
    serialized = str(captured_state)
    assert "_gm_prompt_context" not in captured_state
    assert "SECRET_CHAPITRE" not in serialized
    assert "player_contract" not in serialized
    assert "active_chapter" not in serialized
    assert "Omu" not in serialized


@pytest.mark.asyncio
async def test_exploration_reactions_skips_trigger_character() -> None:
    """run_exploration_reactions() ne fait pas agir le personnage déclencheur."""
    active = _make_exploration_session()

    ai_agent = PlayerAgent(
        character_id="ai_1",
        character_name="Thorin",
        personality=PlayerPersonality(traits=["noble"]),
        client=MagicMock(),
    )
    active.ai_players["ai_1"] = ai_agent

    with patch.object(
        ai_agent._client,
        "chat",
        new=AsyncMock(return_value=_roleplay_json("Thorin")),
    ):
        resolver = MagicMock()
        resolver.resolve = AsyncMock()

        with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=AsyncMock()):
            ai_manager = AIPlayerManager()
            # Thorin himself triggers: should skip himself
            reacted, _ = await ai_manager.run_exploration_reactions(
                "expl_session", active, resolver, trigger_character_id="ai_1"
            )

    assert reacted == 0
    resolver.resolve.assert_not_called()


@pytest.mark.asyncio
async def test_exploration_reactions_attack_without_encounter_converts_to_wait() -> None:
    """Sans pending_encounter, une action agressive est remplacée par une hésitation.

    Le compagnon IA ne peut pas introduire unilatéralement une nouvelle menace —
    seul le MJ peut établir un encounter via 'pending_encounter'.
    """
    active = _make_exploration_session()
    # pas de pending_encounter dans state_data

    ai_agent = PlayerAgent(
        character_id="ai_1",
        character_name="Thorin",
        personality=PlayerPersonality(traits=["brave"]),
        client=MagicMock(),
    )
    active.ai_players["ai_1"] = ai_agent

    with patch.object(
        ai_agent._client, "chat", new=AsyncMock(return_value=_attack_roleplay_json("Thorin"))
    ):
        resolver = MagicMock()
        resolver.resolve = AsyncMock()

        publish = AsyncMock()
        with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=publish):
            ai_manager = AIPlayerManager()
            reacted, _ = await ai_manager.run_exploration_reactions(
                "expl_session", active, resolver, trigger_character_id="human_1"
            )

    assert reacted == 1
    assert "pending_phase_transition" not in active.state_data
    resolver.resolve.assert_not_called()
    # Le texte publié doit être celui de l'hésitation, pas l'attaque originale
    narration_calls = [call for call in publish.await_args_list if call.args[1] == "narration"]
    assert narration_calls, "Au moins une narration doit être publiée"
    published_text = narration_calls[-1].args[2]["text"]
    assert "dégainer" in published_text or "méfiant" in published_text


@pytest.mark.asyncio
async def test_exploration_reactions_attack_with_pending_encounter_triggers_combat() -> None:
    """Avec un pending_encounter confirmé par le MJ, une action agressive déclenche COMBAT."""
    active = _make_exploration_session()
    active.state_data["pending_encounter"] = {"monster_ids": ["goblin_1"]}

    ai_agent = PlayerAgent(
        character_id="ai_1",
        character_name="Thorin",
        personality=PlayerPersonality(traits=["brave"]),
        client=MagicMock(),
    )
    active.ai_players["ai_1"] = ai_agent

    with patch.object(
        ai_agent._client, "chat", new=AsyncMock(return_value=_attack_roleplay_json("Thorin"))
    ):
        resolver = MagicMock()
        resolver.resolve = AsyncMock()

        publish = AsyncMock()
        with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=publish):
            ai_manager = AIPlayerManager()
            reacted, responses = await ai_manager.run_exploration_reactions(
                "expl_session", active, resolver, trigger_character_id="human_1"
            )

    assert reacted == 1
    assert active.state_data["pending_phase_transition"] == "COMBAT"
    resolver.resolve.assert_not_called()
    narration_calls = [call for call in publish.await_args_list if call.args[1] == "narration"]
    assert narration_calls[-1].args[2]["text"] == "Thorin dégaine et se jette dans la mêlée."
    assert responses == []


@pytest.mark.asyncio
async def test_exploration_reactions_examine_triggers_gm_arbitrage() -> None:
    """Une action 'examine' déclenche le pipeline MJ (arbitrage monde requis)."""
    import json

    active = _make_exploration_session()
    ai_agent = PlayerAgent(
        character_id="ai_1",
        character_name="Thorin",
        personality=PlayerPersonality(traits=["cautious"]),
        client=MagicMock(),
    )
    active.ai_players["ai_1"] = ai_agent

    examine_json = json.dumps(
        {
            "action_type": "examine",
            "action_description": "Thorin examine la porte suspecte.",
            "target": None,
            "params": {},
            "roleplay_text": "Thorin s'approche lentement et inspecte la porte.",
            "inner_reasoning": "Cherche des pièges.",
        },
        ensure_ascii=False,
    )

    with patch.object(ai_agent._client, "chat", new=AsyncMock(return_value=examine_json)):
        resolver = MagicMock()
        resolver.resolve = AsyncMock()

        publish = AsyncMock()
        with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=publish):
            ai_manager = AIPlayerManager()
            reacted, responses = await ai_manager.run_exploration_reactions(
                "expl_session", active, resolver, trigger_character_id="human_1"
            )

    assert reacted == 1
    resolver.resolve.assert_called_once()
    call_kwargs = resolver.resolve.call_args.kwargs
    assert call_kwargs["character_id"] == "ai_1"
    assert call_kwargs["action_type"] == "examine"
    assert call_kwargs["content"] == "Thorin examine la porte suspecte."

    narration_calls = [call for call in publish.await_args_list if call.args[1] == "narration"]
    assert (
        narration_calls[-1].args[2]["text"] == "Thorin s'approche lentement et inspecte la porte."
    )
    assert call_kwargs["display_text"] == "Thorin s'approche lentement et inspecte la porte."
    assert responses == [
        {"speaker": "Thorin", "text": "Thorin s'approche lentement et inspecte la porte."}
    ]


@pytest.mark.asyncio
async def test_manual_exploration_reactions_use_individual_flow_even_in_sober_mode() -> None:
    """Le mode sobre ne court-circuite plus les réactions individuelles."""
    from app.api import ws_game

    active = _make_exploration_session()
    active.ai_players["ai_1"] = PlayerAgent(
        character_id="ai_1",
        character_name="Thorin",
        personality=PlayerPersonality(traits=["noble"]),
        client=MagicMock(),
    )

    with (
        patch.object(ws_game.session_manager, "get_session", return_value=active),
        patch("app.llm.budget.get_llm_budget_mode", return_value="sober"),
        patch.object(
            AIPlayerManager,
            "run_exploration_reactions",
            new=AsyncMock(return_value=(1, [])),
        ) as reactions,
        patch.object(
            ws_game,
            "_consume_pending_combat_transition",
            new=AsyncMock(),
        ) as consume,
    ):
        await ws_game._handle_trigger_ai_reactions(
            "expl_session",
            db=None,
            trigger_character_id="human_1",
        )

    reactions.assert_awaited_once()
    assert reactions.await_args.args[:3] == (
        "expl_session",
        active,
        ws_game.action_resolver,
    )
    assert reactions.await_args.kwargs["trigger_character_id"] == "human_1"
    consume.assert_awaited_once()


@pytest.mark.asyncio
async def test_exploration_reactions_no_ai_players_returns_zero() -> None:
    """Aucun compagnon IA enregistré → run_exploration_reactions() retourne 0."""
    active = _make_exploration_session()
    # ai_players dict is empty

    resolver = MagicMock()
    resolver.resolve = AsyncMock()

    ai_manager = AIPlayerManager()
    reacted, responses = await ai_manager.run_exploration_reactions(
        "expl_session", active, resolver, trigger_character_id="human_1"
    )

    assert reacted == 0
    assert responses == []
    resolver.resolve.assert_not_called()


# ---------------------------------------------------------------------------
# 2. rebuild_ai_players
# ---------------------------------------------------------------------------


def test_rebuild_ai_players_creates_agents_for_is_ai_characters() -> None:
    """rebuild_ai_players() instancie un PlayerAgent pour chaque personnage is_ai=True."""
    active = _make_exploration_session()
    assert len(active.ai_players) == 0

    created = rebuild_ai_players(active)

    assert created == 1
    assert "ai_1" in active.ai_players
    agent = active.ai_players["ai_1"]
    assert agent.character_name == "Thorin"


def test_rebuild_ai_players_idempotent() -> None:
    """rebuild_ai_players() n'écrase pas un agent déjà enregistré."""
    active = _make_exploration_session()
    rebuild_ai_players(active)
    existing_agent = active.ai_players["ai_1"]

    # Call again — should not replace the existing agent
    rebuild_ai_players(active)
    assert active.ai_players["ai_1"] is existing_agent


def test_rebuild_ai_players_ignores_human_characters() -> None:
    """rebuild_ai_players() ne crée pas d'agent pour les personnages humains."""
    active = _make_exploration_session()
    rebuild_ai_players(active)

    assert "human_1" not in active.ai_players
    assert "ai_1" in active.ai_players


# ---------------------------------------------------------------------------
# 3. Reprise mi-combat — ai_players peuplé avant le 1er tour IA
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_mid_combat_ai_players_populated_before_first_ai_turn() -> None:
    """Simule une reprise de session en combat : rebuild_ai_players() peuple
    ai_players avant le premier appel à process_ai_turns().
    """
    state: dict[str, Any] = {
        "phase": "COMBAT",
        "characters": {
            "human_1": {"name": "Aria", "is_ai": False, "hp": 30, "hp_max": 30},
            "ai_1": {
                "name": "Thorin",
                "is_ai": True,
                "hp": 28,
                "hp_max": 28,
                "personality": ["brave"],
            },
        },
        "combatants": {
            "human_1": {"hp": 30, "is_player": True},
            "ai_1": {"hp": 28, "is_player": True},
        },
    }

    active = ActiveSession(
        session_id="resume_session",
        phase=SessionStatus.COMBAT,
        state_data=state,
    )
    active.turn_manager._order = [
        TurnEntry("ai_1", "Thorin", 18, True, True),
        TurnEntry("human_1", "Aria", 12, True, False),
    ]
    active.turn_manager._index = 0

    # Simulate what open_session does: rebuild_ai_players
    rebuild_ai_players(active)
    assert "ai_1" in active.ai_players, "ai_players must be populated before AI turn"

    agent = active.ai_players["ai_1"]
    import json

    attack_json = json.dumps(
        {
            "action_type": "attack",
            "action_description": "Thorin attaque",
            "target": "human_1",
            "params": {"weapon": "hache"},
            "roleplay_text": "Thorin frappe !",
        }
    )

    with patch.object(agent._client, "chat", new=AsyncMock(return_value=attack_json)):
        resolver = MagicMock()
        resolver.resolve = AsyncMock()

        with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=AsyncMock()):
            ai_manager = AIPlayerManager()
            triggered = await ai_manager.process_ai_turns("resume_session", active, resolver)

    assert triggered == 1
    resolver.resolve.assert_called_once()


# ---------------------------------------------------------------------------
# 4. toggle_ai_control via WebSocket (integration)
# ---------------------------------------------------------------------------


def _create_session_with_character(ws_client) -> tuple[str, str]:
    """Crée une session + un personnage, retourne (session_id, character_id)."""
    resp = ws_client.post("/api/sessions/", json={"name": "Toggle IA Test"})
    assert resp.status_code == 201
    session_id = resp.json()["id"]

    resp = ws_client.post(
        "/api/characters/",
        json={
            "session_id": session_id,
            "name": "Thorvald",
            "char_class": "fighter",
            "species": "human",
            "level": 1,
            "ability_scores": {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 11, "cha": 8},
            "background": "soldier",
            "is_ai": False,
        },
    )
    assert resp.status_code == 201, resp.text
    character_id = resp.json()["id"]
    return session_id, character_id


def test_toggle_ai_control_ws_updates_state(ws_client) -> None:
    """toggle_ai_control WS message → is_ai mis à jour + SESSION_STATE diffusé."""
    session_id, character_id = _create_session_with_character(ws_client)

    # Start the game so the session is opened
    ws_client.post(f"/api/game/{session_id}/start")

    from app.api import ws_game

    with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
        # Consume initial session_state
        data = ws.receive_json()
        assert data["event_type"] == "session_state"

        # Send toggle: make character AI-controlled
        ws.send_json(
            {
                "type": "toggle_ai_control",
                "character_id": character_id,
                "is_ai": True,
            }
        )

        # Consume events until we get a session_state update
        events = []
        for _ in range(5):
            try:
                msg = ws.receive_json()
                events.append(msg)
                if msg.get("event_type") == "session_state":
                    break
            except Exception:
                break

        active = ws_game.session_manager.get_session(session_id)
        assert active is not None
        assert active.state_data["characters"][character_id]["is_ai"] is True
        assert character_id in active.ai_players

    assert any(event.get("event_type") == "session_state" for event in events)


@pytest.mark.asyncio
async def test_sync_ai_control_from_db_repairs_stale_combat_state(db_session) -> None:
    """If REST/DB says a character is AI but the saved combat snapshot is stale,
    the live TurnEntry and combatant payload are repaired before combat proceeds.
    """
    from app.api import ws_game

    session = Session(id="sync_ai_session", name="Sync AI", status=SessionStatus.COMBAT)
    sunwing = Character(
        id="sunwing_1",
        session_id=session.id,
        name="Sunwing",
        char_class="monk",
        species="human",
        level=1,
        is_ai=True,
        ability_scores={"str": 13, "dex": 16, "con": 12, "int": 10, "wis": 14, "cha": 8},
        hp_current=10,
        hp_max=10,
    )
    db_session.add_all([session, sunwing])
    await db_session.commit()

    active = ActiveSession(
        session_id=session.id,
        phase=SessionStatus.COMBAT,
        state_data={
            "characters": {
                "sunwing_1": {
                    "name": "Sunwing",
                    "is_ai": False,
                    "hp": 10,
                    "hp_max": 10,
                },
            },
            "combatants": {
                "sunwing_1": {
                    "name": "Sunwing",
                    "is_player": True,
                    "is_ai": False,
                    "hp": 10,
                    "hp_max": 10,
                },
            },
        },
    )
    active.turn_manager._order = [TurnEntry("sunwing_1", "Sunwing", 13, True, False)]
    active.turn_manager._index = 0
    ws_game.session_manager._sessions[session.id] = active

    try:
        changed = await ws_game._sync_ai_control_from_db(session.id, active, db_session)
    finally:
        ws_game.session_manager._sessions.pop(session.id, None)

    assert changed is True
    assert active.state_data["characters"]["sunwing_1"]["is_ai"] is True
    assert active.state_data["combatants"]["sunwing_1"]["is_ai"] is True
    assert active.turn_manager.current_turn is not None
    assert active.turn_manager.current_turn.is_ai_controlled is True
    assert "sunwing_1" in active.ai_players


# ---------------------------------------------------------------------------
# Tests Wiggly Moore — visibilité PNJ + cap réactions + séquentialité
# ---------------------------------------------------------------------------


def _make_two_ai_session() -> ActiveSession:
    """ActiveSession en EXPLORATION avec 1 joueur humain + 2 compagnons IA."""
    state: dict[str, Any] = {
        "phase": "EXPLORATION",
        "characters": {
            "human_1": {"name": "Aria", "is_ai": False, "hp": 30, "hp_max": 30},
            "ai_1": {
                "name": "Thorin",
                "is_ai": True,
                "hp": 28,
                "hp_max": 28,
                "personality": ["noble"],
            },
            "ai_2": {
                "name": "Shade",
                "is_ai": True,
                "hp": 22,
                "hp_max": 22,
                "personality": ["cautious"],
            },
        },
    }
    active = ActiveSession(
        session_id="two_ai_session",
        phase=SessionStatus.EXPLORATION,
        state_data=state,
    )
    active.turn_manager._order = [
        TurnEntry("human_1", "Aria", 0, True, False),
        TurnEntry("ai_1", "Thorin", 0, True, True),
        TurnEntry("ai_2", "Shade", 0, True, True),
    ]
    return active


def test_anonymize_npc_masks_unknown_npc() -> None:
    """anonymize_npc() masque nom et id d'un PNJ known_to_party=False."""
    from app.game.companion_visibility import anonymize_npc

    npc = {
        "id": "volothamp",
        "name": "Volothamp Geddarm",
        "known_to_party": False,
        "description": "un homme au chapeau à plumes",
    }
    result = anonymize_npc(npc)
    assert result["name"] == "un homme au chapeau à plumes"
    assert "id" not in result
    assert result["known_to_party"] is False


def test_anonymize_npc_keeps_known_npc() -> None:
    """anonymize_npc() ne modifie pas un PNJ known_to_party=True."""
    from app.game.companion_visibility import anonymize_npc

    npc = {
        "id": "volothamp",
        "name": "Volothamp Geddarm",
        "known_to_party": True,
        "description": "un homme au chapeau à plumes",
    }
    result = anonymize_npc(npc)
    assert result["name"] == "Volothamp Geddarm"
    assert result["id"] == "volothamp"


def test_anonymize_npc_treats_absent_known_to_party_as_true() -> None:
    """Sans known_to_party, le NPC est traité comme connu (compat sauvegardes anciennes)."""
    from app.game.companion_visibility import anonymize_npc

    npc = {"id": "azaka", "name": "Azaka Stormfang"}
    result = anonymize_npc(npc)
    assert result["name"] == "Azaka Stormfang"
    assert result["id"] == "azaka"


def test_companion_visible_state_anonymizes_unknown_npc_in_scene() -> None:
    """companion_visible_game_state() filtre les PNJ inconnus dans les POIs de scène."""
    from app.game.companion_visibility import companion_visible_game_state

    state_data = {
        "current_scene": {
            "scene_layout": {
                "pois": [
                    {
                        "id": "volothamp",
                        "name": "Volothamp Geddarm",
                        "kind": "npc",
                        "known_to_party": False,
                        "description": "un homme au chapeau à plumes",
                    },
                    {
                        "id": "tente_bleue",
                        "name": "Tente bleue",
                        "kind": "clue",
                        "description": "Une tente bleue vive.",
                    },
                ]
            }
        },
        "npc_states": {
            "volothamp": {
                "name": "Volothamp Geddarm",
                "attitude": "friendly",
                "known_to_party": False,
                "description": "un homme au chapeau à plumes",
            }
        },
    }
    visible = companion_visible_game_state(state_data)

    # POI NPC anonymisé
    pois = visible["current_scene"]["scene_layout"]["pois"]
    npc_poi = next(p for p in pois if p.get("kind") == "npc")
    assert npc_poi["name"] == "un homme au chapeau à plumes"
    assert "id" not in npc_poi

    # POI clue inchangé
    clue_poi = next(p for p in pois if p.get("kind") == "clue")
    assert clue_poi["id"] == "tente_bleue"

    # npc_states anonymisé
    npc_state = visible["npc_states"]["volothamp"]
    assert npc_state["name"] == "un homme au chapeau à plumes"
    assert "id" not in npc_state


def test_companion_visible_state_anonymizes_unknown_npc_in_root_scene_pois() -> None:
    """La forme canonique current_scene.pois est anonymisée."""
    from app.game.companion_visibility import companion_visible_game_state

    visible = companion_visible_game_state(
        {
            "current_scene": {
                "pois": [
                    {
                        "id": "volothamp",
                        "name": "Volothamp Geddarm",
                        "kind": "npc",
                        "known_to_party": False,
                        "description": "un homme au chapeau à plumes",
                    }
                ]
            }
        }
    )

    npc_poi = visible["current_scene"]["pois"][0]
    assert npc_poi["name"] == "un homme au chapeau à plumes"
    assert "id" not in npc_poi


def test_companion_visible_state_reveals_known_npc() -> None:
    """Quand known_to_party=True, le nom propre du PNJ reste visible."""
    from app.game.companion_visibility import companion_visible_game_state

    state_data = {
        "current_scene": {
            "scene_layout": {
                "pois": [
                    {
                        "id": "azaka",
                        "name": "Azaka Stormfang",
                        "kind": "npc",
                        "known_to_party": True,
                        "description": "guide halfling",
                    },
                ]
            }
        },
        "npc_states": {},
    }
    visible = companion_visible_game_state(state_data)
    pois = visible["current_scene"]["scene_layout"]["pois"]
    npc_poi = next(p for p in pois if p.get("kind") == "npc")
    assert npc_poi["name"] == "Azaka Stormfang"
    assert npc_poi["id"] == "azaka"


@pytest.mark.asyncio
async def test_max_reactors_caps_at_one_in_open_scene() -> None:
    """En mode open_scene (pas d'action joueur récente), un seul compagnon réagit.

    Détection automatique via recent_messages vide → open_scene → max_reactors=1.
    """
    active = _make_two_ai_session()

    for char_id, char_name in [("ai_1", "Thorin"), ("ai_2", "Shade")]:
        agent = PlayerAgent(
            character_id=char_id,
            character_name=char_name,
            personality=PlayerPersonality(traits=["noble"]),
            client=MagicMock(),
        )
        agent._client.chat = AsyncMock(return_value=_roleplay_json(char_name))
        active.ai_players[char_id] = agent

    with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=AsyncMock()):
        reacted, _ = await AIPlayerManager().run_exploration_reactions(
            "two_ai_session", active, MagicMock(), trigger_character_id="human_1"
        )

    assert reacted == 1, "open_scene doit limiter à 1 compagnon"


@pytest.mark.asyncio
async def test_max_reactors_explicit_override() -> None:
    """max_reactors explicite prend le dessus sur la détection automatique."""
    active = _make_two_ai_session()

    for char_id, char_name in [("ai_1", "Thorin"), ("ai_2", "Shade")]:
        agent = PlayerAgent(
            character_id=char_id,
            character_name=char_name,
            personality=PlayerPersonality(traits=["noble"]),
            client=MagicMock(),
        )
        agent._client.chat = AsyncMock(return_value=_roleplay_json(char_name))
        active.ai_players[char_id] = agent

    with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=AsyncMock()):
        reacted, _ = await AIPlayerManager().run_exploration_reactions(
            "two_ai_session",
            active,
            MagicMock(),
            trigger_character_id="human_1",
            max_reactors=2,
        )

    assert reacted == 2, "max_reactors=2 explicite doit permettre les 2 compagnons"


@pytest.mark.asyncio
async def test_single_reactor_rotates_after_previous_spotlight() -> None:
    """Deux réactions successives ne redonnent pas la parole au même compagnon."""
    active = _make_two_ai_session()

    for char_id, char_name in [("ai_1", "Thorin"), ("ai_2", "Shade")]:
        agent = PlayerAgent(
            character_id=char_id,
            character_name=char_name,
            personality=PlayerPersonality(traits=["noble"]),
            client=MagicMock(),
        )
        agent._client.chat = AsyncMock(return_value=_roleplay_json(char_name))
        active.ai_players[char_id] = agent

    with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=AsyncMock()):
        reacted_1, responses_1 = await AIPlayerManager().run_exploration_reactions(
            "two_ai_session",
            active,
            MagicMock(),
            trigger_character_id="human_1",
            max_reactors=1,
        )
        reacted_2, responses_2 = await AIPlayerManager().run_exploration_reactions(
            "two_ai_session",
            active,
            MagicMock(),
            trigger_character_id="human_1",
            max_reactors=1,
        )

    assert reacted_1 == 1
    assert reacted_2 == 1
    assert responses_1[0]["speaker"] == "Thorin"
    assert responses_2[0]["speaker"] == "Shade"


@pytest.mark.asyncio
async def test_follow_up_mode_allows_two_reactors() -> None:
    """En mode follow_up (action joueur dans recent_messages), cap à 2 compagnons."""
    from types import SimpleNamespace

    from app.game.ai_player_manager import _detect_reaction_mode

    # Simuler un message joueur humain dans recent_messages
    player_msg = SimpleNamespace(role=SimpleNamespace(value="player"), metadata={})
    gm_msg = SimpleNamespace(role=SimpleNamespace(value="gm"), metadata={})

    # Dernier non-IA est joueur → follow_up
    assert _detect_reaction_mode([gm_msg, player_msg]) == "follow_up"
    # Dernier non-IA est MJ → open_scene
    assert _detect_reaction_mode([player_msg, gm_msg]) == "open_scene"
    # Vide → open_scene
    assert _detect_reaction_mode([]) == "open_scene"


@pytest.mark.asyncio
async def test_context_reloaded_between_companions() -> None:
    """Le contexte (recent_messages) est rechargé entre deux compagnons IA.

    Le compagnon 2 doit voir la réplique du compagnon 1 dans ses recent_messages.
    """
    from types import SimpleNamespace

    active = _make_two_ai_session()
    captured_messages: list = []

    for char_id, char_name in [("ai_1", "Thorin"), ("ai_2", "Shade")]:
        agent = MagicMock()
        agent.character_name = char_name

        async def make_roleplay(name=char_name):
            return PlayerActionChoice(
                action_type="talk",
                action_description=f"{name} parle.",
                roleplay_text=f"{name} s'avance vers l'inconnu.",
            )

        async def capture_roleplay(name=char_name, **kwargs):
            captured_messages.append((name, list(kwargs.get("messages", []))))
            return PlayerActionChoice(
                action_type="talk",
                action_description=f"{name} parle.",
                roleplay_text=f"{name} s'avance vers l'inconnu.",
            )

        agent.roleplay = AsyncMock(side_effect=capture_roleplay)
        active.ai_players[char_id] = agent

    # Simuler un DB qui retourne de plus en plus de messages à chaque appel.
    call_count = 0
    initial_msg = SimpleNamespace(
        role=SimpleNamespace(value="gm"), metadata={}, content="La scène s'ouvre."
    )
    thorin_msg = SimpleNamespace(
        role=SimpleNamespace(value="player"),
        metadata={"is_ai_player": True},
        content="Thorin s'avance vers l'inconnu.",
        speaker="Thorin",
    )

    async def mock_load_recent(session_id, db):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return [initial_msg]
        return [initial_msg, thorin_msg]

    mock_db = MagicMock()
    resolver = MagicMock()
    resolver.resolve = AsyncMock()

    with (
        patch("app.game.ai_player_manager.event_bus.publish_to_session", new=AsyncMock()),
        patch("app.services.message_service.persist_narration", new=AsyncMock()),
        patch(
            "app.services.message_service.load_recent_messages",
            new=AsyncMock(side_effect=mock_load_recent),
        ),
    ):
        reacted, _ = await AIPlayerManager().run_exploration_reactions(
            "two_ai_session",
            active,
            resolver,
            trigger_character_id="human_1",
            max_reactors=2,
            db=mock_db,
        )

    assert reacted == 2
    # Thorin (premier) a vu le message initial (1 msg)
    thorin_received = captured_messages[0][1]
    assert len(thorin_received) == 1
    # Shade (second) a vu le message de Thorin aussi (2 msgs)
    shade_received = captured_messages[1][1]
    assert len(shade_received) == 2


# ---------------------------------------------------------------------------
# P1 — Garde-fou de transition : un compagnon IA ne franchit pas seul une
# frontière de scène (sortie) avant le joueur humain (chronique « Haut les
# Cœurs » : Shade franchit `exit_to_garden` avant Thorvald, msg 41 → 42).
# ---------------------------------------------------------------------------

_BOUNDARY_SCENE: dict[str, Any] = {
    "current_scene": {
        "exits": [
            {
                "id": "exit_to_garden",
                "label": "Porte du Jardin",
                "leads_to": "Le Jardin Suspendu",
                "element_id": "element_door_garden",
            }
        ],
        "pois": [{"id": "zone_echo", "name": "Centre de la nef"}],
    }
}


def _companion_move(
    *,
    target: str | None,
    description: str = "Le personnage se déplace.",
    roleplay: str = "(avance)",
) -> PlayerActionChoice:
    return PlayerActionChoice(
        action_type="move",
        action_description=description,
        target=target,
        roleplay_text=roleplay,
    )


def test_companion_move_to_exit_id_is_boundary_crossing() -> None:
    action = _companion_move(target="exit_to_garden")
    assert AIPlayerManager._move_crosses_scene_boundary(action, _BOUNDARY_SCENE) is True


def test_companion_move_within_scene_is_not_boundary() -> None:
    # « prend les devants vers le centre de la nef » : intra-scène, jamais bloqué.
    action = _companion_move(target="zone_echo")
    assert AIPlayerManager._move_crosses_scene_boundary(action, _BOUNDARY_SCENE) is False


def test_non_move_action_never_crosses_boundary() -> None:
    action = PlayerActionChoice(
        action_type="examine",
        action_description="examine la porte",
        target="exit_to_garden",
        roleplay_text="(observe la porte)",
    )
    assert AIPlayerManager._move_crosses_scene_boundary(action, _BOUNDARY_SCENE) is False


def test_companion_move_matches_exit_by_label_in_text() -> None:
    # Pas d'id en cible, mais le texte nomme la sortie : on bloque quand même.
    action = _companion_move(
        target=None, roleplay="(se faufile par la Porte du Jardin avant les autres)"
    )
    assert AIPlayerManager._move_crosses_scene_boundary(action, _BOUNDARY_SCENE) is True


def test_human_led_transition_true_when_player_travels() -> None:
    assert (
        AIPlayerManager._human_led_transition("en route vers le Jardin Suspendu", _BOUNDARY_SCENE)
        is True
    )


def test_human_led_transition_false_for_non_travel_action() -> None:
    # Le rituel de sang de Thorvald (msg 39) n'est PAS un voyage : un compagnon ne
    # doit pas enchaîner en franchissant le seuil (msg 41 doit être bloqué).
    assert (
        AIPlayerManager._human_led_transition(
            "j'applique ma paume ensanglantée contre le bronze des sculptures",
            _BOUNDARY_SCENE,
        )
        is False
    )


def test_human_led_transition_false_when_no_action_text() -> None:
    assert AIPlayerManager._human_led_transition(None, _BOUNDARY_SCENE) is False
