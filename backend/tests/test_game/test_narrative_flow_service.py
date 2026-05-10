from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.schemas import GMResponse, PlayerActionChoice
from app.game.action_resolver import ActionResolver
from app.game.event_bus import EventType
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


def _add_third_companion(active: ActiveSession) -> None:
    solana = MagicMock()
    solana.character_name = "Solana"
    solana.respond_to_player = AsyncMock(
        return_value=PlayerActionChoice(
            action_type="talk",
            action_description="Propose une alternative.",
            roleplay_text="Je chercherais une autre piste avant de décider.",
        )
    )
    active.ai_players["solana_1"] = solana
    active.state_data["characters"]["solana_1"] = {"name": "Solana", "is_ai": True}


def _action(content: str, **extra):
    return SimpleNamespace(
        type="action",
        action_type="free_text",
        content=content,
        character_id="human_1",
        target_id=extra.get("target_id"),
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
async def test_companion_dialogue_strips_gm_owned_world_result() -> None:
    active = _active_with_companions()
    active.ai_players["thorin_1"].character_name = "Oaken"
    active.ai_players["thorin_1"].respond_to_player = AsyncMock(
        return_value=PlayerActionChoice(
            action_type="talk",
            action_description="Appuie son propos.",
            roleplay_text=(
                "Je pose une main sur la table, le bois craque sous mes doigts. "
                "« Nous ne sommes pas des touristes, Azaka. »"
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
        await NarrativeFlowService().handle_exploration_action(
            session_id="scene-1",
            action=_action("@Oaken que dis-tu ?", addressed_to="thorin_1"),
            active=active,
            action_resolver=resolver,
            db=None,
        )

    dialogue_payload = next(
        payload for event_type, payload in published
        if event_type == "narration" and payload.get("speaker") == "Oaken"
    )
    assert "bois craque" not in dialogue_payload["text"]
    assert "pose une main sur la table" in dialogue_payload["text"]
    assert "Nous ne sommes pas des touristes" in dialogue_payload["text"]


@pytest.mark.asyncio
async def test_companion_state_hides_unplayed_campaign_hook() -> None:
    active = _active_with_companions()
    active.state_data["campaign_context"] = {
        "player_contract": {
            "hook": "Une amie se meurt d'une malédiction liée à Omu.",
            "known_objectives": ["Trouver Omu."],
        },
        "active_chapter": {
            "clues": ["La piste mène à Omu."],
            "complications": ["La malédiction empire."],
            "possible_exits": ["Partir vers la jungle."],
        },
        "known_quests": [
            {
                "id": "omu",
                "title": "Sauver l'amie mourante",
                "summary": "Omu est la source du mal.",
            }
        ],
        "played_canon": {
            "established_facts": [],
            "player_decisions": [],
            "revealed_secrets": [],
            "rolling_summary": "",
        },
    }
    captured_state: dict = {}

    async def capture_state(**kwargs):
        captured_state.update(kwargs["game_state"])
        return PlayerActionChoice(
            action_type="talk",
            action_description="Répond prudemment.",
            roleplay_text="Je ne sais que ce que nous avons vu.",
        )

    active.ai_players["thorin_1"].respond_to_player = AsyncMock(side_effect=capture_state)
    resolver = MagicMock()
    resolver.resolve = AsyncMock()
    resolver.social_conclude = AsyncMock()

    with patch("app.services.narrative_flow_service.event_bus.publish_to_session", new=AsyncMock()):
        await NarrativeFlowService().handle_exploration_action(
            session_id="scene-1",
            action=_action("@Thorin que sais-tu d'Omu ?"),
            active=active,
            action_resolver=resolver,
            db=None,
        )

    serialized = json.dumps(captured_state, ensure_ascii=False)
    assert "player_contract" not in serialized
    assert "active_chapter" not in serialized
    assert "known_quests" not in serialized
    assert "Omu" not in serialized
    assert "amie se meurt" not in serialized


@pytest.mark.asyncio
async def test_companion_state_keeps_played_campaign_facts() -> None:
    active = _active_with_companions()
    active.state_data["campaign_context"] = {
        "player_contract": {
            "hook": "Une amie se meurt d'une malédiction liée à Omu.",
        },
        "played_canon": {
            "established_facts": ["Le MJ a révélé qu'une amie se meurt près d'Omu."],
            "player_decisions": [],
            "revealed_secrets": [],
            "rolling_summary": "Le groupe a accepté d'enquêter sur Omu.",
        },
    }
    captured_state: dict = {}

    async def capture_state(**kwargs):
        captured_state.update(kwargs["game_state"])
        return PlayerActionChoice(
            action_type="talk",
            action_description="Répond.",
            roleplay_text="Ce point a été établi devant nous.",
        )

    active.ai_players["thorin_1"].respond_to_player = AsyncMock(side_effect=capture_state)
    resolver = MagicMock()
    resolver.resolve = AsyncMock()
    resolver.social_conclude = AsyncMock()

    with patch("app.services.narrative_flow_service.event_bus.publish_to_session", new=AsyncMock()):
        await NarrativeFlowService().handle_exploration_action(
            session_id="scene-1",
            action=_action("@Thorin que sais-tu d'Omu ?"),
            active=active,
            action_resolver=resolver,
            db=None,
        )

    serialized = json.dumps(captured_state, ensure_ascii=False)
    assert "player_contract" not in serialized
    assert "Le MJ a révélé" in serialized
    assert "enquêter sur Omu" in serialized


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
async def test_party_dialogue_limits_group_companion_responses() -> None:
    active = _active_with_companions()
    _add_third_companion(active)
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

    resolver.social_conclude.assert_awaited_once()
    assert len(exchange.companion_responses) == 2
    active.ai_players["solana_1"].respond_to_player.assert_not_called()


@pytest.mark.asyncio
async def test_mixed_scene_gets_companions_then_world_arbitration() -> None:
    active = _active_with_companions()
    resolver = MagicMock()
    resolver.resolve = AsyncMock()
    resolver.social_conclude = AsyncMock()
    resolver.resolve_npc_dialogue = AsyncMock()

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
    resolver.resolve_npc_dialogue.assert_not_called()
    assert resolver.resolve.await_args.kwargs["persist_actor_action"] is False
    assert exchange.gm_arbitrated is True


@pytest.mark.asyncio
async def test_world_social_action_calls_npc_dialogue_for_npc_poi_only() -> None:
    active = ActiveSession(
        session_id="scene-1",
        phase=SessionStatus.EXPLORATION,
        state_data={
            "characters": {"human_1": {"name": "Aria", "is_ai": False}},
            "current_scene": {
                "pois": [
                    {
                        "id": "azaka",
                        "name": "Azaka",
                        "kind": "npc",
                        "icon": "npc",
                    },
                    {
                        "id": "locked_door",
                        "name": "Porte verrouillée",
                        "kind": "clue",
                        "icon": "door",
                    },
                ],
                "exits": [],
            },
        },
    )
    resolver = MagicMock()
    resolver.resolve = AsyncMock(
        return_value=SimpleNamespace(mechanics={"type": "skill_check", "success": True})
    )
    resolver.social_conclude = AsyncMock()
    resolver.resolve_npc_dialogue = AsyncMock()

    with patch("app.services.narrative_flow_service.event_bus.publish_to_session", new=AsyncMock()):
        await NarrativeFlowService().handle_exploration_action(
            session_id="scene-1",
            action=_action("Je demande à Azaka d'être notre guide."),
            active=active,
            action_resolver=resolver,
            db=None,
        )

    resolver.resolve.assert_awaited_once()
    resolver.resolve_npc_dialogue.assert_awaited_once()
    assert resolver.resolve_npc_dialogue.await_args.kwargs["target_id"] == "azaka"
    assert resolver.resolve_npc_dialogue.await_args.kwargs["roll_results"] == {
        "type": "skill_check",
        "success": True,
    }


@pytest.mark.asyncio
async def test_direct_npc_dialogue_skips_redundant_gm_narration() -> None:
    active = ActiveSession(
        session_id="scene-1",
        phase=SessionStatus.EXPLORATION,
        state_data={
            "characters": {"human_1": {"name": "Thorvald", "is_ai": False}},
            "current_scene": {
                "scene_id": "scene_goldenthrone",
                "pois": [
                    {
                        "id": "syndra_silvane",
                        "name": "Syndra Silvane",
                        "kind": "npc",
                        "icon": "npc",
                    }
                ],
            },
            "npc_states": {
                "syndra_silvane": {
                    "name": "Syndra Silvane",
                    "attitude": "indifferent",
                }
            },
        },
    )
    gm = MagicMock()
    gm.think = AsyncMock(return_value=GMResponse(narration="Narration redondante.", actions=[]))
    gm.run_npc_dialogue = AsyncMock(
        return_value=GMResponse(narration="« Que souhaitez-vous savoir ? »", actions=[])
    )
    resolver = ActionResolver(gm_agent=gm)
    published: list[tuple[str, dict]] = []

    async def capture(_session_id, event_type, payload, source=None):
        published.append((event_type, payload))

    with patch("app.game.action_resolver.event_bus.publish_to_session", new=capture):
        await NarrativeFlowService().handle_exploration_action(
            session_id="scene-1",
            action=_action("Je m'approche de Syndra Silvane et lui adresse la parole."),
            active=active,
            action_resolver=resolver,
            db=None,
        )

    gm.think.assert_not_called()
    gm.run_npc_dialogue.assert_awaited_once()
    assert [payload for event, payload in published if event == EventType.NARRATION] == []
    dialogues = [payload for event, payload in published if event == EventType.DIALOGUE]
    assert len(dialogues) == 1
    assert dialogues[0]["speaker"] == "Syndra Silvane"


@pytest.mark.asyncio
async def test_direct_npc_social_check_keeps_roll_then_dialogue_only() -> None:
    active = ActiveSession(
        session_id="scene-1",
        phase=SessionStatus.EXPLORATION,
        state_data={
            "characters": {
                "human_1": {
                    "name": "Thorvald",
                    "is_ai": False,
                    "level": 1,
                    "ability_scores": {"cha": 12},
                    "skill_proficiencies": ["persuasion"],
                }
            },
            "current_scene": {
                "scene_id": "scene_goldenthrone",
                "pois": [
                    {
                        "id": "syndra_silvane",
                        "name": "Syndra Silvane",
                        "kind": "npc",
                        "icon": "npc",
                    }
                ],
            },
            "npc_states": {
                "syndra_silvane": {
                    "name": "Syndra Silvane",
                    "attitude": "indifferent",
                }
            },
        },
    )
    gm = MagicMock()
    gm.think = AsyncMock(return_value=GMResponse(narration="Narration redondante.", actions=[]))
    gm.run_npc_dialogue = AsyncMock(
        return_value=GMResponse(narration="« Je peux vous fournir un appui limité. »", actions=[])
    )
    resolver = ActionResolver(gm_agent=gm)
    published: list[tuple[str, dict]] = []

    async def capture(_session_id, event_type, payload, source=None):
        published.append((event_type, payload))

    with patch("app.game.action_resolver.event_bus.publish_to_session", new=capture):
        await NarrativeFlowService().handle_exploration_action(
            session_id="scene-1",
            action=_action("Je persuade Syndra Silvane de financer l'expédition."),
            active=active,
            action_resolver=resolver,
            db=None,
        )

    gm.think.assert_not_called()
    roll_results = gm.run_npc_dialogue.await_args.kwargs["roll_results"]
    assert roll_results["type"] == "skill_check"
    assert roll_results["social_target_id"] == "syndra_silvane"
    assert [payload for event, payload in published if event == EventType.NARRATION] == []
    assert len([payload for event, payload in published if event == EventType.ROLL_RESULT]) == 1
    assert len([payload for event, payload in published if event == EventType.DIALOGUE]) == 1


@pytest.mark.asyncio
async def test_npc_social_action_does_not_trigger_companion_echoes() -> None:
    active = _active_with_companions()
    active.state_data["current_scene"] = {
        "pois": [
            {
                "id": "azaka",
                "name": "Azaka",
                "kind": "npc",
                "icon": "npc",
            }
        ]
    }
    resolver = MagicMock()
    resolver.resolve = AsyncMock(
        return_value=SimpleNamespace(mechanics={"type": "skill_check", "success": True})
    )
    resolver.social_conclude = AsyncMock()
    resolver.resolve_npc_dialogue = AsyncMock()

    with patch("app.services.narrative_flow_service.event_bus.publish_to_session", new=AsyncMock()):
        exchange = await NarrativeFlowService().handle_exploration_action(
            session_id="scene-1",
            action=_action("Je demande à Azaka d'être notre guide."),
            active=active,
            action_resolver=resolver,
            db=None,
        )

    assert exchange.audience == "world"
    resolver.resolve.assert_awaited_once()
    resolver.resolve_npc_dialogue.assert_awaited_once()
    active.ai_players["thorin_1"].respond_to_player.assert_not_called()
    active.ai_players["elara_1"].respond_to_player.assert_not_called()
