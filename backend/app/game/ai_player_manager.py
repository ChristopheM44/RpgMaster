"""AI player manager — triggers PlayerAgent actions during AI combatant turns.

Integrates with TurnManager: when the current turn belongs to an AI-controlled
player character, this module calls PlayerAgent.decide_action() (or .roleplay()),
validates the result, and dispatches it through ActionResolver. Monster turns
are handled by the combat WebSocket loop, not by PlayerAgent.

Usage::

    from app.game.ai_player_manager import AIPlayerManager

    ai_manager = AIPlayerManager()

    # After a human action resolves, trigger any consecutive AI turns:
    triggered = await ai_manager.process_ai_turns(session_id, active, action_resolver)
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import TYPE_CHECKING, Any, Optional

from app.agents.player_agent import _NON_JSON_LLM_ERROR
from app.agents.schemas import PlayerActionChoice
from app.game.companion_visibility import (
    companion_visible_game_state,
    sanitize_companion_visible_text,
)
from app.game.constants import INACTIVE_STATUSES
from app.game.event_bus import EventType, event_bus
from app.llm.budget import (
    begin_llm_call_scope,
    end_llm_call_scope,
    is_sober_mode,
    record_llm_call,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.game.action_resolver import ActionResolver
    from app.game.session_manager import ActiveSession

logger = logging.getLogger(__name__)

_WAIT_ACTION = PlayerActionChoice(
    action_type="wait",
    action_description="Le personnage attend son tour.",
    roleplay_text="(attend, sur la défensive)",
    inner_reasoning="Fallback : aucune action valide disponible.",
)

_COMBAT_STARTING_ACTIONS = {"attack", "cast_spell", "shove"}

# Actions d'exploration qui nécessitent un arbitrage MJ (résolution moteur + narration).
# talk/wait sont purement narratifs et ne déclenchent PAS le pipeline MJ.
_EXPLORATION_ARBITRAGE_ACTIONS = {"examine", "move", "use_item", "help"}
_MECHANICAL_ACTION_TYPES = (
    _COMBAT_STARTING_ACTIONS
    | _EXPLORATION_ARBITRAGE_ACTIONS
    | {"dash", "disengage", "dodge", "hide", "stabilize", "death_save"}
)


def _build_scene_context(messages: list) -> str:
    """Construit un résumé de scène à partir des derniers messages persistés.

    Extrait le dernier message du MJ et le dernier message joueur pour que le
    compagnon IA sache ce qui vient de se passer sans ingérer l'historique entier.
    """
    last_gm: Optional[str] = None
    last_player: Optional[str] = None
    for msg in reversed(messages):
        role = getattr(msg, "role", None)
        role_val = role.value if hasattr(role, "value") else str(role)
        if last_gm is None and role_val == "gm":
            last_gm = f"[Narration MJ] {msg.content}"
        if last_player is None and role_val == "player":
            speaker = getattr(msg, "speaker", "Joueur")
            last_player = f"[{speaker}] {msg.content}"
        if last_gm and last_player:
            break
    return "\n".join(p for p in [last_gm, last_player] if p)


def register_ai_player(active: "ActiveSession", char_id: str, cdata: dict[str, Any]) -> None:
    """Instancie et enregistre un PlayerAgent pour un compagnon IA donné.

    Idempotent : ne recrée pas l'agent s'il est déjà présent dans
    ``active.ai_players``. Ignore les entrées non-IA.
    """
    from app.agents.player_agent import PlayerAgent, PlayerPersonality

    if not cdata.get("is_ai", False):
        return
    if char_id in active.ai_players:
        return

    traits = cdata.get("personality") or ["brave"]
    if isinstance(traits, str):
        traits = [traits]
    # Les traits peuvent être stockés comme dict {"traits": [...]}
    if isinstance(traits, dict):
        traits = list(traits.get("traits") or ["brave"])

    active.ai_players[char_id] = PlayerAgent(
        character_id=char_id,
        character_name=cdata.get("name", char_id),
        personality=PlayerPersonality(traits=list(traits)),
    )
    logger.info(
        "register_ai_player: PlayerAgent enregistré pour '%s' (%s).",
        cdata.get("name", char_id),
        char_id,
    )


def unregister_ai_player(active: "ActiveSession", char_id: str) -> None:
    """Retire le PlayerAgent d'un personnage (passage sous contrôle humain)."""
    if active.ai_players.pop(char_id, None) is not None:
        logger.info("unregister_ai_player: PlayerAgent retiré pour %s.", char_id)


def rebuild_ai_players(active: "ActiveSession") -> int:
    """Reconstruit le registre ``ai_players`` à partir de ``state_data['characters']``.

    Appelé à l'ouverture d'une session pour restaurer les agents après un
    redémarrage backend, un ``load_save`` ou une fermeture/réouverture.

    Retourne le nombre d'agents (re)créés.
    """
    characters = active.state_data.get("characters") or {}
    before = len(active.ai_players)
    for char_id, cdata in characters.items():
        register_ai_player(active, char_id, cdata)
    created = len(active.ai_players) - before
    if created:
        logger.info(
            "rebuild_ai_players: %d agent(s) reconstruit(s) pour la session %s.",
            created,
            active.session_id,
        )
    return created


class AIPlayerManager:
    """Orchestrates AI companion turns within a game session.

    After each human player action, call :meth:`process_ai_turns` to let all
    consecutive AI-controlled player characters act before the next human or
    monster turn.

    The method stops as soon as a non-player, non-AI, or missing turn is reached
    (or the order is exhausted), so it is safe to call unconditionally.
    """

    async def process_ai_turns(
        self,
        session_id: str,
        active: "ActiveSession",
        action_resolver: "ActionResolver",
        db: Optional["AsyncSession"] = None,
        max_turns: Optional[int] = None,
    ) -> int:
        """Trigger all consecutive AI-controlled PC turns from the current entry.

        Args:
            session_id: Active session identifier (for event publishing).
            active: In-memory session state (provides turn_manager and ai_players).
            action_resolver: Pipeline that resolves actions through engine + GM agent.
            max_turns: Optional cap on processed AI PC turns. ``None`` keeps the
                legacy batch behavior.

        Returns:
            The number of AI actions triggered this call.
        """
        triggered = 0

        while True:
            current = active.turn_manager.current_turn
            if current is None or not current.is_ai_controlled:
                break
            if not current.is_player:
                break

            agent = active.ai_players.get(current.combatant_id)
            if agent is None:
                logger.warning(
                    "AIPlayerManager: no PlayerAgent registered for AI combatant '%s' — skipping.",
                    current.combatant_id,
                )
                active.turn_manager.next_turn()
                continue

            available_actions = self._available_combat_actions(
                current.combatant_id,
                active.state_data,
            )
            if active.phase.value == "combat" and is_sober_mode():
                action = self._build_deterministic_combat_action(
                    current.combatant_id,
                    current.name,
                    active.state_data,
                    available_actions,
                )
            else:
                # Ask the agent for an action
                await self._publish_thinking(
                    session_id,
                    True,
                    character_id=current.combatant_id,
                    character_name=current.name,
                )
                try:
                    action = await self._get_action(agent, active, available_actions)
                finally:
                    await self._publish_thinking(
                        session_id,
                        False,
                        character_id=current.combatant_id,
                        character_name=current.name,
                    )

            # Les erreurs provider doivent rester visibles. Le JSON invalide,
            # lui, dégrade en attente silencieuse après tentative de réparation.
            if action.llm_error and action.llm_error != _NON_JSON_LLM_ERROR:
                await event_bus.publish_to_session(
                    session_id,
                    EventType.ERROR,
                    {
                        "source": "player_agent",
                        "character": current.name,
                        "message": (
                            f"L'IA de {current.name} n'a pas pu répondre : "
                            f"{action.llm_error}"
                        ),
                    },
                    source="ai_player_manager",
                )

            spell_id: Optional[str] = None
            slot_level: Optional[int] = None
            if active.phase.value == "combat":
                action, spell_id, slot_level = self._normalize_combat_action(
                    action,
                    current.combatant_id,
                    active.state_data,
                    available_actions,
                )

            # Pre-validate before dispatching to the engine
            is_valid, reason = agent.validate_action(action, active.state_data)
            if not is_valid:
                logger.warning(
                    "AIPlayerManager: action '%s' invalid for '%s': %s — using fallback.",
                    action.action_type,
                    current.name,
                    reason,
                )
                if active.phase.value == "combat":
                    if self._character_can_act(current.combatant_id, active.state_data):
                        action = self._build_fallback_combat_action(
                            current.combatant_id,
                            current.name,
                            active.state_data,
                            available_actions,
                        )
                    else:
                        action = _WAIT_ACTION
                    spell_id = None
                    slot_level = None
                else:
                    action = _WAIT_ACTION

            visible_text = self._visible_action_text(action, current.name)

            # Broadcast the AI player's visible intention first
            await event_bus.publish_to_session(
                session_id,
                EventType.NARRATION,
                {
                    "text": visible_text,
                    "speaker": current.name,
                    "action_type": action.action_type,
                    "is_ai_player": True,
                },
                source="ai_player_manager",
            )

            if db is not None and action.action_type in {"talk", "wait"}:
                from app.models.message import MessageRole, MessageType
                from app.services.message_service import persist_narration
                await persist_narration(
                    session_id,
                    visible_text,
                    current.name,
                    db,
                    role=MessageRole.PLAYER,
                    message_type=MessageType.ACTION,
                    metadata={
                        "is_ai_player": True,
                        "character_id": current.combatant_id,
                        "action_type": action.action_type,
                        "target": action.target,
                    },
                )

            # Full engine + GM pipeline for mechanical/arbitrated actions.
            if action.action_type not in {"talk", "wait"}:
                await action_resolver.resolve(
                    session_id=session_id,
                    action_type=action.action_type,
                    content=f"[Compagnon IA] {action.action_description}",
                    character_id=current.combatant_id,
                    target_id=action.target,
                    active=active,
                    db=db,
                    spell_id=spell_id,
                    slot_level=slot_level,
                    actor_kind="companion",
                    actor_name=current.name,
                    display_text=visible_text,
                )

            active.turn_number += 1
            active.mark_dirty()
            triggered += 1

            # Advance to the next combatant for the next iteration
            active.turn_manager.next_turn()
            if max_turns is not None and triggered >= max_turns:
                break

        return triggered

    async def run_exploration_reactions(
        self,
        session_id: str,
        active: "ActiveSession",
        action_resolver: "ActionResolver",
        trigger_character_id: Optional[str] = None,
        db: Optional["AsyncSession"] = None,
    ) -> "tuple[int, list[dict[str, str]]]":
        """Fait réagir une fois chaque compagnon IA en exploration.

        Contrairement à :meth:`process_ai_turns` (pensé pour le combat), cette
        méthode **ne modifie pas l'index** du turn manager : l'exploration reste
        en flux libre. Pour chaque entrée ``is_ai_controlled=True`` de l'ordre,
        on appelle ``agent.roleplay()`` avec l'historique récent puis, selon le
        type d'action :
          - talk / wait : publication + persistance, pas de pipeline MJ.
          - examine / move / use_item / help : pipeline MJ complet.
          - attack / cast_spell / shove : transition COMBAT si pending_encounter,
            sinon remplacement par une hésitation prudente.

        Args:
            session_id: session active.
            active: état mémoire.
            action_resolver: pour faire réagir le MJ après le roleplay IA.
            trigger_character_id: si défini, on saute ce personnage.
            db: session DB async pour charger l'historique et persister les actions.

        Returns:
            Tuple (nombre de compagnons ayant réagi,
                   liste de dicts {"speaker": nom, "text": roleplay_text}).
        """
        if not active.ai_players:
            return 0, []

        # Charger l'historique une seule fois pour tous les compagnons
        recent_messages: list = []
        scene_context = ""
        if db is not None:
            from app.services.message_service import load_recent_messages
            recent_messages = await load_recent_messages(session_id, db)
            scene_context = _build_scene_context(recent_messages)

        visible_game_state = companion_visible_game_state(active.state_data)
        order = list(active.turn_manager._order)
        reacted = 0
        companion_responses: list[dict[str, str]] = []
        seen: set[str] = set()
        iterable = [e.combatant_id for e in order if e.is_ai_controlled]
        if not iterable:
            iterable = list(active.ai_players.keys())

        for char_id in iterable:
            if char_id == trigger_character_id or char_id in seen:
                continue
            seen.add(char_id)
            agent = active.ai_players.get(char_id)
            if agent is None:
                continue

            char_name = getattr(agent, "character_name", char_id)
            await self._publish_thinking(
                session_id, True, character_id=char_id, character_name=char_name,
            )
            try:
                action = await agent.roleplay(
                    game_state=visible_game_state,
                    scene_context=scene_context,
                    messages=recent_messages,
                )
            except Exception as exc:
                logger.error(
                    "run_exploration_reactions: agent '%s' raised exception: %s",
                    char_name, exc,
                )
                action = PlayerActionChoice(
                    action_type="wait",
                    action_description=_WAIT_ACTION.action_description,
                    roleplay_text=_WAIT_ACTION.roleplay_text,
                    llm_error=f"{type(exc).__name__}: {exc}",
                )
            finally:
                await self._publish_thinking(
                    session_id, False, character_id=char_id, character_name=char_name,
                )

            # Provider error → visible event, skip this companion
            if action.llm_error and action.llm_error != _NON_JSON_LLM_ERROR:
                await event_bus.publish_to_session(
                    session_id,
                    EventType.ERROR,
                    {
                        "source": "player_agent",
                        "character": char_name,
                        "message": (
                            f"L'IA de {char_name} n'a pas pu répondre : "
                            f"{action.llm_error}"
                        ),
                    },
                    source="ai_player_manager",
                )
                continue

            # Combat guard BEFORE publishing: only allow combat transition if
            # an encounter is already pending (GM-established), otherwise the
            # companion cannot unilaterally introduce a new threat.
            if (
                active.phase.value == "exploration"
                and action.action_type in _COMBAT_STARTING_ACTIONS
            ):
                if active.state_data.get("pending_encounter"):
                    # Legitimate: publish the aggressive action, flag transition, stop
                    visible_text = self._visible_action_text(action, char_name)
                    await event_bus.publish_to_session(
                        session_id,
                        EventType.NARRATION,
                        {
                            "text": visible_text,
                            "speaker": char_name,
                            "action_type": action.action_type,
                            "is_ai_player": True,
                        },
                        source="ai_player_manager",
                    )
                    active.state_data["pending_phase_transition"] = "COMBAT"
                    active.mark_dirty()
                    reacted += 1
                    break
                else:
                    # No confirmed threat: replace with cautious hesitation
                    action = PlayerActionChoice(
                        action_type="wait",
                        action_description="Le personnage hésite prudemment.",
                        roleplay_text=(
                            "(jette un regard méfiant, la main sur l'arme, mais sans dégainer)"
                        ),
                        inner_reasoning="Pas de menace confirmée par le MJ — attente.",
                    )

            # Publish post-guard roleplay
            visible_text = self._visible_action_text(action, char_name)
            await event_bus.publish_to_session(
                session_id,
                EventType.NARRATION,
                {
                    "text": visible_text,
                    "speaker": char_name,
                    "action_type": action.action_type,
                    "is_ai_player": True,
                },
                source="ai_player_manager",
            )

            # Collecter la réponse pour la conclusion sociale éventuelle
            companion_responses.append({"speaker": char_name, "text": visible_text})

            # Persist locally only for non-pipeline social/passive reactions.
            if db is not None and action.action_type not in _EXPLORATION_ARBITRAGE_ACTIONS:
                from app.models.message import MessageRole, MessageType
                from app.services.message_service import persist_narration
                msg_type = (
                    MessageType.ACTION
                    if action.action_type in _EXPLORATION_ARBITRAGE_ACTIONS
                    else MessageType.DIALOGUE
                )
                await persist_narration(
                    session_id,
                    visible_text,
                    char_name,
                    db,
                    role=MessageRole.PLAYER,
                    message_type=msg_type,
                    metadata={
                        "is_ai_player": True,
                        "character_id": char_id,
                        "action_type": action.action_type,
                    },
                )

            # GM pipeline only for actions requiring world arbitration
            if action.action_type in _EXPLORATION_ARBITRAGE_ACTIONS:
                try:
                    await action_resolver.resolve(
                        session_id=session_id,
                        action_type=action.action_type,
                        content=f"[Compagnon IA] {action.action_description}",
                        character_id=char_id,
                        target_id=action.target,
                        active=active,
                        db=db,
                        actor_kind="companion",
                        actor_name=char_name,
                        display_text=visible_text,
                    )
                except Exception as exc:
                    logger.error(
                        "run_exploration_reactions: action_resolver a échoué pour %s : %s",
                        char_name, exc,
                    )

            reacted += 1

            if active.state_data.get("pending_phase_transition") == "COMBAT":
                break

        return reacted, companion_responses

    async def run_party_reaction_batch(
        self,
        session_id: str,
        active: "ActiveSession",
        player_action: str,
        trigger_character_id: Optional[str] = None,
        db: Optional["AsyncSession"] = None,
    ) -> "tuple[int, list[dict[str, str]]]":
        """Produit les reactions sociales des compagnons en un seul appel LLM."""
        companions = self._party_reaction_targets(active, trigger_character_id)
        if not companions:
            return 0, []

        await self._publish_thinking(session_id, True)
        try:
            raw = await self._call_party_reaction_llm(active, player_action, companions)
            parsed = self._parse_party_reaction(raw)
        except Exception as exc:
            logger.warning("run_party_reaction_batch: fallback sobre apres erreur: %s", exc)
            parsed = []
        finally:
            await self._publish_thinking(session_id, False)

        by_id = {
            str(item.get("character_id") or item.get("id") or ""): item
            for item in parsed
            if isinstance(item, dict)
        }
        responses: list[dict[str, str]] = []
        for companion in companions:
            candidate = by_id.get(companion["id"], {})
            text = str(candidate.get("text") or candidate.get("roleplay_text") or "").strip()
            speaker = str(candidate.get("speaker") or companion["name"])
            if not text:
                text = f"{speaker} acquiesce et garde son attention sur la suite."
            text = sanitize_companion_visible_text(text, character_name=speaker)

            await event_bus.publish_to_session(
                session_id,
                EventType.NARRATION,
                {
                    "text": text,
                    "speaker": speaker,
                    "action_type": "talk",
                    "is_ai_player": True,
                },
                source="ai_player_manager",
            )
            if db is not None:
                from app.models.message import MessageRole, MessageType
                from app.services.message_service import persist_narration

                await persist_narration(
                    session_id,
                    text,
                    speaker,
                    db,
                    role=MessageRole.PLAYER,
                    message_type=MessageType.DIALOGUE,
                    metadata={
                        "is_ai_player": True,
                        "character_id": companion["id"],
                        "action_type": "talk",
                        "llm_budget": "batch_party",
                    },
                )
            responses.append({"speaker": speaker, "text": text})

        return len(responses), responses

    @staticmethod
    def _party_reaction_targets(
        active: "ActiveSession",
        trigger_character_id: Optional[str],
    ) -> list[dict[str, str]]:
        companions: list[dict[str, str]] = []
        for char_id, agent in active.ai_players.items():
            if char_id == trigger_character_id:
                continue
            name = str(getattr(agent, "character_name", char_id))
            personality = getattr(agent, "personality", None)
            traits = getattr(personality, "traits", None)
            companions.append(
                {
                    "id": str(char_id),
                    "name": name,
                    "traits": ", ".join(traits) if isinstance(traits, list) else "",
                }
            )
        return companions

    @staticmethod
    async def _call_party_reaction_llm(
        active: "ActiveSession",
        player_action: str,
        companions: list[dict[str, str]],
    ) -> str:
        from app.llm.model_router import router

        client = router.get_player_client()
        compact_state = {
            "phase": active.phase.value if hasattr(active.phase, "value") else str(active.phase),
            "location": active.state_data.get("adventure_journal", {}),
            "companions": companions,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "Tu ecris les reactions breves de compagnons de JDR. "
                    "Retourne uniquement un JSON valide."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Le joueur sollicite le groupe :\n"
                    f"{player_action}\n\n"
                    "Etat compact :\n"
                    f"{json.dumps(compact_state, ensure_ascii=False)}\n\n"
                    "Retourne ce schema exact :\n"
                    '{"responses":[{"character_id":"id","speaker":"nom",'
                    '"text":"1 phrase en francais"}]}'
                ),
            },
        ]
        token, scope = begin_llm_call_scope(active.session_id, "party_reaction")
        try:
            record_llm_call("party")
            return await client.chat(messages=messages, temperature=0.65, max_tokens=700)
        finally:
            end_llm_call_scope(token, scope)

    @staticmethod
    def _parse_party_reaction(raw: str) -> list[dict[str, Any]]:
        stripped = raw.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
            stripped = re.sub(r"```$", "", stripped).strip()
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            end = stripped.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return []
            try:
                data = json.loads(stripped[start:end + 1])
            except json.JSONDecodeError:
                return []
        responses = data.get("responses", []) if isinstance(data, dict) else []
        return [item for item in responses if isinstance(item, dict)]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _publish_thinking(
        session_id: str,
        thinking: bool,
        *,
        character_id: Optional[str] = None,
        character_name: Optional[str] = None,
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
            source="ai_player_manager",
        )

    @staticmethod
    async def _get_action(
        agent: Any,
        active: "ActiveSession",
        available_actions: Optional[list[str]] = None,
    ) -> PlayerActionChoice:
        """Ask the agent for an action based on the current game phase."""
        from app.models.session import SessionStatus

        try:
            if active.phase == SessionStatus.COMBAT:
                return await agent.decide_action(
                    game_state=active.state_data,
                    available_actions=available_actions,
                )
            else:
                return await agent.roleplay(
                    game_state=companion_visible_game_state(active.state_data)
                )
        except Exception as exc:
            logger.error(
                "AIPlayerManager: agent '%s' raised exception: %s",
                getattr(agent, "character_name", "?"),
                exc,
            )
            return PlayerActionChoice(
                action_type="wait",
                action_description=_WAIT_ACTION.action_description,
                roleplay_text=_WAIT_ACTION.roleplay_text,
                inner_reasoning=_WAIT_ACTION.inner_reasoning,
                llm_error=f"{type(exc).__name__}: {exc}",
            )

    @classmethod
    def _available_combat_actions(
        cls,
        character_id: str,
        state_data: dict[str, Any],
    ) -> list[str]:
        actions = ["attack"]
        if cls._find_unstable_ally(character_id, state_data) is not None:
            actions.append("stabilize")
        if cls._has_castable_spell(character_id, state_data):
            actions.append("cast_spell")
        actions.extend(["dodge", "wait"])
        return actions

    @classmethod
    def _has_castable_spell(cls, character_id: str, state_data: dict[str, Any]) -> bool:
        cdata = cls._character_data(character_id, state_data)
        known_spells = cdata.get("known_spells", [])
        if not isinstance(known_spells, list) or not known_spells:
            return False
        try:
            from app.game.action_resolver import _load_spells
            spells = _load_spells()
        except Exception:
            return False
        for spell_id in known_spells:
            spell = spells.get(str(spell_id))
            if not spell:
                continue
            if int(spell.get("level", 0)) == 0:
                return True
            if cls._slot_level_available(cdata.get("spell_slots", {}), int(spell["level"])):
                return True
        return False

    @classmethod
    def _normalize_combat_action(
        cls,
        action: PlayerActionChoice,
        character_id: str,
        state_data: dict[str, Any],
        available_actions: list[str],
    ) -> tuple[PlayerActionChoice, Optional[str], Optional[int]]:
        if action.action_type not in set(available_actions):
            return (
                cls._build_fallback_combat_action(
                    character_id,
                    cls._character_data(character_id, state_data).get("name", character_id),
                    state_data,
                    available_actions,
                ),
                None,
                None,
            )

        if action.action_type != "cast_spell":
            return action, None, None

        spell_choice = cls._resolve_spell_choice(action, character_id, state_data)
        if spell_choice is None:
            return (
                cls._build_fallback_combat_action(
                    character_id,
                    cls._character_data(character_id, state_data).get("name", character_id),
                    state_data,
                    available_actions,
                ),
                None,
                None,
            )

        spell_id, spell_name, slot_level = spell_choice
        action.params["spell_id"] = spell_id
        action.params["spell_name"] = spell_name
        if action.target is None:
            action.target = cls._select_default_enemy_target(character_id, state_data)
        return action, spell_id, slot_level

    @classmethod
    def _resolve_spell_choice(
        cls,
        action: PlayerActionChoice,
        character_id: str,
        state_data: dict[str, Any],
    ) -> Optional[tuple[str, str, int]]:
        cdata = cls._character_data(character_id, state_data)
        known_spells = cdata.get("known_spells", [])
        if not isinstance(known_spells, list) or not known_spells:
            return None

        raw_spell = (
            action.params.get("spell_id")
            or action.params.get("spell_name")
            or action.action_description
        )
        if not raw_spell:
            return None

        try:
            from app.game.action_resolver import _load_spells
            spells = _load_spells()
        except Exception:
            return None

        wanted = cls._normalize_text(raw_spell)
        known_ids = {str(s) for s in known_spells}
        for spell_id in known_ids:
            spell = spells.get(spell_id)
            if not spell:
                continue
            aliases = [
                spell_id,
                spell.get("name", ""),
                spell.get("name_fr", ""),
            ]
            if not any(
                cls._normalize_text(alias) in wanted
                or wanted in cls._normalize_text(alias)
                for alias in aliases
                if alias
            ):
                continue

            spell_level = int(spell.get("level", 0))
            if spell_level == 0:
                spell_name = str(spell.get("name_fr") or spell.get("name") or spell_id)
                return spell_id, spell_name, 0

            slot_level = cls._choose_slot_level(
                cdata.get("spell_slots", {}),
                spell_level,
                requested=action.params.get("slot_level") or action.params.get("level"),
            )
            if slot_level is None:
                return None
            spell_name = str(spell.get("name_fr") or spell.get("name") or spell_id)
            return spell_id, spell_name, slot_level

        return None

    @classmethod
    def _build_fallback_combat_action(
        cls,
        character_id: str,
        character_name: str,
        state_data: dict[str, Any],
        available_actions: list[str],
    ) -> PlayerActionChoice:
        target = cls._select_default_enemy_target(character_id, state_data)
        target_name = cls._combatant_name(state_data, target)
        if target and "attack" in available_actions:
            return PlayerActionChoice(
                action_type="attack",
                action_description=f"Attaque {target_name}",
                target=target,
                params={},
                roleplay_text=f"{character_name} reprend l'initiative et attaque {target_name}.",
                inner_reasoning="Fallback combat : attaque fiable sur une cible hostile active.",
            )
        if "dodge" in available_actions:
            return PlayerActionChoice(
                action_type="dodge",
                action_description="Se met en défense",
                roleplay_text=f"{character_name} se remet en garde.",
                inner_reasoning="Fallback combat : aucune cible hostile active.",
            )
        return PlayerActionChoice(
            action_type="wait",
            action_description=_WAIT_ACTION.action_description,
            roleplay_text=_WAIT_ACTION.roleplay_text,
            inner_reasoning=_WAIT_ACTION.inner_reasoning,
        )

    @classmethod
    def _build_deterministic_combat_action(
        cls,
        character_id: str,
        character_name: str,
        state_data: dict[str, Any],
        available_actions: list[str],
    ) -> PlayerActionChoice:
        unstable_ally = cls._find_unstable_ally(character_id, state_data)
        if unstable_ally and "stabilize" in available_actions:
            ally_name = cls._combatant_name(state_data, unstable_ally)
            return PlayerActionChoice(
                action_type="stabilize",
                action_description=f"Stabilise {ally_name}",
                target=unstable_ally,
                params={},
                roleplay_text=f"{character_name} se penche vers {ally_name} pour le stabiliser.",
                inner_reasoning="Mode sobre : priorite a la survie d'un allie a 0 PV.",
            )

        return cls._build_fallback_combat_action(
            character_id,
            character_name,
            state_data,
            available_actions,
        )

    @classmethod
    def _find_unstable_ally(
        cls,
        character_id: str,
        state_data: dict[str, Any],
    ) -> Optional[str]:
        combatants = state_data.get("combatants", {})
        if not isinstance(combatants, dict):
            return None

        for cid, cdata in combatants.items():
            if cid == character_id or not isinstance(cdata, dict):
                continue
            if cdata.get("is_player") is not True:
                continue
            if str(cdata.get("status", "active")).lower() in INACTIVE_STATUSES:
                continue
            try:
                hp = int(cdata.get("hp", cdata.get("current_hp", 1)))
            except (TypeError, ValueError):
                hp = 1
            death_saves = cdata.get("death_saves", {})
            if hp == 0 and not death_saves.get("stable") and not cdata.get("dead"):
                return str(cid)
        return None

    @staticmethod
    def _character_data(character_id: str, state_data: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        characters = state_data.get("characters", {})
        if isinstance(characters, dict):
            cdata = characters.get(character_id)
            if isinstance(cdata, dict):
                result.update(cdata)
        combatants = state_data.get("combatants", {})
        if isinstance(combatants, dict):
            cdata = combatants.get(character_id)
            if isinstance(cdata, dict):
                result.setdefault("name", cdata.get("name", character_id))
                result["current_hp"] = cdata.get(
                    "hp",
                    result.get("current_hp", result.get("hp", 1)),
                )
                result.setdefault("hp", result["current_hp"])
                result.setdefault("hp_max", cdata.get("hp_max"))
                result.setdefault("conditions", cdata.get("conditions", []))
                result.setdefault("status", cdata.get("status", "active"))
        return result

    @classmethod
    def _character_can_act(cls, character_id: str, state_data: dict[str, Any]) -> bool:
        cdata = cls._character_data(character_id, state_data)
        if str(cdata.get("status", "active")).lower() in INACTIVE_STATUSES:
            return False
        try:
            hp = int(cdata.get("current_hp", cdata.get("hp", 1)))
        except (TypeError, ValueError):
            hp = 1
        return hp > 0

    @classmethod
    def _visible_action_text(cls, action: PlayerActionChoice, character_name: str) -> str:
        if action.action_type not in _MECHANICAL_ACTION_TYPES:
            return sanitize_companion_visible_text(
                action.roleplay_text,
                character_name=character_name,
            )

        description = str(action.action_description or "").strip()
        if not description:
            return action.roleplay_text

        if description.casefold().startswith(character_name.casefold()):
            text = description
        else:
            text = f"{character_name} {cls._lowercase_initial(description)}"
        if text[-1] not in ".!?…":
            text += "."
        return sanitize_companion_visible_text(text, character_name=character_name)

    @staticmethod
    def _lowercase_initial(text: str) -> str:
        if not text:
            return text
        return text[0].lower() + text[1:]

    @staticmethod
    def _normalize_text(value: Any) -> str:
        normalized = unicodedata.normalize("NFKD", str(value).lower())
        without_accents = "".join(
            ch for ch in normalized if not unicodedata.combining(ch)
        )
        return re.sub(r"[^a-z0-9_]+", " ", without_accents).strip()

    @classmethod
    def _choose_slot_level(
        cls,
        spell_slots: Any,
        minimum_level: int,
        requested: Any = None,
    ) -> Optional[int]:
        if requested is not None:
            try:
                requested_level = max(minimum_level, int(requested))
            except (TypeError, ValueError):
                requested_level = minimum_level
            if cls._slot_level_available(spell_slots, requested_level):
                return requested_level

        for level in range(minimum_level, 10):
            if cls._slot_level_available(spell_slots, level):
                return level
        return None

    @staticmethod
    def _slot_level_available(spell_slots: Any, level: int) -> bool:
        if not isinstance(spell_slots, dict):
            return False
        slot = spell_slots.get(str(level), spell_slots.get(level))
        if isinstance(slot, dict):
            try:
                return int(slot.get("total", 0)) - int(slot.get("used", 0)) > 0
            except (TypeError, ValueError):
                return False
        try:
            return int(slot) > 0
        except (TypeError, ValueError):
            return False

    @classmethod
    def _select_default_enemy_target(
        cls,
        character_id: str,
        state_data: dict[str, Any],
    ) -> Optional[str]:
        combatants = state_data.get("combatants", {})
        if not isinstance(combatants, dict):
            return None
        characters = state_data.get("characters", {})
        character_ids = set(characters) if isinstance(characters, dict) else set()
        candidates: list[tuple[int, str]] = []
        for cid, cdata in combatants.items():
            if cid == character_id or not isinstance(cdata, dict):
                continue
            is_enemy = cdata.get("is_player") is False or (
                cdata.get("is_player") is not True and cid not in character_ids
            )
            if not is_enemy:
                continue
            if str(cdata.get("status", "active")).lower() in INACTIVE_STATUSES:
                continue
            try:
                hp = int(cdata.get("hp", 0))
            except (TypeError, ValueError):
                hp = 0
            if hp <= 0:
                continue
            candidates.append((hp, str(cid)))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates[0][1]

    @staticmethod
    def _combatant_name(state_data: dict[str, Any], target: Optional[str]) -> str:
        if target is None:
            return "la cible"
        combatants = state_data.get("combatants", {})
        if isinstance(combatants, dict):
            cdata = combatants.get(target, {})
            if isinstance(cdata, dict) and cdata.get("name"):
                return str(cdata["name"])
        return target
