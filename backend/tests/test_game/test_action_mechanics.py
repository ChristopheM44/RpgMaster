from __future__ import annotations

from unittest.mock import AsyncMock

from app.game.action_mechanics import ActionMechanics
from app.game.action_resolver import ActionResolver


def test_action_mechanics_normalizes_attack_roll_event() -> None:
    event = ActionMechanics()._normalize_roll_event(
        {
            "type": "attack",
            "d20_roll": 13,
            "attack_total": 18,
            "summary": "Attaque : 18 touche",
            "hit": True,
        }
    )

    assert event == {
        "dice_notation": "1d20",
        "rolls": [13],
        "total": 18,
        "modifier": 5,
        "label": "Attaque : 18 touche",
        "success": True,
    }


def test_action_resolver_keeps_action_mechanics_facade() -> None:
    resolver = ActionResolver(gm_agent=AsyncMock())

    assert isinstance(resolver, ActionMechanics)
    assert resolver._resolve_generic_roll("test")["type"] == "generic_roll"
