"""Pipeline unifie de resolution et publication d'action.

Le pipeline centralise le contrat visible :
action acteur -> resolution mecanique -> ROLL_RESULT -> narration MJ.
Il ne choisit pas les actions et ne fait pas avancer les tours.
"""

from __future__ import annotations

import logging
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.agents.schemas import AgentContext, AgentResponse, GMAction, GMResponse
from app.engine.ability_checks import SKILL_ABILITY, Ability, Proficiency, skill_check
from app.engine.tactical_grid import GridPosition
from app.game.action_narration import (
    _FALLBACK_NARRATION,
    _infer_risky_roll_request,
    _tactical_block_narration,
)
from app.game.action_orchestrator import ActionOrchestrator
from app.game.combat_triggers import prime_combat_from_hostile_narration
from app.game.constants import INACTIVE_STATUSES
from app.game.event_bus import EventType, event_bus
from app.game.gm_response_executor import GMResponseExecutor
from app.game.session_manager import ActiveSession
from app.game.social_resolution import (
    _ability_short_key,
    _calculate_social_dc,
    _detect_social_skill,
    _is_combat_social_text,
    _is_social_exploration_text,
    _normalized_skill_proficiencies,
    resolve_npc_target_id,
)
from app.game.social_scene_state import resolve_scene_interaction_context
from app.game.stealth_resolution import resolve_hide_action
from app.game.tactical_combat import (
    apply_tactical_move,
    calculate_reachable_cells,
    choose_attack_target,
    combatant_speed_m,
    prepare_attack,
    prepare_cast_spell,
)
from app.llm.budget import (
    begin_llm_call_scope,
    end_llm_call_scope,
    is_pure_companion_social_prompt,
    is_sober_mode,
    should_use_gm_for_action,
)
from app.llm.voxtral_client import tts_router
from app.services import campaign_dossier_service
from app.services.spellcasting_service import SpellcastingService, SpellcastingServiceError

logger = logging.getLogger(__name__)

ResolvedActionResult = tuple[
    str | None,
    str,
    dict[str, Any] | None,
    list[dict[str, Any]],
    Optional["ResolvedAction"],
]

spellcasting_service = SpellcastingService()


class ActionRequest(BaseModel):
    """Action normalisee envoyee au pipeline."""

    session_id: str
    actor_id: str | None = None
    actor_name: str | None = None
    actor_kind: Literal["player", "companion", "monster"] = "player"
    action_type: str
    content: str | None = None
    target_id: str | None = None
    spell_id: str | None = None
    slot_level: int | None = None
    display_text: str | None = None
    persist_actor_action: bool = True
    suppress_gm_narration: bool = False
    scene_poi_id: str | None = None
    scene_interaction_id: str | None = None
    scene_interaction_intent: str | None = None
    scene_interaction_context: dict[str, Any] = Field(default_factory=dict)
    travel_intent: dict[str, Any] | None = None


class ResolvedAction(BaseModel):
    """Resultat structure d'une action resolue et publiee."""

    actor_id: str | None = None
    actor_name: str = ""
    actor_kind: Literal["player", "companion", "monster"]
    action_type: str
    target_id: str | None = None
    mechanics: dict[str, Any] = Field(default_factory=dict)
    roll_events: list[dict[str, Any]] = Field(default_factory=list)
    narration: str = ""
    gm_actions: list[dict[str, Any]] = Field(default_factory=list)
    canon_dirty: bool = False


class ActionPipeline:
    """Resolve une action et publie les evenements canoniques."""

    def __init__(
        self,
        gm_agent: Any,
        event_bus_instance: Any = event_bus,
        db: Any | None = None,
        *,
        mechanics: Any | None = None,
        combat_gm_agent: Any | None = None,
        source: str = "action_pipeline",
    ) -> None:
        self._gm = gm_agent
        self._combat_gm = combat_gm_agent or gm_agent
        self._event_bus = event_bus_instance
        self._db = db
        self._mechanics = mechanics
        self._source = source
        self._executor = GMResponseExecutor(event_bus_instance, source=source)
        self._orchestrator = ActionOrchestrator(
            event_bus_instance,
            source=source,
            tts_router=tts_router,
        )

    async def resolve_and_publish(
        self,
        request: ActionRequest,
        active: ActiveSession,
        db: Any | None = None,
    ) -> ResolvedAction:
        """Execute le flux complet pour une action deja choisie."""
        token, scope = begin_llm_call_scope(
            request.session_id,
            f"{request.actor_kind}:{request.action_type}",
        )
        try:
            return await self._resolve_and_publish_impl(request, active, db)
        finally:
            end_llm_call_scope(token, scope)

    async def _resolve_and_publish_impl(
        self,
        request: ActionRequest,
        active: ActiveSession,
        db: Any | None = None,
    ) -> ResolvedAction:
        """Execute le flux complet pour une action deja choisie."""
        actual_db = db if db is not None else self._db
        actor_name = request.actor_name or self._actor_name(
            request.actor_id,
            request.actor_kind,
            active.state_data,
        )
        target_id = request.target_id or self._default_target_id(request, active.state_data)
        target_name = self._combatant_name(active.state_data, target_id)
        display_text = self._display_text(request, actor_name, target_name)
        phase_value = self._phase_value(active).upper()
        scene_interaction_context = resolve_scene_interaction_context(
            active,
            poi_id=request.scene_poi_id,
            interaction_id=request.scene_interaction_id,
            interaction_intent=request.scene_interaction_intent,
        )
        if scene_interaction_context:
            request.scene_interaction_context = scene_interaction_context

        roll_results: dict[str, Any] | None = None
        roll_events: list[dict[str, Any]] = []
        executed_actions: list[dict[str, Any]] = []
        canon_dirty = False

        # 1. Resolution mecanique pure.
        # 1. Resolution mecanique pure par delegation.
        if request.action_type == "attack":
            (
                target_id,
                target_name,
                roll_results,
                executed_actions,
                err_act,
            ) = await self._resolve_attack_action(
                request,
                active,
                phase_value,
                actor_name,
                target_id,
                actual_db,
            )
            if err_act is not None:
                return err_act
        elif request.action_type == "death_save":
            roll_results = await self._resolve_death_save_action(request, active)
        elif request.action_type == "stabilize":
            roll_results = await self._resolve_stabilize_action(request, active, target_id)
        elif request.action_type in ("move", "dash", "disengage") and phase_value == "COMBAT":
            err_act = await self._resolve_movement_actions(
                request,
                active,
                phase_value,
                actor_name,
                target_id,
            )
            if err_act is not None:
                return err_act
        elif request.action_type == "hide":
            err_act = await self._consume_hide_action(
                request,
                active,
                phase_value,
                actor_name,
                target_id,
            )
            if err_act is not None:
                return err_act
            roll_results = resolve_hide_action(active, request.actor_id)
        elif request.action_type == "cast_spell":
            (
                target_id,
                target_name,
                roll_results,
                executed_actions,
                err_act,
            ) = await self._resolve_cast_spell_action(
                request,
                active,
                phase_value,
                actor_name,
                target_id,
                actual_db,
            )
            if err_act is not None:
                return err_act
        elif request.action_type == "free_text" and _is_social_exploration_text(request.content):
            roll_results = self._resolve_social_check(request, active)
        elif (
            phase_value == "EXPLORATION"
            and request.action_type == "free_text"
            and request.actor_kind == "player"
            and scene_interaction_context
        ):
            roll_results = self._resolve_scene_interaction_roll(request, active)
        if roll_results:
            roll_results = self._enrich_mechanics_result(
                roll_results,
                request,
                actor_name,
                target_id,
                active,
            )

        # 2. Persistance visible puis contexte GM avec resume mecanique.
        if request.persist_actor_action:
            await self._persist_actor_action(
                request.session_id,
                display_text,
                actor_name,
                request,
                target_id,
                actual_db,
            )

        prompt_action_text = self._prompt_action_text(
            request,
            actor_name,
            target_name,
            roll_results,
        )
        use_gm = should_use_gm_for_action(
            phase=phase_value,
            action_type=request.action_type,
            actor_kind=request.actor_kind,
            content=request.content,
            roll_results=roll_results,
        )
        if request.suppress_gm_narration:
            use_gm = False
        if (
            is_sober_mode()
            and phase_value != "COMBAT"
            and is_pure_companion_social_prompt(request.action_type, request.content)
            and not request.suppress_gm_narration
            and not active.ai_players
        ):
            use_gm = True
        context: AgentContext | None = None

        gm_response: AgentResponse | None = None
        if use_gm:
            recent_messages: list[Any] = []
            try:
                # L'indicateur d'attente doit s'allumer AVANT toute I/O (lecture
                # de l'historique en DB, snapshot du game state) pour un retour
                # immédiat côté joueur. Le finally garantit son extinction même
                # si une de ces étapes échoue (route alors vers la branche erreur).
                await self._publish_ai_thinking(request.session_id, True)
                if actual_db is not None:
                    from app.services.message_service import load_recent_messages

                    recent_messages = await load_recent_messages(request.session_id, actual_db)

                game_state_for_gm = await self._game_state_for_gm(
                    request.session_id,
                    active,
                    actual_db,
                )
                context = AgentContext(
                    session_id=request.session_id,
                    game_phase=phase_value,
                    game_state=game_state_for_gm,
                    player_action=prompt_action_text,
                    roll_results=roll_results or {},
                    messages=recent_messages,
                    travel_intent=request.travel_intent,
                )
                gm_agent = self._gm_for_phase(phase_value)
                gm_candidate = await gm_agent.think(context)
                gm_response = self._as_agent_response(gm_candidate)
                if gm_response and roll_results:
                    gm_response = self._ensure_actor_attribution(
                        gm_response,
                        roll_results,
                    )
                if (
                    gm_response
                    and gm_response.content == _FALLBACK_NARRATION
                    and not gm_response.actions
                ):
                    err_msg = "Service IA indisponible. Vérifiez le provider LLM configuré."
                    await self._event_bus.publish_to_session(
                        request.session_id,
                        EventType.ERROR,
                        {"message": err_msg},
                        source=self._source,
                    )
            except Exception as exc:
                logger.error("ActionPipeline : GMAgent echoue : %s", exc)
                await self._event_bus.publish_to_session(
                    request.session_id,
                    EventType.ERROR,
                    {"message": "Le service de narration IA est temporairement indisponible."},
                    source=self._source,
                )
            finally:
                await self._publish_ai_thinking(request.session_id, False)

        if gm_response and phase_value == "COMBAT":
            gm_response = self._with_social_roll_fallback(
                gm_response,
                request,
                target_id,
                active.state_data,
            )
        if gm_response and roll_results and roll_results.get("type") == "skill_check":
            gm_response = self._without_redundant_social_roll_requests(
                gm_response,
                roll_results,
            )
        if gm_response and roll_results and roll_results.get("scene_poi_id"):
            gm_response = self._with_scene_interaction_update_fallback(
                gm_response,
                roll_results,
            )
        if gm_response and phase_value == "EXPLORATION":
            gm_response = self._with_travel_scene_fallback(gm_response, request, active)

        if gm_response:
            active.last_gm_intent = gm_response.action_intent
        elif (
            is_sober_mode()
            and phase_value != "COMBAT"
            and is_pure_companion_social_prompt(request.action_type, request.content)
        ):
            active.last_gm_intent = "social"
        else:
            active.last_gm_intent = None

        has_gm_roll_request = bool(
            gm_response
            and any(
                gm_action.type in {"roll_request", "stealth_event"}
                for gm_action in gm_response.actions
            )
        )

        # Garde-fou hors-combat : si le MJ n'a pas émis de résolution différée pour une
        # action libre contenant un verbe risqué (et qu'aucun résultat mécanique
        # n'existe déjà), on injecte un roll_request minimal de sauvegarde.
        # Conservateur : ne s'applique qu'en exploration, sur free_text humain.
        if (
            not has_gm_roll_request
            and not roll_results
            and phase_value == "EXPLORATION"
            and request.action_type == "free_text"
            and request.actor_kind == "player"
        ):
            fallback_roll = _infer_risky_roll_request(request.content or "")
            if fallback_roll and gm_response is not None:
                gm_response.actions.append(
                    GMAction(
                        type=fallback_roll["type"],
                        target=fallback_roll.get("target"),
                        params=fallback_roll.get("params", {}),
                    )
                )
                has_gm_roll_request = True
                logger.debug(
                    "ActionPipeline : roll_request fallback injecte pour action risquee : %r",
                    request.content,
                )

        if gm_response and phase_value == "COMBAT":
            gm_response = self._without_combat_damage_actions(gm_response)

        if gm_response and not has_gm_roll_request:
            prime_combat_from_hostile_narration(
                active,
                gm_response.content,
                source="gm_narration",
            )

        # 3. Evenement canonique de jet mecanique initial.
        if roll_results:
            mechanics = self._get_mechanics()
            roll_evt = mechanics._normalize_roll_event(roll_results)
            roll_evt = self._enrich_roll_event(roll_evt, request, actor_name, target_id)
            roll_events.append(roll_evt)
            await self._event_bus.publish_to_session(
                request.session_id,
                EventType.ROLL_RESULT,
                roll_evt,
                source=self._source,
            )
            from app.services.message_service import persist_roll_result

            await persist_roll_result(request.session_id, roll_evt, actual_db)

        if request.suppress_gm_narration:
            narration_text = ""
        elif gm_response:
            narration_text = gm_response.content
        elif use_gm:
            narration_text = _FALLBACK_NARRATION
        else:
            narration_text = self._deterministic_narration(
                request,
                actor_name,
                target_name,
                roll_results,
            )
        final_narration = narration_text
        if not has_gm_roll_request and narration_text:
            await self._publish_gm_narration(request.session_id, narration_text, actual_db)

        # 4. Actions GM initiales. Si roll_request/stealth_event, l'outcome narrera le resultat.
        pending_rolls: list[dict[str, Any]] = []
        if gm_response:
            exec_result = await self._executor.execute_gm_response(
                gm_response,
                active,
                actual_db,
                session_id=request.session_id,
                fallback_actor_id=request.actor_id,
                social_roll_results=roll_results,
                provenance_context={
                    "phase": phase_value,
                    "player_action": request.content or "",
                    "recent_messages": (context.messages if context is not None else []),
                    "roll_results": roll_results or {},
                    "scene_interaction": request.scene_interaction_context,
                },
            )
            enriched_pending = [
                self._enrich_mechanics_result(roll, request, actor_name, target_id, active)
                for roll in exec_result.pending_rolls
            ]
            pending_rolls.extend(enriched_pending)
            roll_events.extend(enriched_pending)
            executed_actions.extend(exec_result.executed_actions)
            canon_dirty = canon_dirty or exec_result.canon_dirty

        if has_gm_roll_request and not pending_rolls:
            prime_combat_from_hostile_narration(
                active,
                narration_text,
                source="gm_narration",
            )
            if narration_text:
                await self._publish_gm_narration(request.session_id, narration_text, actual_db)

        # 5. Narration finale des jets demandes par le GM.
        if pending_rolls:
            if context is None:
                logger.warning("ActionPipeline : jets GM en attente sans contexte de narration.")
                context = AgentContext(
                    session_id=request.session_id,
                    game_phase=phase_value,
                    game_state=await self._game_state_for_gm(
                        request.session_id,
                        active,
                        actual_db,
                    ),
                    player_action=prompt_action_text,
                    roll_results=roll_results or {},
                    messages=[],
                    travel_intent=request.travel_intent,
                )
            outcome_response = await self._narrate_outcome(
                request.session_id,
                context,
                pending_rolls,
                gm_agent=self._gm_for_phase(phase_value),
            )
            if outcome_response and outcome_response.narration:
                outcome_response = self._ensure_actor_attribution(
                    outcome_response,
                    pending_rolls[0] if pending_rolls else {},
                )
                final_narration = outcome_response.narration
                prime_combat_from_hostile_narration(
                    active,
                    final_narration,
                    source="gm_roll_outcome",
                )
                await self._publish_gm_narration(
                    request.session_id,
                    final_narration,
                    actual_db,
                )
                outcome_exec = await self._executor.execute_gm_response(
                    outcome_response,
                    active,
                    actual_db,
                    session_id=request.session_id,
                    fallback_actor_id=request.actor_id,
                    social_roll_results=(
                        pending_rolls[0]
                        if pending_rolls
                        and (
                            pending_rolls[0].get("type") == "skill_check"
                            or pending_rolls[0].get("social_target_id")
                        )
                        else None
                    ),
                    provenance_context={
                        "phase": phase_value,
                        "player_action": request.content or "",
                        "recent_messages": (context.messages if context is not None else []),
                        "roll_results": pending_rolls,
                    },
                )
                roll_events.extend(outcome_exec.pending_rolls)
                executed_actions.extend(outcome_exec.executed_actions)
                canon_dirty = canon_dirty or outcome_exec.canon_dirty
            elif narration_text:
                await self._publish_gm_narration(
                    request.session_id,
                    narration_text,
                    actual_db,
                )

        if canon_dirty and actual_db is not None:
            try:
                from app.services import campaign_dossier_service

                await campaign_dossier_service.synthesize_canon_for_session(
                    request.session_id,
                    active.state_data,
                    [],
                    actual_db,
                )
            except Exception as exc:
                logger.warning("Synthese canon campagne ignoree : %s", exc)

        return ResolvedAction(
            actor_id=request.actor_id,
            actor_name=actor_name,
            actor_kind=request.actor_kind,
            action_type=request.action_type,
            target_id=target_id,
            mechanics=roll_results or {},
            roll_events=roll_events,
            narration=final_narration,
            gm_actions=executed_actions,
            canon_dirty=canon_dirty,
        )

    def _get_mechanics(self) -> Any:
        if self._mechanics is None:
            from app.game.action_resolver import ActionResolver

            self._mechanics = ActionResolver(gm_agent=self._gm)
        return self._mechanics

    def _gm_for_phase(self, phase_value: str) -> Any:
        return self._combat_gm if phase_value.upper() == "COMBAT" else self._gm

    async def _game_state_for_gm(
        self,
        session_id: str,
        active: ActiveSession,
        db: Any | None,
    ) -> dict[str, Any]:
        game_state = dict(active.state_data)
        if db is not None:
            try:
                game_state["world_maps"] = await campaign_dossier_service.map_context_for_session(
                    session_id,
                    db,
                    active.state_data,
                )
            except Exception as exc:
                logger.debug("ActionPipeline : contexte cartes indisponible : %s", exc)
            try:
                gm_prompt_context = await campaign_dossier_service.build_gm_prompt_context(
                    session_id,
                    db,
                    active.state_data,
                )
                if gm_prompt_context:
                    game_state["_gm_prompt_context"] = gm_prompt_context
            except Exception as exc:
                logger.debug("ActionPipeline : dossier MJ privé indisponible : %s", exc)
        return game_state

    @staticmethod
    def _deterministic_narration(
        request: ActionRequest,
        actor_name: str,
        target_name: str,
        roll_results: dict[str, Any] | None,
    ) -> str:
        action = request.action_type.strip().lower()
        target_label = target_name or "la cible"

        if is_pure_companion_social_prompt(request.action_type, request.content):
            return ""

        if action == "attack" and roll_results:
            hit = bool(roll_results.get("hit"))
            critical = bool(roll_results.get("critical"))
            if hit:
                damage = int(roll_results.get("damage", {}).get("total", 0))
                crit_text = " d'un coup critique" if critical else ""
                return f"{actor_name} touche {target_label}{crit_text} et inflige {damage} degats."
            return f"{actor_name} attaque {target_label}, mais manque sa cible."

        if action == "cast_spell" and roll_results:
            summary = str(roll_results.get("summary") or "").strip()
            spell_name = str(roll_results.get("spell_name") or "un sort")
            if summary:
                return f"{actor_name} lance {spell_name}. {summary}."
            return f"{actor_name} lance {spell_name} vers {target_label}."

        if action == "death_save" and roll_results:
            return str(roll_results.get("summary") or f"{actor_name} lutte pour survivre.")

        if action == "stabilize" and roll_results:
            if roll_results.get("success"):
                return f"{actor_name} stabilise {target_label}."
            return f"{actor_name} tente de stabiliser {target_label}, sans y parvenir."

        if action == "dodge":
            return f"{actor_name} se met en defense."
        if action == "dash":
            return f"{actor_name} se deplace aussi vite que possible."
        if action == "disengage":
            return f"{actor_name} se degage prudemment de la melee."
        if action == "hide":
            return f"{actor_name} cherche un couvert et tente de se dissimuler."
        if action == "wait":
            return f"{actor_name} temporise et observe le combat."

        display = request.display_text or request.content
        if display:
            return str(display)
        return f"{actor_name} agit."

    async def _publish_ai_thinking(self, session_id: str, thinking: bool) -> None:
        await self._orchestrator.publish_ai_thinking(session_id, thinking)

    async def _publish_tactical_move_result(
        self,
        session_id: str,
        combatant_id: str | None,
        move_result: Any,
        active: ActiveSession,
    ) -> None:
        if not combatant_id or not move_result.valid or move_result.final_position is None:
            return
        await self._event_bus.publish_to_session(
            session_id,
            EventType.COMBATANT_MOVED,
            {
                "combatant_id": combatant_id,
                "position": move_result.final_position.to_dict(),
                "movement_used_m": move_result.movement_used_m,
                "path": [step.to_dict() for step in move_result.path],
                "interrupted": move_result.interrupted,
                "reason": move_result.reason,
            },
            source=self._source,
        )
        current = active.turn_manager.current_turn
        if current is not None and current.combatant_id == combatant_id:
            payload: dict[str, Any] = {
                "combatant_id": combatant_id,
                "action_economy": getattr(
                    current.action_economy,
                    "__dict__",
                    current.action_economy,
                ),
            }
            reachable = calculate_reachable_cells(active, combatant_id)
            if reachable is not None:
                payload["reachable_cells"] = reachable
            await self._event_bus.publish_to_session(
                session_id,
                EventType.ACTION_ECONOMY_CHANGED,
                payload,
                source=self._source,
            )

    async def _execute_tactical_move_request(
        self,
        request: ActionRequest,
        active: ActiveSession,
    ) -> tuple[bool, str, Any]:
        if not request.actor_id:
            return False, "Combattant introuvable.", None
        destination = self._parse_move_destination(request.content)
        if destination is None:
            return False, "Format de déplacement invalide. Attendu: 'col,row'", None

        combatants = active.state_data.get("combatants") or {}
        mover_data = combatants.get(request.actor_id, {})
        if not isinstance(mover_data, dict):
            mover_data = {}
        current = active.turn_manager.current_turn
        economy = (
            current.action_economy
            if current is not None and current.combatant_id == request.actor_id
            else None
        )
        movement_m = float(
            economy.movement if economy is not None else combatant_speed_m(mover_data)
        )
        move_result = await apply_tactical_move(
            session_id=request.session_id,
            active=active,
            mover_id=request.actor_id,
            destination=destination,
            event_bus=self._event_bus,
            movement_m=movement_m,
            source=self._source,
        )
        if not move_result.valid:
            return False, f"Déplacement invalide : {move_result.reason}", move_result
        if economy is not None and not economy.spend_movement(move_result.movement_used_m):
            return False, "Mouvement insuffisant pour ce déplacement.", move_result
        await self._publish_tactical_move_result(
            request.session_id,
            request.actor_id,
            move_result,
            active,
        )
        return True, "", move_result

    @staticmethod
    def _parse_move_destination(content: str | None) -> GridPosition | None:
        if not content or "," not in content:
            return None
        try:
            col_text, row_text = content.split(",", 1)
            return GridPosition(col=int(col_text.strip()), row=int(row_text.strip()))
        except (TypeError, ValueError):
            return None

    async def _publish_action_economy_result(
        self,
        active: ActiveSession,
        combatant_id: str | None,
    ) -> None:
        if not combatant_id:
            return
        current = active.turn_manager.current_turn
        if current is None or current.combatant_id != combatant_id:
            return
        payload: dict[str, Any] = {
            "combatant_id": combatant_id,
            "action_economy": getattr(
                current.action_economy,
                "__dict__",
                current.action_economy,
            ),
        }
        reachable = calculate_reachable_cells(active, combatant_id)
        if reachable is not None:
            payload["reachable_cells"] = reachable
        await self._event_bus.publish_to_session(
            active.session_id,
            EventType.ACTION_ECONOMY_CHANGED,
            payload,
            source=self._source,
        )

    async def _publish_gm_narration(
        self,
        session_id: str,
        narration_text: str,
        db: Any | None,
    ) -> None:
        await self._orchestrator.publish_gm_narration(session_id, narration_text, db)

    async def _narrate_outcome(
        self,
        session_id: str,
        context: AgentContext,
        pending_rolls: list[dict[str, Any]],
        *,
        gm_agent: Any | None = None,
    ) -> GMResponse | None:
        outcome_response: GMResponse | None = None
        agent = gm_agent or self._gm_for_phase(context.game_phase)
        try:
            await self._publish_ai_thinking(session_id, True)
            try:
                outcome_candidate = await agent.narrate_outcome_response(
                    context,
                    pending_rolls,
                )
            except (AttributeError, TypeError):
                outcome_candidate = await agent.narrate_outcome(context, pending_rolls)

            if isinstance(outcome_candidate, GMResponse):
                outcome_response = outcome_candidate
            elif isinstance(outcome_candidate, AgentResponse):
                outcome_response = GMResponse(
                    narration=outcome_candidate.content,
                    actions=outcome_candidate.actions,
                    action_intent=outcome_candidate.action_intent,
                )
            elif outcome_candidate is not None:
                outcome_response = GMResponse(narration=str(outcome_candidate))
        except Exception as exc:
            logger.error("ActionPipeline : narrate_outcome echoue : %s", exc)
            from app.llm.ollama_client import OllamaError
            from app.llm.openai_compatible_client import OpenAICompatibleError

            if isinstance(exc, (OllamaError, OpenAICompatibleError)):
                err_msg = (
                    "Le serveur LLM local (Ollama) ou l'API distante est injoignable. "
                    "Veuillez vérifier que le service Ollama est bien démarré "
                    "et que le modèle configuré est installé."
                )
            else:
                err_msg = f"Le Maître du Jeu a rencontré une erreur : {type(exc).__name__}"
            await self._event_bus.publish_to_session(
                session_id,
                EventType.ERROR,
                {"message": err_msg},
                source=self._source,
            )
        finally:
            await self._publish_ai_thinking(session_id, False)
        return outcome_response

    async def _persist_actor_action(
        self,
        session_id: str,
        visible_text: str,
        actor_name: str,
        request: ActionRequest,
        target_id: str | None,
        db: Any | None,
    ) -> None:
        if db is None:
            return

        from app.models.message import MessageRole, MessageType
        from app.services.message_service import persist_narration

        metadata: dict[str, Any] = {
            "action_type": request.action_type,
            "character_id": request.actor_id,
            "actor_kind": request.actor_kind,
            "target": target_id,
        }
        if request.scene_poi_id:
            metadata["scene_poi_id"] = request.scene_poi_id
        if request.scene_interaction_id:
            metadata["scene_interaction_id"] = request.scene_interaction_id
        if request.scene_interaction_intent:
            metadata["scene_interaction_intent"] = request.scene_interaction_intent
        if request.actor_kind == "companion":
            metadata["is_ai_player"] = True

        await persist_narration(
            session_id,
            visible_text,
            actor_name,
            db,
            role=MessageRole.PLAYER,
            message_type=MessageType.ACTION,
            metadata=metadata,
        )

    @staticmethod
    def _as_agent_response(candidate: Any) -> AgentResponse | None:
        if isinstance(candidate, AgentResponse):
            return candidate
        if isinstance(candidate, GMResponse):
            return AgentResponse(
                content=candidate.narration,
                actions=candidate.actions,
                action_intent=candidate.action_intent,
            )
        if candidate is None:
            return None
        return AgentResponse(content=str(candidate), actions=[])

    @staticmethod
    def _with_social_roll_fallback(
        response: AgentResponse,
        request: ActionRequest,
        social_target_id: str | None,
        state_data: dict[str, Any],
    ) -> AgentResponse:
        if (
            request.actor_kind != "player"
            or request.action_type != "free_text"
            or not request.actor_id
            or not _is_combat_social_text(request.content)
        ):
            return response

        if any(
            gm_action.type in {"roll_request", "combatant_status"} for gm_action in response.actions
        ):
            return response

        dc = _calculate_social_dc(state_data, social_target_id, None)
        actions = [
            *response.actions,
            GMAction(
                type="roll_request",
                target=request.actor_id,
                params={
                    "ability": "cha",
                    "type": "check",
                    "dc": dc,
                    "reason": "social_combat",
                    "social_target": social_target_id,
                },
            ),
        ]
        return AgentResponse(
            content=response.content,
            actions=actions,
            action_intent=response.action_intent or "mixed",
        )

    @staticmethod
    def _resolve_social_check(
        request: ActionRequest,
        active: ActiveSession,
    ) -> dict[str, Any] | None:
        """Resout un jet de competence social en exploration via le moteur.

        Retourne un dict roll_results injecte dans le contexte GM pour narration.
        Le LLM ne resout jamais le jet ; il recoit le resultat deterministe.
        """
        if not request.actor_id or not request.content:
            return None

        skill = _detect_social_skill(request.content)
        if not skill:
            return None

        social_target_id = resolve_npc_target_id(
            request.content,
            active.state_data,
            request.target_id,
        )
        dc = _calculate_social_dc(active.state_data, social_target_id, skill)

        characters = active.state_data.get("characters", {})
        char_data = characters.get(request.actor_id, {}) if isinstance(characters, dict) else {}
        if not isinstance(char_data, dict):
            return None

        ability = SKILL_ABILITY.get(skill, Ability.CHA)
        ab_key = _ability_short_key(ability)
        ability_scores = char_data.get("ability_scores", {})
        if not isinstance(ability_scores, dict):
            ability_scores = {}
        score = int(
            ability_scores.get(
                ab_key,
                ability_scores.get(ability.value if isinstance(ability, Ability) else "", 10),
            )
        )
        level = int(char_data.get("level", 1))
        skill_profs = _normalized_skill_proficiencies(char_data)
        prof = Proficiency.PROFICIENT if skill in skill_profs else Proficiency.NONE

        result = skill_check(score, skill, level, prof, dc)
        skill_label = skill.replace("_", " ").title()
        outcome = "succès" if result.success else "échec"
        summary = f"{result.label} : {result.breakdown} ({outcome})"
        roll_results: dict[str, Any] = {
            "type": "skill_check",
            "skill": skill,
            "dice_notation": "1d20",
            "rolls": result.all_rolls,
            "d20": result.d20_roll,
            "d20_roll": result.d20_roll,
            "modifier": result.modifier,
            "total": result.total,
            "dc": result.dc,
            "success": result.success,
            "label": result.label or skill_label,
            "breakdown": result.breakdown,
            "summary": summary,
            "target_id": social_target_id,
            "social_target_id": social_target_id,
            "actor_id": request.actor_id,
        }

        if social_target_id:
            npc_states = active.state_data.setdefault("npc_states", {})
            if not isinstance(npc_states, dict):
                npc_states = {}
                active.state_data["npc_states"] = npc_states
            npc = npc_states.setdefault(social_target_id, {})
            if isinstance(npc, dict):
                npc.setdefault("name", social_target_id)
                npc.setdefault("attitude", "indifferent")
                npc["last_interaction_turn"] = active.state_data.get("turn_number", 0)
        return roll_results

    @staticmethod
    def _resolve_scene_interaction_roll(
        request: ActionRequest,
        active: ActiveSession,
    ) -> dict[str, Any] | None:
        context = request.scene_interaction_context or {}
        mechanics = context.get("mechanics")
        if not isinstance(mechanics, dict):
            return None
        roll_params = mechanics.get("roll")
        if not isinstance(roll_params, dict):
            return None

        from app.game.roll_executor import execute_roll_request

        payload = execute_roll_request(roll_params, request.actor_id, active)
        if not payload:
            return None
        success_label = "réussite" if payload.get("success") else "échec"
        label = str(payload.get("label") or "Jet")
        payload.update(
            {
                "type": "skill_check",
                "actor_id": request.actor_id,
                "scene_poi_id": context.get("poi_id"),
                "scene_poi_name": context.get("poi_name"),
                "scene_interaction_id": context.get("interaction_id"),
                "scene_interaction_intent": context.get("interaction_intent"),
                "safe_observation": mechanics.get("safe_observation"),
                "reveal_tier": mechanics.get("reveal_tier"),
                "summary": (
                    f"{label} : {payload.get('total')} vs DD {payload.get('dc')} ({success_label})"
                ),
            }
        )
        return payload

    @staticmethod
    def _without_redundant_social_roll_requests(
        response: AgentResponse,
        roll_results: dict[str, Any],
    ) -> AgentResponse:
        if roll_results.get("type") != "skill_check":
            return response
        actions = [gm_action for gm_action in response.actions if gm_action.type != "roll_request"]
        if len(actions) == len(response.actions):
            return response
        logger.warning(
            "ActionPipeline : roll_request GM ignore ; le skill_check social est deja resolu."
        )
        return AgentResponse(
            content=response.content,
            actions=actions,
            action_intent=response.action_intent,
        )

    @staticmethod
    def _with_travel_scene_fallback(
        response: AgentResponse,
        request: ActionRequest,
        active: ActiveSession,
    ) -> AgentResponse:
        """Deterministic transition when the player clearly travels to a *known*
        destination but the GM forgot to emit a ``scene_layout``.

        Builds a sober-but-real layout for the destination so the move always
        happens (free text behaves like a POI click). The next GM turn enriches
        it, and ``_apply_scene_layout`` carries party-accompanying NPCs across —
        so a guide can never be lost just because the transition was implicit.
        Conservative: only fires for a matched exit/map node, out of combat.
        """
        intent = request.travel_intent
        if not isinstance(intent, dict) or not intent.get("is_travel"):
            return response
        node_id = str(intent.get("destination_node_id") or "").strip()
        if not node_id:
            return response  # only auto-transition to a known exit/map node
        if any(action.type == "scene_layout" for action in response.actions):
            return response  # the GM already moved the scene itself

        state = active.state_data if isinstance(active.state_data, dict) else {}
        scene = state.get("current_scene") or {}
        current_scene_id = (
            str(scene.get("scene_id") or "").strip() if isinstance(scene, dict) else ""
        )
        if node_id == current_scene_id:
            return response  # already there

        # Human-readable label: prefer the matched exit, then a region-map node.
        label = ""
        if isinstance(scene, dict):
            for exit_ in scene.get("exits") or []:
                if isinstance(exit_, dict) and str(exit_.get("leads_to") or "") == node_id:
                    label = str(exit_.get("label") or "").strip()
                    break
        if not label:
            world_maps = state.get("world_maps") or {}
            region = world_maps.get("region_map") or {} if isinstance(world_maps, dict) else {}
            for node in (region.get("nodes") or []) if isinstance(region, dict) else []:
                if isinstance(node, dict) and str(node.get("id") or "") == node_id:
                    label = str(node.get("name") or "").strip()
                    break
        if not label:
            label = str(intent.get("destination") or "").strip()
        place = f"à {label}" if label else "sur les lieux"

        # Cluster the party near the centre of the fresh map.
        positions: dict[str, Any] = {}
        spots = [(6, 6), (5, 6), (6, 7), (5, 7), (7, 6), (6, 5)]
        characters = state.get("characters") or {}
        if isinstance(characters, dict):
            for index, char_id in enumerate(list(characters.keys())[:6]):
                col, row = spots[index % len(spots)]
                positions[str(char_id)] = {"col": col, "row": row}

        response.actions.append(
            GMAction(
                type="scene_layout",
                params={
                    "scene_id": node_id,
                    "cols": 12,
                    "rows": 12,
                    "cell_size_m": 1.5,
                    "terrain": "unknown",
                    "description": (f"Le groupe arrive {place}. Les lieux se précisent peu à peu."),
                    "pois": [],
                    "exits": [],
                    "party_positions": positions,
                },
            )
        )
        # Keep the journal's location in sync with the new scene: the next turn's
        # anti-hallucination anchor (gm_narrate VERROU) reads location_place, so a
        # scene_layout without a journal_update would tell the GM it is still in the
        # old place — defeating the "enrich next turn" plan. Don't clobber a journal
        # the LLM already emitted.
        if label and not any(action.type == "journal_update" for action in response.actions):
            response.actions.append(
                GMAction(type="journal_update", params={"location_place": label})
            )
        logger.info(
            "ActionPipeline : scene_layout de secours injecté pour un voyage vers '%s'",
            node_id,
        )
        return response

    @staticmethod
    def _with_scene_interaction_update_fallback(
        response: AgentResponse,
        roll_results: dict[str, Any],
    ) -> AgentResponse:
        if any(action.type == "scene_update" for action in response.actions):
            return response
        poi_id = str(roll_results.get("scene_poi_id") or "").strip()
        if not poi_id:
            return response
        poi_name = str(roll_results.get("scene_poi_name") or "ce point").strip()
        success = roll_results.get("success")
        state = "discovered" if success is True else "examined"
        summary = str(roll_results.get("summary") or "").strip()
        if not summary:
            summary = (
                f"{poi_name} livre une information utile."
                if success is True
                else f"{poi_name} reste ambigu malgré l'examen."
            )
        response.actions.append(
            GMAction(
                type="scene_update",
                params={
                    "update_pois": [
                        {
                            "id": poi_id,
                            "state": state,
                            "visibility": "subtle",
                            "discovered": True,
                            "facts": [summary],
                        }
                    ],
                    "discovered_ids": [poi_id],
                },
            )
        )
        return response

    @staticmethod
    def _without_combat_damage_actions(response: AgentResponse) -> AgentResponse:
        actions = [gm_action for gm_action in response.actions if gm_action.type != "damage_apply"]
        if len(actions) == len(response.actions):
            return response
        logger.warning(
            "ActionPipeline : damage_apply GM ignore en combat ; les degats viennent du moteur."
        )
        return AgentResponse(
            content=response.content,
            actions=actions,
            action_intent=response.action_intent,
        )

    @staticmethod
    def _enrich_roll_event(
        payload: dict[str, Any],
        request: ActionRequest,
        actor_name: str,
        target_id: str | None,
    ) -> dict[str, Any]:
        enriched = dict(payload)
        effective_actor_id = enriched.get("actor_id") or request.actor_id
        effective_actor_name = str(enriched.get("actor_name") or actor_name)
        enriched.setdefault("character_id", effective_actor_id)
        enriched["actor_id"] = effective_actor_id
        enriched["actor_name"] = effective_actor_name
        enriched["actor_kind"] = enriched.get("actor_kind") or request.actor_kind
        enriched["action_type"] = request.action_type
        enriched["target_id"] = target_id
        if request.scene_interaction_context:
            enriched["scene_poi_id"] = request.scene_interaction_context.get("poi_id")
            enriched["scene_poi_name"] = request.scene_interaction_context.get("poi_name")
            enriched["scene_interaction_id"] = request.scene_interaction_context.get(
                "interaction_id"
            )
            enriched["scene_interaction_intent"] = request.scene_interaction_context.get(
                "interaction_intent"
            )
        if enriched.get("dc") is not None and enriched.get("total") is not None:
            try:
                enriched["margin"] = int(enriched["total"]) - int(enriched["dc"])
            except (TypeError, ValueError):
                pass
        return enriched

    @staticmethod
    def _enrich_mechanics_result(
        payload: dict[str, Any],
        request: ActionRequest,
        actor_name: str,
        target_id: str | None,
        active: ActiveSession,
    ) -> dict[str, Any]:
        enriched = dict(payload)
        effective_actor_id = enriched.get("actor_id") or request.actor_id
        effective_actor_name = str(enriched.get("actor_name") or actor_name)
        enriched.setdefault("character_id", effective_actor_id)
        enriched["actor_id"] = effective_actor_id
        enriched["actor_name"] = effective_actor_name
        enriched["actor_kind"] = enriched.get("actor_kind") or request.actor_kind
        enriched["action_type"] = request.action_type
        enriched["target_id"] = target_id
        if request.scene_interaction_context:
            enriched["scene_poi_id"] = request.scene_interaction_context.get("poi_id")
            enriched["scene_poi_name"] = request.scene_interaction_context.get("poi_name")
            enriched["scene_interaction_id"] = request.scene_interaction_context.get(
                "interaction_id"
            )
            enriched["scene_interaction_intent"] = request.scene_interaction_context.get(
                "interaction_intent"
            )
        if enriched.get("dc") is not None and enriched.get("total") is not None:
            try:
                enriched["margin"] = int(enriched["total"]) - int(enriched["dc"])
            except (TypeError, ValueError):
                pass
        other_names: list[str] = []
        characters = active.state_data.get("characters", {})
        if isinstance(characters, dict):
            for char_id, data in characters.items():
                if str(char_id) == str(effective_actor_id) or not isinstance(data, dict):
                    continue
                name = str(data.get("name") or "").strip()
                if name and name.casefold() != effective_actor_name.casefold():
                    other_names.append(name)
        if other_names:
            enriched["non_actor_names"] = other_names[:12]
        return enriched

    @staticmethod
    def _ensure_actor_attribution(
        response: AgentResponse | GMResponse,
        roll_results: dict[str, Any],
    ) -> AgentResponse | GMResponse:
        if roll_results.get("type") == "stealth_event":
            return response
        actor_name = str(roll_results.get("actor_name") or "").strip()
        if not actor_name:
            return response
        text = response.content if isinstance(response, AgentResponse) else response.narration
        wrong_name = ActionPipeline._misattributed_actor_name(text, actor_name, roll_results)
        if wrong_name is None:
            return response

        success = roll_results.get("success")
        poi_name = str(roll_results.get("scene_poi_name") or "l'indice").strip()
        if success is True:
            repaired = f"{actor_name} tire les informations utiles de {poi_name}."
        elif success is False:
            repaired = (
                f"{actor_name} n'obtient qu'une lecture partielle de {poi_name}; "
                "l'indice reste ambigu et la scène avance avec prudence."
            )
        else:
            repaired = f"{actor_name} porte l'action à son terme."
        logger.warning(
            "ActionPipeline : attribution de jet corrigee (%s attribue a %s).",
            actor_name,
            wrong_name,
        )
        if isinstance(response, AgentResponse):
            return AgentResponse(
                content=repaired,
                actions=response.actions,
                raw_llm_output=response.raw_llm_output,
                action_intent=response.action_intent,
            )
        return GMResponse(
            narration=repaired,
            actions=response.actions,
            mood=response.mood,
            inner_reasoning=response.inner_reasoning,
            action_intent=response.action_intent,
            start_mode=response.start_mode,
        )

    @staticmethod
    def _misattributed_actor_name(
        text: str,
        actor_name: str,
        roll_results: dict[str, Any],
    ) -> str | None:
        normalized = text.casefold()
        actor_norm = actor_name.casefold()
        if actor_norm in normalized:
            return None
        discovery_markers = (
            "déchiffre",
            "dechiffre",
            "découvre",
            "decouvre",
            "remarque",
            "repère",
            "repere",
            "trouve",
            "comprend",
            "identifie",
            "perçoit",
            "percoit",
        )
        if not any(marker in normalized for marker in discovery_markers):
            return None
        for name in roll_results.get("non_actor_names") or []:
            candidate = str(name).strip()
            if candidate and candidate.casefold() in normalized:
                return candidate
        return None

    @classmethod
    def _prompt_action_text(
        cls,
        request: ActionRequest,
        actor_name: str,
        target_name: str,
        roll_results: dict[str, Any] | None,
    ) -> str:
        if request.content:
            text = request.content
            if (
                request.action_type == "free_text"
                and target_name
                and _is_combat_social_text(request.content)
            ):
                target_id = request.target_id or "unknown"
                text = f"{text} [Cible sociale : {target_name} ({target_id})]"
            if request.scene_interaction_context:
                ctx = request.scene_interaction_context
                mechanics = ctx.get("mechanics") if isinstance(ctx.get("mechanics"), dict) else {}
                safe_observation = mechanics.get("safe_observation")
                reveal_tier = mechanics.get("reveal_tier")
                parts = [
                    f"POI={ctx.get('poi_name')}",
                    f"intention={ctx.get('interaction_intent')}",
                ]
                if safe_observation is not None:
                    parts.append(f"observation_sans_contact={bool(safe_observation)}")
                if reveal_tier:
                    parts.append(f"palier_indice={reveal_tier}")
                text = f"{text} [Interaction de scène : {' ; '.join(parts)}]"
        elif request.action_type == "attack" and target_name:
            if request.actor_kind == "monster":
                text = f"[Tour du monstre] {actor_name} attaque {target_name}."
            else:
                text = f"{actor_name} attaque {target_name}."
        else:
            text = request.action_type

        if roll_results:
            text = f"{text} [Résultat mécanique : {roll_results.get('summary', '')}]"
        return text

    @classmethod
    def _display_text(
        cls,
        request: ActionRequest,
        actor_name: str,
        target_name: str,
    ) -> str:
        if request.display_text:
            return request.display_text
        if request.content:
            return request.content
        if request.action_type == "attack" and target_name:
            return f"{actor_name} attaque {target_name}."
        return request.action_type

    @staticmethod
    def _default_target_id(request: ActionRequest, state_data: dict[str, Any]) -> str | None:
        combatants = state_data.get("combatants", {})
        if not isinstance(combatants, dict):
            return None

        if request.action_type == "free_text" and _is_combat_social_text(request.content):
            active_npcs: list[str] = []
            for combatant_id, cdata in combatants.items():
                if not isinstance(cdata, dict) or cdata.get("is_player", True):
                    continue
                status = str(cdata.get("status", "active")).lower()
                try:
                    hp = int(cdata.get("hp", 0))
                except (TypeError, ValueError):
                    hp = 0
                if hp > 0 and status not in INACTIVE_STATUSES:
                    active_npcs.append(combatant_id)
            return active_npcs[0] if len(active_npcs) == 1 else None

        if request.actor_kind != "monster" or request.action_type != "attack":
            return None

        return choose_attack_target(
            state_data,
            request.actor_id,
            actor_is_player=False,
        )

    @staticmethod
    def _actor_name(
        actor_id: str | None,
        actor_kind: str,
        state_data: dict[str, Any],
    ) -> str:
        fallback = {
            "player": "Joueur",
            "companion": "Compagnon",
            "monster": "Monstre",
        }.get(actor_kind, "Joueur")
        if not actor_id:
            return fallback

        characters = state_data.get("characters", {})
        if isinstance(characters, dict):
            cdata = characters.get(actor_id)
            if isinstance(cdata, dict) and cdata.get("name"):
                return str(cdata["name"])

        combatants = state_data.get("combatants", {})
        if isinstance(combatants, dict):
            cdata = combatants.get(actor_id)
            if isinstance(cdata, dict) and cdata.get("name"):
                return str(cdata["name"])
        return fallback

    @staticmethod
    def _combatant_name(state_data: dict[str, Any], combatant_id: str | None) -> str:
        if not combatant_id:
            return ""
        combatants = state_data.get("combatants", {})
        if isinstance(combatants, dict):
            cdata = combatants.get(combatant_id)
            if isinstance(cdata, dict) and cdata.get("name"):
                return str(cdata["name"])
        characters = state_data.get("characters", {})
        if isinstance(characters, dict):
            cdata = characters.get(combatant_id)
            if isinstance(cdata, dict) and cdata.get("name"):
                return str(cdata["name"])
        return str(combatant_id)

    @staticmethod
    def _phase_value(active: ActiveSession) -> str:
        phase = active.phase
        return phase.value if hasattr(phase, "value") else str(phase)

    async def _apply_stabilize_success(
        self,
        session_id: str,
        target_id: str | None,
        roll_results: dict[str, Any],
        active: ActiveSession,
    ) -> None:
        if not roll_results.get("success") or not target_id:
            return
        combatants: dict[str, Any] = active.state_data.setdefault("combatants", {})
        if target_id not in combatants:
            return

        death_saves = combatants[target_id].setdefault(
            "death_saves",
            {"successes": 0, "failures": 0, "stable": False},
        )
        death_saves["stable"] = True
        conditions = list(combatants[target_id].get("conditions", []))
        if "inconscient" in conditions:
            conditions.remove("inconscient")
            combatants[target_id]["conditions"] = conditions
            await self._event_bus.publish_to_session(
                session_id,
                EventType.CONDITION_CHANGED,
                {"combatant_id": target_id, "condition": "inconscient", "added": False},
                source=self._source,
            )
        await self._event_bus.publish_to_session(
            session_id,
            EventType.DEATH_SAVE_UPDATED,
            {"combatant_id": target_id, "death_saves": dict(death_saves)},
            source=self._source,
        )
        active.mark_dirty()

    async def _resolve_attack_action(
        self,
        request: ActionRequest,
        active: ActiveSession,
        phase_value: str,
        actor_name: str,
        target_id: str | None,
        actual_db: Any | None,
    ) -> ResolvedActionResult:
        target_name = self._combatant_name(active.state_data, target_id)
        roll_results = None
        executed_actions = []
        tactical = None

        if phase_value == "COMBAT":
            tactical = await prepare_attack(
                session_id=request.session_id,
                active=active,
                actor_id=request.actor_id,
                target_id=target_id,
                actor_kind=request.actor_kind,
                event_bus=self._event_bus,
                source=self._source,
            )
            target_id = tactical.target_id
            target_name = self._combatant_name(active.state_data, target_id)
            if tactical.moved is not None:
                await self._publish_tactical_move_result(
                    request.session_id,
                    request.actor_id,
                    tactical.moved,
                    active,
                )
            if not tactical.allowed:
                message = tactical.reason or "Action tactique impossible."
                if request.actor_kind in {"monster", "companion"}:
                    narration = _tactical_block_narration(actor_name, "attack")
                    await self._publish_gm_narration(request.session_id, narration, actual_db)
                else:
                    await self._event_bus.publish_to_session(
                        request.session_id,
                        EventType.ERROR,
                        {"message": message},
                        source=self._source,
                    )
                    narration = ""
                error_action = ResolvedAction(
                    actor_id=request.actor_id,
                    actor_name=actor_name,
                    actor_kind=request.actor_kind,
                    action_type=request.action_type,
                    target_id=target_id,
                    mechanics={"error": True, "summary": message},
                    roll_events=[],
                    narration=narration,
                    gm_actions=[],
                    canon_dirty=False,
                )
                return target_id, target_name, roll_results, executed_actions, error_action

        mechanics = self._get_mechanics()
        roll_results = mechanics._resolve_attack(
            request.actor_id,
            target_id,
            active.state_data,
        )
        if tactical is not None:
            roll_results["tactical"] = {
                "target_id": target_id,
                "moved": bool(tactical.moved),
                "movement_used_m": (tactical.moved.movement_used_m if tactical.moved else 0),
                "path": (
                    [step.to_dict() for step in tactical.moved.path] if tactical.moved else []
                ),
                "opportunity_attacks": [
                    attack.__dict__ for attack in tactical.moved.opportunity_attacks
                ]
                if tactical.moved
                else [],
            }
        if roll_results and roll_results.get("hit") and target_id:
            damage_amount = int(roll_results.get("damage", {}).get("total", 0))
            if damage_amount > 0:
                await self._executor.execute_action(
                    request.session_id,
                    "damage_apply",
                    {"target": target_id, "amount": damage_amount},
                    active,
                )
                executed_actions.append(
                    {
                        "type": "damage_apply",
                        "target": target_id,
                        "params": {"amount": damage_amount},
                        "origin": "engine",
                    }
                )
        return target_id, target_name, roll_results, executed_actions, None

    async def _resolve_death_save_action(
        self,
        request: ActionRequest,
        active: ActiveSession,
    ) -> dict[str, Any]:
        mechanics = self._get_mechanics()
        roll_results = mechanics._resolve_death_save(request.actor_id, active.state_data)
        await mechanics._apply_death_save_outcome(
            request.session_id,
            request.actor_id,
            roll_results,
            active,
        )
        return roll_results

    async def _resolve_stabilize_action(
        self,
        request: ActionRequest,
        active: ActiveSession,
        target_id: str | None,
    ) -> dict[str, Any]:
        mechanics = self._get_mechanics()
        roll_results = mechanics._resolve_stabilize(
            request.actor_id,
            target_id,
            active.state_data,
        )
        await self._apply_stabilize_success(
            request.session_id,
            target_id,
            roll_results,
            active,
        )
        return roll_results

    async def _consume_hide_action(
        self,
        request: ActionRequest,
        active: ActiveSession,
        phase_value: str,
        actor_name: str,
        target_id: str | None,
    ) -> ResolvedAction | None:
        if phase_value != "COMBAT":
            return None

        current = active.turn_manager.current_turn
        economy = (
            current.action_economy
            if current is not None and current.combatant_id == request.actor_id
            else None
        )
        if economy is None or not economy.use_action():
            message = "Action déjà utilisée ce tour."
            await self._event_bus.publish_to_session(
                request.session_id,
                EventType.ERROR,
                {"message": message},
                source=self._source,
            )
            return ResolvedAction(
                actor_id=request.actor_id,
                actor_name=actor_name,
                actor_kind=request.actor_kind,
                action_type=request.action_type,
                target_id=target_id,
                mechanics={"error": True, "summary": message},
                roll_events=[],
                narration="",
                gm_actions=[],
                canon_dirty=False,
            )

        active.mark_dirty()
        await self._publish_action_economy_result(active, request.actor_id)
        return None

    async def _resolve_movement_actions(
        self,
        request: ActionRequest,
        active: ActiveSession,
        phase_value: str,
        actor_name: str,
        target_id: str | None,
    ) -> ResolvedAction | None:
        if request.action_type == "move" and phase_value == "COMBAT":
            ok, message, _move_result = await self._execute_tactical_move_request(
                request,
                active,
            )
            if not ok:
                await self._event_bus.publish_to_session(
                    request.session_id,
                    EventType.ERROR,
                    {"message": message},
                    source=self._source,
                )
                return ResolvedAction(
                    actor_id=request.actor_id,
                    actor_name=actor_name,
                    actor_kind=request.actor_kind,
                    action_type=request.action_type,
                    target_id=target_id,
                    mechanics={"error": True, "summary": message},
                    roll_events=[],
                    narration="",
                    gm_actions=[],
                    canon_dirty=False,
                )
        elif request.action_type == "dash" and phase_value == "COMBAT":
            current = active.turn_manager.current_turn
            economy = (
                current.action_economy
                if current is not None and current.combatant_id == request.actor_id
                else None
            )
            if economy is None or not economy.use_action():
                message = "Action déjà utilisée ce tour."
                await self._event_bus.publish_to_session(
                    request.session_id,
                    EventType.ERROR,
                    {"message": message},
                    source=self._source,
                )
                return ResolvedAction(
                    actor_id=request.actor_id,
                    actor_name=actor_name,
                    actor_kind=request.actor_kind,
                    action_type=request.action_type,
                    target_id=target_id,
                    mechanics={"error": True, "summary": message},
                    roll_events=[],
                    narration="",
                    gm_actions=[],
                    canon_dirty=False,
                )
            economy.movement += economy.movement_max
            economy.has_dashed = True
            active.mark_dirty()
            if self._parse_move_destination(request.content) is not None:
                ok, message, _move_result = await self._execute_tactical_move_request(
                    request,
                    active,
                )
                if not ok:
                    await self._event_bus.publish_to_session(
                        request.session_id,
                        EventType.ERROR,
                        {"message": message},
                        source=self._source,
                    )
                    return ResolvedAction(
                        actor_id=request.actor_id,
                        actor_name=actor_name,
                        actor_kind=request.actor_kind,
                        action_type=request.action_type,
                        target_id=target_id,
                        mechanics={"error": True, "summary": message},
                        roll_events=[],
                        narration="",
                        gm_actions=[],
                        canon_dirty=False,
                    )
            else:
                await self._publish_action_economy_result(active, request.actor_id)
        elif request.action_type == "disengage" and phase_value == "COMBAT":
            current = active.turn_manager.current_turn
            economy = (
                current.action_economy
                if current is not None and current.combatant_id == request.actor_id
                else None
            )
            if economy is None or not economy.use_action():
                message = "Action déjà utilisée ce tour."
                await self._event_bus.publish_to_session(
                    request.session_id,
                    EventType.ERROR,
                    {"message": message},
                    source=self._source,
                )
                return ResolvedAction(
                    actor_id=request.actor_id,
                    actor_name=actor_name,
                    actor_kind=request.actor_kind,
                    action_type=request.action_type,
                    target_id=target_id,
                    mechanics={"error": True, "summary": message},
                    roll_events=[],
                    narration="",
                    gm_actions=[],
                    canon_dirty=False,
                )
            economy.has_disengaged = True
            active.mark_dirty()
            if self._parse_move_destination(request.content) is not None:
                ok, message, _move_result = await self._execute_tactical_move_request(
                    request,
                    active,
                )
                if not ok:
                    await self._event_bus.publish_to_session(
                        request.session_id,
                        EventType.ERROR,
                        {"message": message},
                        source=self._source,
                    )
                    return ResolvedAction(
                        actor_id=request.actor_id,
                        actor_name=actor_name,
                        actor_kind=request.actor_kind,
                        action_type=request.action_type,
                        target_id=target_id,
                        mechanics={"error": True, "summary": message},
                        roll_events=[],
                        narration="",
                        gm_actions=[],
                        canon_dirty=False,
                    )
            else:
                await self._publish_action_economy_result(active, request.actor_id)
        return None

    async def _resolve_cast_spell_action(
        self,
        request: ActionRequest,
        active: ActiveSession,
        phase_value: str,
        actor_name: str,
        target_id: str | None,
        actual_db: Any | None,
    ) -> ResolvedActionResult:
        target_name = self._combatant_name(active.state_data, target_id)
        roll_results = None
        executed_actions = []
        tactical = None

        if request.spell_id is not None:
            if phase_value == "COMBAT":
                tactical = await prepare_cast_spell(
                    session_id=request.session_id,
                    active=active,
                    actor_id=request.actor_id,
                    target_id=target_id,
                    spell_id=request.spell_id,
                    actor_kind=request.actor_kind,
                    event_bus=self._event_bus,
                    source=self._source,
                )
                target_id = tactical.target_id
                target_name = self._combatant_name(active.state_data, target_id)
                if tactical.moved is not None:
                    await self._publish_tactical_move_result(
                        request.session_id,
                        request.actor_id,
                        tactical.moved,
                        active,
                    )
                if not tactical.allowed:
                    message = tactical.reason or "Sort tactique impossible."
                    if request.actor_kind in {"monster", "companion"}:
                        narration = _tactical_block_narration(actor_name, "cast_spell")
                        await self._publish_gm_narration(
                            request.session_id,
                            narration,
                            actual_db,
                        )
                    else:
                        await self._event_bus.publish_to_session(
                            request.session_id,
                            EventType.ERROR,
                            {"message": message},
                            source=self._source,
                        )
                        narration = ""
                    error_action = ResolvedAction(
                        actor_id=request.actor_id,
                        actor_name=actor_name,
                        actor_kind=request.actor_kind,
                        action_type=request.action_type,
                        target_id=target_id,
                        mechanics={"error": True, "summary": message},
                        roll_events=[],
                        narration=narration,
                        gm_actions=[],
                        canon_dirty=False,
                    )
                    return target_id, target_name, roll_results, executed_actions, error_action

            caster_snapshot: dict[str, Any] | None = None
            if actual_db is not None:
                try:
                    prepared = await spellcasting_service.prepare_cast(
                        session_id=request.session_id,
                        character_id=request.actor_id,
                        spell_id=request.spell_id,
                        slot_level=request.slot_level,
                        active=active,
                        db=actual_db,
                        event_bus_instance=self._event_bus,
                    )
                    prepared_caster = prepared.caster if prepared is not None else None
                    caster_snapshot = prepared_caster
                except SpellcastingServiceError as exc:
                    roll_results = {
                        "type": "cast_spell",
                        "summary": str(exc),
                        "error": True,
                    }
            if caster_snapshot is None and request.actor_id:
                snapshot = (active.state_data.get("characters") or {}).get(request.actor_id)
                if isinstance(snapshot, dict):
                    caster_snapshot = snapshot

            mechanics = self._get_mechanics()
            if roll_results is None:
                roll_results = await mechanics._resolve_cast_spell(
                    request.session_id,
                    request.actor_id,
                    request.spell_id,
                    request.slot_level,
                    target_id,
                    active,
                    caster_snapshot,
                )
            if tactical is not None and roll_results is not None:
                roll_results["tactical"] = {
                    "target_id": target_id,
                    "moved": bool(tactical.moved),
                    "movement_used_m": (tactical.moved.movement_used_m if tactical.moved else 0),
                    "path": (
                        [step.to_dict() for step in tactical.moved.path] if tactical.moved else []
                    ),
                    "opportunity_attacks": [
                        attack.__dict__ for attack in tactical.moved.opportunity_attacks
                    ]
                    if tactical.moved
                    else [],
                }
            if roll_results and not roll_results.get("error") and target_id:
                attack = roll_results.get("attack", {})
                damage = roll_results.get("damage", {})
                if damage:
                    hit = attack.get("hit", True) if attack else True
                    if hit:
                        damage_amount = int(damage.get("total", 0))
                        if damage_amount > 0:
                            await self._executor.execute_action(
                                request.session_id,
                                "damage_apply",
                                {"target": target_id, "amount": damage_amount},
                                active,
                            )
                            executed_actions.append(
                                {
                                    "type": "damage_apply",
                                    "target": target_id,
                                    "params": {"amount": damage_amount},
                                    "origin": "engine",
                                }
                            )
        else:
            mechanics = self._get_mechanics()
            roll_results = mechanics._resolve_generic_roll(request.content)
        return target_id, target_name, roll_results, executed_actions, None
