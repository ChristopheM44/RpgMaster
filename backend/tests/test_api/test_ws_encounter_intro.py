from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agents.schemas import GMResponse
from app.api.ws_handlers.encounter_intro import (
    generate_encounter_intro,
    should_pause_for_encounter_intro,
)
from app.game.event_bus import EventType


class _EventBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    async def publish_to_session(
        self,
        session_id: str,
        event_type: str,
        payload: dict,
        *,
        source: str | None = None,
    ) -> None:
        self.published.append((event_type, payload))


class _GmAgent:
    async def run_encounter_intro(self, **kwargs) -> GMResponse:
        assert kwargs["combatants"][0]["id"] == "goblin_1"
        assert kwargs["combatants"][0]["name"] == "Goblin"
        return GMResponse(narration="Le gobelin leve sa lame.", start_mode="pause")


@pytest.mark.asyncio
async def test_generate_encounter_intro_sets_start_mode_and_thinking_events() -> None:
    active = SimpleNamespace(state_data={})
    bus = _EventBus()

    async def load_recent_messages(session_id, db):
        return []

    intro = await generate_encounter_intro(
        "session-1",
        active,
        None,
        {
            "hero-1": {"is_player": True, "name": "Aria"},
            "goblin_1": {"is_player": False, "name": "Goblin"},
        },
        gm_agent=_GmAgent(),
        event_bus=bus,
        load_recent_messages=load_recent_messages,
    )

    assert intro == "Le gobelin leve sa lame."
    assert active.state_data["_encounter_intro_start_mode"] == "pause"
    assert [event_type for event_type, _ in bus.published] == [
        EventType.AI_THINKING,
        EventType.AI_THINKING,
    ]


def test_should_pause_for_encounter_intro_ignores_immediate_attacks() -> None:
    assert should_pause_for_encounter_intro("Halte, pose tes armes !")
    assert not should_pause_for_encounter_intro("Les gobelins chargent et frappent.")
