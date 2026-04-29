from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.schemas import PlayerActionChoice
from app.game.session_manager import ActiveSession
from app.models.session import SessionStatus
from app.services.narrative_flow_service import NarrativeFlowService


def _active_with_companions() -> ActiveSession:
    active = ActiveSession(
        session_id="scene-1",
        phase=SessionStatus.EXPLORATION,
        state_data={
            "characters": {
                "human_1": {"name": "Aria", "is_ai": False},
                "thorin_1": {"name": "Thorin", "is_ai": True},
                "elara_1": {"name": "Elara", "is_ai": True},
            }
        },
    )
    thorin = MagicMock()
    thorin.character_name = "Thorin"
    thorin.respond_to_player = AsyncMock(
        return_value=PlayerActionChoice(
            action_type="talk",
            action_description="Répond à Aria.",
            roleplay_text="Je te couvre, avance prudemment.",
        )
    )
    elara = MagicMock()
    elara.character_name = "Elara"
    elara.respond_to_player = AsyncMock(
        return_value=PlayerActionChoice(
            action_type="talk",
            action_description="Donne son avis.",
            roleplay_text="Les runes méritent qu'on les lise avant d'ouvrir.",
        )
    )
    active.ai_players = {"thorin_1": thorin, "elara_1": elara}
    return active


def _action(content: str, **extra):
    return SimpleNamespace(
        type="action",
        action_type="free_text",
        content=content,
        character_id="human_1",
        target_id=None,
        spell_id=None,
        slot_level=None,
        addressed_to=extra.get("addressed_to"),
        audience=extra.get("audience"),
        scene_id=extra.get("scene_id"),
    )


def test_detects_named_companion_mentions() -> None:
    active = _active_with_companions()
    service = NarrativeFlowService()

    detected = service.detect_audience("@Thorin que penses-tu ?", active)

    assert detected.audience == "companion"
    assert detected.target_ids == ["thorin_1"]


def test_detects_party_prompt() -> None:
    active = _active_with_companions()
    service = NarrativeFlowService()

    detected = service.detect_audience("Compagnons, que fait-on ?", active)

    assert detected.audience == "party"
    assert set(detected.target_ids) == {"thorin_1", "elara_1"}


def test_detects_mixed_world_and_party_prompt() -> None:
    active = _active_with_companions()
    service = NarrativeFlowService()

    detected = service.detect_audience("J'examine la porte, vous me couvrez ?", active)

    assert detected.audience == "mixed"
    assert set(detected.target_ids) == {"thorin_1", "elara_1"}


@pytest.mark.asyncio
async def test_direct_companion_dialogue_does_not_call_gm() -> None:
    active = _active_with_companions()
    resolver = MagicMock()
    resolver.resolve = AsyncMock()
    resolver.social_conclude = AsyncMock()
    published: list[tuple[str, dict]] = []

    async def capture(_session_id, event_type, payload, source=None):
        published.append((event_type, payload))

    with patch("app.services.narrative_flow_service.event_bus.publish_to_session", new=capture):
        exchange = await NarrativeFlowService().handle_exploration_action(
            session_id="scene-1",
            action=_action("@Thorin que penses-tu ?"),
            active=active,
            action_resolver=resolver,
            db=None,
        )

    resolver.resolve.assert_not_called()
    resolver.social_conclude.assert_not_called()
    active.ai_players["thorin_1"].respond_to_player.assert_awaited_once()
    active.ai_players["elara_1"].respond_to_player.assert_not_called()
    assert exchange.audience == "companion"
    assert any(p.get("speaker_id") == "thorin_1" for _, p in published)


@pytest.mark.asyncio
async def test_direct_companion_action_keeps_dialogue_then_calls_gm() -> None:
    active = _active_with_companions()
    active.ai_players["thorin_1"].respond_to_player = AsyncMock(
        return_value=PlayerActionChoice(
            action_type="examine",
            action_description="examine le passage secret pour détecter les pièges",
            roleplay_text=(
                "Thorin s'accroupit à l'entrée du passage. "
                "« Je passe devant, attendez mon signal. »"
            ),
        )
    )
    resolver = MagicMock()
    resolver.resolve = AsyncMock()
    resolver.social_conclude = AsyncMock()
    published: list[tuple[str, dict]] = []

    async def capture(_session_id, event_type, payload, source=None):
        published.append((event_type, payload))

    with patch("app.services.narrative_flow_service.event_bus.publish_to_session", new=capture):
        exchange = await NarrativeFlowService().handle_exploration_action(
            session_id="scene-1",
            action=_action("@Thorin tu peux vérifier le passage ?"),
            active=active,
            action_resolver=resolver,
            db=None,
        )

    resolver.resolve.assert_awaited_once()
    resolver.social_conclude.assert_not_called()
    assert resolver.resolve.await_args.kwargs["action_type"] == "examine"
    assert resolver.resolve.await_args.kwargs["actor_kind"] == "companion"
    assert resolver.resolve.await_args.kwargs["content"] == (
        "Thorin examine le passage secret pour détecter les pièges."
    )
    assert exchange.audience == "companion"
    dialogue_payloads = [
        payload for event_type, payload in published if event_type == "narration"
    ]
    assert dialogue_payloads[-1]["text"] == (
        "Thorin s'accroupit à l'entrée du passage. "
        "« Je passe devant, attendez mon signal. »"
    )


@pytest.mark.asyncio
async def test_party_dialogue_gets_companions_then_gm_conclusion() -> None:
    active = _active_with_companions()
    resolver = MagicMock()
    resolver.resolve = AsyncMock()
    resolver.social_conclude = AsyncMock()

    with patch("app.services.narrative_flow_service.event_bus.publish_to_session", new=AsyncMock()):
        exchange = await NarrativeFlowService().handle_exploration_action(
            session_id="scene-1",
            action=_action("Compagnons, que fait-on ?"),
            active=active,
            action_resolver=resolver,
            db=None,
        )

    resolver.resolve.assert_not_called()
    resolver.social_conclude.assert_awaited_once()
    assert len(exchange.companion_responses) == 2


@pytest.mark.asyncio
async def test_mixed_scene_gets_companions_then_world_arbitration() -> None:
    active = _active_with_companions()
    resolver = MagicMock()
    resolver.resolve = AsyncMock()
    resolver.social_conclude = AsyncMock()

    with patch("app.services.narrative_flow_service.event_bus.publish_to_session", new=AsyncMock()):
        exchange = await NarrativeFlowService().handle_exploration_action(
            session_id="scene-1",
            action=_action("J'examine la porte, vous me couvrez ?"),
            active=active,
            action_resolver=resolver,
            db=None,
        )

    resolver.social_conclude.assert_not_called()
    resolver.resolve.assert_awaited_once()
    assert resolver.resolve.await_args.kwargs["persist_actor_action"] is False
    assert exchange.gm_arbitrated is True
