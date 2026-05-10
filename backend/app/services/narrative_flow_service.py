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
from typing import Any, Literal, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.player_agent import _NON_JSON_LLM_ERROR
from app.agents.schemas import PlayerActionChoice
from app.game.companion_visibility import (
    companion_visible_game_state,
    sanitize_companion_visible_text,
)
from app.game.event_bus import EventType, event_bus
from app.game.session_manager import ActiveSession
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
_COMPANION_ARBITRAGE_ACTIONS = {"examine", "move", "use_item", "help"}
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
    addressed_to: Optional[str] = None
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
        db: Optional[AsyncSession],
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
        exchange = SceneExchange(
            scene_id=scene_id,
            audience=detection.audience,
            player_text=text,
            target_ids=list(detection.target_ids),
        )

        should_ask_companions = detection.audience in {"companion", "party", "mixed"}
        should_arbitrate_world = detection.audience in {"gm", "world", "mixed"}
        pure_social = detection.audience in {"companion", "party"} and not should_arbitrate_world

        if db is not None and (pure_social or detection.audience == "mixed"):
            await self._persist_player_message(session_id, action, active, detection, db, scene_id)

        if should_ask_companions:
            exchange.companion_responses = await self._run_companion_responses(
                session_id=session_id,
                active=active,
                action_resolver=action_resolver,
                player_text=text,
                target_ids=detection.target_ids,
                trigger_character_id=getattr(action, "character_id", None),
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
            resolved = await action_resolver.resolve(
                session_id=session_id,
                action_type=getattr(action, "action_type", "free_text"),
                content=getattr(action, "content", None),
                character_id=getattr(action, "character_id", None),
                target_id=getattr(action, "target_id", None),
                active=active,
                db=db,
                spell_id=getattr(action, "spell_id", None),
                slot_level=getattr(action, "slot_level", None),
                persist_actor_action=detection.audience != "mixed",
            )
            if hasattr(action_resolver, "resolve_npc_dialogue"):
                from app.game.action_pipeline import resolve_npc_target_id

                npc_target_id = resolve_npc_target_id(
                    text,
                    active.state_data,
                    getattr(action, "target_id", None),
                )
                roll_results = getattr(resolved, "mechanics", None)
                if not isinstance(roll_results, dict):
                    roll_results = None
                if npc_target_id:
                    await action_resolver.resolve_npc_dialogue(
                        session_id=session_id,
                        content=text,
                        character_id=getattr(action, "character_id", None),
                        target_id=npc_target_id,
                        active=active,
                        db=db,
                        roll_results=roll_results,
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
            )
            exchange.gm_arbitrated = True
        return exchange

    def detect_audience(
        self,
        text: str,
        active: ActiveSession,
        *,
        action_type: str = "free_text",
        addressed_to: Optional[str] = None,
        explicit_audience: Optional[str] = None,
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
        trigger_character_id: Optional[str],
        db: Optional[AsyncSession],
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

            if choice.llm_error and choice.llm_error != _NON_JSON_LLM_ERROR:
                await event_bus.publish_to_session(
                    session_id,
                    EventType.ERROR,
                    {
                        "source": "player_agent",
                        "character": char_name,
                        "message": f"L'IA de {char_name} n'a pas pu répondre : {choice.llm_error}",
                    },
                    source="narrative_flow",
                )
                continue

            visible_text = self._visible_companion_text(choice, char_name)
            await event_bus.publish_to_session(
                session_id,
                EventType.NARRATION,
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

            if choice.action_type in _COMPANION_ARBITRAGE_ACTIONS:
                await action_resolver.resolve(
                    session_id=session_id,
                    action_type=choice.action_type,
                    content=self._companion_action_prompt(choice, char_name),
                    character_id=char_id,
                    target_id=choice.target,
                    active=active,
                    db=db,
                    actor_kind="companion",
                    actor_name=char_name,
                    display_text=visible_text,
                    persist_actor_action=False,
                )

        return responses

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
        addressed_to: Optional[str],
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
        reference: Optional[str],
        companions: dict[str, str],
    ) -> Optional[str]:
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
    ) -> Optional[str]:
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
    def _actor_name(character_id: Optional[str], active: ActiveSession) -> str:
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
