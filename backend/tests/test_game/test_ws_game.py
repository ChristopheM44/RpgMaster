"""Tests for api/ws_game.py — WebSocket protocol.

Chaque test utilise `ws_client` (fixture sync de test_game/conftest.py).
Les sessions sont créées via l'API HTTP avant chaque connexion WS,
assurant que tout s'exécute dans le même event loop interne du TestClient.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_session(ws_client, name: str = "Test Session") -> str:
    """Crée une session via l'API REST et retourne son id."""
    resp = ws_client.post("/api/sessions/", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _receive_until(ws, expected_type: str, max_messages: int = 8) -> dict:
    """Lit les messages WS jusqu'au type attendu."""
    for _ in range(max_messages):
        data = ws.receive_json()
        if data["event_type"] == expected_type:
            return data
    raise AssertionError(f"Événement '{expected_type}' non reçu dans les {max_messages} messages.")


# ---------------------------------------------------------------------------
# Connection + initial state
# ---------------------------------------------------------------------------


class TestWebSocketConnection:
    def test_connect_unknown_session_closes_with_error(self, ws_client) -> None:
        """Connexion à une session inexistante → message error puis fermeture."""
        with ws_client.websocket_connect("/ws/game/non-existent-id") as ws:
            data = ws.receive_json()
            assert data["event_type"] == "error"

    def test_connect_valid_session_receives_session_state(self, ws_client) -> None:
        session_id = _create_session(ws_client)
        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            data = ws.receive_json()
            assert data["event_type"] == "session_state"
            assert data["session_id"] == session_id
            assert "phase" in data["payload"]
            assert data["payload"]["phase"] == "lobby"


# ---------------------------------------------------------------------------
# Ping / pong
# ---------------------------------------------------------------------------


class TestPingPong:
    def test_ping_receives_pong(self, ws_client) -> None:
        session_id = _create_session(ws_client)
        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["event_type"] == "pong"


# ---------------------------------------------------------------------------
# Join
# ---------------------------------------------------------------------------


class TestJoin:
    def test_join_broadcasts_player_joined(self, ws_client) -> None:
        session_id = _create_session(ws_client)
        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state
            ws.send_json({"type": "join", "character_id": "hero-1"})
            data = ws.receive_json()
            assert data["event_type"] == "player_joined"
            assert data["payload"]["character_id"] == "hero-1"

    def test_join_missing_character_id_returns_error(self, ws_client) -> None:
        session_id = _create_session(ws_client)
        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state
            ws.send_json({"type": "join"})  # character_id manquant
            data = ws.receive_json()
            assert data["event_type"] == "error"


# ---------------------------------------------------------------------------
# Player action
# ---------------------------------------------------------------------------


class TestPlayerAction:
    def test_free_text_action_returns_narration(self, ws_client) -> None:
        session_id = _create_session(ws_client)
        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state
            ws.send_json({
                "type": "action",
                "action_type": "free_text",
                "content": "Je cherche des pièges",
            })
            narration = _receive_until(ws, "narration")
            assert narration["event_type"] == "narration"
            # Le GMAgent génère la narration (ou fallback si Ollama indisponible)
            assert len(narration["payload"]["text"]) > 0

    def test_action_produces_turn_end_event(self, ws_client) -> None:
        session_id = _create_session(ws_client)
        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state
            ws.send_json({
                "type": "action",
                "action_type": "free_text",
                "content": "Je passe prudemment au tour suivant.",
            })
            msg1 = _receive_until(ws, "narration")
            msg2 = _receive_until(ws, "turn_end")
            assert msg1["event_type"] not in ("error",)
            assert msg2["event_type"] == "turn_end"
            assert "turn_number" in msg2["payload"]

    def test_action_increments_turn_number(self, ws_client) -> None:
        session_id = _create_session(ws_client)
        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state
            for _ in range(3):
                ws.send_json({
                    "type": "action",
                    "action_type": "free_text",
                    "content": "Je continue d'explorer.",
                })
                _receive_until(ws, "narration")
                turn_end = _receive_until(ws, "turn_end")
            assert turn_end["payload"]["turn_number"] == 3

    def test_reset_combat_exits_combat_phase(self, ws_client) -> None:
        from app.api import ws_game
        from app.game.turn_manager import TurnEntry
        from app.models.session import SessionStatus

        session_id = _create_session(ws_client)

        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state

            active = ws_game.session_manager.get_session(session_id)
            assert active is not None
            active.phase = SessionStatus.COMBAT
            active.state_data["phase"] = "COMBAT"
            active.state_data["characters"] = {
                "hero-1": {
                    "name": "Thorvald",
                    "level": 1,
                    "hp": 10,
                    "hp_max": 10,
                    "dex": 14,
                    "is_ai": False,
                    "equipment": [],
                }
            }
            active.state_data["combatants"] = {
                "hero-1": {
                    "name": "Thorvald",
                    "hp": 10,
                    "hp_max": 10,
                    "is_player": True,
                    "is_ai": False,
                    "ac": 12,
                },
                "orc_1": {
                    "name": "Orc",
                    "hp": 15,
                    "hp_max": 15,
                    "is_player": False,
                    "is_ai": True,
                    "ac": 13,
                },
            }
            active.turn_manager._order = [
                TurnEntry("hero-1", "Thorvald", 15, True, False),
                TurnEntry("orc_1", "Orc", 12, False, True),
            ]
            active.turn_manager._index = 0

            ws.send_json({
                "type": "action",
                "action_type": "reset_combat",
                "character_id": "hero-1",
            })

            event_types: list[str] = []
            exploration_seen = False
            for _ in range(5):
                evt = ws.receive_json()
                event_types.append(evt["event_type"])
                if evt["event_type"] == "phase_change" and evt["payload"]["phase"] == "exploration":
                    exploration_seen = True
                if evt["event_type"] == "session_state" and evt["payload"]["phase"] == "exploration":
                    break

            assert "combat_end" in event_types
            assert exploration_seen
            assert active.phase == SessionStatus.EXPLORATION

    def test_surrendered_last_bandit_ends_combat(self, ws_client) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from app.agents.schemas import AgentResponse, GMAction, GMResponse
        from app.api import ws_game
        from app.game.action_resolver import ActionResolver
        from app.game.turn_manager import TurnEntry
        from app.models.session import SessionStatus

        session_id = _create_session(ws_client)
        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(return_value=AgentResponse(
            content="Le bandit hésite, son arme tremblante à la main.",
            actions=[
                GMAction(
                    type="roll_request",
                    target="hero-1",
                    params={"ability": "cha", "type": "check", "dc": 1},
                )
            ],
        ))
        mock_gm.narrate_outcome_response = AsyncMock(return_value=GMResponse(
            narration="Le bandit laisse tomber son cimeterre et lève les mains.",
            actions=[
                GMAction(
                    type="combatant_status",
                    target="bandit_1",
                    params={"status": "surrendered", "reason": "reddition"},
                )
            ],
        ))
        previous_resolver = ws_game.action_resolver
        ws_game.action_resolver = ActionResolver(gm_agent=mock_gm)

        try:
            with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
                ws.receive_json()  # session_state

                active = ws_game.session_manager.get_session(session_id)
                assert active is not None
                active.phase = SessionStatus.COMBAT
                active.state_data["phase"] = "COMBAT"
                active.state_data["characters"] = {
                    "hero-1": {
                        "name": "Thorvald",
                        "level": 1,
                        "hp": 10,
                        "hp_max": 10,
                        "ability_scores": {"cha": 16},
                        "is_ai": False,
                        "equipment": [],
                    }
                }
                active.state_data["combatants"] = {
                    "hero-1": {
                        "name": "Thorvald",
                        "hp": 10,
                        "hp_max": 10,
                        "is_player": True,
                        "is_ai": False,
                        "ac": 18,
                    },
                    "bandit_1": {
                        "name": "Bandit 1",
                        "hp": 7,
                        "hp_max": 7,
                        "is_player": False,
                        "is_ai": True,
                        "status": "active",
                        "ac": 12,
                    },
                }
                active.turn_manager._order = [
                    TurnEntry("hero-1", "Thorvald", 15, True, False),
                    TurnEntry("bandit_1", "Bandit 1", 10, False, True),
                ]
                active.turn_manager._index = 0
                active.turn_manager._mode = "combat"
                active.turn_manager._round = 1

                ws.send_json({
                    "type": "action",
                    "action_type": "free_text",
                    "content": "Rends-toi bandit.",
                    "character_id": "hero-1",
                })

                events = []
                for _ in range(18):
                    evt = ws.receive_json()
                    events.append(evt)
                    if evt["event_type"] == "session_state" and evt["payload"]["phase"] == "exploration":
                        break

            event_types = [evt["event_type"] for evt in events]
            assert "combatant_status_changed" in event_types
            assert "combatant_removed" in event_types
            assert "combat_end" in event_types
            assert not any(
                evt["event_type"] == "turn_start"
                and evt["payload"].get("combatant_id") == "bandit_1"
                for evt in events
            )
            assert active.phase == SessionStatus.EXPLORATION
        finally:
            ws_game.action_resolver = previous_resolver


# ---------------------------------------------------------------------------
# Unknown message type
# ---------------------------------------------------------------------------


class TestUnknownMessageType:
    def test_unknown_type_returns_error(self, ws_client) -> None:
        session_id = _create_session(ws_client)
        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state
            ws.send_json({"type": "invalid_type"})
            data = ws.receive_json()
            assert data["event_type"] == "error"
            assert "invalid_type" in data["payload"]["message"]
