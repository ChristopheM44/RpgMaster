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
            return _WAIT_ACTION
