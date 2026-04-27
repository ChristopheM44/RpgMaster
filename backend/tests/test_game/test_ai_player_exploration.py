"""Tests pour les compagnons IA en exploration + reprise mi-combat.

Couvre :
1. run_exploration_reactions() — chaque compagnon IA réagit une fois hors combat
2. rebuild_ai_players() — les agents sont restaurés après un redémarrage backend
3. Reprise mid-combat — après open_session, ai_players est peuplé avant le 1er tour IA
4. toggle_ai_control WS message — via TestClient
"""
from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.player_agent import PlayerAgent
from app.agents.schemas import PlayerPersonality
from app.game.ai_player_manager import AIPlayerManager, rebuild_ai_players
from app.game.session_manager import ActiveSession
from app.game.turn_manager import TurnEntry
from app.models.character import Character
from app.models.session import Session
from app.models.session import SessionStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _roleplay_json(character_name: str) -> str:
    import json
    return json.dumps({
        "action_type": "talk",
        "action_description": f"{character_name} commente la situation.",
        "target": None,
        "params": {},
        "roleplay_text": f"{character_name} regarde autour de lui, méfiant.",
        "inner_reasoning": "Observer l'environnement.",
    }, ensure_ascii=False)


def _attack_roleplay_json(character_name: str) -> str:
    import json
    return json.dumps({
        "action_type": "attack",
        "action_description": f"{character_name} attaque la menace la plus proche.",
        "target": None,
        "params": {},
        "roleplay_text": f"{character_name} dégaine et se jette dans la mêlée.",
        "inner_reasoning": "La situation bascule en combat.",
    }, ensure_ascii=False)


def _make_exploration_session() -> ActiveSession:
    """ActiveSession en EXPLORATION avec 1 joueur humain + 1 compagnon IA."""
    state: Dict[str, Any] = {
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
    narration_calls = [
        call for call in publish.await_args_list if call.args[1] == "narration"
    ]
    assert narration_calls[-1].args[2]["text"] == "Thorin regarde autour de lui, méfiant."
    assert responses == [
        {"speaker": "Thorin", "text": "Thorin regarde autour de lui, méfiant."}
    ]


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

    with patch.object(ai_agent._client, "chat", new=AsyncMock(return_value=_roleplay_json("Thorin"))):
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
    narration_calls = [
        call for call in publish.await_args_list if call.args[1] == "narration"
    ]
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
    narration_calls = [
        call for call in publish.await_args_list if call.args[1] == "narration"
    ]
    assert narration_calls[-1].args[2]["text"] == "Thorin attaque la menace la plus proche."
    assert "se jette dans la mêlée" not in narration_calls[-1].args[2]["text"]
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

    examine_json = json.dumps({
        "action_type": "examine",
        "action_description": "Thorin examine la porte suspecte.",
        "target": None,
        "params": {},
        "roleplay_text": "Thorin s'approche lentement et inspecte la porte.",
        "inner_reasoning": "Cherche des pièges.",
    }, ensure_ascii=False)

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
    assert call_kwargs["content"] == "[Compagnon IA] Thorin examine la porte suspecte."

    narration_calls = [
        call for call in publish.await_args_list if call.args[1] == "narration"
    ]
    assert narration_calls[-1].args[2]["text"] == "Thorin examine la porte suspecte."
    assert "s'approche lentement" not in narration_calls[-1].args[2]["text"]
    assert responses == [
        {"speaker": "Thorin", "text": "Thorin examine la porte suspecte."}
    ]


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
    state: Dict[str, Any] = {
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
    attack_json = json.dumps({
        "action_type": "attack",
        "action_description": "Thorin attaque",
        "target": "human_1",
        "params": {"weapon": "hache"},
        "roleplay_text": "Thorin frappe !",
    })

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

    resp = ws_client.post("/api/characters/", json={
        "session_id": session_id,
        "name": "Thorvald",
        "char_class": "fighter",
        "species": "human",
        "level": 1,
        "ability_scores": {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 11, "cha": 8},
        "background": "soldier",
        "is_ai": False,
    })
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
        ws.send_json({
            "type": "toggle_ai_control",
            "character_id": character_id,
            "is_ai": True,
        })

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
