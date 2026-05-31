from __future__ import annotations

import random

from app.game.session_manager import ActiveSession
from app.game.stealth_resolution import resolve_stealth_event
from app.models.session import SessionStatus


def _active() -> ActiveSession:
    return ActiveSession(
        session_id="stealth-test",
        phase=SessionStatus.EXPLORATION,
        state_data={
            "characters": {
                "thorvald": {
                    "name": "Thorvald",
                    "level": 1,
                    "ability_scores": {"wis": 14},
                    "skill_proficiencies": ["perception"],
                },
                "oaken": {
                    "name": "Oaken",
                    "level": 1,
                    "ability_scores": {"wis": 20},
                },
                "solana": {
                    "name": "Solana",
                    "level": 1,
                    "ability_scores": {"wis": 10},
                },
            },
            "npc_states": {
                "shadow": {"name": "Ombre"},
            },
        },
    )


def test_stealth_event_noticed_by_observers_above_total() -> None:
    result = resolve_stealth_event(
        _active(),
        {
            "actor_id": "shadow",
            "actor_kind": "npc",
            "event_type": "escape",
            "stealth_total_override": 13,
        },
    )

    assert result["stealth_succeeded"] is False
    assert [observer["name"] for observer in result["noticed_by"]] == ["Thorvald", "Oaken"]


def test_stealth_event_equal_passive_perception_succeeds() -> None:
    result = resolve_stealth_event(
        _active(),
        {
            "actor_id": "shadow",
            "actor_kind": "npc",
            "event_type": "hide",
            "stealth_total_override": 15,
        },
    )

    assert result["stealth_succeeded"] is True
    assert result["noticed_by"] == []


def test_stealth_event_supports_deprecated_dc_override_alias() -> None:
    result = resolve_stealth_event(
        _active(),
        {
            "actor_id": "shadow",
            "actor_kind": "npc",
            "event_type": "abduction",
            "dc_override": 9,
        },
    )

    assert result["total"] == 9
    assert result["stealth_succeeded"] is False


def test_stealth_event_rolls_modifier_with_advantage() -> None:
    result = resolve_stealth_event(
        _active(),
        {
            "actor_id": "shadow",
            "actor_kind": "npc",
            "event_type": "move_unnoticed",
            "stealth_modifier": 4,
            "advantage": True,
        },
        rng=random.Random(7),
    )

    assert len(result["rolls"]) == 2
    assert result["d20"] == max(result["rolls"])
    assert result["modifier"] == 4
    assert result["total"] == result["d20"] + 4
