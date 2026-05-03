from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api import ws_game
from app.api.ws_handlers.combat import combat_target_id
from app.api.ws_schemas import PlayerActionMessage
from app.models.session import SessionStatus


def test_combat_target_id_selects_single_npc_for_social_text() -> None:
    active = SimpleNamespace(
        state_data={
            "combatants": {
                "hero-1": {"is_player": True, "hp": 7},
                "goblin-1": {"is_player": False, "hp": 3, "status": "active"},
            }
        }
    )
    action = PlayerActionMessage(
        type="action",
        action_type="free_text",
        content="Je lui crie: rends-toi!",
        character_id="hero-1",
    )

    assert combat_target_id(action, active) == "goblin-1"


@pytest.mark.asyncio
async def test_trigger_ai_reactions_combat_uses_unified_turn_loop_for_monsters(
    monkeypatch,
) -> None:
    active = SimpleNamespace(
        phase=SessionStatus.COMBAT,
        ai_players={},
        turn_manager=SimpleNamespace(
            current_turn=SimpleNamespace(is_ai_controlled=True),
        ),
    )
    handle_ai_turns = AsyncMock()
    monkeypatch.setattr(ws_game.session_manager, "get_session", lambda session_id: active)
    monkeypatch.setattr(ws_game, "_handle_ai_turns", handle_ai_turns)

    await ws_game._handle_trigger_ai_reactions("session-1", db=None)

    handle_ai_turns.assert_awaited_once_with("session-1", active, None)
