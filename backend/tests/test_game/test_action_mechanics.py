from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.game.action_mechanics import ActionMechanics
from app.game.action_resolver import ActionResolver
from app.game.roll_executor import execute_roll_request
from app.game.session_manager import ActiveSession
from app.models.session import SessionStatus


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

    assert not isinstance(resolver, ActionMechanics)
    assert resolver._resolve_generic_roll("test")["type"] == "generic_roll"


def test_roll_executor_supports_social_target_metadata() -> None:
    active = SimpleNamespace(
        state_data={
            "characters": {
                "hero-1": {
                    "name": "Aria",
                    "ability_scores": {"cha": 14},
                    "level": 1,
                    "skill_proficiencies": ["persuasion"],
                }
            }
        }
    )

    event = execute_roll_request(
        {"skill": "persuasion", "dc": 10, "social_target": "goblin-1"},
        "hero-1",
        active,
    )

    assert event is not None
    assert event["character_id"] == "hero-1"
    assert event["social_target_id"] == "goblin-1"


@pytest.mark.asyncio
async def test_action_mechanics_resolves_spell_from_caster_snapshot_without_db() -> None:
    active = ActiveSession(session_id="session-1", phase=SessionStatus.COMBAT)
    active.state_data["combatants"] = {"goblin-1": {"ac": 10}}

    result = await ActionMechanics()._resolve_cast_spell(
        "session-1",
        "hero-1",
        "fire_bolt",
        None,
        "goblin-1",
        active,
        {
            "char_class": "wizard",
            "level": 1,
            "ability_scores": {"int": 16},
            "slots_remaining": {},
        },
    )

    assert result["type"] == "cast_spell"
    assert result["spell_id"] == "fire_bolt"
    assert "summary" in result
