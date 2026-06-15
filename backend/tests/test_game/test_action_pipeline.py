"""Tests pour le pipeline unifie de resolution d'action.

Trois chemins doivent converger vers le meme contrat visible :
  1. Joueur humain   → ActionResolver.resolve()
  2. Compagnon IA    → AIPlayerManager.process_ai_turns() → ActionResolver
  3. Monstre         → _handle_ai_turns() (ws_game) → ActionResolver
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.player_agent import PlayerAgent, PlayerPersonality
from app.agents.schemas import AgentResponse, GMAction, GMResponse
from app.game.action_pipeline import ActionPipeline, ActionRequest
from app.game.action_resolver import ActionResolver
from app.game.ai_player_manager import AIPlayerManager
from app.game.event_bus import EventType
from app.game.gm_response_executor import GMResponseExecutor
from app.game.session_manager import ActiveSession
from app.game.social_scene_state import infer_clock_start_from_opening
from app.game.turn_manager import TurnEntry
from app.models.character import Character
from app.models.session import SessionStatus

SESSION_ID = "test-pipeline-session"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_combat_active(
    *,
    hero_id: str = "hero_1",
    monster_id: str = "goblin_1",
    monster_turn_first: bool = False,
) -> ActiveSession:
    """ActiveSession en phase COMBAT avec 1 héros et 1 gobelin."""
    active = ActiveSession(
        session_id=SESSION_ID,
        phase=SessionStatus.COMBAT,
        state_data={
            "characters": {
                hero_id: {"name": "Aria", "level": 1, "hp": 20, "hp_max": 20},
            },
            "combatants": {
                hero_id: {
                    "name": "Aria",
                    "hp": 20,
                    "hp_max": 20,
                    "is_player": True,
                    "is_ai": False,
                    "ac": 14,
                    "attack_bonus": 5,
                    "damage_notation": "1d8+3",
                    "status": "active",
                },
                monster_id: {
                    "name": "Gobelin",
                    "hp": 7,
                    "hp_max": 7,
                    "is_player": False,
                    "is_ai": True,
                    "status": "active",
                    "ac": 15,
                    "attack_bonus": 4,
                    "damage_notation": "1d6+2",
                },
            },
        },
    )

    if monster_turn_first:
        active.turn_manager._order = [
            TurnEntry(monster_id, "Gobelin", 18, False, True),
            TurnEntry(hero_id, "Aria", 10, True, False),
        ]
    else:
        active.turn_manager._order = [
            TurnEntry(hero_id, "Aria", 18, True, False),
            TurnEntry(monster_id, "Gobelin", 10, False, True),
        ]
    active.turn_manager._index = 0
    active.turn_manager._mode = "combat"
    active.turn_manager._round = 1
    active.ai_players = {}
    return active


def _mock_gm(narration: str = "Le combat fait rage !") -> MagicMock:
    gm = MagicMock()
    gm.think = AsyncMock(return_value=AgentResponse(content=narration, actions=[]))
    gm.run_combat_turn = AsyncMock(return_value=GMResponse(narration=narration, actions=[]))
    gm.narrate_outcome_response = AsyncMock(
        return_value=GMResponse(narration=narration, actions=[])
    )
    return gm


def _event_collector():
    """Retourne (liste_publiée, coroutine_capture) pour patcher publish_to_session."""
    published: list[tuple[EventType, dict]] = []

    async def capture(session_id, event_type, payload, source=None):
        published.append((event_type, payload))

    return published, capture


class _FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[EventType, dict]] = []

    async def publish_to_session(self, session_id, event_type, payload, source=None):
        self.published.append((event_type, payload))


def _narrations(published) -> list[dict]:
    return [p for et, p in published if et == EventType.NARRATION]


# ---------------------------------------------------------------------------
# 0. Pipeline / executor unitaires
# ---------------------------------------------------------------------------


class TestPipelineExecutorUnits:
    async def test_stealth_event_success_applies_npc_update_without_visible_roll(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={
                "characters": {
                    "hero_1": {"name": "Thorvald", "ability_scores": {"wis": 10}},
                },
                "current_scene": {
                    "scene_id": "camp",
                    "cols": 12,
                    "rows": 12,
                    "cell_size_m": 1.5,
                    "scene_theme": "forest",
                    "pois": [
                        {
                            "id": "guide",
                            "name": "Guide",
                            "kind": "npc",
                            "position": {"col": 5, "row": 5},
                        }
                    ],
                    "exits": [],
                    "party_positions": {},
                },
            },
        )
        bus = _FakeBus()

        result = await GMResponseExecutor(bus).execute_gm_response(
            GMResponse(
                narration="Une ombre glisse derrière le camp.",
                actions=[
                    GMAction(
                        type="stealth_event",
                        params={
                            "actor_id": "shadow",
                            "actor_kind": "npc",
                            "event_type": "abduction",
                            "stealth_total_override": 20,
                            "target_npc_ids": ["guide"],
                            "npc_status_on_success": "abducted",
                        },
                    )
                ],
            ),
            active,
            db=None,
        )

        assert result.pending_rolls[0]["type"] == "stealth_event"
        assert result.pending_rolls[0]["stealth_succeeded"] is True
        assert active.state_data["npc_states"]["guide"]["status"] == "abducted"
        assert not [payload for event, payload in bus.published if event == EventType.ROLL_RESULT]
        assert [
            payload for event, payload in bus.published if event == EventType.SCENE_LAYOUT_CHANGED
        ]

    async def test_stealth_event_failure_does_not_apply_npc_update(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={
                "characters": {
                    "hero_1": {"name": "Thorvald", "ability_scores": {"wis": 16}},
                },
                "current_scene": {
                    "scene_id": "camp",
                    "cols": 12,
                    "rows": 12,
                    "cell_size_m": 1.5,
                    "scene_theme": "forest",
                    "pois": [
                        {
                            "id": "guide",
                            "name": "Guide",
                            "kind": "npc",
                            "position": {"col": 5, "row": 5},
                        }
                    ],
                    "exits": [],
                    "party_positions": {},
                },
            },
        )
        bus = _FakeBus()

        result = await GMResponseExecutor(bus).execute_gm_response(
            GMResponse(
                narration="Une ombre tente d'agir en silence.",
                actions=[
                    GMAction(
                        type="stealth_event",
                        params={
                            "actor_id": "shadow",
                            "actor_kind": "npc",
                            "event_type": "abduction",
                            "stealth_total_override": 5,
                            "target_npc_ids": ["guide"],
                            "npc_status_on_success": "abducted",
                        },
                    )
                ],
            ),
            active,
            db=None,
        )

        assert result.pending_rolls[0]["stealth_succeeded"] is False
        assert "guide" not in active.state_data.get("npc_states", {})
        assert not [payload for event, payload in bus.published if event == EventType.ROLL_RESULT]
        assert not [
            payload for event, payload in bus.published if event == EventType.SCENE_LAYOUT_CHANGED
        ]

    async def test_scene_progress_update_stays_private_and_updates_internal_state(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={
                "current_scene": {
                    "scene_id": "oasis_corrompue",
                    "cols": 12,
                    "rows": 12,
                    "scene_theme": "desert",
                    "pois": [],
                    "exits": [],
                    "party_positions": {},
                },
            },
        )
        bus = _FakeBus()

        result = await GMResponseExecutor(bus).execute_gm_response(
            GMResponse(
                narration="L'eau noire frémit sous l'analyse.",
                actions=[
                    GMAction(
                        type="scene_progress_update",
                        params={
                            "scene_id": "oasis_corrompue",
                            "goal": "Comprendre et neutraliser la source.",
                            "status": "active",
                            "obstacle_id": "eau_noire",
                            "progress": 1,
                            "max_progress": 3,
                            "approaches": ["analyser", "purifier", "contourner"],
                            "revelations": ["La corruption vient d'un conduit enterré."],
                            "failure_costs": ["La soif avance."],
                            "success_outcome": "La piste du puits ancien s'ouvre.",
                        },
                    )
                ],
            ),
            active,
            db=None,
        )

        scene_state = active.state_data["gm_scene_state"]["oasis_corrompue"]
        obstacle = scene_state["obstacles"]["eau_noire"]
        assert result.executed_actions[0]["type"] == "scene_progress_update"
        assert scene_state["goal"] == "Comprendre et neutraliser la source."
        assert obstacle["progress"] == 1
        assert "purifier" in obstacle["approaches"]
        assert [event for event, _ in bus.published] == [EventType.SCENE_OPTIONS_UPDATED]
        public_options = bus.published[0][1]["options"]
        assert [option["label"] for option in public_options] == [
            "analyser",
            "purifier",
            "contourner",
        ]
        public_payload = json.dumps(bus.published, ensure_ascii=False)
        assert "La corruption vient d'un conduit enterré." not in public_payload
        assert "La soif avance." not in public_payload
        assert "La piste du puits ancien s'ouvre." not in public_payload

    async def test_hide_action_rolls_stealth_and_consumes_combat_action(self) -> None:
        active = _make_combat_active()
        active.state_data["combatants"]["hero_1"].update(
            {
                "level": 3,
                "ability_scores": {"dex": 14},
                "skill_proficiencies": ["stealth"],
            }
        )
        active.state_data["combatants"]["goblin_1"]["passive_perception"] = 10
        bus = _FakeBus()
        gm = _mock_gm("Aria se fond dans les ombres.")

        pipeline = ActionPipeline(gm, bus, mechanics=ActionResolver(gm_agent=gm))
        with patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()):
            result = await pipeline.resolve_and_publish(
                ActionRequest(
                    session_id=SESSION_ID,
                    actor_id="hero_1",
                    actor_name="Aria",
                    actor_kind="player",
                    action_type="hide",
                    content="Je me cache derrière les pierres.",
                ),
                active,
            )

        assert result.mechanics["skill"] == "stealth"
        assert result.mechanics["modifier"] == 4
        assert result.mechanics["observers"][0]["id"] == "goblin_1"
        assert active.turn_manager.current_turn.action_economy.action is False
        roll_payloads = [
            payload for event_type, payload in bus.published if event_type == EventType.ROLL_RESULT
        ]
        assert roll_payloads
        assert roll_payloads[0]["label"] == "DEX (Stealth)"

    async def test_pipeline_defers_stealth_event_narration_until_outcome(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={
                "characters": {
                    "hero_1": {"name": "Thorvald", "ability_scores": {"wis": 12}},
                },
                "current_scene": {
                    "scene_id": "camp",
                    "cols": 12,
                    "rows": 12,
                    "cell_size_m": 1.5,
                    "scene_theme": "forest",
                    "pois": [],
                    "exits": [],
                    "party_positions": {},
                },
            },
        )
        bus = _FakeBus()
        gm = MagicMock()
        gm.think = AsyncMock(
            return_value=AgentResponse(
                content="Une ombre tente de filer.",
                actions=[
                    GMAction(
                        type="stealth_event",
                        params={
                            "actor_id": "shadow",
                            "actor_kind": "npc",
                            "event_type": "escape",
                            "stealth_total_override": 3,
                        },
                    )
                ],
            )
        )
        gm.narrate_outcome_response = AsyncMock(
            return_value=GMResponse(
                narration="Thorvald perçoit un froissement dans les fougères.",
                actions=[],
            )
        )

        pipeline = ActionPipeline(gm, bus, mechanics=ActionResolver(gm_agent=gm))
        with patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()):
            await pipeline.resolve_and_publish(
                ActionRequest(
                    session_id=SESSION_ID,
                    actor_id="hero_1",
                    actor_name="Thorvald",
                    actor_kind="player",
                    action_type="free_text",
                    content="Je surveille les environs.",
                ),
                active,
            )

        narrations = [
            payload["text"] for event, payload in bus.published if event == EventType.NARRATION
        ]
        assert narrations == ["Thorvald perçoit un froissement dans les fougères."]

    async def test_free_text_ask_azaka_uses_single_social_skill_check(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={
                "characters": {
                    "hero_1": {
                        "name": "Thorvald",
                        "level": 1,
                        "ability_scores": {"cha": 20},
                        "skill_proficiencies": ["Persuasion"],
                    },
                },
                "npc_states": {
                    "azaka": {
                        "name": "Azaka",
                        "attitude": "indifferent",
                    }
                },
            },
        )
        bus = _FakeBus()

        gm = MagicMock()
        gm.think = AsyncMock(
            return_value=AgentResponse(
                content="Azaka jauge la demande avant de répondre.",
                actions=[
                    GMAction(
                        type="roll_request",
                        target="hero_1",
                        params={"skill": "persuasion", "dc": 15, "social_target": "azaka"},
                    )
                ],
            )
        )

        pipeline = ActionPipeline(gm, bus, mechanics=ActionResolver(gm_agent=gm))
        with patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()):
            await pipeline.resolve_and_publish(
                ActionRequest(
                    session_id=SESSION_ID,
                    actor_id="hero_1",
                    actor_name="Thorvald",
                    actor_kind="player",
                    action_type="free_text",
                    content="Je demande à Azaka d'être notre guide.",
                ),
                active,
            )

        roll_payloads = [
            payload for event_type, payload in bus.published if event_type == EventType.ROLL_RESULT
        ]
        assert len(roll_payloads) == 1
        roll_payload = roll_payloads[0]
        assert roll_payload["character_id"] == "hero_1"
        assert roll_payload["social_target_id"] == "azaka"
        assert roll_payload["modifier"] == 7
        assert roll_payload["rolls"]
        assert roll_payload["label"] == "CHA (Persuasion)"
        assert isinstance(roll_payload["success"], bool)

        ctx = gm.think.await_args.args[0]
        assert ctx.roll_results["skill"] == "persuasion"
        assert ctx.roll_results["modifier"] == 7
        assert ctx.roll_results["social_target_id"] == "azaka"

    async def test_social_combat_text_gets_fallback_charisma_roll(self) -> None:
        active = _make_combat_active(monster_id="bandit_1")
        active.state_data["characters"]["hero_1"]["ability_scores"] = {"cha": 14}
        active.state_data["combatants"]["bandit_1"]["name"] = "Bandit 1"
        bus = _FakeBus()

        gm = MagicMock()
        gm.think = AsyncMock(
            return_value=AgentResponse(
                content="Le bandit serre les dents, son cimeterre encore levé.",
                actions=[],
            )
        )
        gm.narrate_outcome_response = AsyncMock(
            return_value=GMResponse(
                narration="Le bandit hésite sous l'ordre lancé.",
                actions=[],
            )
        )

        pipeline = ActionPipeline(gm, bus, mechanics=ActionResolver(gm_agent=gm))
        with patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()):
            await pipeline.resolve_and_publish(
                ActionRequest(
                    session_id=SESSION_ID,
                    actor_id="hero_1",
                    actor_name="Aria",
                    actor_kind="player",
                    action_type="free_text",
                    content="Pose tes armes et rends-toi.",
                    target_id="bandit_1",
                ),
                active,
            )

        event_types = [event_type for event_type, _ in bus.published]
        assert EventType.ROLL_RESULT in event_types
        gm.narrate_outcome_response.assert_awaited_once()
        roll_payload = next(
            payload for event_type, payload in bus.published if event_type == EventType.ROLL_RESULT
        )
        assert roll_payload["character_id"] == "hero_1"
        assert roll_payload["social_target_id"] == "bandit_1"

    async def test_roll_request_publishes_only_outcome_narration(self) -> None:
        active = _make_combat_active()
        active.state_data["characters"]["hero_1"]["ability_scores"] = {"wis": 16}
        bus = _FakeBus()

        gm = MagicMock()
        gm.think = AsyncMock(
            return_value=AgentResponse(
                content="Aria observe les traces.",
                actions=[
                    GMAction(
                        type="roll_request",
                        target="hero_1",
                        params={"ability": "wis", "type": "check", "dc": 10},
                    )
                ],
            )
        )
        gm.narrate_outcome_response = AsyncMock(
            return_value=GMResponse(
                narration="Les traces confirment un passage recent.",
                actions=[],
            )
        )

        pipeline = ActionPipeline(gm, bus, mechanics=ActionResolver(gm_agent=gm))
        with patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()):
            await pipeline.resolve_and_publish(
                ActionRequest(
                    session_id=SESSION_ID,
                    actor_id="hero_1",
                    actor_name="Aria",
                    actor_kind="player",
                    action_type="free_text",
                    content="J'inspecte les traces.",
                ),
                active,
            )

        visible_events = [
            event_type
            for event_type, _payload in bus.published
            if event_type in {EventType.ROLL_RESULT, EventType.NARRATION}
        ]
        assert visible_events == [EventType.ROLL_RESULT, EventType.NARRATION]
        assert _narrations(bus.published)[-1]["text"] == (
            "Les traces confirment un passage recent."
        )

    def _active_with_companion(self) -> ActiveSession:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={
                "characters": {
                    "hero_1": {"name": "Thorvald", "level": 1, "ability_scores": {"int": 10}},
                    "shade": {"name": "Shade", "level": 1, "ability_scores": {"int": 16}},
                },
            },
        )
        active.ai_players = {"shade": MagicMock(character_name="Shade")}
        return active

    async def test_roll_request_attributed_to_addressed_companion(self) -> None:
        """#3 : « @shade examine… » sans target → le jet revient à Shade, pas à l'humain."""
        active = self._active_with_companion()
        bus = _FakeBus()
        response = AgentResponse(
            content="Shade s'accroupit au bord du ruisseau.",
            actions=[GMAction(type="roll_request", params={"skill": "investigation", "dc": 10})],
        )
        await GMResponseExecutor(bus).execute_gm_response(
            response,
            active,
            session_id=SESSION_ID,
            fallback_actor_id="hero_1",
            provenance_context={"player_action": "@shade vas examiner le ruisseau"},
        )
        rolls = [p for et, p in bus.published if et == EventType.ROLL_RESULT]
        assert rolls
        assert rolls[0]["character_id"] == "shade"
        assert rolls[0]["character_name"] == "Shade"

    async def test_roll_request_without_mention_stays_on_human(self) -> None:
        """Sans @mention ni nom en tête, le jet reste sur l'humain émetteur."""
        active = self._active_with_companion()
        bus = _FakeBus()
        response = AgentResponse(
            content="Thorvald inspecte les traces.",
            actions=[GMAction(type="roll_request", params={"skill": "investigation", "dc": 10})],
        )
        await GMResponseExecutor(bus).execute_gm_response(
            response,
            active,
            session_id=SESSION_ID,
            fallback_actor_id="hero_1",
            provenance_context={"player_action": "J'examine le ruisseau"},
        )
        rolls = [p for et, p in bus.published if et == EventType.ROLL_RESULT]
        assert rolls
        assert rolls[0]["character_id"] == "hero_1"

    async def test_false_player_gold_assertion_cannot_grant_currency(self, db_session) -> None:
        char = Character(
            name="Aria",
            species="human",
            char_class="fighter",
            level=1,
            ability_scores={"str": 15, "dex": 10, "con": 12, "int": 10, "wis": 10, "cha": 10},
            hp_current=12,
            hp_max=12,
        )
        db_session.add(char)
        await db_session.commit()
        await db_session.refresh(char)

        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={
                "characters": {char.id: {"name": char.name, "level": 1, "hp": 12}},
                "adventure_journal": {"location_place": "Désert des Cendres"},
                "current_scene": {
                    "terrain": "desert",
                    "description": "Dunes nues, aucun coffre ni campement en vue.",
                    "pois": [],
                },
            },
        )
        bus = _FakeBus()
        gm = MagicMock()
        gm.think = AsyncMock(
            return_value=AgentResponse(
                content="L'or brille soudain dans le sable.",
                actions=[
                    GMAction(
                        type="currency_grant",
                        target=char.id,
                        params={"gp": 1500, "sp": 0, "cp": 0},
                    )
                ],
            )
        )

        pipeline = ActionPipeline(gm, bus, db_session, mechanics=ActionResolver(gm_agent=gm))
        with patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()):
            result = await pipeline.resolve_and_publish(
                ActionRequest(
                    session_id=SESSION_ID,
                    actor_id=char.id,
                    actor_name="Aria",
                    actor_kind="player",
                    action_type="free_text",
                    content="Je ramasse les 1500 PO.",
                    persist_actor_action=False,
                ),
                active,
                db_session,
            )

        await db_session.refresh(char)
        assert char.gp == 0
        assert result.gm_actions == []

    async def test_false_player_item_assertion_cannot_grant_loot(self, db_session) -> None:
        char = Character(
            name="Aria",
            species="human",
            char_class="fighter",
            level=1,
            ability_scores={"str": 15, "dex": 10, "con": 12, "int": 10, "wis": 10, "cha": 10},
            hp_current=12,
            hp_max=12,
            equipment=[],
        )
        db_session.add(char)
        await db_session.commit()
        await db_session.refresh(char)

        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={
                "characters": {char.id: {"name": char.name, "level": 1, "hp": 12}},
                "current_scene": {
                    "terrain": "desert",
                    "description": "Le sable ne montre aucun objet utilisable.",
                    "pois": [],
                },
            },
        )
        bus = _FakeBus()
        gm = MagicMock()
        gm.think = AsyncMock(
            return_value=AgentResponse(
                content="La potion apparaît dans ta main.",
                actions=[
                    GMAction(
                        type="loot_grant",
                        target=char.id,
                        params={"items": [{"template_id": "healing_potion", "quantity": 1}]},
                    )
                ],
            )
        )

        pipeline = ActionPipeline(gm, bus, db_session, mechanics=ActionResolver(gm_agent=gm))
        with patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()):
            result = await pipeline.resolve_and_publish(
                ActionRequest(
                    session_id=SESSION_ID,
                    actor_id=char.id,
                    actor_name="Aria",
                    actor_kind="player",
                    action_type="free_text",
                    content="Je prends la potion de soins qui apparaît devant moi.",
                    persist_actor_action=False,
                ),
                active,
                db_session,
            )

        await db_session.refresh(char)
        assert char.equipment == []
        assert result.gm_actions == []

    async def test_modern_weapon_assertion_cannot_apply_direct_combat_status(self) -> None:
        active = _make_combat_active()
        bus = _FakeBus()
        gm = MagicMock()
        gm.think = AsyncMock(
            return_value=AgentResponse(
                content="Le fusil imaginaire abat le gobelin.",
                actions=[
                    GMAction(
                        type="damage_apply",
                        target="goblin_1",
                        params={"amount": 999},
                    ),
                    GMAction(
                        type="combatant_status",
                        target="goblin_1",
                        params={"status": "defeated", "reason": "fusil d'assaut"},
                    ),
                ],
            )
        )

        pipeline = ActionPipeline(gm, bus, mechanics=ActionResolver(gm_agent=gm))
        with patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()):
            result = await pipeline.resolve_and_publish(
                ActionRequest(
                    session_id=SESSION_ID,
                    actor_id="hero_1",
                    actor_name="Aria",
                    actor_kind="player",
                    action_type="free_text",
                    content="J'utilise mon fusil d'assaut pour buter le PNJ.",
                    target_id="goblin_1",
                ),
                active,
            )

        goblin = active.state_data["combatants"]["goblin_1"]
        assert goblin["hp"] == 7
        assert goblin["status"] == "active"
        assert result.gm_actions == []
        event_types = [event_type for event_type, _payload in bus.published]
        assert EventType.HP_CHANGED not in event_types
        assert EventType.COMBATANT_STATUS_CHANGED not in event_types

    async def test_executor_damage_and_conditions_mutate_state_and_publish(self) -> None:
        active = _make_combat_active()
        bus = _FakeBus()
        executor = GMResponseExecutor(bus)

        response = AgentResponse(
            content="",
            actions=[
                GMAction(type="damage_apply", target="goblin_1", params={"amount": 3}),
                GMAction(type="condition_add", target="goblin_1", params={"condition": "prone"}),
                GMAction(
                    type="condition_remove",
                    target="goblin_1",
                    params={"condition": "prone"},
                ),
            ],
        )

        result = await executor.execute_gm_response(
            response,
            active,
            session_id=SESSION_ID,
            fallback_actor_id="hero_1",
        )

        assert result.pending_rolls == []
        assert active.state_data["combatants"]["goblin_1"]["hp"] == 4
        assert active.state_data["combatants"]["goblin_1"]["conditions"] == []
        event_types = [event_type for event_type, _payload in bus.published]
        assert event_types == [
            EventType.HP_CHANGED,
            EventType.CONDITION_CHANGED,
            EventType.CONDITION_CHANGED,
        ]

    async def test_executor_scene_layout_updates_current_scene_and_publishes(self) -> None:
        active = _make_combat_active()
        bus = _FakeBus()
        executor = GMResponseExecutor(bus)

        response = AgentResponse(
            content="La salle circulaire se révèle.",
            actions=[
                GMAction(
                    type="scene_layout",
                    params={
                        "cols": 8,
                        "rows": 8,
                        "cell_size_m": 1.5,
                        "terrain": "stone_chamber",
                        "pois": [
                            {
                                "id": "well",
                                "name": "Puits scellé",
                                "kind": "hazard",
                                "position": {"col": 4, "row": 4},
                                "icon": "mist",
                                "description": "Brume froide et margelle instable.",
                                "action_hint": "Examiner avant de s'approcher.",
                                "interactions": [
                                    {
                                        "id": "listen",
                                        "label": "Écouter",
                                        "intent": "listen",
                                        "prompt": "J'écoute les sons venus du puits.",
                                        "icon": "clue",
                                        "default": True,
                                    },
                                    {"label": "", "intent": "talk"},
                                ],
                            }
                        ],
                        "exits": [
                            {
                                "id": "wooden_door",
                                "label": "Porte de chêne",
                                "position": {"col": 99, "row": 4},
                                "leads_to": "bandit_room",
                                "description": "Issue solide vers une pièce voisine.",
                            }
                        ],
                        "party_positions": {"hero_1": {"col": 1, "row": 4}},
                    },
                )
            ],
        )

        result = await executor.execute_gm_response(
            response,
            active,
            session_id=SESSION_ID,
            fallback_actor_id="hero_1",
        )

        scene = active.state_data["current_scene"]
        assert result.pending_rolls == []
        assert scene["terrain"] == "stone_chamber"
        assert scene["pois"][0]["description"] == "Brume froide et margelle instable."
        assert scene["pois"][0]["action_hint"] == "Examiner avant de s'approcher."
        assert scene["pois"][0]["interactions"] == [
            {
                "id": "listen",
                "label": "Écouter",
                "intent": "listen",
                "prompt": "J'écoute les sons venus du puits.",
                "icon": "clue",
                "default": True,
            }
        ]
        assert scene["exits"][0]["description"] == "Issue solide vers une pièce voisine."
        assert scene["exits"][0]["position"] == {"col": 7, "row": 4}
        scene_events = [
            payload for event, payload in bus.published if event == EventType.SCENE_LAYOUT_CHANGED
        ]
        assert scene_events[-1]["scene"] == scene
        assert bus.published[-1][0] == EventType.SCENE_OPTIONS_UPDATED
        assert bus.published[-1][1]["options"] == []
        assert active.state_data["scene_options"] == []

    async def test_executor_scene_progress_update_publishes_public_options(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={
                "current_scene": {
                    "scene_id": "cave_cristal",
                    "cols": 12,
                    "rows": 12,
                    "pois": [],
                    "exits": [],
                }
            },
        )
        bus = _FakeBus()
        executor = GMResponseExecutor(bus)

        response = AgentResponse(
            content="Le cristal cède par endroits.",
            actions=[
                GMAction(
                    type="scene_progress_update",
                    params={
                        "scene_id": "cave_cristal",
                        "goal": "Libérer la prison",
                        "approaches": [
                            "Analyser les runes",
                            {"label": "Forcer une brèche", "prompt": "Je force une brèche."},
                        ],
                    },
                )
            ],
        )

        await executor.execute_gm_response(response, active, session_id=SESSION_ID)

        assert active.state_data["scene_options"] == [
            {
                "id": active.state_data["scene_options"][0]["id"],
                "scene_id": "cave_cristal",
                "label": "Analyser les runes",
                "prompt": "Analyser les runes",
                "action_type": "free_text",
            },
            {
                "id": active.state_data["scene_options"][1]["id"],
                "scene_id": "cave_cristal",
                "label": "Forcer une brèche",
                "prompt": "Je force une brèche.",
                "action_type": "free_text",
            },
        ]
        option_events = [
            payload for event, payload in bus.published if event == EventType.SCENE_OPTIONS_UPDATED
        ]
        assert option_events[-1]["scene_id"] == "cave_cristal"
        assert [option["label"] for option in option_events[-1]["options"]] == [
            "Analyser les runes",
            "Forcer une brèche",
        ]

    async def test_executor_scene_update_merges_discoveries_positions_and_absent_npc(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={
                "characters": {"hero_1": {"name": "Thorvald"}},
                "npc_states": {
                    "khalid_guide": {
                        "name": "Khalid le Guide",
                        "status": "present",
                        "last_location": "oasis_corrompue",
                    }
                },
                "current_scene": {
                    "scene_id": "oasis_corrompue",
                    "cols": 12,
                    "rows": 12,
                    "cell_size_m": 1.5,
                    "terrain": "oasis",
                    "scene_theme": "desert",
                    "pois": [
                        {
                            "id": "khalid_guide",
                            "name": "Khalid le Guide",
                            "kind": "npc",
                            "icon": "npc",
                            "position": {"col": 5, "row": 5},
                        }
                    ],
                    "exits": [],
                    "party_positions": {"hero_1": {"col": 5, "row": 6}},
                },
            },
        )
        bus = _FakeBus()

        await GMResponseExecutor(bus).execute_gm_response(
            AgentResponse(
                content="La dalle se révèle, mais Khalid n'est plus là.",
                actions=[
                    GMAction(
                        type="scene_update",
                        params={
                            "upsert_pois": [
                                {
                                    "id": "dalle_fendue",
                                    "name": "Dalle fendue",
                                    "kind": "clue",
                                    "icon": "clue",
                                    "position": {"col": 6, "row": 7},
                                    "description": (
                                        "Une pierre plus claire laisse passer un souffle."
                                    ),
                                    "state": "discovered",
                                    "visibility": "subtle",
                                    "discovered": True,
                                    "physical_state": "pierre humide, joint descellé",
                                    "facts": ["Un courant d'air vient du dessous."],
                                }
                            ],
                            "party_positions": {"hero_1": {"col": 6, "row": 7}},
                            "npc_updates": [
                                {
                                    "id": "khalid_guide",
                                    "status": "missing",
                                    "note": "Ses traces se perdent vers les rochers.",
                                }
                            ],
                            "facts": ["L'oasis cache un passage sous la pierre."],
                            "physical_state": "eau trouble et pierres instables",
                        },
                    )
                ],
            ),
            active,
            session_id=SESSION_ID,
            fallback_actor_id="hero_1",
        )

        scene = active.state_data["current_scene"]
        pois = {poi["id"]: poi for poi in scene["pois"]}
        assert "khalid_guide" not in pois
        assert pois["dalle_fendue"]["state"] == "discovered"
        assert pois["dalle_fendue"]["visibility"] == "subtle"
        assert pois["dalle_fendue"]["physical_state"] == "pierre humide, joint descellé"
        assert pois["dalle_fendue"]["facts"] == ["Un courant d'air vient du dessous."]
        assert scene["party_positions"]["hero_1"] == {"col": 6, "row": 7}
        assert scene["physical_state"] == "eau trouble et pierres instables"
        assert active.state_data["npc_states"]["khalid_guide"]["status"] == "missing"
        assert active.state_data["npc_states"]["khalid_guide"]["notes"] == [
            "Ses traces se perdent vers les rochers."
        ]
        assert bus.published[-1][0] == EventType.SCENE_LAYOUT_CHANGED
        assert bus.published[-1][1]["scene"] == scene

    def test_executor_scene_layout_preserves_scene_state_fields(self) -> None:
        layout = GMResponseExecutor._normalize_scene_layout(
            {
                "cols": 8,
                "rows": 8,
                "terrain": "cave",
                "scene_theme": "cave",
                "state": "examined",
                "physical_state": "air froid, roche humide",
                "facts": ["Une ventilation vient du nord."],
                "ambiance": {"light": "torchlit", "fog_density": 0.6},
                "vegetation_density": 0.2,
                "pois": [
                    {
                        "id": "journal",
                        "name": "Journal trempé",
                        "kind": "clue",
                        "position": {"col": 3, "row": 4},
                        "state": "discovered",
                        "visibility": "visible",
                        "discovered": True,
                        "physical_state": "papier gonflé d'eau",
                        "facts": ["La dernière page manque."],
                    }
                ],
                "elements": [
                    {
                        "id": "conduit",
                        "name": "Conduit étroit",
                        "kind": "stairs",
                        "geometry": {"type": "rect", "col": 5, "row": 3, "width": 1, "height": 1},
                        "state": "locked",
                        "physical_state": "grille rouillée",
                        "facts": ["Des bulles remontent par intervalles."],
                        "height_m": 1.4,
                        "elevation_m": 0.25,
                    }
                ],
            }
        )

        assert layout["state"] == "examined"
        assert layout["physical_state"] == "air froid, roche humide"
        assert layout["facts"] == ["Une ventilation vient du nord."]
        assert layout["pois"][0]["state"] == "discovered"
        assert layout["pois"][0]["physical_state"] == "papier gonflé d'eau"
        assert layout["pois"][0]["facts"] == ["La dernière page manque."]
        assert layout["elements"][0]["state"] == "locked"
        assert layout["elements"][0]["physical_state"] == "grille rouillée"
        assert layout["elements"][0]["facts"] == ["Des bulles remontent par intervalles."]
        # Hints 3D : pass-through LLM conservé après clamp d'enrichissement.
        assert layout["ambiance"] == {"light": "torchlit", "fog_density": 0.6}
        assert layout["vegetation_density"] == 0.2
        assert layout["elements"][0]["height_m"] == 1.4
        assert layout["elements"][0]["elevation_m"] == 0.25
        wall = next(element for element in layout["elements"] if element["kind"] == "wall")
        assert wall["height_m"] == 2.5
        assert wall["elevation_m"] == 0.0

    def test_executor_scene_layout_drops_bad_3d_hint_types(self) -> None:
        layout = GMResponseExecutor._normalize_scene_layout(
            {
                "cols": 8,
                "rows": 8,
                "terrain": "cave",
                "scene_theme": "cave",
                "ambiance": "pénombre",
                "vegetation_density": "dense",
                "pois": [],
                "elements": [
                    {
                        "id": "stalagmite",
                        "name": "Stalagmite",
                        "kind": "cover",
                        "geometry": {"type": "rect", "col": 4, "row": 4, "width": 1, "height": 1},
                        "height_m": "haute",
                        "elevation_m": None,
                    }
                ],
            }
        )

        # Types invalides ignorés -> défauts sûrs injectés par l'enrichissement.
        assert layout["ambiance"] == {"light": "torchlit", "fog_density": 0.35}
        assert layout["vegetation_density"] == 0.0
        stalagmite = next(
            element for element in layout["elements"] if element["id"] == "stalagmite"
        )
        assert stalagmite["height_m"] == 1.0
        assert stalagmite["elevation_m"] == 0.0

    def test_executor_scene_layout_drops_boolean_vegetation_density(self) -> None:
        layout = GMResponseExecutor._normalize_scene_layout(
            {
                "cols": 8,
                "rows": 8,
                "terrain": "clairière",
                "scene_theme": "forest",
                "vegetation_density": True,
                "pois": [],
            }
        )

        assert layout["vegetation_density"] == 0.8

    def test_actor_attribution_guard_repairs_wrong_companion_discovery(self) -> None:
        response = AgentResponse(content="Elara découvre les runes sous la dalle.", actions=[])
        repaired = ActionPipeline._ensure_actor_attribution(
            response,
            {
                "actor_name": "Thorvald",
                "success": True,
                "scene_poi_name": "la dalle fendue",
                "non_actor_names": ["Elara", "Solana"],
            },
        )

        assert repaired.content == "Thorvald tire les informations utiles de la dalle fendue."
        assert "Elara" not in repaired.content

    async def test_empty_llm_fallback_publishes_system_error_without_narration(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={"characters": {"hero_1": {"name": "Thorvald"}}},
        )
        gm = _mock_gm("")
        bus = _FakeBus()

        await ActionPipeline(gm, bus).resolve_and_publish(
            ActionRequest(
                session_id=SESSION_ID,
                actor_id="hero_1",
                actor_name="Thorvald",
                actor_kind="player",
                action_type="free_text",
                content="J'examine la dalle.",
                target_id=None,
            ),
            active,
            db=None,
        )

        assert [payload for event, payload in bus.published if event == EventType.ERROR]
        assert not [payload for event, payload in bus.published if event == EventType.NARRATION]

    async def test_scene_interaction_roll_adds_update_when_gm_forgets(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={
                "characters": {"hero_1": {"name": "Thorvald", "ability_scores": {"int": 10}}},
                "current_scene": {
                    "scene_id": "oasis_corrompue",
                    "cols": 12,
                    "rows": 12,
                    "cell_size_m": 1.5,
                    "terrain": "oasis",
                    "scene_theme": "desert",
                    "pois": [
                        {
                            "id": "journal_cache",
                            "name": "Journal caché",
                            "kind": "clue",
                            "icon": "clue",
                            "position": {"col": 7, "row": 6},
                            "visibility": "hidden",
                            "interactions": [
                                {
                                    "id": "fail_search",
                                    "label": "Inspecter",
                                    "intent": "search",
                                    "mechanics": {
                                        "roll": {
                                            "type": "check",
                                            "ability": "int",
                                            "skill": "Investigation",
                                            "dc": 99,
                                        },
                                        "safe_observation": True,
                                    },
                                }
                            ],
                        }
                    ],
                    "exits": [],
                    "party_positions": {"hero_1": {"col": 6, "row": 7}},
                },
            },
        )
        bus = _FakeBus()
        pipeline = ActionPipeline(_mock_gm("Thorvald obtient un indice ambigu."), bus)

        await pipeline.resolve_and_publish(
            ActionRequest(
                session_id=SESSION_ID,
                actor_id="hero_1",
                actor_name="Thorvald",
                actor_kind="player",
                action_type="free_text",
                content="J'inspecte vite les traces.",
                target_id=None,
                scene_poi_id="journal_cache",
                scene_interaction_id="fail_search",
            ),
            active,
            db=None,
        )

        scene = active.state_data["current_scene"]
        poi = scene["pois"][0]
        assert poi["state"] == "examined"
        assert poi["visibility"] == "subtle"
        assert poi["discovered"] is True
        assert poi["facts"]
        assert [payload for event, payload in bus.published if event == EventType.ROLL_RESULT]
        assert [
            payload for event, payload in bus.published if event == EventType.SCENE_LAYOUT_CHANGED
        ]

    async def test_clock_start_is_opt_in_and_publishes_clock_update(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={},
        )
        bus = _FakeBus()

        await GMResponseExecutor(bus).execute_gm_response(
            GMResponse(
                narration="Les pavés vibrent à intervalle fixe.",
                actions=[
                    GMAction(
                        type="clock_start",
                        params={
                            "id": "menace_docks",
                            "label": "Menace aux docks",
                            "max": 4,
                            "severity": "high",
                        },
                    )
                ],
            ),
            active,
            session_id=SESSION_ID,
        )

        assert active.state_data["scene_clocks"] == [
            {
                "id": "menace_docks",
                "label": "Menace aux docks",
                "scope": "scene",
                "current": 0,
                "max": 4,
                "severity": "high",
                "status": "active",
                "tick_on": "player_action",
                "linked_quest_id": None,
            }
        ]
        assert bus.published[-1][0] == EventType.CLOCK_UPDATED

    async def test_response_without_clock_start_does_not_create_clock(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={},
        )
        bus = _FakeBus()

        await GMResponseExecutor(bus).execute_gm_response(
            GMResponse(narration="La route est calme.", actions=[]),
            active,
            session_id=SESSION_ID,
        )

        assert "scene_clocks" not in active.state_data
        assert not any(event == EventType.CLOCK_UPDATED for event, _ in bus.published)

    def test_opening_with_periodic_vibration_infers_opt_in_clock(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={},
        )

        clock = infer_clock_start_from_opening(
            "Toutes les trente secondes, un bourdonnement fait vibrer les docks.",
            active,
        )

        assert clock is not None
        assert clock["label"] == "Menace aux docks"

    async def test_social_outcome_failure_cannot_improve_attitude(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={"npc_states": {"azaka": {"name": "Azaka", "attitude": "indifferent"}}},
        )
        bus = _FakeBus()

        await GMResponseExecutor(bus).execute_gm_response(
            AgentResponse(
                content="",
                actions=[
                    GMAction(
                        type="social_outcome",
                        params={"npc_id": "azaka", "attitude_shift": "helpful"},
                    )
                ],
            ),
            active,
            session_id=SESSION_ID,
            social_roll_results={
                "type": "skill_check",
                "success": False,
                "social_target_id": "azaka",
            },
        )

        assert active.state_data["npc_states"]["azaka"]["attitude"] == "indifferent"
        social_events = [p for et, p in bus.published if et == EventType.SOCIAL_OUTCOME]
        assert social_events[-1]["clamped"] is True
        assert social_events[-1]["roll_success"] is False

    async def test_social_outcome_success_improves_at_most_one_step(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={"npc_states": {"azaka": {"name": "Azaka", "attitude": "indifferent"}}},
        )

        await GMResponseExecutor(_FakeBus()).execute_gm_response(
            AgentResponse(
                content="",
                actions=[
                    GMAction(
                        type="social_outcome",
                        params={"npc_id": "azaka", "attitude_shift": "helpful"},
                    )
                ],
            ),
            active,
            session_id=SESSION_ID,
            social_roll_results={
                "type": "skill_check",
                "success": True,
                "social_target_id": "azaka",
            },
        )

        assert active.state_data["npc_states"]["azaka"]["attitude"] == "friendly"

    async def test_social_success_without_social_outcome_applies_default(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={"npc_states": {"azaka": {"name": "Azaka", "attitude": "indifferent"}}},
        )
        bus = _FakeBus()

        await GMResponseExecutor(bus).execute_gm_response(
            AgentResponse(content="", actions=[]),
            active,
            session_id=SESSION_ID,
            social_roll_results={
                "type": "skill_check",
                "success": True,
                "social_target_id": "azaka",
            },
        )

        assert active.state_data["npc_states"]["azaka"]["attitude"] == "friendly"
        social_events = [p for et, p in bus.published if et == EventType.SOCIAL_OUTCOME]
        assert social_events[-1]["source"] == "engine_default"

    async def test_social_outcome_ignores_non_target_and_invalid_attitude(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={
                "npc_states": {
                    "azaka": {"name": "Azaka", "attitude": "indifferent"},
                    "jobal": {"name": "Jobal", "attitude": "hostile"},
                }
            },
        )
        bus = _FakeBus()

        await GMResponseExecutor(bus).execute_gm_response(
            AgentResponse(
                content="",
                actions=[
                    GMAction(
                        type="social_outcome",
                        params={"npc_id": "jobal", "attitude_shift": "helpful"},
                    ),
                    GMAction(
                        type="social_outcome",
                        params={"npc_id": "azaka", "attitude_shift": "best_friend"},
                    ),
                ],
            ),
            active,
            session_id=SESSION_ID,
            social_roll_results={
                "type": "skill_check",
                "success": True,
                "social_target_id": "azaka",
            },
        )

        assert active.state_data["npc_states"]["jobal"]["attitude"] == "hostile"
        assert active.state_data["npc_states"]["azaka"]["attitude"] == "indifferent"

    async def test_executor_scene_layout_filters_known_absent_npcs(self) -> None:
        active = _make_combat_active()
        active.state_data["npc_states"] = {
            "wakanga": {"name": "Wakanga O'tamu", "last_location": "scene_palais"}
        }
        bus = _FakeBus()
        executor = GMResponseExecutor(bus)

        response = AgentResponse(
            content="La salle commune s'anime.",
            actions=[
                GMAction(
                    type="scene_layout",
                    params={
                        "scene_id": "scene_auberge",
                        "cols": 8,
                        "rows": 8,
                        "terrain": "tavern",
                        "pois": [
                            {
                                "id": "wakanga",
                                "name": "Wakanga O'tamu",
                                "kind": "npc",
                                "position": {"col": 3, "row": 3},
                            },
                            {
                                "id": "azaka",
                                "name": "Azaka",
                                "kind": "npc",
                                "position": {"col": 4, "row": 3},
                            },
                        ],
                    },
                )
            ],
        )

        await executor.execute_gm_response(
            response,
            active,
            session_id=SESSION_ID,
            fallback_actor_id="hero_1",
        )

        scene = active.state_data["current_scene"]
        poi_ids = [poi["id"] for poi in scene["pois"]]
        assert "wakanga" not in poi_ids
        assert "azaka" in poi_ids
        assert active.state_data["npc_states"]["wakanga"]["last_location"] == "scene_palais"
        assert active.state_data["npc_states"]["azaka"]["last_location"] == "scene_auberge"

    async def test_executor_scene_layout_sanitizes_poi_interactions(self) -> None:
        layout = GMResponseExecutor._normalize_scene_layout(
            {
                "cols": 8,
                "rows": 8,
                "pois": [
                    {
                        "id": "toben",
                        "name": "Toben",
                        "kind": "npc",
                        "position": {"col": 2, "row": 3},
                        "interactions": [
                            {
                                "label": "Négocier",
                                "intent": "parley",
                                "prompt": "Je négocie avec Toben.",
                            },
                            {"intent": "talk", "prompt": "Sans label"},
                            "invalid",
                        ],
                    }
                ],
            }
        )

        assert layout["pois"][0]["interactions"] == [
            {
                "id": "custom_1",
                "label": "Négocier",
                "intent": "custom",
                "prompt": "Je négocie avec Toben.",
            }
        ]

    async def test_executor_scene_layout_preserves_elements_and_element_links(self) -> None:
        layout = GMResponseExecutor._normalize_scene_layout(
            {
                "cols": 8,
                "rows": 8,
                "terrain": "tavern_room",
                "scene_theme": "city",
                "pois": [
                    {
                        "id": "desk",
                        "name": "Bureau fermé",
                        "kind": "loot",
                        "position": {"col": 3, "row": 4},
                        "element_id": "desk_element",
                    }
                ],
                "exits": [
                    {
                        "id": "front_door",
                        "label": "Porte d'entrée",
                        "position": {"col": 0, "row": 4},
                        "element_id": "front_door_element",
                    }
                ],
                "elements": [
                    {
                        "id": "desk_element",
                        "name": "Bureau fermé",
                        "kind": "furniture",
                        "geometry": {"type": "rect", "col": 3, "row": 4, "width": 1, "height": 1},
                    },
                    {
                        "id": "front_door_element",
                        "name": "Porte d'entrée",
                        "kind": "door",
                        "geometry": {"type": "rect", "col": 0, "row": 4, "width": 0.2, "height": 1},
                    },
                ],
                "visual_asset": {
                    "provider": "openai_compatible",
                    "model": "gpt-image-1",
                    "status": "prompt_ready",
                    "prompt": "Top-down tavern.",
                    "prompt_hash": "hash",
                },
            }
        )

        assert layout["pois"][0]["element_id"] == "desk_element"
        assert layout["exits"][0]["element_id"] == "front_door_element"
        assert {element["id"] for element in layout["elements"]} >= {
            "desk_element",
            "front_door_element",
            "wall_north",
        }
        assert layout["visual_asset"]["model"] == "gpt-image-1"

    async def test_executor_scene_layout_enriches_interior_without_duplicate_exit_poi(self) -> None:
        layout = GMResponseExecutor._normalize_scene_layout(
            {
                "cols": 10,
                "rows": 8,
                "terrain": "stone_chamber",
                "scene_theme": "dungeon",
                "pois": [
                    {
                        "id": "stone_door",
                        "name": "Porte de pierre",
                        "kind": "exit",
                        "position": {"col": 9, "row": 4},
                    }
                ],
                "exits": [
                    {
                        "id": "stone_door",
                        "label": "Porte de pierre",
                        "position": {"col": 9, "row": 4},
                    }
                ],
            }
        )

        assert layout["pois"] == []
        assert layout["exits"][0]["element_id"] == "element_stone_door_door"
        assert any(element["kind"] == "wall" for element in layout["elements"])
        assert any(element["id"] == "element_stone_door_door" for element in layout["elements"])

    async def test_executor_scene_layout_normalizes_exit_placement(self) -> None:
        layout = GMResponseExecutor._normalize_scene_layout(
            {
                "cols": 12,
                "rows": 12,
                "terrain": "settlement",
                "scene_theme": "city",
                "description": "Place du Marché Central avec une trappe vers les égouts.",
                "pois": [],
                "exits": [
                    {
                        "id": "quitter_place",
                        "label": "Quitter la place",
                        "position": {"col": 6, "row": 6},
                    },
                    {
                        "id": "trappe_egouts",
                        "label": "Trappe vers les égouts",
                        "position": {"col": 6, "row": 7},
                    },
                ],
            }
        )

        edge_exit = next(exit_ for exit_ in layout["exits"] if exit_["id"] == "quitter_place")
        embedded_exit = next(exit_ for exit_ in layout["exits"] if exit_["id"] == "trappe_egouts")
        assert edge_exit["placement"] == "edge"
        assert edge_exit["position"]["col"] in {0, 11} or edge_exit["position"]["row"] in {0, 11}
        assert embedded_exit["placement"] == "embedded"
        assert embedded_exit["position"] == {"col": 6, "row": 7}
        assert any(element["id"] == embedded_exit["element_id"] for element in layout["elements"])

    async def test_executor_scene_layout_filters_duplicate_exit_pois(self) -> None:
        layout = GMResponseExecutor._normalize_scene_layout(
            {
                "cols": 10,
                "rows": 8,
                "terrain": "dock_ambush",
                "pois": [
                    {
                        "id": "bandit_2",
                        "name": "Bandit 2",
                        "kind": "enemy",
                        "icon": "bandit",
                        "position": {"col": 7, "row": 1},
                        "description": "Pres de la porte de quai. Evalue une fuite.",
                    },
                    {
                        "id": "dock_gate",
                        "name": "Porte de quai",
                        "kind": "exit",
                        "icon": "gate",
                        "position": {"col": 7, "row": 1},
                    },
                ],
                "exits": [
                    {
                        "id": "dock_gate",
                        "label": "Porte de quai",
                        "position": {"col": 7, "row": 1},
                        "leads_to": "souk_streets",
                    },
                ],
            }
        )

        assert [poi["id"] for poi in layout["pois"]] == ["bandit_2"]

    async def test_executor_map_updates_fallback_to_session_world_maps(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={},
        )
        bus = _FakeBus()
        executor = GMResponseExecutor(bus)

        await executor.execute_gm_response(
            GMResponse(
                narration="La carte se dessine.",
                actions=[
                    GMAction(
                        type="region_map_update",
                        params={
                            "name": "Route des Brumes",
                            "current_node_id": "camp",
                            "nodes_upsert": [
                                {
                                    "id": "camp",
                                    "name": "Camp",
                                    "kind": "landmark",
                                    "position": {"x": 40, "y": 60},
                                    "status": "current",
                                }
                            ],
                            "edges_upsert": [],
                        },
                    ),
                    GMAction(
                        type="city_map_update",
                        params={
                            "city_id": "camp",
                            "region_node_id": "camp",
                            "name": "Camp",
                            "current_node_id": "feu",
                            "nodes_upsert": [
                                {
                                    "id": "feu",
                                    "name": "Feu de camp",
                                    "kind": "square",
                                    "position": {"x": 50, "y": 50},
                                    "status": "current",
                                }
                            ],
                            "edges_upsert": [],
                        },
                    ),
                ],
            ),
            active,
            db=None,
            session_id=SESSION_ID,
        )

        world_maps = active.state_data["world_maps"]
        assert world_maps["region_map"]["current_node_id"] == "camp"
        assert world_maps["city_maps"]["camp"]["current_node_id"] == "feu"
        event_types = [event_type for event_type, _ in bus.published]
        assert EventType.REGION_MAP_UPDATED in event_types
        assert EventType.CITY_MAP_UPDATED in event_types

    async def test_executor_region_map_update_without_position_gets_layout_and_decor(
        self,
    ) -> None:
        """Piste C.3/C.4 : region_map_update sans position/decor -> carte placée + décorée."""
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={},
        )
        bus = _FakeBus()
        executor = GMResponseExecutor(bus)

        await executor.execute_gm_response(
            GMResponse(
                narration="La carte de la Côte des Brumes se dessine.",
                actions=[
                    GMAction(
                        type="region_map_update",
                        params={
                            "name": "Côte des Brumes",
                            "current_node_id": "port_neuf",
                            "nodes_upsert": [
                                {
                                    "id": "port_neuf",
                                    "name": "Port-Neuf",
                                    "kind": "settlement",
                                    "status": "current",
                                },
                                {
                                    "id": "phare",
                                    "name": "Phare du large",
                                    "kind": "landmark",
                                    "status": "known",
                                },
                            ],
                            "edges_upsert": [],
                        },
                    ),
                ],
            ),
            active,
            db=None,
            session_id=SESSION_ID,
        )

        region_map = active.state_data["world_maps"]["region_map"]
        nodes_by_id = {node["id"]: node for node in region_map["nodes"]}

        for node in nodes_by_id.values():
            assert 0.0 <= node["position"]["x"] <= 100.0
            assert 0.0 <= node["position"]["y"] <= 100.0
        assert nodes_by_id["port_neuf"]["position"] != nodes_by_id["phare"]["position"]

        decor = region_map["decor"]
        assert decor is not None
        # "Port-Neuf"/"Côte des Brumes" -> mots-clés côtiers -> coastline générée.
        assert decor.get("coastline") is not None

    async def test_executor_city_map_update_without_position_gets_layout_and_decor(self) -> None:
        """Piste C.3/C.4 : city_map_update sans position/decor -> carte placée + décor de ville."""
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={},
        )
        bus = _FakeBus()
        executor = GMResponseExecutor(bus)

        await executor.execute_gm_response(
            GMResponse(
                narration="Le plan de Port-Neuf se précise.",
                actions=[
                    GMAction(
                        type="city_map_update",
                        params={
                            "city_id": "port_neuf",
                            "region_node_id": "port_neuf",
                            "name": "Port-Neuf",
                            "current_node_id": "quai_nord",
                            "nodes_upsert": [
                                {
                                    "id": "quai_nord",
                                    "name": "Quai nord",
                                    "kind": "docks",
                                    "status": "current",
                                },
                                {
                                    "id": "taverne",
                                    "name": "Taverne du Heron",
                                    "kind": "tavern",
                                    "status": "known",
                                },
                            ],
                            "edges_upsert": [],
                        },
                    ),
                ],
            ),
            active,
            db=None,
            session_id=SESSION_ID,
        )

        city_map = active.state_data["world_maps"]["city_maps"]["port_neuf"]
        nodes_by_id = {node["id"]: node for node in city_map["nodes"]}

        for node in nodes_by_id.values():
            assert 0.0 <= node["position"]["x"] <= 100.0
            assert 0.0 <= node["position"]["y"] <= 100.0
        assert nodes_by_id["quai_nord"]["position"] != nodes_by_id["taverne"]["position"]

        decor = city_map["decor"]
        assert decor is not None
        # Décor de ville : périphérique, jamais de montagnes/côte (cf. generateCityDecor).
        assert decor["mountains"] == []
        assert decor.get("coastline") is None
        assert decor["forests"]

    async def test_executor_region_map_update_preserves_decor_on_later_patch(self) -> None:
        """Un region_map_update ultérieur sans decor ne régénère pas le décor existant."""
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={},
        )
        bus = _FakeBus()
        executor = GMResponseExecutor(bus)

        await executor.execute_gm_response(
            GMResponse(
                narration="Premier patch.",
                actions=[
                    GMAction(
                        type="region_map_update",
                        params={
                            "name": "Vallée de l'Épine",
                            "current_node_id": "auberge_du_pont",
                            "nodes_upsert": [
                                {
                                    "id": "auberge_du_pont",
                                    "name": "Auberge du Pont",
                                    "kind": "settlement",
                                    "status": "current",
                                },
                            ],
                            "edges_upsert": [],
                        },
                    ),
                ],
            ),
            active,
            db=None,
            session_id=SESSION_ID,
        )
        decor_after_first = active.state_data["world_maps"]["region_map"]["decor"]
        assert decor_after_first is not None

        await executor.execute_gm_response(
            GMResponse(
                narration="Second patch, sans decor.",
                actions=[
                    GMAction(
                        type="region_map_update",
                        params={
                            "nodes_upsert": [
                                {
                                    "id": "bois_creux",
                                    "name": "Bois Creux",
                                    "kind": "wilderness",
                                    "status": "known",
                                },
                            ],
                            "edges_upsert": [],
                        },
                    ),
                ],
            ),
            active,
            db=None,
            session_id=SESSION_ID,
        )

        decor_after_second = active.state_data["world_maps"]["region_map"]["decor"]
        assert decor_after_second == decor_after_first

    async def test_pipeline_ignores_gm_damage_apply_in_combat(self) -> None:
        active = _make_combat_active()
        bus = _FakeBus()
        gm = MagicMock()
        gm.think = AsyncMock(
            return_value=AgentResponse(
                content="Le gobelin chancelle.",
                actions=[
                    GMAction(
                        type="damage_apply",
                        target="goblin_1",
                        params={"amount": 3},
                    )
                ],
            )
        )

        pipeline = ActionPipeline(gm, bus, mechanics=ActionResolver(gm_agent=gm))
        with patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()):
            await pipeline.resolve_and_publish(
                ActionRequest(
                    session_id=SESSION_ID,
                    actor_id="hero_1",
                    actor_name="Aria",
                    actor_kind="player",
                    action_type="free_text",
                    content="Je menace le gobelin.",
                    target_id="goblin_1",
                ),
                active,
            )

        assert active.state_data["combatants"]["goblin_1"]["hp"] == 7
        assert not any(event_type == EventType.HP_CHANGED for event_type, _ in bus.published)

    async def test_monster_attack_without_target_chooses_first_living_player(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.COMBAT,
            state_data={
                "characters": {
                    "down": {"name": "Down", "level": 1, "hp": 0},
                    "hero_1": {"name": "Aria", "level": 1, "hp": 20},
                },
                "combatants": {
                    "down": {"name": "Down", "hp": 0, "is_player": True, "ac": 12},
                    "hero_1": {"name": "Aria", "hp": 20, "is_player": True, "ac": 14},
                    "goblin_1": {
                        "name": "Gobelin",
                        "hp": 7,
                        "is_player": False,
                        "is_ai": True,
                        "status": "active",
                        "ac": 15,
                        "attack_bonus": 4,
                        "damage_notation": "1d6+2",
                    },
                },
            },
        )
        bus = _FakeBus()
        gm = MagicMock()
        gm.think = AsyncMock(return_value=AgentResponse(content="Le gobelin frappe.", actions=[]))

        pipeline = ActionPipeline(gm, bus, mechanics=ActionResolver(gm_agent=gm))
        with patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()):
            resolved = await pipeline.resolve_and_publish(
                ActionRequest(
                    session_id=SESSION_ID,
                    actor_id="goblin_1",
                    actor_name="Gobelin",
                    actor_kind="monster",
                    action_type="attack",
                ),
                active,
            )

        rolls = [p for et, p in bus.published if et == EventType.ROLL_RESULT]
        assert resolved.target_id == "hero_1"
        assert rolls[-1]["target_id"] == "hero_1"


# ---------------------------------------------------------------------------
# 1. Joueur humain → ActionResolver.resolve()
# ---------------------------------------------------------------------------


class TestHumanPlayerPipeline:
    async def test_human_attack_emits_narration(self) -> None:
        active = _make_combat_active()
        resolver = ActionResolver(gm_agent=_mock_gm("Aria frappe le gobelin !"))
        published, capture = _event_collector()

        with (
            patch("app.game.action_resolver.event_bus.publish_to_session", new=capture),
            patch("app.game.action_resolver.tts_router.synthesize_and_broadcast", new=AsyncMock()),
        ):
            await resolver.resolve(
                session_id=SESSION_ID,
                action_type="attack",
                content="J'attaque le gobelin",
                character_id="hero_1",
                target_id="goblin_1",
                active=active,
                db=None,
            )

        narrs = _narrations(published)
        assert len(narrs) >= 1
        assert any(n.get("text") for n in narrs)
        resolver._gm.think.assert_awaited_once()
        visible_events = [
            event_type
            for event_type, _payload in published
            if event_type in {EventType.ROLL_RESULT, EventType.NARRATION}
        ]
        assert visible_events[-2:] == [EventType.ROLL_RESULT, EventType.NARRATION]

    async def test_human_attack_emits_roll_result(self) -> None:
        active = _make_combat_active()
        resolver = ActionResolver(gm_agent=_mock_gm())
        published, capture = _event_collector()

        with (
            patch("app.game.action_resolver.event_bus.publish_to_session", new=capture),
            patch("app.game.action_resolver.tts_router.synthesize_and_broadcast", new=AsyncMock()),
        ):
            await resolver.resolve(
                session_id=SESSION_ID,
                action_type="attack",
                content="J'attaque",
                character_id="hero_1",
                target_id="goblin_1",
                active=active,
                db=None,
            )

        rolls = [p for et, p in published if et == EventType.ROLL_RESULT]
        assert len(rolls) >= 1
        resolver._gm.think.assert_awaited_once()

    async def test_human_narration_speaker_is_gm(self) -> None:
        active = _make_combat_active()
        resolver = ActionResolver(gm_agent=_mock_gm("Narration du MJ."))
        published, capture = _event_collector()

        with (
            patch("app.game.action_resolver.event_bus.publish_to_session", new=capture),
            patch("app.game.action_resolver.tts_router.synthesize_and_broadcast", new=AsyncMock()),
        ):
            await resolver.resolve(
                session_id=SESSION_ID,
                action_type="free_text",
                content="J'explore la salle",
                character_id="hero_1",
                target_id=None,
                active=active,
                db=None,
            )

        narrs = _narrations(published)
        assert narrs
        # Le chemin humain émet la narration avec speaker="Maître du Jeu"
        assert narrs[-1].get("speaker") == "Maître du Jeu"
        resolver._gm.think.assert_awaited_once()

    async def test_exploration_environmental_uses_one_gm_call(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={"characters": {"hero_1": {"name": "Aria"}}},
        )
        resolver = ActionResolver(gm_agent=_mock_gm("La salle revele ses secrets."))
        published, capture = _event_collector()

        with (
            patch("app.game.action_resolver.event_bus.publish_to_session", new=capture),
            patch("app.game.action_resolver.tts_router.synthesize_and_broadcast", new=AsyncMock()),
        ):
            await resolver.resolve(
                session_id=SESSION_ID,
                action_type="free_text",
                content="J'examine les murs de la salle.",
                character_id="hero_1",
                target_id=None,
                active=active,
                db=None,
            )

        resolver._gm.think.assert_awaited_once()
        assert _narrations(published)

    async def test_scene_poi_examine_runs_backend_arcana_roll(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={
                "characters": {
                    "hero_1": {
                        "name": "Aria",
                        "level": 1,
                        "ability_scores": {"int": 14, "wis": 10, "dex": 12},
                        "skill_proficiencies": ["arcana"],
                    }
                },
                "current_scene": {
                    "scene_id": "scene_docks",
                    "pois": [
                        {
                            "id": "fissure",
                            "name": "Fissure luminescente",
                            "kind": "clue",
                            "icon": "clue",
                            "position": {"col": 4, "row": 4},
                            "description": "Une lueur azur pulse avec une odeur d'ozone.",
                        }
                    ],
                    "exits": [],
                    "party_positions": {},
                },
            },
        )
        gm = _mock_gm("La fissure livre des indices prudents.")
        resolver = ActionResolver(gm_agent=gm)
        published, capture = _event_collector()

        with (
            patch("app.game.action_resolver.event_bus.publish_to_session", new=capture),
            patch("app.game.action_resolver.tts_router.synthesize_and_broadcast", new=AsyncMock()),
        ):
            await resolver.resolve(
                session_id=SESSION_ID,
                action_type="free_text",
                content="J'examine : Fissure luminescente.",
                character_id="hero_1",
                target_id=None,
                active=active,
                db=None,
                scene_poi_id="fissure",
                scene_interaction_id="examine",
                scene_interaction_intent="examine",
            )

        rolls = [payload for event, payload in published if event == EventType.ROLL_RESULT]
        assert rolls
        assert "arcana" in rolls[0]["label"].lower()
        assert rolls[0]["scene_poi_id"] == "fissure"
        gm.think.assert_awaited_once()
        player_action = gm.think.await_args.args[0].player_action
        assert "observation_sans_contact=True" in player_action
        assert "palier_indice=interpreted" in player_action

    async def test_dangerous_touch_fallback_requests_save_when_gm_forgets(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={
                "characters": {
                    "hero_1": {
                        "name": "Aria",
                        "level": 1,
                        "ability_scores": {"dex": 14},
                        "save_proficiencies": [],
                    }
                }
            },
        )
        resolver = ActionResolver(gm_agent=_mock_gm("La porte vibre sous sa main."))
        published, capture = _event_collector()

        with (
            patch("app.game.action_resolver.event_bus.publish_to_session", new=capture),
            patch("app.game.action_resolver.tts_router.synthesize_and_broadcast", new=AsyncMock()),
        ):
            await resolver.resolve(
                session_id=SESSION_ID,
                action_type="free_text",
                content="Je pose la main sur la porte qui vibre.",
                character_id="hero_1",
                target_id=None,
                active=active,
                db=None,
            )

        rolls = [payload for event, payload in published if event == EventType.ROLL_RESULT]
        assert rolls
        assert rolls[0]["dc"] == 14
        label = str(rolls[0]["label"]).lower()
        assert "dex" in label or "dext" in label

    async def test_social_prompt_skips_gm_and_sets_party_intent(self) -> None:
        """En mode sober, un prompt social pur vers les compagnons doit bypasser le MJ.

        Ce test valide l'optimisation budget en mode sober. En mode full (défaut),
        le MJ est appelé pour enrichir la réponse — comportement intentionnel.
        """
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={"characters": {"hero_1": {"name": "Aria"}}},
        )
        active.ai_players = {"ai_1": MagicMock()}
        resolver = ActionResolver(gm_agent=_mock_gm("Ne devrait pas etre appele."))
        published, capture = _event_collector()

        with (
            patch("app.game.action_resolver.event_bus.publish_to_session", new=capture),
            patch("app.game.action_resolver.tts_router.synthesize_and_broadcast", new=AsyncMock()),
            # Force sober mode : c'est ce mode qui désactive le MJ pour les prompts sociaux purs.
            patch("app.llm.budget.get_llm_budget_mode", return_value="sober"),
        ):
            await resolver.resolve(
                session_id=SESSION_ID,
                action_type="free_text",
                content="Compagnons, que pensez-vous de ce plan ?",
                character_id="hero_1",
                target_id=None,
                active=active,
                db=None,
            )

        resolver._gm.think.assert_not_called()
        assert active.last_gm_intent == "social"
        assert _narrations(published) == []

    async def test_companion_world_action_uses_gm_even_if_content_mentions_companion(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={
                "characters": {
                    "shade_1": {"name": "Shade", "level": 1, "is_ai": True},
                }
            },
        )
        active.ai_players = {"shade_1": MagicMock()}
        gm = _mock_gm("Shade inspecte le passage et fait signe d'attendre.")
        bus = _FakeBus()
        pipeline = ActionPipeline(gm, bus, mechanics=ActionResolver(gm_agent=gm))

        with (
            patch("app.llm.budget.get_llm_budget_mode", return_value="sober"),
            patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()),
        ):
            await pipeline.resolve_and_publish(
                ActionRequest(
                    session_id=SESSION_ID,
                    actor_id="shade_1",
                    actor_name="Shade",
                    actor_kind="companion",
                    action_type="examine",
                    content="Shade examine le passage secret.",
                    display_text="Shade s'accroupit à l'entrée du passage.",
                    persist_actor_action=False,
                ),
                active,
            )

        gm.think.assert_awaited_once()
        assert _narrations(bus.published)[-1]["text"] == (
            "Shade inspecte le passage et fait signe d'attendre."
        )


# ---------------------------------------------------------------------------
# 2. Compagnon IA → AIPlayerManager.process_ai_turns() → ActionResolver
# ---------------------------------------------------------------------------


class TestAICompanionPipeline:
    async def test_ai_companion_attack_emits_narration(self) -> None:
        """Le compagnon IA émet NARRATION (son texte de roleplay) avant la résolution GM."""
        companion_id = "thorin_1"
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.COMBAT,
            state_data={
                "characters": {
                    companion_id: {
                        "name": "Thorin",
                        "level": 1,
                        "hp": 20,
                        "hp_max": 20,
                        "is_ai": True,
                        "personality": ["brave"],
                    },
                },
                "combatants": {
                    companion_id: {
                        "name": "Thorin",
                        "hp": 20,
                        "hp_max": 20,
                        "is_player": True,
                        "is_ai": True,
                        "ac": 14,
                        "attack_bonus": 4,
                        "damage_notation": "1d8+2",
                        "status": "active",
                    },
                    "goblin_1": {
                        "name": "Gobelin",
                        "hp": 7,
                        "hp_max": 7,
                        "is_player": False,
                        "is_ai": True,
                        "status": "active",
                        "ac": 15,
                    },
                },
            },
        )
        # Tour du compagnon IA, suivi d'un humain pour stopper la boucle
        # (next_turn() fait un wrap → un seul combattant boucle infiniment)
        active.turn_manager._order = [
            TurnEntry(companion_id, "Thorin", 15, True, True),
            TurnEntry("aria_1", "Aria", 10, True, False),
        ]
        active.turn_manager._index = 0
        active.turn_manager._mode = "combat"
        active.turn_manager._round = 1

        # PlayerAgent mocké avec un LLM factice
        thorin_agent = PlayerAgent(
            character_id=companion_id,
            character_name="Thorin",
            personality=PlayerPersonality(traits=["brave"]),
            client=MagicMock(),
        )
        active.ai_players = {companion_id: thorin_agent}

        # Le resolver est mocké : on ne teste que le chemin ai_player_manager
        mock_resolver = MagicMock()
        mock_resolver.resolve = AsyncMock()

        manager = AIPlayerManager()
        published, capture = _event_collector()

        attack_json = json.dumps(
            {
                "action_type": "attack",
                "action_description": "Thorin attaque le gobelin",
                "target": "goblin_1",
                "params": {},
                "roleplay_text": "Pour la gloire !",
                "inner_reasoning": "Attaque.",
            },
            ensure_ascii=False,
        )

        mock_chat = AsyncMock(return_value=attack_json)
        with (
            patch("app.game.ai_player_manager.event_bus.publish_to_session", new=capture),
            patch.object(thorin_agent._client, "chat", new=mock_chat),
            # Force sober mode : ce test valide le chemin déterministe (sans appel LLM).
            # En mode full (défaut), le LLM est appelé — comportement intentionnel.
            patch("app.game.ai_player_manager.is_sober_mode", return_value=True),
        ):
            await manager.process_ai_turns(SESSION_ID, active, mock_resolver, db=None)

        # Le compagnon doit émettre au moins une NARRATION avec son texte de roleplay
        narrs = _narrations(published)
        assert len(narrs) >= 1
        assert any(n.get("text") for n in narrs)
        # L'action_resolver doit avoir été appelé (pipeline mécanique + GM)
        mock_resolver.resolve.assert_called_once()
        # En mode sober, le chemin déterministe est utilisé — LLM non appelé
        mock_chat.assert_not_called()


# ---------------------------------------------------------------------------
# 2b. Orchestration ws_game : compagnons IA tour par tour
# ---------------------------------------------------------------------------


class TestAICompanionTurnOrdering:
    async def test_ws_ai_turns_cleanup_defeated_npc_before_next_companion_turn(self) -> None:
        from app.api.ws_game import _handle_ai_turns

        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.COMBAT,
            state_data={
                "characters": {
                    "shade_1": {"name": "Shade", "level": 1, "is_ai": True},
                    "elara_1": {"name": "Elara", "level": 1, "is_ai": True},
                    "thorvald_1": {"name": "Thorvald", "level": 1, "is_ai": False},
                },
                "combatants": {
                    "shade_1": {
                        "name": "Shade",
                        "hp": 18,
                        "is_player": True,
                        "is_ai": True,
                        "status": "active",
                        "attack_bonus": 3,
                        "damage_notation": "1d6",
                    },
                    "elara_1": {
                        "name": "Elara",
                        "hp": 12,
                        "is_player": True,
                        "is_ai": True,
                        "status": "active",
                        "attack_bonus": 3,
                        "damage_notation": "1d6",
                    },
                    "thorvald_1": {
                        "name": "Thorvald",
                        "hp": 20,
                        "is_player": True,
                        "is_ai": False,
                        "status": "active",
                    },
                    "bandit_3": {
                        "name": "Bandit 3",
                        "hp": 1,
                        "is_player": False,
                        "is_ai": True,
                        "status": "active",
                        "ac": 12,
                    },
                    "bandit_1": {
                        "name": "Bandit 1",
                        "hp": 7,
                        "is_player": False,
                        "is_ai": True,
                        "status": "active",
                        "ac": 12,
                    },
                },
                "grid_positions": {"bandit_3": {"x": 1, "y": 1}},
            },
        )
        active.turn_manager._order = [
            TurnEntry("shade_1", "Shade", 18, True, True),
            TurnEntry("elara_1", "Elara", 16, True, True),
            TurnEntry("bandit_3", "Bandit 3", 14, False, True),
            TurnEntry("bandit_1", "Bandit 1", 12, False, True),
            TurnEntry("thorvald_1", "Thorvald", 10, True, False),
        ]
        active.turn_manager._index = 0
        active.turn_manager._mode = "combat"
        active.turn_manager._round = 1
        active.ai_players = {
            "shade_1": PlayerAgent(
                character_id="shade_1",
                character_name="Shade",
                personality=PlayerPersonality(traits=["shadow"]),
                client=MagicMock(),
            ),
            "elara_1": PlayerAgent(
                character_id="elara_1",
                character_name="Elara",
                personality=PlayerPersonality(traits=["arcane"]),
                client=MagicMock(),
            ),
        }

        async def resolve_side_effect(**kwargs):
            if kwargs["character_id"] == "shade_1":
                active.state_data["combatants"]["bandit_3"]["hp"] = 0

        published, capture = _event_collector()
        mock_resolve = AsyncMock(side_effect=resolve_side_effect)

        with (
            patch("app.api.ws_game.event_bus.publish_to_session", new=capture),
            patch("app.api.ws_game.action_resolver.resolve", new=mock_resolve),
            patch("app.api.ws_game.session_manager.save_state", new=AsyncMock()),
            patch("app.api.ws_game._build_session_state_payload", return_value={"phase": "combat"}),
            # Les agents utilisent MagicMock comme client — forcer sober pour le chemin
            # déterministe (sans appel LLM). Ce test valide l'ordonnancement des tours,
            # pas la qualité des décisions IA.
            patch("app.game.ai_player_manager.is_sober_mode", return_value=True),
        ):
            await _handle_ai_turns(SESSION_ID, active, None)

        turn_starts = [
            payload["combatant_id"]
            for event_type, payload in published
            if event_type == EventType.TURN_START
        ]
        assert turn_starts[:3] == ["shade_1", "elara_1", "bandit_1"]

        defeated_idx = next(
            idx
            for idx, (event_type, payload) in enumerate(published)
            if event_type == EventType.NARRATION
            and payload.get("text") == "Bandit 3 a été vaincu !"
        )
        elara_turn_idx = next(
            idx
            for idx, (event_type, payload) in enumerate(published)
            if event_type == EventType.TURN_START and payload.get("combatant_id") == "elara_1"
        )
        assert defeated_idx < elara_turn_idx

        resolved_actor_ids = [call.kwargs["character_id"] for call in mock_resolve.await_args_list]
        assert resolved_actor_ids[:2] == ["shade_1", "elara_1"]


# ---------------------------------------------------------------------------
# 3. Monstre → _handle_ai_turns() (ws_game)
# ---------------------------------------------------------------------------


class TestMonsterPipeline:
    async def test_monster_attack_emits_narration(self) -> None:
        from app.api.ws_game import _handle_ai_turns

        active = _make_combat_active(monster_turn_first=True)
        published, capture = _event_collector()
        mock_gm_resp = AgentResponse(content="Le gobelin frappe sauvagement !", actions=[])
        mock_gm_think = AsyncMock(return_value=mock_gm_resp)

        with (
            patch("app.api.ws_game.event_bus.publish_to_session", new=capture),
            patch("app.api.ws_game.action_resolver._gm.think", new=mock_gm_think),
            patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()),
            patch("app.api.ws_game.session_manager.save_state", new=AsyncMock()),
            patch("app.api.ws_game._cleanup_inactive_npcs", new=AsyncMock(return_value=[])),
            patch("app.api.ws_game._build_session_state_payload", return_value={"phase": "combat"}),
        ):
            active.turn_manager.all_npcs_removed = MagicMock(return_value=False)
            await _handle_ai_turns(SESSION_ID, active, None)

        narrs = _narrations(published)
        assert len(narrs) >= 1
        assert any(n.get("text") for n in narrs)
        mock_gm_think.assert_awaited_once()

    async def test_monster_attack_emits_roll_result_event(self) -> None:
        from app.api.ws_game import _handle_ai_turns

        active = _make_combat_active(monster_turn_first=True)
        published, capture = _event_collector()
        mock_gm_resp = AgentResponse(content="Attaque !", actions=[])

        with (
            patch("app.api.ws_game.event_bus.publish_to_session", new=capture),
            patch(
                "app.api.ws_game.action_resolver._gm.think",
                new=AsyncMock(return_value=mock_gm_resp),
            ),
            patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()),
            patch("app.api.ws_game.session_manager.save_state", new=AsyncMock()),
            patch("app.api.ws_game._cleanup_inactive_npcs", new=AsyncMock(return_value=[])),
            patch("app.api.ws_game._build_session_state_payload", return_value={"phase": "combat"}),
        ):
            active.turn_manager.all_npcs_removed = MagicMock(return_value=False)
            await _handle_ai_turns(SESSION_ID, active, None)

        roll_results = [p for et, p in published if et == EventType.ROLL_RESULT]
        assert len(roll_results) >= 1
        assert roll_results[-1]["actor_kind"] == "monster"

    async def test_monster_narration_speaker_is_gm(self) -> None:
        """Le monstre passe par la narration MJ comme les autres acteurs."""
        from app.api.ws_game import _handle_ai_turns

        active = _make_combat_active(monster_turn_first=True)
        published, capture = _event_collector()
        mock_gm_resp = AgentResponse(content="Le gobelin attaque !", actions=[])

        with (
            patch("app.api.ws_game.event_bus.publish_to_session", new=capture),
            patch(
                "app.api.ws_game.action_resolver._gm.think",
                new=AsyncMock(return_value=mock_gm_resp),
            ),
            patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()),
            patch("app.api.ws_game.session_manager.save_state", new=AsyncMock()),
            patch("app.api.ws_game._cleanup_inactive_npcs", new=AsyncMock(return_value=[])),
            patch("app.api.ws_game._build_session_state_payload", return_value={"phase": "combat"}),
        ):
            active.turn_manager.all_npcs_removed = MagicMock(return_value=False)
            await _handle_ai_turns(SESSION_ID, active, None)

        narrs = _narrations(published)
        assert narrs
        assert narrs[-1].get("speaker") == "Maître du Jeu"


class TestTacticalCombatCoherence:
    def _active_with_wolf_between_heroes(self) -> ActiveSession:
        active = _make_combat_active(
            hero_id="thorvald",
            monster_id="wolf_1",
            monster_turn_first=True,
        )
        active.state_data["characters"] = {
            "thorvald": {"name": "Thorvald", "level": 1, "hp": 20, "hp_max": 20},
            "ardent": {"name": "Ardent", "level": 1, "hp": 20, "hp_max": 20},
        }
        active.state_data["combatants"] = {
            "thorvald": {
                "name": "Thorvald",
                "hp": 20,
                "hp_max": 20,
                "is_player": True,
                "is_ai": False,
                "ac": 16,
                "attack_bonus": 5,
                "damage_notation": "1d8+3",
                "status": "active",
            },
            "ardent": {
                "name": "Ardent",
                "hp": 20,
                "hp_max": 20,
                "is_player": True,
                "is_ai": False,
                "ac": 14,
                "attack_bonus": 20,
                "damage_notation": "1",
                "status": "active",
            },
            "wolf_1": {
                "name": "Loup",
                "hp": 30,
                "hp_max": 30,
                "is_player": False,
                "is_ai": True,
                "ac": 13,
                "attack_bonus": 4,
                "damage_notation": "2d4+2",
                "speed_m": 12,
                "reach_m": 1.5,
                "status": "active",
            },
        }
        active.state_data["grid_config"] = {"cols": 8, "rows": 6, "cell_size_m": 1.5}
        active.state_data["grid_positions"] = {
            "wolf_1": {"col": 1, "row": 1},
            "ardent": {"col": 1, "row": 2},
            "thorvald": {"col": 5, "row": 1},
        }
        active.turn_manager._order = [
            TurnEntry("wolf_1", "Loup", 18, False, True),
            TurnEntry("ardent", "Ardent", 12, True, False),
            TurnEntry("thorvald", "Thorvald", 10, True, False),
        ]
        active.turn_manager._index = 0
        return active

    async def test_monster_explicit_far_target_moves_and_triggers_opportunity_attack(self) -> None:
        active = self._active_with_wolf_between_heroes()
        published, capture = _event_collector()
        gm = _mock_gm("Le loup attaque apres s'etre deplace.")
        resolver = ActionResolver(gm_agent=gm, combat_gm_agent=gm)

        with (
            patch("app.game.action_resolver.event_bus.publish_to_session", new=capture),
            patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()),
        ):
            result = await resolver.resolve(
                session_id=SESSION_ID,
                action_type="attack",
                content=None,
                character_id="wolf_1",
                target_id="thorvald",
                active=active,
                actor_kind="monster",
                actor_name="Loup",
            )

        assert result.target_id == "thorvald"
        wolf_pos = active.state_data["grid_positions"]["wolf_1"]
        assert max(abs(wolf_pos["col"] - 5), abs(wolf_pos["row"] - 1)) <= 1
        assert active.turn_manager._order[1].action_economy.reaction is False
        assert any(et == EventType.COMBATANT_MOVED for et, _ in published)
        oa_events = [p for et, p in published if et == EventType.OPPORTUNITY_ATTACK_TRIGGERED]
        assert len(oa_events) == 1
        assert oa_events[0]["attacker_id"] == "ardent"
        assert oa_events[0]["target_id"] == "wolf_1"
        assert "attacker_name" in oa_events[0]
        assert "attack_total" in oa_events[0]

    async def test_disengage_prevents_opportunity_attack_on_monster_move(self) -> None:
        active = self._active_with_wolf_between_heroes()
        active.turn_manager.current_turn.action_economy.has_disengaged = True
        published, capture = _event_collector()
        gm = _mock_gm("Le loup se degage et attaque.")
        resolver = ActionResolver(gm_agent=gm, combat_gm_agent=gm)

        with (
            patch("app.game.action_resolver.event_bus.publish_to_session", new=capture),
            patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()),
        ):
            await resolver.resolve(
                session_id=SESSION_ID,
                action_type="attack",
                content=None,
                character_id="wolf_1",
                target_id="thorvald",
                active=active,
                actor_kind="monster",
                actor_name="Loup",
            )

        wolf_pos = active.state_data["grid_positions"]["wolf_1"]
        assert max(abs(wolf_pos["col"] - 5), abs(wolf_pos["row"] - 1)) <= 1
        assert active.turn_manager._order[1].action_economy.reaction is True
        assert not [p for et, p in published if et == EventType.OPPORTUNITY_ATTACK_TRIGGERED]

    async def test_creature_without_reaction_cannot_make_opportunity_attack(self) -> None:
        active = self._active_with_wolf_between_heroes()
        active.state_data["combatants"]["ardent"]["conditions"] = ["incapacitated"]
        published, capture = _event_collector()
        gm = _mock_gm("Le loup file vers Thorvald.")
        resolver = ActionResolver(gm_agent=gm, combat_gm_agent=gm)

        with (
            patch("app.game.action_resolver.event_bus.publish_to_session", new=capture),
            patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()),
        ):
            await resolver.resolve(
                session_id=SESSION_ID,
                action_type="attack",
                content=None,
                character_id="wolf_1",
                target_id="thorvald",
                active=active,
                actor_kind="monster",
                actor_name="Loup",
            )

        assert active.turn_manager._order[1].action_economy.reaction is True
        assert not [p for et, p in published if et == EventType.OPPORTUNITY_ATTACK_TRIGGERED]

    async def test_companion_ranged_weapon_attacks_without_auto_move(self) -> None:
        active = _make_combat_active()
        active.state_data["combatants"]["hero_1"].update(
            {
                "is_ai": True,
                "attack_range_m": 24.0,
                "reach_m": 1.5,
            }
        )
        active.state_data["grid_config"] = {"cols": 12, "rows": 3, "cell_size_m": 1.5}
        active.state_data["grid_positions"] = {
            "hero_1": {"col": 0, "row": 1},
            "goblin_1": {"col": 10, "row": 1},
        }
        published, capture = _event_collector()
        gm = _mock_gm("Aria tire de loin.")
        resolver = ActionResolver(gm_agent=gm, combat_gm_agent=gm)

        with (
            patch("app.game.action_resolver.event_bus.publish_to_session", new=capture),
            patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()),
        ):
            result = await resolver.resolve(
                session_id=SESSION_ID,
                action_type="attack",
                content=None,
                character_id="hero_1",
                target_id="goblin_1",
                active=active,
                actor_kind="companion",
                actor_name="Aria",
            )

        assert result.mechanics["type"] == "attack"
        assert result.mechanics["tactical"]["moved"] is False
        assert not [p for et, p in published if et == EventType.ERROR]
        assert not [p for et, p in published if et == EventType.COMBATANT_MOVED]

    async def test_companion_thrown_weapon_range_is_accepted(self) -> None:
        active = _make_combat_active()
        active.state_data["combatants"]["hero_1"].update(
            {
                "is_ai": True,
                "attack_range_m": 6.0,
                "reach_m": 1.5,
            }
        )
        active.state_data["grid_config"] = {"cols": 6, "rows": 3, "cell_size_m": 1.5}
        active.state_data["grid_positions"] = {
            "hero_1": {"col": 0, "row": 1},
            "goblin_1": {"col": 4, "row": 1},
        }
        published, capture = _event_collector()
        gm = _mock_gm("Aria lance sa dague.")
        resolver = ActionResolver(gm_agent=gm, combat_gm_agent=gm)

        with (
            patch("app.game.action_resolver.event_bus.publish_to_session", new=capture),
            patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()),
        ):
            result = await resolver.resolve(
                session_id=SESSION_ID,
                action_type="attack",
                content=None,
                character_id="hero_1",
                target_id="goblin_1",
                active=active,
                actor_kind="companion",
                actor_name="Aria",
            )

        assert result.mechanics["type"] == "attack"
        assert result.mechanics["tactical"]["moved"] is False
        assert not [p for et, p in published if et == EventType.ERROR]

    async def test_companion_melee_attack_auto_approaches(self) -> None:
        active = _make_combat_active()
        active.state_data["combatants"]["hero_1"].update(
            {
                "is_ai": True,
                "attack_range_m": 1.5,
                "reach_m": 1.5,
                "speed_m": 9.0,
            }
        )
        active.state_data["grid_config"] = {"cols": 6, "rows": 3, "cell_size_m": 1.5}
        active.state_data["grid_positions"] = {
            "hero_1": {"col": 0, "row": 1},
            "goblin_1": {"col": 4, "row": 1},
        }
        published, capture = _event_collector()
        gm = _mock_gm("Aria rejoint le gobelin.")
        resolver = ActionResolver(gm_agent=gm, combat_gm_agent=gm)

        with (
            patch("app.game.action_resolver.event_bus.publish_to_session", new=capture),
            patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()),
        ):
            result = await resolver.resolve(
                session_id=SESSION_ID,
                action_type="attack",
                content=None,
                character_id="hero_1",
                target_id="goblin_1",
                active=active,
                actor_kind="companion",
                actor_name="Aria",
            )

        assert result.mechanics["type"] == "attack"
        assert result.mechanics["tactical"]["moved"] is True
        hero_pos = active.state_data["grid_positions"]["hero_1"]
        assert max(abs(hero_pos["col"] - 4), abs(hero_pos["row"] - 1)) <= 1
        assert any(et == EventType.COMBATANT_MOVED for et, _ in published)

    async def test_companion_touch_spell_auto_approaches(self) -> None:
        active = _make_combat_active(monster_id="ally_1")
        active.state_data["characters"]["hero_1"].update(
            {
                "char_class": "cleric",
                "ability_scores": {"wis": 16},
            }
        )
        active.state_data["combatants"]["ally_1"].update(
            {
                "name": "Allie",
                "is_player": True,
                "is_ai": False,
                "hp": 5,
                "hp_max": 12,
            }
        )
        active.state_data["grid_config"] = {"cols": 6, "rows": 3, "cell_size_m": 1.5}
        active.state_data["grid_positions"] = {
            "hero_1": {"col": 0, "row": 1},
            "ally_1": {"col": 3, "row": 1},
        }
        published, capture = _event_collector()
        gm = _mock_gm("Aria s'approche pour soigner.")
        resolver = ActionResolver(gm_agent=gm, combat_gm_agent=gm)

        with (
            patch("app.game.action_resolver.event_bus.publish_to_session", new=capture),
            patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()),
        ):
            result = await resolver.resolve(
                session_id=SESSION_ID,
                action_type="cast_spell",
                content=None,
                character_id="hero_1",
                target_id="ally_1",
                active=active,
                spell_id="cure_wounds",
                slot_level=1,
                actor_kind="companion",
                actor_name="Aria",
            )

        assert result.mechanics["type"] == "cast_spell"
        assert result.mechanics["tactical"]["moved"] is True
        assert any(et == EventType.COMBATANT_MOVED for et, _ in published)

    async def test_player_touch_spell_out_of_range_does_not_consume_slot(self) -> None:
        active = _make_combat_active(monster_id="ally_1")
        active.state_data["combatants"]["ally_1"].update(
            {
                "name": "Allie",
                "is_player": True,
                "hp": 5,
                "hp_max": 12,
            }
        )
        active.state_data["grid_config"] = {"cols": 6, "rows": 3, "cell_size_m": 1.5}
        active.state_data["grid_positions"] = {
            "hero_1": {"col": 0, "row": 1},
            "ally_1": {"col": 3, "row": 1},
        }
        published, capture = _event_collector()
        gm = _mock_gm("Ne devrait pas etre appele.")
        resolver = ActionResolver(gm_agent=gm, combat_gm_agent=gm)

        with (
            patch("app.game.action_resolver.event_bus.publish_to_session", new=capture),
            patch(
                "app.game.action_pipeline.spellcasting_service.prepare_cast", new=AsyncMock()
            ) as prepare_cast,
            patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()),
        ):
            result = await resolver.resolve(
                session_id=SESSION_ID,
                action_type="cast_spell",
                content=None,
                character_id="hero_1",
                target_id="ally_1",
                active=active,
                db=object(),
                spell_id="cure_wounds",
                slot_level=1,
            )

        assert result.mechanics["error"] is True
        assert "hors de portee" in result.mechanics["summary"]
        prepare_cast.assert_not_awaited()
        assert [p for et, p in published if et == EventType.ERROR]

    async def test_player_melee_attack_out_of_range_is_rejected_without_turn_cost(self) -> None:
        active = _make_combat_active()
        active.state_data["grid_config"] = {"cols": 8, "rows": 6, "cell_size_m": 1.5}
        active.state_data["grid_positions"] = {
            "hero_1": {"col": 0, "row": 0},
            "goblin_1": {"col": 4, "row": 0},
        }
        published, capture = _event_collector()
        gm = _mock_gm("Ne devrait pas etre appele.")
        resolver = ActionResolver(gm_agent=gm, combat_gm_agent=gm)

        with (
            patch("app.game.action_resolver.event_bus.publish_to_session", new=capture),
            patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()),
        ):
            result = await resolver.resolve(
                session_id=SESSION_ID,
                action_type="attack",
                content=None,
                character_id="hero_1",
                target_id="goblin_1",
                active=active,
            )

        assert result.mechanics["error"] is True
        assert active.state_data["combatants"]["goblin_1"]["hp"] == 7
        assert [p for et, p in published if et == EventType.ERROR]
        assert not [p for et, p in published if et == EventType.ROLL_RESULT]

    async def test_move_rejects_destination_without_path(self) -> None:
        from app.api import ws_game
        from app.api.ws_schemas import PlayerActionMessage

        active = _make_combat_active()
        active.state_data["grid_config"] = {"cols": 4, "rows": 1, "cell_size_m": 1.5}
        active.state_data["grid_positions"] = {
            "hero_1": {"col": 0, "row": 0},
            "goblin_1": {"col": 3, "row": 0},
        }
        active.state_data["grid_decoration"] = {"obstacles": [{"col": 1, "row": 0}]}
        action = PlayerActionMessage(
            type="action",
            action_type="move",
            content="2,0",
            character_id="hero_1",
        )
        published, capture = _event_collector()

        with patch("app.api.ws_game.event_bus.publish_to_session", new=capture):
            await ws_game._handle_move(SESSION_ID, action, active, db=None)

        assert active.state_data["grid_positions"]["hero_1"] == {"col": 0, "row": 0}
        assert [p for et, p in published if et == EventType.ERROR]
        assert not [p for et, p in published if et == EventType.COMBATANT_MOVED]


# ---------------------------------------------------------------------------
# 4. Encounter intro
# ---------------------------------------------------------------------------


class TestEncounterIntro:
    async def test_monster_tokens_stay_stable_when_initiative_reorders(self) -> None:
        from app.api import ws_game

        active = _make_combat_active(monster_id="bandit_1")
        active.state_data["combatants"] = {
            "hero_1": {
                "name": "Aria",
                "hp": 20,
                "hp_max": 20,
                "is_player": True,
                "is_ai": False,
                "ac": 14,
            },
            "bandit_1": {
                "name": "Bandit 1",
                "hp": 11,
                "hp_max": 11,
                "is_player": False,
                "is_ai": True,
                "status": "active",
                "monster_id": "bandit",
                "ac": 12,
            },
            "bandit_2": {
                "name": "Bandit 2",
                "hp": 11,
                "hp_max": 11,
                "is_player": False,
                "is_ai": True,
                "status": "active",
                "monster_id": "bandit",
                "ac": 12,
            },
            "bandit_3": {
                "name": "Bandit 3",
                "hp": 11,
                "hp_max": 11,
                "is_player": False,
                "is_ai": True,
                "status": "active",
                "monster_id": "bandit",
                "ac": 12,
            },
        }
        active.state_data["grid_positions"] = {
            cid: {"col": idx, "row": 0} for idx, cid in enumerate(active.state_data["combatants"])
        }
        active.turn_manager._order = [
            TurnEntry("bandit_3", "Bandit 3", 19, False, True),
            TurnEntry("hero_1", "Aria", 12, True, False),
            TurnEntry("bandit_2", "Bandit 2", 7, False, True),
            TurnEntry("bandit_1", "Bandit 1", 2, False, True),
        ]
        active.turn_manager._index = 2

        payload = ws_game._build_combat_start_payload(active)
        tokens = {c["name"]: c.get("token") for c in payload["combatants"]}

        assert tokens["Bandit 1"] == "B1"
        assert tokens["Bandit 2"] == "B2"
        assert tokens["Bandit 3"] == "B3"

    async def test_generate_encounter_intro_uses_gm_dedicated_method(self) -> None:
        from app.api import ws_game

        active = _make_combat_active()
        published, capture = _event_collector()

        async def run_encounter_intro(**kwargs):
            assert kwargs["combatants"][0]["id"] == "goblin_1"
            return GMResponse(
                narration="Le gobelin ricane : « Approchez donc. »",
                actions=[],
            )

        mock_resolver = MagicMock()
        mock_resolver._gm.run_encounter_intro = AsyncMock(side_effect=run_encounter_intro)

        with (
            patch("app.api.ws_game.action_resolver", mock_resolver),
            patch("app.api.ws_game.event_bus.publish_to_session", new=capture),
            patch("app.api.ws_game.load_recent_messages", new=AsyncMock(return_value=[])),
        ):
            intro = await ws_game._generate_encounter_intro(
                SESSION_ID,
                active,
                MagicMock(),
                active.state_data["combatants"],
            )

        assert intro == "Le gobelin ricane : « Approchez donc. »"
        mock_resolver._gm.run_encounter_intro.assert_awaited_once()
        assert [event_type for event_type, _ in published] == [
            EventType.AI_THINKING,
            EventType.AI_THINKING,
        ]

    async def test_generate_encounter_intro_applies_scene_layout_action(self) -> None:
        from app.api import ws_game

        active = _make_combat_active()
        published, capture = _event_collector()

        mock_resolver = MagicMock()
        mock_resolver._gm.run_encounter_intro = AsyncMock(
            return_value=GMResponse(
                narration="Une cave basse s'ouvre autour d'un brasero.",
                actions=[
                    GMAction(
                        type="scene_layout",
                        params={
                            "cols": 7,
                            "rows": 6,
                            "terrain": "cellar",
                            "pois": [
                                {
                                    "id": "brazier",
                                    "name": "Brasero",
                                    "kind": "light",
                                    "position": {"col": 3, "row": 2},
                                }
                            ],
                            "exits": [],
                            "party_positions": {"hero_1": {"col": 1, "row": 3}},
                        },
                    )
                ],
            )
        )

        with (
            patch("app.api.ws_game.action_resolver", mock_resolver),
            patch("app.api.ws_game.event_bus.publish_to_session", new=capture),
            patch("app.api.ws_game.load_recent_messages", new=AsyncMock(return_value=[])),
        ):
            intro = await ws_game._generate_encounter_intro(
                SESSION_ID,
                active,
                MagicMock(),
                active.state_data["combatants"],
            )

        assert intro == "Une cave basse s'ouvre autour d'un brasero."
        assert active.state_data["current_scene"]["terrain"] == "cellar"
        assert any(event_type == EventType.SCENE_LAYOUT_CHANGED for event_type, _ in published)

    async def test_sommation_intro_pauses_in_encounter_start(self) -> None:
        from app.api import ws_game

        active = _make_combat_active(monster_id="bandit_1")
        active.phase = SessionStatus.EXPLORATION
        active.state_data["phase"] = "exploration"
        active.state_data["pending_encounter"] = {
            "monster_ids": ["bandit"],
            "context": "Un bandit surgit dans les ruines.",
        }
        published, capture = _event_collector()

        mock_resolver = MagicMock()
        mock_resolver._gm.run_encounter_intro = AsyncMock(
            return_value=GMResponse(
                narration="Le bandit lève sa lame : « Pas un pas de plus. »",
                actions=[],
            )
        )

        with (
            patch("app.api.ws_game.action_resolver", mock_resolver),
            patch("app.api.ws_game.event_bus.publish_to_session", new=capture),
            patch("app.api.ws_game._sync_ai_control_from_db", new=AsyncMock(return_value=False)),
            patch("app.api.ws_game.session_manager.save_state", new=AsyncMock()),
            patch("app.api.ws_game.load_recent_messages", new=AsyncMock(return_value=[])),
            patch("app.api.ws_game.persist_narration", new=AsyncMock()),
            patch(
                "app.api.ws_game._build_session_state_payload",
                return_value={"phase": "encounter_start"},
            ),
        ):
            await ws_game._handle_start_combat(SESSION_ID, active, None)

        event_types = [event_type for event_type, _ in published]
        assert active.phase == SessionStatus.ENCOUNTER_START
        assert active.state_data["pending_encounter"]["intro_played"] is True
        assert "combatants" not in active.state_data
        assert "combat_start" not in event_types
        assert EventType.PHASE_CHANGE in event_types

    async def test_intro_start_mode_combat_overrides_pause_markers(self) -> None:
        from app.api import ws_game

        active = _make_combat_active(monster_id="bandit_1")
        active.phase = SessionStatus.EXPLORATION
        active.state_data["phase"] = "exploration"
        active.state_data["pending_encounter"] = {
            "monster_ids": ["bandit"],
            "context": "Un bandit surgit dans les ruines.",
        }
        published, capture = _event_collector()

        mock_resolver = MagicMock()
        mock_resolver._gm.run_encounter_intro = AsyncMock(
            return_value=GMResponse(
                narration="Le bandit crie : « Pas un pas de plus ! » puis charge.",
                actions=[],
                start_mode="combat",
            )
        )

        with (
            patch("app.api.ws_game.action_resolver", mock_resolver),
            patch("app.api.ws_game.event_bus.publish_to_session", new=capture),
            patch("app.api.ws_game._sync_ai_control_from_db", new=AsyncMock(return_value=False)),
            patch("app.api.ws_game._handle_ai_turns", new=AsyncMock()),
            patch("app.api.ws_game.session_manager.save_state", new=AsyncMock()),
            patch("app.api.ws_game.load_recent_messages", new=AsyncMock(return_value=[])),
            patch("app.api.ws_game.persist_narration", new=AsyncMock()),
            patch("app.api.ws_game._build_session_state_payload", return_value={"phase": "combat"}),
        ):
            await ws_game._handle_start_combat(SESSION_ID, active, None)

        event_types = [event_type for event_type, _ in published]
        assert active.phase == SessionStatus.COMBAT
        assert active.state_data.get("pending_encounter") is None
        assert "combat_start" in event_types

    async def test_forced_combat_from_encounter_start_does_not_replay_intro(self) -> None:
        from app.api import ws_game

        active = _make_combat_active(monster_id="bandit_1")
        active.phase = SessionStatus.ENCOUNTER_START
        active.state_data["phase"] = "encounter_start"
        active.state_data["pending_encounter"] = {
            "monster_ids": ["bandit"],
            "intro_played": True,
            "intro_text": "Le bandit lève sa lame : « Pas un pas de plus. »",
        }
        old_intro = active.state_data["pending_encounter"]["intro_text"]
        published, capture = _event_collector()

        mock_resolver = MagicMock()
        mock_resolver._gm.run_encounter_intro = AsyncMock()

        with (
            patch("app.api.ws_game.action_resolver", mock_resolver),
            patch("app.api.ws_game.event_bus.publish_to_session", new=capture),
            patch("app.api.ws_game._sync_ai_control_from_db", new=AsyncMock(return_value=False)),
            patch("app.api.ws_game._handle_ai_turns", new=AsyncMock()),
            patch("app.api.ws_game.session_manager.save_state", new=AsyncMock()),
            patch("app.api.ws_game.persist_narration", new=AsyncMock()),
            patch("app.api.ws_game._build_session_state_payload", return_value={"phase": "combat"}),
        ):
            await ws_game._handle_start_combat(SESSION_ID, active, None, force=True)

        event_types = [event_type for event_type, _ in published]
        narrations = _narrations(published)
        assert active.phase == SessionStatus.COMBAT
        assert "combat_start" in event_types
        assert narrations[-1]["text"] != old_intro
        mock_resolver._gm.run_encounter_intro.assert_not_called()

    def test_build_combat_summary_classifies_all_enemy_outcomes(self) -> None:
        from app.api import ws_game

        active = _make_combat_active(monster_id="bandit_1")
        active.state_data["combatants"].update(
            {
                "bandit_2": {
                    "name": "Bandit 2",
                    "hp": 5,
                    "hp_max": 11,
                    "is_player": False,
                    "status": "fled",
                    "monster_id": "bandit",
                },
                "bandit_3": {
                    "name": "Bandit 3",
                    "hp": 7,
                    "hp_max": 11,
                    "is_player": False,
                    "status": "surrendered",
                    "monster_id": "bandit",
                },
                "emissary": {
                    "name": "Emissaire Zhentarim",
                    "hp": 18,
                    "hp_max": 18,
                    "is_player": False,
                    "status": "active",
                    "monster_id": "bandit",
                },
            }
        )
        active.state_data["combatants"]["bandit_1"]["hp"] = 0
        active.state_data["combatants"]["bandit_1"]["status"] = "active"
        active.state_data["grid_positions"] = {
            "hero_1": {"col": 1, "row": 5},
            "bandit_1": {"col": 3, "row": 2},
            "bandit_2": {"col": 4, "row": 2},
            "bandit_3": {"col": 5, "row": 2},
            "emissary": {"col": 6, "row": 1},
        }

        summary = ws_game._build_combat_summary(active)

        assert summary["outcome"] == "partial"
        assert [e["id"] for e in summary["enemies_defeated"]] == ["bandit_1"]
        assert [e["id"] for e in summary["enemies_fled"]] == ["bandit_2"]
        assert [e["id"] for e in summary["enemies_surrendered"]] == ["bandit_3"]
        assert [e["id"] for e in summary["enemies_unresolved"]] == ["emissary"]
        assert summary["total_enemies"] == 4
        assert summary["enemies_defeated"][0]["position"] == {"col": 3, "row": 2}

    async def test_generate_encounter_end_filters_unsafe_actions(self) -> None:
        from app.api import ws_game

        active = _make_combat_active(monster_id="bandit_1")
        active.state_data["current_scene"] = {
            "cols": 6,
            "rows": 6,
            "cell_size_m": 1.5,
            "terrain": "dock",
            "pois": [],
            "exits": [],
            "party_positions": {},
        }
        summary = ws_game._build_combat_summary(active)
        published, capture = _event_collector()

        mock_resolver = MagicMock()
        mock_resolver._gm.run_encounter_end = AsyncMock(
            return_value=GMResponse(
                narration="Le silence retombe sur le quai.",
                actions=[
                    GMAction(
                        type="damage_apply",
                        target="hero_1",
                        params={"amount": 99, "target": "hero_1"},
                    ),
                    GMAction(
                        type="state_transition",
                        params={"new_phase": "COMBAT"},
                    ),
                    GMAction(
                        type="scene_layout",
                        params={
                            "cols": 6,
                            "rows": 6,
                            "terrain": "dock_aftermath",
                            "pois": [
                                {
                                    "id": "fallen_bandit",
                                    "name": "Bandit au sol",
                                    "kind": "corpse",
                                    "icon": "ruins",
                                    "position": {"col": 3, "row": 2},
                                }
                            ],
                            "exits": [],
                            "party_positions": {},
                        },
                    ),
                    GMAction(
                        type="journal_update",
                        params={"location_place": "Quai silencieux"},
                    ),
                ],
            )
        )

        with (
            patch("app.api.ws_game.action_resolver", mock_resolver),
            patch("app.api.ws_game.event_bus.publish_to_session", new=capture),
            patch("app.api.ws_game.load_recent_messages", new=AsyncMock(return_value=[])),
        ):
            narration, scene_applied = await ws_game._generate_encounter_end(
                SESSION_ID,
                active,
                MagicMock(),
                summary,
            )

        assert narration == "Le silence retombe sur le quai."
        assert scene_applied is True
        assert active.state_data["combatants"]["hero_1"]["hp"] == 20
        assert "pending_phase_transition" not in active.state_data
        assert active.state_data["current_scene"]["terrain"] == "dock_aftermath"
        assert active.state_data["adventure_journal"]["location_place"] == "Quai silencieux"
        assert [event_type for event_type, _ in published].count(EventType.AI_THINKING) == 2

    async def test_handle_combat_end_uses_encounter_end_and_fallback_scene(self) -> None:
        from app.api import ws_game

        active = _make_combat_active(monster_id="bandit_1")
        active.state_data["combatants"]["bandit_1"]["hp"] = 0
        active.state_data["combatants"]["bandit_1"]["status"] = "defeated"
        active.state_data["grid_positions"] = {
            "hero_1": {"col": 1, "row": 4},
            "bandit_1": {"col": 3, "row": 2},
        }
        active.state_data["grid_config"] = {"cols": 6, "rows": 6, "cell_size_m": 1.5}
        active.state_data["current_scene"] = {
            "cols": 6,
            "rows": 6,
            "cell_size_m": 1.5,
            "terrain": "dock",
            "pois": [
                {
                    "id": "bandit_lookout",
                    "name": "Bandit aux aguets",
                    "kind": "enemy",
                    "icon": "npc",
                    "position": {"col": 3, "row": 2},
                },
                {
                    "id": "crate",
                    "name": "Caisse brisee",
                    "kind": "loot",
                    "icon": "chest",
                    "position": {"col": 2, "row": 2},
                },
            ],
            "exits": [
                {
                    "id": "street",
                    "label": "Rue du port",
                    "position": {"col": 5, "row": 3},
                    "leads_to": "harbor_street",
                }
            ],
            "party_positions": {"hero_1": {"col": 1, "row": 4}},
        }
        active.turn_manager._order = [
            TurnEntry("hero_1", "Aria", 18, True, False),
        ]
        active.turn_manager._mode = "combat"
        active.turn_manager._round = 1
        published, capture = _event_collector()

        mock_resolver = MagicMock()
        mock_resolver._gm = object()

        with (
            patch("app.api.ws_game.action_resolver", mock_resolver),
            patch("app.api.ws_game.event_bus.publish_to_session", new=capture),
            patch("app.api.ws_game.session_manager.save_state", new=AsyncMock()),
            patch("app.api.ws_game.persist_narration", new=AsyncMock()),
            patch(
                "app.api.ws_game._build_session_state_payload",
                return_value={"phase": "exploration"},
            ),
            patch(
                "app.services.campaign_dossier_service.synthesize_canon_for_session",
                new=AsyncMock(),
            ),
        ):
            await ws_game._handle_combat_end(
                SESSION_ID,
                active,
                MagicMock(),
                reason="victory",
                removed_npcs=[
                    {
                        "combatant_id": "bandit_1",
                        "name": "Bandit",
                        "status": "defeated",
                        "position": {"col": 3, "row": 2},
                    }
                ],
            )

        event_types = [event_type for event_type, _ in published]
        phase_payloads = [
            payload["phase"]
            for event_type, payload in published
            if event_type == EventType.PHASE_CHANGE
        ]
        narrations = _narrations(published)
        scene = active.state_data["current_scene"]
        poi_ids = {poi["id"] for poi in scene["pois"]}

        assert active.phase == SessionStatus.EXPLORATION
        assert event_types.index(EventType.COMBAT_END) < event_types.index(EventType.NARRATION)
        assert phase_payloads == ["encounter_end", "exploration"]
        assert narrations[-1]["text"] == (
            "Victoire ! Tous les ennemis ont été vaincus. Le calme revient."
        )
        assert "bandit_lookout" not in poi_ids
        assert "crate" in poi_ids
        assert any(poi["kind"] == "corpse" for poi in scene["pois"])
        assert scene["exits"][0]["id"] == "street"
        assert EventType.SCENE_LAYOUT_CHANGED in event_types
        assert EventType.SESSION_STATE in event_types


# ---------------------------------------------------------------------------
# 5. Cohérence entre les trois acteurs
# ---------------------------------------------------------------------------


class TestThreeActorsNarrationFormat:
    async def test_all_three_actors_emit_narration_event(self) -> None:
        """Chaque chemin de résolution doit émettre au moins un NARRATION event."""
        # --- Joueur humain ---
        active_h = _make_combat_active()
        resolver_h = ActionResolver(gm_agent=_mock_gm("Narration humain"))
        published_h, capture_h = _event_collector()
        with (
            patch("app.game.action_resolver.event_bus.publish_to_session", new=capture_h),
            patch("app.game.action_resolver.tts_router.synthesize_and_broadcast", new=AsyncMock()),
        ):
            await resolver_h.resolve(
                session_id=SESSION_ID,
                action_type="free_text",
                content="Je cherche",
                character_id="hero_1",
                target_id=None,
                active=active_h,
                db=None,
            )
        assert _narrations(published_h), "Joueur humain doit émettre NARRATION"

        # --- Monstre ---
        from app.api.ws_game import _handle_ai_turns

        active_m = _make_combat_active(monster_turn_first=True)
        published_m, capture_m = _event_collector()
        mock_gm_resp = AgentResponse(content="Narration monstre", actions=[])
        with (
            patch("app.api.ws_game.event_bus.publish_to_session", new=capture_m),
            patch(
                "app.api.ws_game.action_resolver._gm.think",
                new=AsyncMock(return_value=mock_gm_resp),
            ),
            patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()),
            patch("app.api.ws_game.session_manager.save_state", new=AsyncMock()),
            patch("app.api.ws_game._cleanup_inactive_npcs", new=AsyncMock(return_value=[])),
            patch("app.api.ws_game._build_session_state_payload", return_value={"phase": "combat"}),
        ):
            active_m.turn_manager.all_npcs_removed = MagicMock(return_value=False)
            await _handle_ai_turns(SESSION_ID, active_m, None)
        assert _narrations(published_m), "Monstre doit émettre NARRATION"

    async def test_monster_and_human_use_same_narration_speaker(self) -> None:
        """Tous les acteurs emettent NARRATION avec speaker='Maître du Jeu'."""
        # --- Joueur humain ---
        active_h = _make_combat_active()
        published_h, capture_h = _event_collector()
        with (
            patch("app.game.action_resolver.event_bus.publish_to_session", new=capture_h),
            patch("app.game.action_resolver.tts_router.synthesize_and_broadcast", new=AsyncMock()),
        ):
            await ActionResolver(gm_agent=_mock_gm("Narration")).resolve(
                session_id=SESSION_ID,
                action_type="free_text",
                content="J'avance",
                character_id="hero_1",
                target_id=None,
                active=active_h,
                db=None,
            )
        human_speaker = _narrations(published_h)[-1].get("speaker")

        # --- Monstre ---
        from app.api.ws_game import _handle_ai_turns

        active_m = _make_combat_active(monster_turn_first=True)
        published_m, capture_m = _event_collector()
        mock_gm_resp = AgentResponse(content="Narration", actions=[])
        with (
            patch("app.api.ws_game.event_bus.publish_to_session", new=capture_m),
            patch(
                "app.api.ws_game.action_resolver._gm.think",
                new=AsyncMock(return_value=mock_gm_resp),
            ),
            patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast", new=AsyncMock()),
            patch("app.api.ws_game.session_manager.save_state", new=AsyncMock()),
            patch("app.api.ws_game._cleanup_inactive_npcs", new=AsyncMock(return_value=[])),
            patch("app.api.ws_game._build_session_state_payload", return_value={"phase": "combat"}),
        ):
            active_m.turn_manager.all_npcs_removed = MagicMock(return_value=False)
            await _handle_ai_turns(SESSION_ID, active_m, None)
        monster_speaker = _narrations(published_m)[-1].get("speaker")

        assert human_speaker == monster_speaker, (
            f"Speakers divergent : humain={human_speaker!r}, monstre={monster_speaker!r}"
        )


# ---------------------------------------------------------------------------
# Phase 0 — Détection PNJ anonymisé par mots-clés de description
# ---------------------------------------------------------------------------


class TestDetectNpcTargetByDescription:
    """Le pipeline doit identifier un PNJ anonyme désigné par sa description."""

    def _state_with_anonymous_npc(self) -> dict:
        return {
            "current_scene": {
                "pois": [
                    {
                        "id": "volothamp",
                        "name": "Volothamp Geddarm",
                        "kind": "npc",
                        "known_to_party": False,
                        "description": (
                            "Un cartographe excentrique en chapeau à plumes, tenant un carnet."
                        ),
                    },
                    {
                        "id": "tente_bleue",
                        "name": "Tente bleue",
                        "kind": "clue",
                        "description": "Une tente bleue vive au cœur du marché.",
                    },
                ]
            },
            "npc_states": {
                "volothamp": {
                    "name": "Volothamp Geddarm",
                    "attitude": "friendly",
                    "known_to_party": False,
                    "description": (
                        "Un cartographe excentrique en chapeau à plumes, tenant un carnet."
                    ),
                }
            },
        }

    def test_descriptive_approach_matches_anonymous_npc(self) -> None:
        from app.game.social_resolution import resolve_npc_target_id

        text = "Je m'approche de l'homme au chapeau à plumes et le salue d'un geste désinvolte."
        npc_id = resolve_npc_target_id(text, self._state_with_anonymous_npc())
        assert npc_id == "volothamp"

    def test_exact_name_still_wins(self) -> None:
        from app.game.social_resolution import resolve_npc_target_id

        state = self._state_with_anonymous_npc()
        # Le joueur l'a déjà engagé : known_to_party=True et nom visible.
        state["npc_states"]["volothamp"]["known_to_party"] = True
        text = "Je demande à Volothamp ce qu'il sait de la Tombe."
        npc_id = resolve_npc_target_id(text, state)
        assert npc_id == "volothamp"

    def test_unrelated_action_returns_none(self) -> None:
        from app.game.social_resolution import resolve_npc_target_id

        text = "Je marche jusqu'à la fontaine pour boire."
        npc_id = resolve_npc_target_id(text, self._state_with_anonymous_npc())
        assert npc_id is None

    def test_single_present_npc_accepts_one_keyword_match(self) -> None:
        from app.game.social_resolution import resolve_npc_target_id

        text = "J'aborde le cartographe."
        npc_id = resolve_npc_target_id(text, self._state_with_anonymous_npc())
        assert npc_id == "volothamp"

    def test_clue_poi_is_never_matched_as_npc(self) -> None:
        from app.game.social_resolution import resolve_npc_target_id

        state = self._state_with_anonymous_npc()
        # On retire le PNJ pour ne laisser que la tente bleue.
        state["current_scene"]["pois"] = [
            poi for poi in state["current_scene"]["pois"] if poi.get("kind") != "npc"
        ]
        state["npc_states"] = {}
        text = "J'examine la tente bleue au cœur du marché."
        npc_id = resolve_npc_target_id(text, state)
        assert npc_id is None


class TestFailForward:
    """N4 — fail-forward déterministe + anti-roll-spam sur échec d'investigation.

    Chronique « Haut les Cœurs » : Thorvald rate l'investigation de
    `clue_corrupted_bird` (msg 3, total 4 vs DC 14), le MJ écrit « ne livre aucun
    secret immédiat », puis Thorvald relance le MÊME jet sur le MÊME POI (msg 9).
    """

    @staticmethod
    def _active_with_clue_poi() -> ActiveSession:
        return ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={
                "current_scene": {
                    "pois": [
                        {
                            "id": "clue_corrupted_bird",
                            "name": "Oiseau pétrifié",
                            "description": (
                                "Un passereau changé en cristal violet, figé en plein cri."
                            ),
                        }
                    ]
                }
            },
        )

    @staticmethod
    def _failed_roll(
        *,
        poi: str = "clue_corrupted_bird",
        label: str = "INT (Investigation)",
        intent: str = "search",
    ) -> dict:
        return {
            "success": False,
            "scene_poi_id": poi,
            "scene_poi_name": "Oiseau pétrifié",
            "scene_interaction_intent": intent,
            "label": label,
            "dc": 14,
            "total": 4,
        }

    def test_failed_investigation_injects_material(self) -> None:
        active = self._active_with_clue_poi()
        out = ActionPipeline._inject_fail_forward(self._failed_roll(), active)
        assert out["fail_forward"] is True
        assert out["fail_forward_attempt"] == 1
        assert out["fail_forward_subject"] == "Oiseau pétrifié"
        # Le MJ reçoit de la matière concrète (la description du POI) à révéler.
        assert "cristal" in out["fail_forward_detail"].lower()

    def test_identical_reroll_same_skill_escalates(self) -> None:
        active = self._active_with_clue_poi()
        ActionPipeline._inject_fail_forward(self._failed_roll(), active)
        out2 = ActionPipeline._inject_fail_forward(self._failed_roll(), active)
        assert out2["fail_forward_attempt"] == 2

    def test_switching_skill_resets_counter(self) -> None:
        # Investigation → Arcane = nouvelle approche, pas du spam : repart à 1.
        active = self._active_with_clue_poi()
        ActionPipeline._inject_fail_forward(self._failed_roll(label="INT (Investigation)"), active)
        out = ActionPipeline._inject_fail_forward(self._failed_roll(label="INT (Arcana)"), active)
        assert out["fail_forward_attempt"] == 1

    def test_success_does_not_inject(self) -> None:
        active = self._active_with_clue_poi()
        roll = self._failed_roll()
        roll["success"] = True
        out = ActionPipeline._inject_fail_forward(roll, active)
        assert "fail_forward" not in out

    def test_saving_throw_does_not_inject(self) -> None:
        active = self._active_with_clue_poi()
        out = ActionPipeline._inject_fail_forward(
            self._failed_roll(label="DEX Save", intent=""), active
        )
        assert "fail_forward" not in out

    def test_no_poi_does_not_inject(self) -> None:
        active = self._active_with_clue_poi()
        out = ActionPipeline._inject_fail_forward(self._failed_roll(poi=""), active)
        assert "fail_forward" not in out

    def test_non_investigative_action_does_not_inject(self) -> None:
        active = self._active_with_clue_poi()
        out = ActionPipeline._inject_fail_forward(
            self._failed_roll(label="STR (Athletics)", intent="climb"), active
        )
        assert "fail_forward" not in out
