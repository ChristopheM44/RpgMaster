"""Pipeline unifie de resolution et publication d'action.

Le pipeline centralise le contrat visible :
action acteur -> resolution mecanique -> ROLL_RESULT -> narration MJ.
Il ne choisit pas les actions et ne fait pas avancer les tours.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.agents.schemas import AgentContext, AgentResponse, GMResponse
from app.game.combat_triggers import prime_combat_from_hostile_narration
from app.game.constants import INACTIVE_STATUSES
from app.game.event_bus import EventType, event_bus
from app.game.gm_response_executor import GMResponseExecutor
from app.game.session_manager import ActiveSession
from app.llm.budget import (
    begin_llm_call_scope,
    end_llm_call_scope,
    is_companion_social_prompt,
    is_sober_mode,
    should_use_gm_for_action,
)
from app.llm.voxtral_client import tts_router

logger = logging.getLogger(__name__)

_FALLBACK_NARRATION = (
    "Le Maître du Jeu observe la situation... "
    "(Le système de narration est temporairement indisponible.)"
)


class ActionRequest(BaseModel):
    """Action normalisee envoyee au pipeline."""

    session_id: str
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    actor_kind: Literal["player", "companion", "monster"] = "player"
    action_type: str
    content: Optional[str] = None
    target_id: Optional[str] = None
    spell_id: Optional[str] = None
    slot_level: Optional[int] = None
    display_text: Optional[str] = None


class ResolvedAction(BaseModel):
    """Resultat structure d'une action resolue et publiee."""

    actor_id: Optional[str] = None
    actor_name: str = ""
    actor_kind: Literal["player", "companion", "monster"]
    action_type: str
    target_id: Optional[str] = None
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
        db: Optional[Any] = None,
        *,
        mechanics: Optional[Any] = None,
        source: str = "action_pipeline",
    ) -> None:
        self._gm = gm_agent
        self._event_bus = event_bus_instance
        self._db = db
        self._mechanics = mechanics
        self._source = source
        self._executor = GMResponseExecutor(event_bus_instance, source=source)

    async def resolve_and_publish(
        self,
        request: ActionRequest,
        active: ActiveSession,
        db: Optional[Any] = None,
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
        db: Optional[Any] = None,
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

        roll_results: Optional[dict[str, Any]] = None
        roll_events: list[dict[str, Any]] = []
        executed_actions: list[dict[str, Any]] = []
        canon_dirty = False

        # 1. Resolution mecanique pure.
        mechanics = self._get_mechanics()
        if request.action_type == "attack":
            roll_results = mechanics._resolve_attack(
                request.actor_id,
                target_id,
                active.state_data,
            )
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
        elif request.action_type == "death_save":
            roll_results = mechanics._resolve_death_save(request.actor_id, active.state_data)
            await mechanics._apply_death_save_outcome(
                request.session_id,
                request.actor_id,
                roll_results,
                active,
            )
        elif request.action_type == "stabilize":
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
        elif request.action_type == "cast_spell":
            if request.spell_id is not None and actual_db is not None:
                roll_results = await mechanics._resolve_cast_spell(
                    request.session_id,
                    request.actor_id,
                    request.spell_id,
                    request.slot_level,
                    target_id,
                    active,
                    actual_db,
                )
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
                roll_results = mechanics._resolve_generic_roll(request.content)

        # 2. Persistance visible puis contexte GM avec resume mecanique.
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
        phase_value = self._phase_value(active).upper()
        use_gm = should_use_gm_for_action(
            phase=phase_value,
            action_type=request.action_type,
            actor_kind=request.actor_kind,
            content=request.content,
            roll_results=roll_results,
        )
        if (
            is_sober_mode()
            and phase_value != "COMBAT"
            and is_companion_social_prompt(request.content)
            and not active.ai_players
        ):
            use_gm = True
        context: Optional[AgentContext] = None

        gm_response: Optional[AgentResponse] = None
        if use_gm:
            recent_messages: list[Any] = []
            if actual_db is not None:
                from app.services.message_service import load_recent_messages

                recent_messages = await load_recent_messages(request.session_id, actual_db)

            context = AgentContext(
                session_id=request.session_id,
                game_phase=phase_value,
                game_state=active.state_data,
                player_action=prompt_action_text,
                roll_results=roll_results or {},
                messages=recent_messages,
            )

            try:
                await self._publish_ai_thinking(request.session_id, True)
                gm_candidate = await self._gm.think(context)
                gm_response = self._as_agent_response(gm_candidate)
            except Exception as exc:
                logger.error("ActionPipeline : GMAgent echoue : %s", exc)
            finally:
                await self._publish_ai_thinking(request.session_id, False)

        if gm_response:
            active.last_gm_intent = gm_response.action_intent
        elif (
            is_sober_mode()
            and phase_value != "COMBAT"
            and is_companion_social_prompt(request.content)
        ):
            active.last_gm_intent = "social"
        else:
            active.last_gm_intent = None

        has_gm_roll_request = bool(
            gm_response
            and any(gm_action.type == "roll_request" for gm_action in gm_response.actions)
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
            roll_evt = mechanics._normalize_roll_event(roll_results)
            roll_evt = self._enrich_roll_event(roll_evt, request, actor_name, target_id)
            roll_events.append(roll_evt)
            await self._event_bus.publish_to_session(
                request.session_id,
                EventType.ROLL_RESULT,
                roll_evt,
                source=self._source,
            )

        if gm_response:
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

        # 4. Actions GM initiales. Si roll_request, l'outcome narrera le resultat.
        pending_rolls: list[dict[str, Any]] = []
        if gm_response:
            exec_result = await self._executor.execute_gm_response(
                gm_response,
                active,
                actual_db,
                session_id=request.session_id,
                fallback_actor_id=request.actor_id,
            )
            pending_rolls.extend(exec_result.pending_rolls)
            roll_events.extend(exec_result.pending_rolls)
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
                logger.warning(
                    "ActionPipeline : jets GM en attente sans contexte de narration."
                )
                context = AgentContext(
                    session_id=request.session_id,
                    game_phase=phase_value,
                    game_state=active.state_data,
                    player_action=prompt_action_text,
                    roll_results=roll_results or {},
                    messages=[],
                )
            outcome_response = await self._narrate_outcome(
                request.session_id,
                context,
                pending_rolls,
            )
            if outcome_response and outcome_response.narration:
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
                )
                roll_events.extend(outcome_exec.pending_rolls)
                executed_actions.extend(outcome_exec.executed_actions)
                canon_dirty = canon_dirty or outcome_exec.canon_dirty

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

    @staticmethod
    def _deterministic_narration(
        request: ActionRequest,
        actor_name: str,
        target_name: str,
        roll_results: Optional[dict[str, Any]],
    ) -> str:
        action = request.action_type.strip().lower()
        target_label = target_name or "la cible"

        if is_companion_social_prompt(request.content):
            return ""

        if action == "attack" and roll_results:
            hit = bool(roll_results.get("hit"))
            critical = bool(roll_results.get("critical"))
            if hit:
                damage = int(roll_results.get("damage", {}).get("total", 0))
                crit_text = " d'un coup critique" if critical else ""
                return (
                    f"{actor_name} touche {target_label}{crit_text} "
                    f"et inflige {damage} degats."
                )
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
        await self._event_bus.publish_to_session(
            session_id,
            EventType.AI_THINKING,
            {"agent_kind": "gm", "thinking": thinking},
            source=self._source,
        )

    async def _publish_gm_narration(
        self,
        session_id: str,
        narration_text: str,
        db: Optional[Any],
    ) -> None:
        narration_id = str(uuid.uuid4())
        await self._event_bus.publish_to_session(
            session_id,
            EventType.NARRATION,
            {
                "text": narration_text,
                "speaker": "Maître du Jeu",
                "narration_id": narration_id,
            },
            source=self._source,
        )

        if db is not None:
            from app.services.message_service import persist_narration

            await persist_narration(session_id, narration_text, "Maître du Jeu", db)

        asyncio.create_task(
            tts_router.synthesize_and_broadcast(narration_text, session_id, narration_id)
        )

    async def _narrate_outcome(
        self,
        session_id: str,
        context: AgentContext,
        pending_rolls: list[dict[str, Any]],
    ) -> Optional[GMResponse]:
        outcome_response: Optional[GMResponse] = None
        try:
            await self._publish_ai_thinking(session_id, True)
            try:
                outcome_candidate = await self._gm.narrate_outcome_response(
                    context,
                    pending_rolls,
                )
            except (AttributeError, TypeError):
                outcome_candidate = await self._gm.narrate_outcome(context, pending_rolls)

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
        finally:
            await self._publish_ai_thinking(session_id, False)
        return outcome_response

    async def _persist_actor_action(
        self,
        session_id: str,
        visible_text: str,
        actor_name: str,
        request: ActionRequest,
        target_id: Optional[str],
        db: Optional[Any],
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
    def _as_agent_response(candidate: Any) -> Optional[AgentResponse]:
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
    def _without_combat_damage_actions(response: AgentResponse) -> AgentResponse:
        actions = [
            gm_action for gm_action in response.actions if gm_action.type != "damage_apply"
        ]
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
        target_id: Optional[str],
    ) -> dict[str, Any]:
        enriched = dict(payload)
        enriched.setdefault("character_id", request.actor_id)
        enriched["actor_id"] = request.actor_id
        enriched["actor_name"] = actor_name
        enriched["actor_kind"] = request.actor_kind
        enriched["action_type"] = request.action_type
        enriched["target_id"] = target_id
        return enriched

    @classmethod
    def _prompt_action_text(
        cls,
        request: ActionRequest,
        actor_name: str,
        target_name: str,
        roll_results: Optional[dict[str, Any]],
    ) -> str:
        if request.content:
            text = request.content
        elif request.action_type == "attack" and target_name:
            if request.actor_kind == "monster":
                text = f"[Tour du monstre] {actor_name} attaque {target_name}."
            elif request.actor_kind == "companion":
                text = f"[Compagnon IA] {actor_name} attaque {target_name}."
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
    def _default_target_id(request: ActionRequest, state_data: dict[str, Any]) -> Optional[str]:
        if request.actor_kind != "monster" or request.action_type != "attack":
            return None

        combatants = state_data.get("combatants", {})
        if not isinstance(combatants, dict):
            return None
        for combatant_id, cdata in combatants.items():
            if not isinstance(cdata, dict):
                continue
            status = str(cdata.get("status", "active")).lower()
            try:
                hp = int(cdata.get("hp", 0))
            except (TypeError, ValueError):
                hp = 0
            if cdata.get("is_player", False) and hp > 0 and status not in INACTIVE_STATUSES:
                return combatant_id
        return None

    @staticmethod
    def _actor_name(
        actor_id: Optional[str],
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
    def _combatant_name(state_data: dict[str, Any], combatant_id: Optional[str]) -> str:
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
        target_id: Optional[str],
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
