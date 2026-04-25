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
from app.game.ai_player_manager import AIPlayerManager, rebuild_ai_players, register_ai_player
from app.game.session_manager import ActiveSession
from app.game.turn_manager import TurnEntry
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
    """run_exploration_reactions() déclenche le roleplay du compagnon IA."""
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

        with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=AsyncMock()):
            ai_manager = AIPlayerManager()
            reacted = await ai_manager.run_exploration_reactions(
                "expl_session", active, resolver, trigger_character_id="human_1"
            )

    assert reacted == 1
    resolver.resolve.assert_called_once()
    call_kwargs = resolver.resolve.call_args.kwargs
    assert call_kwargs["character_id"] == "ai_1"
    assert call_kwargs["action_type"] == "free_action"


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
            reacted = await ai_manager.run_exploration_reactions(
                "expl_session", active, resolver, trigger_character_id="ai_1"
            )

    assert reacted == 0
    resolver.resolve.assert_not_called()


@pytest.mark.asyncio
async def test_exploration_reactions_no_ai_players_returns_zero() -> None:
    """Aucun compagnon IA enregistré → run_exploration_reactions() retourne 0."""
    active = _make_exploration_session()
    # ai_players dict is empty

    resolver = MagicMock()
    resolver.resolve = AsyncMock()

    ai_manager = AIPlayerManager()
    reacted = await ai_manager.run_exploration_reactions(
        "expl_session", active, resolver, trigger_character_id="human_1"
    )

    assert reacted == 0
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

    # Verify the character is now AI in the DB
    resp = ws_client.get(f"/api/characters/{character_id}")
    assert resp.status_code == 200
    assert resp.json()["is_ai"] is True
