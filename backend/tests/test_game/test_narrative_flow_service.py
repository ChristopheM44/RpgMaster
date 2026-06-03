from __future__ import annotations

import json
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.schemas import GMResponse, PlayerActionChoice
from app.game.action_resolver import ActionResolver
from app.game.event_bus import EventType
from app.game.session_manager import ActiveSession
from app.game.social_scene_state import (
    _clock_roll_outcome_text,
    _clock_threat_kind,
    _default_clock_crisis_text,
)
from app.game.visible_events import strip_visible_speaker_prefix
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


def test_visible_dialogue_strips_redundant_speaker_prefix() -> None:
    text = strip_visible_speaker_prefix(
        "Syndra laisse échapper un soupir las.",
        "Syndra Silvane",
    )

    assert text == "laisse échapper un soupir las."


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
        if event_type == "dialogue" and payload.get("speaker") == "Oaken"
    )
    assert "bois craque" not in dialogue_payload["text"]
    assert "pose une main sur la table" in dialogue_payload["text"]
    assert "Nous ne sommes pas des touristes" in dialogue_payload["text"]


@pytest.mark.asyncio
async def test_companion_dialogue_persisted_text_matches_cleaned_published_text() -> None:
    """Symétrie persisté = publié pour le dialogue compagnon IA.

    La copie persistée ne doit porter ni guillemets englobants ni préfixe de nom :
    sinon, au rechargement de l'historique, la couture nettoyée à l'affichage live
    réapparaît (même classe de régression que celle fermée pour les PNJ).
    """
    active = _active_with_companions()
    active.ai_players["thorin_1"].character_name = "Oaken"
    active.ai_players["thorin_1"].respond_to_player = AsyncMock(
        return_value=PlayerActionChoice(
            action_type="talk",
            action_description="Tient la ligne.",
            roleplay_text="Oaken : « Nous tenons la position, restez derrière moi. »",
        )
    )
    resolver = MagicMock()
    resolver.resolve = AsyncMock()

    published: list[tuple[str, dict]] = []
    persisted: list[tuple[str, str]] = []

    async def capture_publish(_session_id, event_type, payload, source=None):
        published.append((event_type, payload))

    async def capture_persist(_session_id, content, speaker, _db, **_kwargs):
        persisted.append((speaker, content))

    with (
        patch(
            "app.services.narrative_flow_service.event_bus.publish_to_session",
            new=capture_publish,
        ),
        patch(
            "app.services.narrative_flow_service.persist_narration",
            new=capture_persist,
        ),
        patch(
            "app.services.narrative_flow_service.load_recent_messages",
            new=AsyncMock(return_value=[]),
        ),
    ):
        await NarrativeFlowService()._run_companion_responses(
            session_id="scene-1",
            active=active,
            action_resolver=resolver,
            player_text="que dis-tu ?",
            target_ids=["thorin_1"],
            trigger_character_id="human_1",
            db=MagicMock(),
            scene_id="scene-x",
        )

    published_text = next(
        payload["text"]
        for event_type, payload in published
        if event_type == EventType.DIALOGUE and payload.get("speaker") == "Oaken"
    )
    persisted_text = next(content for speaker, content in persisted if speaker == "Oaken")

    # Idempotence : persisté = clean(src), publié = clean(clean(src)) → l'égalité
    # prouve que publish_visible_entry re-nettoie en no-op.
    assert persisted_text == published_text
    assert not persisted_text.startswith("«")
    assert not persisted_text.lower().startswith("oaken")
    assert persisted_text == "Nous tenons la position, restez derrière moi."


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
        payload for event_type, payload in published if event_type == "dialogue"
    ]
    assert dialogue_payloads[-1]["text"] == (
        "s'accroupit à l'entrée du passage. "
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
async def test_party_dialogue_rotates_group_companion_responses() -> None:
    active = _active_with_companions()
    _add_third_companion(active)
    resolver = MagicMock()
    resolver.resolve = AsyncMock()
    resolver.social_conclude = AsyncMock()
    service = NarrativeFlowService()

    with patch("app.services.narrative_flow_service.event_bus.publish_to_session", new=AsyncMock()):
        first = await service.handle_exploration_action(
            session_id="scene-1",
            action=_action("Compagnons, que fait-on ?"),
            active=active,
            action_resolver=resolver,
            db=None,
        )
        second = await service.handle_exploration_action(
            session_id="scene-1",
            action=_action("Compagnons, que fait-on ?"),
            active=active,
            action_resolver=resolver,
            db=None,
        )

    assert [r["speaker"] for r in first.companion_responses] == ["Thorin", "Elara"]
    assert [r["speaker"] for r in second.companion_responses] == ["Solana", "Thorin"]


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
async def test_npc_dialogue_failure_after_suppressed_gm_narration_is_visible() -> None:
    active = ActiveSession(
        session_id="scene-1",
        phase=SessionStatus.EXPLORATION,
        state_data={
            "characters": {"human_1": {"name": "Aria", "is_ai": False}},
            "current_scene": {
                "scene_id": "scene_tavern",
                "pois": [{"id": "azaka", "name": "Azaka", "kind": "npc", "icon": "npc"}],
            },
        },
    )
    resolver = MagicMock()
    resolver.resolve = AsyncMock(return_value=SimpleNamespace(mechanics={}))
    resolver.social_conclude = AsyncMock()
    resolver.resolve_npc_dialogue = AsyncMock(return_value=False)
    published: list[tuple[str, dict]] = []

    async def capture(_session_id, event_type, payload, source=None):
        published.append((event_type, payload))

    with patch("app.services.narrative_flow_service.event_bus.publish_to_session", new=capture):
        exchange = await NarrativeFlowService().handle_exploration_action(
            session_id="scene-1",
            action=_action("Je demande à Azaka si elle connaît la route."),
            active=active,
            action_resolver=resolver,
            db=None,
        )

    resolver.resolve.assert_awaited_once()
    resolver.resolve_npc_dialogue.assert_awaited_once()
    system_entries = [
        payload
        for event_type, payload in published
        if event_type == EventType.NARRATION and payload.get("entry_kind") == "system"
    ]
    assert system_entries
    assert system_entries[0]["target_id"] == "azaka"
    assert exchange.gm_arbitrated is True


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
    dialogue_state = active.state_data["npc_states"]["syndra_silvane"]["dialogue_state"]
    assert dialogue_state["stage"] == "briefing_given"
    assert active.state_data["current_scene"]["pois"][0]["interactions"][0]["id"] == "ask_details"


@pytest.mark.asyncio
async def test_repeated_generic_npc_talk_updates_dialogue_state_without_world_narration() -> None:
    active = ActiveSession(
        session_id="scene-1",
        phase=SessionStatus.EXPLORATION,
        state_data={
            "characters": {"human_1": {"name": "Thorvald", "is_ai": False}},
            "current_scene": {
                "scene_id": "scene_market",
                "pois": [{"id": "mayor", "name": "Maire Valerius", "kind": "npc", "icon": "npc"}],
            },
            "npc_states": {"mayor": {"name": "Maire Valerius", "attitude": "indifferent"}},
        },
    )
    gm = MagicMock()
    gm.think = AsyncMock(return_value=GMResponse(narration="Narration redondante.", actions=[]))
    gm.run_npc_dialogue = AsyncMock(
        return_value=GMResponse(narration="« Posez une vraie question, vite. »", actions=[])
    )
    resolver = ActionResolver(gm_agent=gm)

    async def capture(_session_id, _event_type, _payload, source=None):
        return None

    action = _action(
        "Je m'approche de Maire Valerius et lui adresse la parole.",
        target_id="mayor",
    )
    with patch("app.game.action_resolver.event_bus.publish_to_session", new=capture):
        await NarrativeFlowService().handle_exploration_action(
            session_id="scene-1",
            action=action,
            active=active,
            action_resolver=resolver,
            db=None,
        )
        await NarrativeFlowService().handle_exploration_action(
            session_id="scene-1",
            action=action,
            active=active,
            action_resolver=resolver,
            db=None,
        )

    dialogue_state = active.state_data["npc_states"]["mayor"]["dialogue_state"]
    assert dialogue_state["stage"] == "briefing_given"
    assert dialogue_state["talk_count"] == 2
    assert dialogue_state["generic_repeat_count"] == 1
    assert gm.think.call_count == 0


@pytest.mark.asyncio
async def test_impossible_hostile_action_refuses_effect_and_marks_npc_wary() -> None:
    active = ActiveSession(
        session_id="scene-1",
        phase=SessionStatus.EXPLORATION,
        state_data={
            "characters": {"human_1": {"name": "Oaken", "is_ai": False}},
            "current_scene": {
                "scene_id": "scene_market",
                "pois": [{"id": "mayor", "name": "Maire Valerius", "kind": "npc", "icon": "npc"}],
            },
            "npc_states": {"mayor": {"name": "Maire Valerius", "attitude": "indifferent"}},
        },
    )
    resolver = MagicMock()
    resolver.resolve = AsyncMock()
    resolver.resolve_npc_dialogue = AsyncMock()
    resolver.social_conclude = AsyncMock()
    published: list[tuple[str, dict]] = []

    async def capture(_session_id, event_type, payload, source=None):
        published.append((event_type, payload))

    with patch("app.services.narrative_flow_service.event_bus.publish_to_session", new=capture):
        exchange = await NarrativeFlowService().handle_exploration_action(
            session_id="scene-1",
            action=_action(
                "Je sors mon bazouka et je tire une roquette sur le maire.",
                target_id="mayor",
            ),
            active=active,
            action_resolver=resolver,
            db=None,
        )

    resolver.resolve.assert_not_called()
    resolver.resolve_npc_dialogue.assert_not_called()
    assert exchange.gm_arbitrated is True
    assert active.state_data["npc_states"]["mayor"]["attitude"] == "unfriendly"
    assert active.state_data["npc_states"]["mayor"]["dialogue_state"]["stage"] == "angered"
    assert active.state_data["pending_clarification"]["type"] == "impossible_hostile_action"
    assert not active.state_data.get("scene_clocks")
    assert any(event == EventType.SOCIAL_OUTCOME for event, _ in published)
    narrations = [payload for event, payload in published if event == EventType.NARRATION]
    assert "n'existe pas" in narrations[-1]["text"]


@pytest.mark.asyncio
async def test_filled_scene_clock_triggers_crisis_roll_and_resolves() -> None:
    active = ActiveSession(
        session_id="scene-1",
        phase=SessionStatus.EXPLORATION,
        state_data={
            "characters": {
                "human_1": {
                    "name": "Aria",
                    "level": 1,
                    "ability_scores": {"dex": 14},
                    "save_proficiencies": [],
                }
            },
            "scene_clocks": [
                {
                    "id": "menace_docks",
                    "label": "Menace aux docks",
                    "scope": "scene",
                    "current": 3,
                    "max": 4,
                    "severity": "high",
                    "status": "active",
                    "tick_on": "player_action",
                    "linked_quest_id": None,
                }
            ],
        },
    )
    resolver = MagicMock()
    resolver.resolve = AsyncMock()
    resolver.resolve_npc_dialogue = AsyncMock()
    resolver.social_conclude = AsyncMock()
    published: list[tuple[str, dict]] = []

    async def capture(_session_id, event_type, payload, source=None):
        published.append((event_type, payload))

    with patch("app.services.narrative_flow_service.event_bus.publish_to_session", new=capture):
        await NarrativeFlowService().handle_exploration_action(
            session_id="scene-1",
            action=_action("J'examine la porte qui vibre."),
            active=active,
            action_resolver=resolver,
            db=None,
        )

    assert active.state_data["scene_clocks"][0]["status"] == "resolved"
    clock_updates = [payload for event, payload in published if event == EventType.CLOCK_UPDATED]
    assert [payload["status"] for payload in clock_updates[:2]] == ["resolving", "resolved"]
    assert any(event == EventType.ROLL_RESULT for event, _ in published)

    narrations = [
        payload["text"] for event, payload in published if event == EventType.NARRATION
    ]
    # La crise se raconte par un phénomène physique concret (catégorie "dock"),
    # jamais par le label interne ni un placeholder d'acteur.
    assert any(
        any(token in text.lower() for token in ("amarre", "pilotis", "eau noire"))
        for text in narrations
    )
    # Le résultat du jet nomme le personnage réel et décrit une conséquence.
    assert any("Aria" in text for text in narrations)
    # Aucune couture mécanique (label d'horloge, placeholder, jargon) ne fuit.
    for text in narrations:
        assert "Menace aux docks" not in text
        assert "point critique" not in text
        assert "le personnage exposé" not in text
    assert not any(
        "Menace aux docks atteint son point critique" in text for text in narrations
    )


@pytest.mark.asyncio
async def test_resolved_scene_clock_does_not_retrigger_crisis() -> None:
    active = ActiveSession(
        session_id="scene-1",
        phase=SessionStatus.EXPLORATION,
        state_data={
            "characters": {"human_1": {"name": "Aria", "level": 1}},
            "scene_clocks": [
                {
                    "id": "menace_docks",
                    "label": "Menace aux docks",
                    "scope": "scene",
                    "current": 4,
                    "max": 4,
                    "severity": "high",
                    "status": "resolved",
                    "tick_on": "player_action",
                }
            ],
        },
    )
    resolver = MagicMock()
    resolver.resolve = AsyncMock()
    resolver.resolve_npc_dialogue = AsyncMock()
    resolver.social_conclude = AsyncMock()
    published: list[tuple[str, dict]] = []

    async def capture(_session_id, event_type, payload, source=None):
        published.append((event_type, payload))

    with patch("app.services.narrative_flow_service.event_bus.publish_to_session", new=capture):
        await NarrativeFlowService().handle_exploration_action(
            session_id="scene-1",
            action=_action("J'examine la porte."),
            active=active,
            action_resolver=resolver,
            db=None,
        )

    assert not any(event == EventType.ROLL_RESULT for event, _ in published)
    assert not any(event == EventType.CLOCK_UPDATED for event, _ in published)


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
async def test_npc_social_action_does_not_trigger_party_dialogue_path() -> None:
    """Une adresse à un PNJ ne déclenche pas le chemin 'party' (cascade).

    Le pipeline `respond_to_player` est réservé aux adresses au groupe ou à
    un compagnon précis. Quand le joueur parle à un PNJ, on passe par
    `resolve_npc_dialogue` (PNJ répond) puis `run_exploration_reactions`
    (un seul compagnon réagit, voir Phase 3) — jamais le multi-réponse
    `respond_to_player` du chemin party.
    """
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

    with patch(
        "app.services.narrative_flow_service.event_bus.publish_to_session", new=AsyncMock()
    ), patch(
        "app.game.ai_player_manager.AIPlayerManager.run_exploration_reactions",
        new=AsyncMock(return_value=(0, [])),
    ):
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


@pytest.mark.asyncio
async def test_npc_dialogue_triggers_one_companion_reaction() -> None:
    """Après la réplique du PNJ, un compagnon prend la parole (cap 1).

    Reproduit le comportement d'une vraie table : quand un PJ parle à un PNJ,
    les autres PJ écoutent et l'un d'eux peut commenter ou enchaîner. La cap à
    1 réaction évite les cascades synchronisées.
    """
    active = _active_with_companions()
    active.state_data["current_scene"] = {
        "pois": [
            {
                "id": "azaka",
                "name": "Azaka",
                "kind": "npc",
                "icon": "npc",
                "description": "guide halfling",
            }
        ]
    }
    resolver = MagicMock()
    resolver.resolve = AsyncMock(return_value=SimpleNamespace(mechanics=None))
    resolver.resolve_npc_dialogue = AsyncMock()
    resolver.social_conclude = AsyncMock()

    reaction_mock = AsyncMock(return_value=(1, [{"speaker": "Thorin", "text": "Méfions-nous."}]))

    with patch(
        "app.services.narrative_flow_service.event_bus.publish_to_session", new=AsyncMock()
    ), patch(
        "app.game.ai_player_manager.AIPlayerManager.run_exploration_reactions",
        new=reaction_mock,
    ):
        await NarrativeFlowService().handle_exploration_action(
            session_id="scene-1",
            action=_action("Je m'approche d'Azaka et lui demande conseil."),
            active=active,
            action_resolver=resolver,
            db=None,
        )

    resolver.resolve_npc_dialogue.assert_awaited_once()
    reaction_mock.assert_awaited_once()
    assert reaction_mock.await_args.kwargs["max_reactors"] == 1


@pytest.mark.asyncio
async def test_npc_dialogue_reaction_skipped_when_no_ai_players() -> None:
    """Sans compagnons IA, aucune réaction n'est déclenchée après le dialogue.

    Garde-fou : on ne paie pas de LLM call inutile quand le solo player est
    le seul humain et qu'aucun compagnon IA n'est enregistré.
    """
    active = ActiveSession(
        session_id="scene-solo",
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
                    }
                ]
            },
        },
    )
    # Pas d'ai_players enregistrés.
    resolver = MagicMock()
    resolver.resolve = AsyncMock(return_value=SimpleNamespace(mechanics=None))
    resolver.resolve_npc_dialogue = AsyncMock()
    resolver.social_conclude = AsyncMock()

    reaction_mock = AsyncMock(return_value=(0, []))

    with patch(
        "app.services.narrative_flow_service.event_bus.publish_to_session", new=AsyncMock()
    ), patch(
        "app.game.ai_player_manager.AIPlayerManager.run_exploration_reactions",
        new=reaction_mock,
    ):
        await NarrativeFlowService().handle_exploration_action(
            session_id="scene-solo",
            action=_action("Je parle à Azaka."),
            active=active,
            action_resolver=resolver,
            db=None,
        )

    resolver.resolve_npc_dialogue.assert_awaited_once()
    reaction_mock.assert_not_called()


# ── Voix fictionnelle des horloges de menace (LOT B) ──────────────────────────

_CLOCK_FORBIDDEN = ("point critique", "le personnage exposé", "horloge")


@pytest.mark.parametrize(
    "label,kind,token",
    [
        ("Menace aux docks", "dock", "amarre"),
        ("Rituel en cours", "ritual", "rune"),
        ("Incendie", "fire", "flamme"),
        ("Effondrement de la galerie", "collapse", "plafond"),
        ("Menace imminente", "generic", "tension"),
        ("", "generic", "tension"),
    ],
)
def test_clock_crisis_text_is_concrete_and_label_free(label, kind, token) -> None:
    clock = {"label": label, "severity": "high"}
    assert _clock_threat_kind(label) == kind
    text = _default_clock_crisis_text(clock)
    assert token in text.lower()
    # Le label interne ne fuit jamais dans la narration joueur.
    if label:
        assert label not in text
    for forbidden in _CLOCK_FORBIDDEN:
        assert forbidden not in text.lower()


def test_clock_crisis_text_critical_adds_urgency_without_leaking_label() -> None:
    base = _default_clock_crisis_text({"label": "Menace aux docks", "severity": "high"})
    critical = _default_clock_crisis_text({"label": "Menace aux docks", "severity": "critical"})
    assert critical != base
    assert critical.startswith(base)
    assert "Menace aux docks" not in critical


def test_clock_outcome_names_character_and_success_still_costs() -> None:
    clock = {"label": "Menace aux docks", "severity": "high"}
    success = _clock_roll_outcome_text(clock, {"character_name": "Bram", "success": True})
    failure = _clock_roll_outcome_text(clock, {"character_name": "Bram", "success": False})

    assert success.startswith("Bram ")
    assert failure.startswith("Bram ")
    assert success != failure
    # "Même un succès coûte" : la réussite décrit une conséquence concrète.
    assert any(token in success.lower() for token in ("prix", "genou", "noyé", "trempé"))
    for text in (success, failure):
        assert "Menace aux docks" not in text
        for forbidden in _CLOCK_FORBIDDEN:
            assert forbidden not in text.lower()


def test_clock_outcome_falls_back_to_generic_character_name() -> None:
    text = _clock_roll_outcome_text({"label": "Menace imminente"}, {"success": False})
    assert text.startswith("Le personnage ")


# Pronom « il » ou participe passé s'accordant au sujet → texte faux pour un PC
# féminin (« Aria est emporté »). On verrouille la neutralité de genre.
_GENDERED_PC_AGREEMENT = re.compile(
    r"\bil\b|\b(?:emporté|pris|rattrapé|projeté|cueilli|happé|transi|enseveli|plaqué|roulé|"
    r"désorienté|trempé)\b",
    re.IGNORECASE,
)


def test_clock_outcomes_are_gender_neutral_for_any_pc() -> None:
    labels = [
        "Menace aux docks",
        "Incendie",
        "Rituel",
        "Inondation",
        "Effondrement",
        "Poursuite",
        "Explosion",
        "Menace imminente",
    ]
    for label in labels:
        for success in (True, False):
            text = _clock_roll_outcome_text(
                {"label": label}, {"character_name": "Aria", "success": success}
            )
            match = _GENDERED_PC_AGREEMENT.search(text)
            assert match is None, (label, success, match.group(0) if match else None, text)
