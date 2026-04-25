"""AI player manager — triggers PlayerAgent actions during AI combatant turns.

Integrates with TurnManager: when the current turn belongs to an AI-controlled
combatant, this module calls PlayerAgent.decide_action() (or .roleplay()),
validates the result, and dispatches it through ActionResolver.

Usage::

    from app.game.ai_player_manager import AIPlayerManager

    ai_manager = AIPlayerManager()

    # After a human action resolves, trigger any consecutive AI turns:
    triggered = await ai_manager.process_ai_turns(session_id, active, action_resolver)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from app.agents.schemas import PlayerActionChoice
from app.game.event_bus import EventType, event_bus

if TYPE_CHECKING:
    from app.game.action_resolver import ActionResolver
    from app.game.session_manager import ActiveSession

logger = logging.getLogger(__name__)

_WAIT_ACTION = PlayerActionChoice(
    action_type="wait",
    action_description="Le personnage attend son tour.",
    roleplay_text="(attend, sur la défensive)",
    inner_reasoning="Fallback : aucune action valide disponible.",
)


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
    consecutive AI-controlled combatants act before the next human turn.

    The method stops as soon as a non-AI combatant's turn is reached (or the
    order is exhausted), so it is safe to call unconditionally.
    """

    async def process_ai_turns(
        self,
        session_id: str,
        active: "ActiveSession",
        action_resolver: "ActionResolver",
    ) -> int:
        """Trigger all consecutive AI-controlled turns starting from the current entry.

        Args:
            session_id: Active session identifier (for event publishing).
            active: In-memory session state (provides turn_manager and ai_players).
            action_resolver: Pipeline that resolves actions through engine + GM agent.

        Returns:
            The number of AI actions triggered this call.
        """
        triggered = 0

        while True:
            current = active.turn_manager.current_turn
            if current is None or not current.is_ai_controlled:
                break

            agent = active.ai_players.get(current.combatant_id)
            if agent is None:
                logger.warning(
                    "AIPlayerManager: no PlayerAgent registered for AI combatant '%s' — skipping.",
                    current.combatant_id,
                )
                active.turn_manager.next_turn()
                continue

            # Ask the agent for an action
            action = await self._get_action(agent, active)

            # Si l'agent a remonté un échec LLM (provider injoignable, JSON
            # invalide…), le signaler explicitement à l'utilisateur au lieu
            # de laisser le personnage « attendre » en silence.
            if action.llm_error:
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

            # Pre-validate before dispatching to the engine
            is_valid, reason = agent.validate_action(action, active.state_data)
            if not is_valid:
                logger.warning(
                    "AIPlayerManager: action '%s' invalid for '%s': %s — using wait.",
                    action.action_type,
                    current.name,
                    reason,
                )
                action = _WAIT_ACTION

            # Broadcast the AI player's in-character text first
            await event_bus.publish_to_session(
                session_id,
                EventType.NARRATION,
                {
                    "text": action.roleplay_text,
                    "speaker": current.name,
                    "action_type": action.action_type,
                    "is_ai_player": True,
                },
                source="ai_player_manager",
            )

            # Full engine + GM pipeline
            await action_resolver.resolve(
                session_id=session_id,
                action_type=action.action_type,
                content=f"[Compagnon IA] {action.action_description}",
                character_id=current.combatant_id,
                target_id=action.target,
                active=active,
            )

            active.turn_number += 1
            active.mark_dirty()
            triggered += 1

            # Advance to the next combatant for the next iteration
            active.turn_manager.next_turn()

        return triggered

    async def run_exploration_reactions(
        self,
        session_id: str,
        active: "ActiveSession",
        action_resolver: "ActionResolver",
        trigger_character_id: Optional[str] = None,
    ) -> int:
        """Fait réagir une fois chaque compagnon IA en exploration.

        Contrairement à :meth:`process_ai_turns` (pensé pour le combat), cette
        méthode **ne modifie pas l'index** du turn manager : l'exploration reste
        en flux libre. Pour chaque entrée ``is_ai_controlled=True`` de l'ordre,
        on appelle ``agent.roleplay()`` puis on laisse le MJ réagir via
        ``action_resolver.resolve()``.

        Args:
            session_id: session active.
            active: état mémoire.
            action_resolver: pour faire réagir le MJ après le roleplay IA.
            trigger_character_id: si défini, on saute ce personnage (c'est le
                personnage qui vient d'agir — il ne doit pas se répondre à
                lui-même).

        Returns:
            Nombre de compagnons IA qui ont réagi.
        """
        if not active.ai_players:
            return 0

        order = list(active.turn_manager._order)
        if not order:
            # Pas de turn_manager initialisé : on réagit dans l'ordre des
            # ai_players (dict insertion order = ordre de création).
            order = []

        reacted = 0
        seen: set[str] = set()
        iterable = [e.combatant_id for e in order if e.is_ai_controlled]
        # Fallback si l'ordre n'est pas configuré
        if not iterable:
            iterable = list(active.ai_players.keys())

        for char_id in iterable:
            if char_id == trigger_character_id or char_id in seen:
                continue
            seen.add(char_id)
            agent = active.ai_players.get(char_id)
            if agent is None:
                continue

            action = await self._get_action(agent, active)
            char_name = getattr(agent, "character_name", char_id)

            if action.llm_error:
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

            # Publier le roleplay
            await event_bus.publish_to_session(
                session_id,
                EventType.NARRATION,
                {
                    "text": action.roleplay_text,
                    "speaker": char_name,
                    "action_type": action.action_type,
                    "is_ai_player": True,
                },
                source="ai_player_manager",
            )

            # Laisser le MJ réagir à l'intervention du compagnon
            try:
                await action_resolver.resolve(
                    session_id=session_id,
                    action_type="free_action",
                    content=f"[Compagnon IA] {action.roleplay_text}",
                    character_id=char_id,
                    target_id=action.target,
                    active=active,
                )
            except Exception as exc:
                logger.error(
                    "run_exploration_reactions: action_resolver a échoué "
                    "pour %s : %s",
                    char_name,
                    exc,
                )

            reacted += 1

        return reacted

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_action(
        agent: Any,
        active: "ActiveSession",
    ) -> PlayerActionChoice:
        """Ask the agent for an action based on the current game phase."""
        from app.models.session import SessionStatus

        try:
            if active.phase == SessionStatus.COMBAT:
                return await agent.decide_action(game_state=active.state_data)
            else:
                return await agent.roleplay(game_state=active.state_data)
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
