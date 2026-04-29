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
from app.game.turn_manager import TurnEntry
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
    async def test_roll_request_publishes_only_outcome_narration(self) -> None:
        active = _make_combat_active()
        active.state_data["characters"]["hero_1"]["ability_scores"] = {"wis": 16}
        bus = _FakeBus()

        gm = MagicMock()
        gm.think = AsyncMock(return_value=AgentResponse(
            content="Aria observe les traces.",
            actions=[
                GMAction(
                    type="roll_request",
                    target="hero_1",
                    params={"ability": "wis", "type": "check", "dc": 10},
                )
            ],
        ))
        gm.narrate_outcome_response = AsyncMock(return_value=GMResponse(
            narration="Les traces confirment un passage recent.",
            actions=[],
        ))

        pipeline = ActionPipeline(gm, bus, mechanics=ActionResolver(gm_agent=gm))
        with patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast",
                   new=AsyncMock()):
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

    async def test_pipeline_ignores_gm_damage_apply_in_combat(self) -> None:
        active = _make_combat_active()
        bus = _FakeBus()
        gm = MagicMock()
        gm.think = AsyncMock(return_value=AgentResponse(
            content="Le gobelin chancelle.",
            actions=[
                GMAction(
                    type="damage_apply",
                    target="goblin_1",
                    params={"amount": 3},
                )
            ],
        ))

        pipeline = ActionPipeline(gm, bus, mechanics=ActionResolver(gm_agent=gm))
        with patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast",
                   new=AsyncMock()):
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
        with patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast",
                   new=AsyncMock()):
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

        with patch("app.game.action_resolver.event_bus.publish_to_session", new=capture), \
             patch("app.game.action_resolver.tts_router.synthesize_and_broadcast",
                   new=AsyncMock()):
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

        with patch("app.game.action_resolver.event_bus.publish_to_session", new=capture), \
             patch("app.game.action_resolver.tts_router.synthesize_and_broadcast",
                   new=AsyncMock()):
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

        with patch("app.game.action_resolver.event_bus.publish_to_session", new=capture), \
             patch("app.game.action_resolver.tts_router.synthesize_and_broadcast",
                   new=AsyncMock()):
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

        with patch("app.game.action_resolver.event_bus.publish_to_session", new=capture), \
             patch("app.game.action_resolver.tts_router.synthesize_and_broadcast",
                   new=AsyncMock()):
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

    async def test_social_prompt_skips_gm_and_sets_party_intent(self) -> None:
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={"characters": {"hero_1": {"name": "Aria"}}},
        )
        active.ai_players = {"ai_1": MagicMock()}
        resolver = ActionResolver(gm_agent=_mock_gm("Ne devrait pas etre appele."))
        published, capture = _event_collector()

        with patch("app.game.action_resolver.event_bus.publish_to_session", new=capture), \
             patch("app.game.action_resolver.tts_router.synthesize_and_broadcast",
                   new=AsyncMock()):
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

        with patch("app.llm.budget.get_llm_budget_mode", return_value="sober"), \
             patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast",
                   new=AsyncMock()):
            await pipeline.resolve_and_publish(
                ActionRequest(
                    session_id=SESSION_ID,
                    actor_id="shade_1",
                    actor_name="Shade",
                    actor_kind="companion",
                    action_type="examine",
                    content="[Compagnon IA] Shade examine le passage secret.",
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

        attack_json = json.dumps({
            "action_type": "attack",
            "action_description": "Thorin attaque le gobelin",
            "target": "goblin_1",
            "params": {},
            "roleplay_text": "Pour la gloire !",
            "inner_reasoning": "Attaque.",
        }, ensure_ascii=False)

        mock_chat = AsyncMock(return_value=attack_json)
        with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=capture), \
             patch.object(thorin_agent._client, "chat", new=mock_chat):
            await manager.process_ai_turns(SESSION_ID, active, mock_resolver, db=None)

        # Le compagnon doit émettre au moins une NARRATION avec son texte de roleplay
        narrs = _narrations(published)
        assert len(narrs) >= 1
        assert any(n.get("text") for n in narrs)
        # L'action_resolver doit avoir été appelé (pipeline mécanique + GM)
        mock_resolver.resolve.assert_called_once()
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

        with patch("app.api.ws_game.event_bus.publish_to_session", new=capture), \
             patch("app.api.ws_game.action_resolver.resolve", new=mock_resolve), \
             patch("app.api.ws_game.session_manager.save_state", new=AsyncMock()), \
             patch("app.api.ws_game._build_session_state_payload",
                   return_value={"phase": "combat"}):
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
            if event_type == EventType.TURN_START
            and payload.get("combatant_id") == "elara_1"
        )
        assert defeated_idx < elara_turn_idx

        resolved_actor_ids = [
            call.kwargs["character_id"]
            for call in mock_resolve.await_args_list
        ]
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

        with patch("app.api.ws_game.event_bus.publish_to_session", new=capture), \
             patch("app.api.ws_game.action_resolver._gm.think", new=mock_gm_think), \
             patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast",
                   new=AsyncMock()), \
             patch("app.api.ws_game.session_manager.save_state", new=AsyncMock()), \
             patch("app.api.ws_game._cleanup_inactive_npcs",
                   new=AsyncMock(return_value=[])), \
             patch("app.api.ws_game._build_session_state_payload",
                   return_value={"phase": "combat"}):
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

        with patch("app.api.ws_game.event_bus.publish_to_session", new=capture), \
             patch("app.api.ws_game.action_resolver._gm.think",
                   new=AsyncMock(return_value=mock_gm_resp)), \
             patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast",
                   new=AsyncMock()), \
             patch("app.api.ws_game.session_manager.save_state", new=AsyncMock()), \
             patch("app.api.ws_game._cleanup_inactive_npcs",
                   new=AsyncMock(return_value=[])), \
             patch("app.api.ws_game._build_session_state_payload",
                   return_value={"phase": "combat"}):
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

        with patch("app.api.ws_game.event_bus.publish_to_session", new=capture), \
             patch("app.api.ws_game.action_resolver._gm.think",
                   new=AsyncMock(return_value=mock_gm_resp)), \
             patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast",
                   new=AsyncMock()), \
             patch("app.api.ws_game.session_manager.save_state", new=AsyncMock()), \
             patch("app.api.ws_game._cleanup_inactive_npcs",
                   new=AsyncMock(return_value=[])), \
             patch("app.api.ws_game._build_session_state_payload",
                   return_value={"phase": "combat"}):
            active.turn_manager.all_npcs_removed = MagicMock(return_value=False)
            await _handle_ai_turns(SESSION_ID, active, None)

        narrs = _narrations(published)
        assert narrs
        assert narrs[-1].get("speaker") == "Maître du Jeu"


# ---------------------------------------------------------------------------
# 4. Cohérence entre les trois acteurs
# ---------------------------------------------------------------------------


class TestThreeActorsNarrationFormat:
    async def test_all_three_actors_emit_narration_event(self) -> None:
        """Chaque chemin de résolution doit émettre au moins un NARRATION event."""
        # --- Joueur humain ---
        active_h = _make_combat_active()
        resolver_h = ActionResolver(gm_agent=_mock_gm("Narration humain"))
        published_h, capture_h = _event_collector()
        with patch("app.game.action_resolver.event_bus.publish_to_session",
                   new=capture_h), \
             patch("app.game.action_resolver.tts_router.synthesize_and_broadcast",
                   new=AsyncMock()):
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
        with patch("app.api.ws_game.event_bus.publish_to_session", new=capture_m), \
             patch("app.api.ws_game.action_resolver._gm.think",
                   new=AsyncMock(return_value=mock_gm_resp)), \
             patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast",
                   new=AsyncMock()), \
             patch("app.api.ws_game.session_manager.save_state", new=AsyncMock()), \
             patch("app.api.ws_game._cleanup_inactive_npcs",
                   new=AsyncMock(return_value=[])), \
             patch("app.api.ws_game._build_session_state_payload",
                   return_value={"phase": "combat"}):
            active_m.turn_manager.all_npcs_removed = MagicMock(return_value=False)
            await _handle_ai_turns(SESSION_ID, active_m, None)
        assert _narrations(published_m), "Monstre doit émettre NARRATION"

    async def test_monster_and_human_use_same_narration_speaker(self) -> None:
        """Tous les acteurs emettent NARRATION avec speaker='Maître du Jeu'."""
        # --- Joueur humain ---
        active_h = _make_combat_active()
        published_h, capture_h = _event_collector()
        with patch("app.game.action_resolver.event_bus.publish_to_session",
                   new=capture_h), \
             patch("app.game.action_resolver.tts_router.synthesize_and_broadcast",
                   new=AsyncMock()):
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
        with patch("app.api.ws_game.event_bus.publish_to_session", new=capture_m), \
             patch("app.api.ws_game.action_resolver._gm.think",
                   new=AsyncMock(return_value=mock_gm_resp)), \
             patch("app.game.action_pipeline.tts_router.synthesize_and_broadcast",
                   new=AsyncMock()), \
             patch("app.api.ws_game.session_manager.save_state", new=AsyncMock()), \
             patch("app.api.ws_game._cleanup_inactive_npcs",
                   new=AsyncMock(return_value=[])), \
             patch("app.api.ws_game._build_session_state_payload",
                   return_value={"phase": "combat"}):
            active_m.turn_manager.all_npcs_removed = MagicMock(return_value=False)
            await _handle_ai_turns(SESSION_ID, active_m, None)
        monster_speaker = _narrations(published_m)[-1].get("speaker")

        assert human_speaker == monster_speaker, (
            f"Speakers divergent : humain={human_speaker!r}, monstre={monster_speaker!r}"
        )
