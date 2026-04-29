from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.combat_gm_agent import CombatGMAgent
from app.agents.schemas import AgentResponse
from app.game.action_resolver import ActionResolver
from app.game.session_manager import ActiveSession
from app.models.session import SessionStatus


@pytest.mark.asyncio
async def test_combat_gm_uses_compact_state_in_prompt() -> None:
    agent = CombatGMAgent(client=MagicMock())
    captured_messages = []

    async def capture(messages, temperature, max_tokens):
        captured_messages.extend(messages)
        return json.dumps({"narration": "Le coup fend l'air.", "actions": []})

    with patch.object(agent._client, "chat", new=AsyncMock(side_effect=capture)):
        await agent.run_combat_turn(
            game_state={
                "phase": "COMBAT",
                "combatants": {
                    "hero_1": {
                        "name": "Aria",
                        "is_player": True,
                        "hp": 8,
                        "hp_max": 12,
                        "inventory": ["ne doit pas fuiter"],
                        "private_notes": "secret",
                    }
                },
                "campaign_context": {"secret": "ne doit pas fuiter"},
            },
            player_action="Aria attaque.",
            roll_results={"hit": False},
        )

    prompt = captured_messages[-1]["content"]
    assert "Aria" in prompt
    assert "private_notes" not in prompt
    assert "campaign_context" not in prompt


@pytest.mark.asyncio
async def test_action_resolver_routes_combat_to_combat_gm() -> None:
    narrative_gm = MagicMock()
    narrative_gm.think = AsyncMock(
        return_value=AgentResponse(content="Narration exploration", actions=[])
    )
    combat_gm = MagicMock()
    combat_gm.think = AsyncMock(return_value=AgentResponse(content="Narration combat", actions=[]))

    active = ActiveSession(
        session_id="combat-route",
        phase=SessionStatus.COMBAT,
        state_data={
            "characters": {"hero_1": {"name": "Aria"}},
            "combatants": {
                "hero_1": {"name": "Aria", "is_player": True, "hp": 10, "ac": 14},
                "goblin_1": {"name": "Gobelin", "is_player": False, "hp": 7, "ac": 12},
            },
        },
    )

    published: list[tuple[str, dict]] = []

    async def capture(_session_id, event_type, payload, source=None):
        published.append((event_type, payload))

    resolver = ActionResolver(gm_agent=narrative_gm, combat_gm_agent=combat_gm)
    with patch("app.game.action_resolver.event_bus.publish_to_session", new=capture), patch(
        "app.game.action_resolver.tts_router.synthesize_and_broadcast",
        new=AsyncMock(),
    ):
        await resolver.resolve(
            session_id="combat-route",
            action_type="free_text",
            content="Je tente de l'intimider.",
            character_id="hero_1",
            target_id=None,
            active=active,
            db=None,
        )

    narrative_gm.think.assert_not_called()
    combat_gm.think.assert_awaited_once()
    assert any(payload.get("text") == "Narration combat" for _, payload in published)
