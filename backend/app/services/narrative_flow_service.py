"""Orchestrateur du flux narratif d'exploration.

Ce service donne à l'exploration un rythme plus proche d'une table de JDR :
le joueur peut s'adresser au monde, au MJ, au groupe ou à un compagnon précis ;
les compagnons concernés répondent, puis le MJ arbitre seulement si la scène le
nécessite.
"""
from __future__ import annotations

import logging
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import PlayerActionChoice
from app.game.ai_player_manager import (
    order_companion_spotlight,
    record_companion_spotlight,
)
from app.game.companion_visibility import (
    companion_visible_game_state,
    sanitize_companion_visible_text,
)
from app.game.event_bus import EventType, event_bus
from app.game.session_manager import ActiveSession
from app.game.social_scene_state import (
    advance_scene_clocks,
    detect_impossible_hostile_action,
    publish_impossible_hostile_action,
    resolve_scene_clock_crises,
)
from app.game.travel_detection import TravelIntent, detect_travel_intent, travel_intent_as_dict
from app.game.visible_events import publish_visible_entry
from app.services.message_service import load_recent_messages, persist_narration

logger = logging.getLogger(__name__)

Audience = Literal["gm", "world", "party", "companion", "mixed"]

_DIRECT_ACTION_TYPES = {
    "attack",
    "cast_spell",
    "dash",
    "dodge",
    "help",
    "use_item",
    "move",
    "disengage",
    "hide",
    "shove",
    "examine",
    "death_save",
    "stabilize",
}
_COMPANION_ARBITRAGE_ACTIONS = {"examine", "move", "use_item", "help", "cast_spell"}
_MAX_GROUP_COMPANION_RESPONSES = 2
_SOCIAL_MARKERS = (
    "compagnon",
    "compagnons",
    "amis",
    "votre avis",
    "vos avis",
    "que pensez",
    "qu en pensez",
    "vous en pensez",
    "on fait quoi",
    "que fait on",
    "que faisons nous",
    "vous proposez",
    "vous me couvrez",
    "couvrez moi",
)
_SOCIAL_SKILL_MARKERS = (
    "persuad",
    "convainc",
    "supplier",
    "plaider",
    "enjoindre",
    "intimid",
    "menac",
    "terrifier",
    "brandir",
    "perspicac",
    "detecter le mensonge",
    "sonder",
    "lire",
    "deviner",
    "tromp",
    "mentir",
    "feindre",
    "bluffer",
    "parlement",
    "negoc",
    "charmer",
    "seduire",
    "soudoyer",
    "reconcilier",
    "demander",
    "supplier",
    "implorer",
    "flatter",
    "menacer",
    "intimider",
    "persuader",
    "convaincre",
    "tromper",
    "bluffer",
    "négocier",
    "parlementer",
    "séduire",
)
_WORLD_MARKERS = (
    "j examine",
    "j inspecte",
    "je regarde",
    "je fouille",
    "je cherche",
    "j ecoute",
    "j ouvre",
    "je tente",
    "j essaie",
    "je crochete",
    "je grimpe",
    "j avance",
    "je vais",
    "je prends",
    "j utilise",
    "je pousse",
    "je tire",
)


@dataclass
class AudienceDetection:
    audience: Audience
    target_ids: list[str] = field(default_factory=list)
    addressed_to: str | None = None
    reason: str = ""


@dataclass
class SceneExchange:
    scene_id: str
    audience: Audience
    player_text: str
    target_ids: list[str]
    companion_responses: list[dict[str, str]] = field(default_factory=list)
    gm_arbitrated: bool = False


class NarrativeFlowService:
    """Coordonne une action libre d'exploration avant l'arbitrage éventuel du MJ."""

    async def handle_exploration_action(
        self,
        *,
        session_id: str,
        action: Any,
        active: ActiveSession,
        action_resolver: Any,
        db: AsyncSession | None,
    ) -> SceneExchange:
        """Traite une action joueur hors combat en flux de scène vivant."""
        text = str(getattr(action, "content", "") or getattr(action, "action_type", ""))
        scene_id = str(getattr(action, "scene_id", None) or uuid.uuid4())
        detection = self.detect_audience(
            text,
            active,
            action_type=str(getattr(action, "action_type", "free_text")),
            addressed_to=getattr(action, "addressed_to", None),
            explicit_audience=getattr(action, "audience", None),
        )
        if detection.audience in {"gm", "mixed"} and self._targets_npc(
            text,
            active,
            getattr(action, "target_id", None),
        ):
            detection = AudienceDetection(
                audience="world",
                target_ids=[],
                addressed_to=None,
                reason="npc_target",
            )
        # --- Détection d'intention de voyage ---
        travel_intent = detect_travel_intent(text, active.state_data)
        # Vérifier aussi si le joueur a cliqué sur une sortie de scène
        exit_id = getattr(action, "exit_id", None)
        if exit_id and not travel_intent.is_travel:
            scene = active.state_data.get("current_scene") or {}
            if isinstance(scene, dict):
                for exit_data in scene.get("exits") or []:
                    if isinstance(exit_data, dict) and str(exit_data.get("id") or "") == exit_id:
                        travel_intent = TravelIntent(
                            is_travel=True,
                            destination=str(exit_data.get("label") or ""),
                            destination_node_id=str(exit_data.get("leads_to") or ""),
                            confidence="explicit",
                        )
                        break
        trigger_character_id = getattr(action, "character_id", None)
        target_ids = list(detection.target_ids)
        if detection.audience in {"party", "mixed"}:
            target_ids = order_companion_spotlight(
                active,
                target_ids,
                trigger_character_id=trigger_character_id,
                max_count=_MAX_GROUP_COMPANION_RESPONSES,
            )
        exchange = SceneExchange(
            scene_id=scene_id,
            audience=detection.audience,
            player_text=text,
            target_ids=target_ids,
        )
        filled_clocks = await advance_scene_clocks(
            session_id=session_id,
            active=active,
            event_bus=event_bus,
            source="narrative_flow",
        )
        clock_crisis_happened = False
        if filled_clocks:
            resolved_clocks = await resolve_scene_clock_crises(
                session_id=session_id,
                active=active,
                event_bus=event_bus,
                clocks=filled_clocks,
                actor_id=getattr(action, "character_id", None),
                db=db,
                source="narrative_flow",
            )
            if resolved_clocks:
                clock_crisis_happened = True
                await self._react_after_world_action(
                    session_id=session_id,
                    active=active,
                    action_resolver=action_resolver,
                    trigger_character_id=getattr(action, "character_id", None),
                    db=db,
                    action_text=(
                        "Le danger qui montait dans la scène vient de se déchaîner pour "
                        "de bon. Réagis en une phrase courte, seulement comme "
                        "avertissement ou conseil."
                    ),
                )

        should_ask_companions = detection.audience in {"companion", "party", "mixed"}
        should_arbitrate_world = detection.audience in {"gm", "world", "mixed"}
        pure_social = detection.audience in {"companion", "party"} and not should_arbitrate_world

        if db is not None and (pure_social or detection.audience == "mixed"):
            await self._persist_player_message(session_id, action, active, detection, db, scene_id)

        impossible_weapon = detect_impossible_hostile_action(
            text,
            active,
            getattr(action, "character_id", None),
        )
        if impossible_weapon:
            npc_target_id = self._present_npc_target_id(
                text,
                active,
                getattr(action, "target_id", None),
            )
            if db is not None and detection.audience not in {"companion", "party", "mixed"}:
                await self._persist_player_message(
                    session_id,
                    action,
                    active,
                    detection,
                    db,
                    scene_id,
                )
            await publish_impossible_hostile_action(
                session_id=session_id,
                active=active,
                event_bus=event_bus,
                player_text=text,
                actor_id=getattr(action, "character_id", None),
                npc_id=npc_target_id,
                weapon_marker=impossible_weapon,
                db=db,
            )
            exchange.gm_arbitrated = True
            return exchange

        if should_ask_companions:
            exchange.companion_responses = await self._run_companion_responses(
                session_id=session_id,
                active=active,
                action_resolver=action_resolver,
                player_text=text,
                target_ids=target_ids,
                trigger_character_id=trigger_character_id,
                db=db,
                scene_id=scene_id,
            )

        # Direct one-to-one companion chat should remain a real dialogue, not a
        # forced MJ interruption.
        if detection.audience == "companion" and exchange.companion_responses:
            return exchange

        if detection.audience == "party" and exchange.companion_responses:
            await action_resolver.social_conclude(
                session_id=session_id,
                active=active,
                player_action=text,
                companion_responses=exchange.companion_responses,
                db=db,
            )
            exchange.gm_arbitrated = True
            return exchange

        if should_arbitrate_world:
            npc_target_id = None
            if hasattr(action_resolver, "resolve_npc_dialogue"):
                npc_target_id = self._present_npc_target_id(
                    text,
                    active,
                    getattr(action, "target_id", None),
                )
            resolved = await action_resolver.resolve(
                session_id=session_id,
                action_type=getattr(action, "action_type", "free_text"),
                content=getattr(action, "content", None),
                character_id=getattr(action, "character_id", None),
                target_id=npc_target_id or getattr(action, "target_id", None),
                active=active,
                db=db,
                spell_id=getattr(action, "spell_id", None),
                slot_level=getattr(action, "slot_level", None),
                persist_actor_action=detection.audience != "mixed",
                suppress_gm_narration=bool(npc_target_id),
                scene_poi_id=getattr(action, "scene_poi_id", None),
                scene_interaction_id=getattr(action, "scene_interaction_id", None),
                scene_interaction_intent=getattr(action, "scene_interaction_intent", None),
                travel_intent=travel_intent_as_dict(travel_intent),
            )
            if npc_target_id:
                roll_results = getattr(resolved, "mechanics", None)
                if not isinstance(roll_results, dict):
                    roll_results = None
                dialogue_published = await action_resolver.resolve_npc_dialogue(
                    session_id=session_id,
                    content=text,
                    character_id=getattr(action, "character_id", None),
                    target_id=npc_target_id,
                    active=active,
                    db=db,
                    roll_results=roll_results,
                )
                if not dialogue_published:
                    await self._publish_npc_dialogue_fallback(
                        session_id=session_id,
                        active=active,
                        npc_target_id=npc_target_id,
                        db=db,
                    )
                    exchange.gm_arbitrated = True
                    return exchange
                # Spotlight pass : laisse un compagnon réagir à la réplique du
                # PNJ, comme à une vraie table où les autres PJ écoutent et
                # commentent l'échange. Cap à 1 pour ne pas saturer la scène.
                await self._react_after_npc_dialogue(
                    session_id=session_id,
                    active=active,
                    action_resolver=action_resolver,
                    trigger_character_id=getattr(action, "character_id", None),
                    db=db,
                )
            elif not clock_crisis_happened:
                # Action monde sans PNJ (examiner un monolithe, se déplacer, fouiller…)
                # Laisser un compagnon réagir spontanément au résultat du MJ —
                # comme à une vraie table où les autres PJ observent et commentent.
                # Cap à 1 pour ne pas saturer le flux narratif.
                await self._react_after_world_action(
                    session_id=session_id,
                    active=active,
                    action_resolver=action_resolver,
                    trigger_character_id=getattr(action, "character_id", None),
                    db=db,
                    action_text=text,
                )
            exchange.gm_arbitrated = True
            return exchange

        # Fallback : si aucune IA n'a répondu à une adresse sociale, repasser au MJ.
        if not exchange.companion_responses:
            await action_resolver.resolve(
                session_id=session_id,
                action_type=getattr(action, "action_type", "free_text"),
                content=getattr(action, "content", None),
                character_id=getattr(action, "character_id", None),
                target_id=getattr(action, "target_id", None),
                active=active,
                db=db,
                spell_id=getattr(action, "spell_id", None),
                slot_level=getattr(action, "slot_level", None),
                scene_poi_id=getattr(action, "scene_poi_id", None),
                scene_interaction_id=getattr(action, "scene_interaction_id", None),
                scene_interaction_intent=getattr(action, "scene_interaction_intent", None),
                travel_intent=travel_intent_as_dict(travel_intent),
            )
            exchange.gm_arbitrated = True
        return exchange

    def detect_audience(
        self,
        text: str,
        active: ActiveSession,
        *,
        action_type: str = "free_text",
        addressed_to: str | None = None,
        explicit_audience: str | None = None,
    ) -> AudienceDetection:
        """Détecte à qui s'adresse un message d'exploration."""
        companions = self._companion_index(active)
        explicit = str(explicit_audience or "").strip().lower()
        if explicit in {"gm", "world", "party", "companion", "mixed"}:
            targets = self._target_ids_for_explicit(explicit, addressed_to, companions)
            return AudienceDetection(
                audience=explicit,  # type: ignore[arg-type]
                target_ids=targets,
                addressed_to=addressed_to,
                reason="explicit",
            )

        addressed_id = self._resolve_companion_reference(addressed_to, companions)
        if addressed_id:
            return AudienceDetection(
                audience="companion",
                target_ids=[addressed_id],
                addressed_to=addressed_id,
                reason="addressed_to",
            )

        mentioned_id = self._find_mentioned_companion(text, companions)
        normalized = _normalize_text(text)
        has_social = mentioned_id is not None or any(m in normalized for m in _SOCIAL_MARKERS)
        has_world = action_type in _DIRECT_ACTION_TYPES or any(
            m in normalized for m in _WORLD_MARKERS
        )
        has_social_skill = any(m in normalized for m in _SOCIAL_SKILL_MARKERS)

        if mentioned_id and has_world:
            return AudienceDetection("mixed", [mentioned_id], mentioned_id, "mention+world")
        if mentioned_id:
            return AudienceDetection("companion", [mentioned_id], mentioned_id, "mention")
        if has_social_skill and companions:
            return AudienceDetection("mixed", list(companions), None, "social_skill")
        if has_social_skill:
            return AudienceDetection("world", [], None, "social_skill")
        if has_social and has_world:
            return AudienceDetection("mixed", list(companions), None, "party+world")
        if has_social:
            return AudienceDetection("party", list(companions), None, "party")
        if has_world:
            return AudienceDetection("world", [], None, "world")
        return AudienceDetection("gm", [], None, "default_gm")

    async def _run_companion_responses(
        self,
        *,
        session_id: str,
        active: ActiveSession,
        action_resolver: Any,
        player_text: str,
        target_ids: list[str],
        trigger_character_id: str | None,
        db: AsyncSession | None,
        scene_id: str,
    ) -> list[dict[str, str]]:
        if not active.ai_players:
            return []

        recent_messages = await load_recent_messages(session_id, db) if db is not None else []
        visible_game_state = companion_visible_game_state(active.state_data)
        responses: list[dict[str, str]] = []
        for char_id in target_ids:
            if char_id == trigger_character_id:
                continue
            agent = active.ai_players.get(char_id)
            if agent is None:
                continue

            char_name = str(getattr(agent, "character_name", char_id))
            await self._publish_thinking(session_id, True, char_id, char_name)
            try:
                if hasattr(agent, "respond_to_player"):
                    choice = await agent.respond_to_player(
                        game_state=visible_game_state,
                        player_message=player_text,
                        messages=recent_messages,
                    )
                else:
                    choice = await agent.roleplay(
                        game_state=visible_game_state,
                        scene_context=player_text,
                        messages=recent_messages,
                    )
            except Exception as exc:
                logger.error("NarrativeFlowService: companion '%s' failed: %s", char_name, exc)
                choice = PlayerActionChoice(
                    action_type="wait",
                    action_description="Le personnage hésite.",
                    roleplay_text=f"{char_name} hésite, le regard attentif.",
                    llm_error=f"{type(exc).__name__}: {exc}",
                )
            finally:
                await self._publish_thinking(session_id, False, char_id, char_name)

            if choice.llm_error:
                await event_bus.publish_to_session(
                    session_id,
                    EventType.ERROR,
                    {
                        "source": "player_agent",
                        "character": char_name,
                        "message": f"Le compagnon IA {char_name} est temporairement indisponible.",
                    },
                    source="narrative_flow",
                )
                continue

            visible_text = self._visible_companion_text(choice, char_name)
            await publish_visible_entry(
                event_bus,
                session_id,
                {
                    "text": visible_text,
                    "speaker": char_name,
                    "speaker_id": char_id,
                    "speaker_kind": "companion",
                    "entry_kind": "dialogue",
                    "action_type": choice.action_type,
                    "is_ai_player": True,
                    "scene_id": scene_id,
                },
                source="narrative_flow",
            )
            if db is not None:
                from app.models.message import MessageRole, MessageType

                await persist_narration(
                    session_id,
                    visible_text,
                    char_name,
                    db,
                    role=MessageRole.PLAYER,
                    message_type=MessageType.DIALOGUE,
                    metadata={
                        "is_ai_player": True,
                        "character_id": char_id,
                        "action_type": choice.action_type,
                        "speaker_kind": "companion",
                        "scene_id": scene_id,
                    },
                )
            responses.append({"speaker": char_name, "text": visible_text})
            record_companion_spotlight(active, char_id)

            if choice.action_type in _COMPANION_ARBITRAGE_ACTIONS:
                await action_resolver.resolve(
                    session_id=session_id,
                    action_type=choice.action_type,
                    content=self._companion_action_prompt(choice, char_name),
                    character_id=char_id,
                    target_id=choice.target,
                    active=active,
                    db=db,
                    spell_id=self._choice_spell_id(choice),
                    slot_level=self._choice_slot_level(choice),
                    actor_kind="companion",
                    actor_name=char_name,
                    display_text=visible_text,
                    persist_actor_action=False,
                )

        return responses

    @staticmethod
    def _targets_npc(
        text: str,
        active: ActiveSession,
        explicit_target_id: str | None,
    ) -> bool:
        try:
            from app.game.social_resolution import resolve_npc_target_id

            return bool(resolve_npc_target_id(text, active.state_data, explicit_target_id))
        except Exception:
            return False

    @staticmethod
    def _present_npc_target_id(
        text: str,
        active: ActiveSession,
        explicit_target_id: str | None,
    ) -> str | None:
        try:
            from app.game.social_resolution import _is_npc_poi, _poi_by_id, resolve_npc_target_id

            npc_target_id = resolve_npc_target_id(text, active.state_data, explicit_target_id)
            poi = _poi_by_id(active.state_data, npc_target_id)
            return npc_target_id if _is_npc_poi(poi) else None
        except Exception:
            return None

    @staticmethod
    async def _publish_npc_dialogue_fallback(
        *,
        session_id: str,
        active: ActiveSession,
        npc_target_id: str,
        db: AsyncSession | None,
    ) -> None:
        text = "Service IA indisponible pour ce PNJ."
        scene = active.state_data.get("current_scene")
        scene_id = str(scene.get("scene_id") or "") if isinstance(scene, dict) else ""
        payload = {
            "message": text,
            "source": "npc_dialogue",
            "target_id": npc_target_id,
        }
        await event_bus.publish_to_session(
            session_id,
            EventType.NARRATION,
            {
                "text": text,
                "message": text,
                "speaker": "Système",
                "speaker_kind": "system",
                "entry_kind": "system",
                "target_id": npc_target_id,
                "scene_id": scene_id or None,
            },
            source="narrative_flow",
        )
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            payload,
            source="narrative_flow",
        )
        if db is not None:
            from app.models.message import MessageRole, MessageType

            await persist_narration(
                session_id,
                text,
                "Maître du Jeu",
                db,
                role=MessageRole.SYSTEM,
                message_type=MessageType.SYSTEM,
                metadata={
                    "speaker_kind": "gm",
                    "entry_kind": "system",
                    "target": npc_target_id,
                    "scene_id": scene_id or None,
                },
            )

    @staticmethod
    async def _react_after_npc_dialogue(
        *,
        session_id: str,
        active: ActiveSession,
        action_resolver: Any,
        trigger_character_id: str | None,
        db: AsyncSession | None,
    ) -> None:
        """Laisse un compagnon IA réagir à la réplique d'un PNJ.

        Garde-fou : cap explicite à 1 compagnon pour ne pas saturer la scène
        sociale, et silencieux si aucun compagnon IA n'est présent.
        """
        if not active.ai_players:
            return
        try:
            from app.game.ai_player_manager import AIPlayerManager

            await AIPlayerManager().run_exploration_reactions(
                session_id,
                active,
                action_resolver,
                trigger_character_id=trigger_character_id,
                db=db,
                max_reactors=1,
            )
        except Exception as exc:
            logger.error(
                "NarrativeFlowService: companion reaction after NPC dialogue failed: %s",
                exc,
            )

    @staticmethod
    async def _react_after_world_action(
        *,
        session_id: str,
        active: ActiveSession,
        action_resolver: Any,
        trigger_character_id: str | None,
        db: AsyncSession | None,
        action_text: str | None = None,
    ) -> None:
        """Laisse un compagnon IA réagir après une action monde arbitrée par le MJ.

        Déclenché après que le joueur examine un objet, se déplace, fouille une
        zone ou interagit avec l'environnement — à condition qu'il y ait au moins
        un compagnon IA actif. Le cap à 1 évite de saturer le flux narratif après
        chaque action. Silencieux en cas d'erreur pour ne pas bloquer la session.

        ``action_text`` est transmis à ``run_exploration_reactions`` pour activer
        le biais de spécialité : le mage réagit en priorité aux POI magiques,
        le roublard aux pièges, etc.
        """
        if not active.ai_players:
            return
        try:
            from app.game.ai_player_manager import AIPlayerManager

            await AIPlayerManager().run_exploration_reactions(
                session_id,
                active,
                action_resolver,
                trigger_character_id=trigger_character_id,
                db=db,
                max_reactors=1,
                action_text=action_text,
            )
        except Exception as exc:
            logger.error(
                "NarrativeFlowService: companion reaction after world action failed: %s",
                exc,
            )

    async def _persist_player_message(
        self,
        session_id: str,
        action: Any,
        active: ActiveSession,
        detection: AudienceDetection,
        db: AsyncSession,
        scene_id: str,
    ) -> None:
        from app.models.message import MessageRole, MessageType

        speaker = self._actor_name(getattr(action, "character_id", None), active)
        await persist_narration(
            session_id,
            str(getattr(action, "content", "") or getattr(action, "action_type", "")),
            speaker,
            db,
            role=MessageRole.PLAYER,
            message_type=MessageType.DIALOGUE,
            metadata={
                "action_type": getattr(action, "action_type", "free_text"),
                "character_id": getattr(action, "character_id", None),
                "audience": detection.audience,
                "addressed_to": detection.addressed_to,
                "speaker_kind": "human",
                "scene_id": scene_id,
            },
        )

    async def _publish_thinking(
        self,
        session_id: str,
        thinking: bool,
        character_id: str,
        character_name: str,
    ) -> None:
        await event_bus.publish_to_session(
            session_id,
            EventType.AI_THINKING,
            {
                "agent_kind": "player_ai",
                "thinking": thinking,
                "character_id": character_id,
                "character_name": character_name,
            },
            source="narrative_flow",
        )

    def _target_ids_for_explicit(
        self,
        explicit: str,
        addressed_to: str | None,
        companions: dict[str, str],
    ) -> list[str]:
        if explicit == "companion":
            resolved = self._resolve_companion_reference(addressed_to, companions)
            return [resolved] if resolved else []
        if explicit in {"party", "mixed"}:
            resolved = self._resolve_companion_reference(addressed_to, companions)
            return [resolved] if resolved else list(companions)
        return []

    @staticmethod
    def _companion_index(active: ActiveSession) -> dict[str, str]:
        return {
            str(char_id): str(getattr(agent, "character_name", char_id))
            for char_id, agent in active.ai_players.items()
        }

    @staticmethod
    def _resolve_companion_reference(
        reference: str | None,
        companions: dict[str, str],
    ) -> str | None:
        if not reference:
            return None
        normalized_ref = _normalize_text(reference)
        for char_id, name in companions.items():
            if normalized_ref in {_normalize_text(char_id), _normalize_text(name)}:
                return char_id
        return None

    @classmethod
    def _find_mentioned_companion(
        cls,
        text: str,
        companions: dict[str, str],
    ) -> str | None:
        raw = text or ""
        normalized = _normalize_text(raw)
        for char_id, name in companions.items():
            name_norm = _normalize_text(name)
            id_norm = _normalize_text(char_id)
            if re.search(rf"(^|\s)@{re.escape(name_norm)}(\s|$)", normalized):
                return char_id
            if re.search(rf"(^|\s)@{re.escape(id_norm)}(\s|$)", normalized):
                return char_id
            if normalized.startswith(f"{name_norm} ") or normalized.startswith(f"{name_norm},"):
                return char_id
            if (
                normalized.startswith(f"{name_norm} que")
                or normalized.startswith(f"{name_norm} qu")
            ):
                return char_id
        return None

    @staticmethod
    def _visible_companion_text(choice: PlayerActionChoice, character_name: str) -> str:
        roleplay = str(choice.roleplay_text or "").strip()
        if roleplay:
            return sanitize_companion_visible_text(roleplay, character_name=character_name)
        if choice.action_type not in _COMPANION_ARBITRAGE_ACTIONS:
            return roleplay
        return sanitize_companion_visible_text(
            NarrativeFlowService._companion_action_prompt(choice, character_name),
            character_name=character_name,
        )

    @staticmethod
    def _choice_spell_id(choice: PlayerActionChoice) -> str | None:
        spell_id = str(
            choice.params.get("spell_id")
            or choice.params.get("spell_name")
            or ""
        ).strip()
        return spell_id or None

    @staticmethod
    def _choice_slot_level(choice: PlayerActionChoice) -> int | None:
        raw_level = choice.params.get("slot_level")
        if raw_level is None:
            raw_level = choice.params.get("level")
        if raw_level is None or raw_level == "":
            return None
        try:
            return int(raw_level)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _companion_action_prompt(choice: PlayerActionChoice, character_name: str) -> str:
        description = str(choice.action_description or "").strip()
        if not description:
            description = str(choice.roleplay_text or choice.action_type).strip()
        if not description:
            return f"{character_name} agit."
        if description.casefold().startswith(character_name.casefold()):
            text = description
        else:
            text = f"{character_name} {description[:1].lower()}{description[1:]}"
        return text if text[-1] in ".!?…" else f"{text}."

    @staticmethod
    def _actor_name(character_id: str | None, active: ActiveSession) -> str:
        if not character_id:
            return "Joueur"
        characters = active.state_data.get("characters", {})
        if isinstance(characters, dict):
            cdata = characters.get(character_id)
            if isinstance(cdata, dict) and cdata.get("name"):
                return str(cdata["name"])
        return str(character_id)


def _normalize_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value).lower())
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9_@]+", " ", without_accents).strip()
