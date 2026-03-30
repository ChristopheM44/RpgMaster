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
            narration = ws.receive_json()
            assert narration["event_type"] == "narration"
            # Le GMAgent génère la narration (ou fallback si Ollama indisponible)
            assert len(narration["payload"]["text"]) > 0

    def test_action_produces_turn_end_event(self, ws_client) -> None:
        session_id = _create_session(ws_client)
        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state
            ws.send_json({"type": "action", "action_type": "end_turn"})
            msg1 = ws.receive_json()  # narration
            msg2 = ws.receive_json()  # turn_end
            assert msg1["event_type"] not in ("error",)
            assert msg2["event_type"] == "turn_end"
            assert "turn_number" in msg2["payload"]

    def test_action_increments_turn_number(self, ws_client) -> None:
        session_id = _create_session(ws_client)
        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state
            for _ in range(3):
                ws.send_json({"type": "action", "action_type": "end_turn"})
                ws.receive_json()  # narration
                turn_end = ws.receive_json()
            assert turn_end["payload"]["turn_number"] == 3


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
