"""Tests for conservative combat-start heuristics."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.ws_schemas import PlayerActionMessage
from app.game.combat_triggers import (
    infer_monster_ids_from_text,
    is_aggressive_player_intent,
    prime_combat_from_aggressive_action,
)
from app.game.session_manager import ActiveSession
from app.models.session import SessionStatus


def test_tactical_melee_wording_is_aggressive_intent() -> None:
    assert is_aggressive_player_intent(
        "free_text",
        "Cible prioritaire : attaque en melee.",
    )
    assert is_aggressive_player_intent(
        "free_text",
        "Cible prioritaire : attaque en mêlée.",
    )


def test_vague_text_without_attack_or_target_does_not_prime_combat() -> None:
    active = ActiveSession(
        session_id="session-1",
        phase=SessionStatus.EXPLORATION,
        state_data={"phase": "exploration"},
    )

    primed = prime_combat_from_aggressive_action(
        active,
        action_type="free_text",
        content="Je regarde le quai et j'attends.",
    )

    assert primed is False
    assert "pending_phase_transition" not in active.state_data
    assert "pending_encounter" not in active.state_data


def test_aggressive_text_without_pending_encounter_or_target_stays_conservative() -> None:
    active = ActiveSession(
        session_id="session-1",
        phase=SessionStatus.EXPLORATION,
        state_data={"phase": "exploration"},
    )

    primed = prime_combat_from_aggressive_action(
        active,
        action_type="free_text",
        content="Cible prioritaire : attaque en mêlée.",
    )

    assert primed is False
    assert "pending_phase_transition" not in active.state_data
    assert "pending_encounter" not in active.state_data


def test_zhentarim_alias_maps_to_bandit() -> None:
    assert infer_monster_ids_from_text("L'emissaire Zhentarim tire son couteau.") == [
        "bandit"
    ]


@pytest.mark.asyncio
async def test_dispatch_tactical_attack_from_encounter_start_opens_combat() -> None:
    from app.api import ws_game

    active = ActiveSession(
        session_id="session-1",
        phase=SessionStatus.ENCOUNTER_START,
        state_data={
            "phase": "encounter_start",
            "pending_encounter": {
                "monster_ids": ["bandit"],
                "intro_played": True,
                "intro_text": "L'emissaire Zhentarim exige que les armes tombent.",
            },
            "characters": {
                "hero-1": {
                    "name": "Thorvald",
                    "level": 1,
                    "hp": 10,
                    "hp_max": 10,
                    "dex": 12,
                    "is_ai": False,
                    "equipment": [],
                },
            },
        },
    )
    action = PlayerActionMessage(
        type="action",
        action_type="free_text",
        content="Cible prioritaire : attaque en mêlée.",
        character_id="hero-1",
    )
    db = MagicMock()
    resolver = MagicMock()
    resolver.resolve = AsyncMock()
    start_combat = AsyncMock()

    with patch.object(ws_game.session_manager, "get_session", return_value=active), \
        patch.object(ws_game.session_manager, "save_state", new=AsyncMock()), \
        patch.object(ws_game, "_handle_start_combat", new=start_combat), \
        patch.object(ws_game, "action_resolver", resolver):
        await ws_game._dispatch_action("session-1", action, db)

    start_combat.assert_awaited_once_with(
        "session-1",
        active,
        db,
        encounter_id=None,
        force=True,
    )
    resolver.resolve.assert_not_awaited()
    assert "pending_phase_transition" not in active.state_data
