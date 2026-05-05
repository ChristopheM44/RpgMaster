"""Active session lifecycle manager.

Keeps an in-memory registry of sessions currently being played and provides
helpers to open, persist, and close them.

Responsibilities:
- Load a session and its game state from the database into memory.
- Expose the associated :class:`~app.game.game_loop.GameLoop` and
  :class:`~app.game.turn_manager.TurnManager` for the hot path (no DB round-trip
  on every action).
- Persist state back to SQLite on demand or on close.
- Validate and apply phase transitions, keeping ``Session.status`` and
  ``GameState.state_data["phase"]`` in sync.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.game.game_loop import GameLoop
from app.game.state_schema import migrate_state_data
from app.game.turn_manager import TurnManager
from app.models.game_state import GameState
from app.models.session import Session, SessionStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ActiveSession
# ---------------------------------------------------------------------------


@dataclass
class ActiveSession:
    """In-memory representation of a running game session.

    Attributes:
        session_id: UUID string of the session.
        phase: Current :class:`SessionStatus` (mirrors ``Session.status``).
        game_loop: Stateless transition validator.
        turn_manager: Stateful turn order tracker.
        state_data: Mutable game state dict. During an active session this is
            the authoritative character/game snapshot; typed ``Character``
            columns are persistence/loading snapshots synchronized at explicit
            service boundaries.
        turn_number: Monotonic counter incremented on every turn.
        round_number: Combat/exploration round counter (reset on new encounter).
        is_dirty: True when ``state_data`` has unsaved changes.
        ai_players: Registry of AI-controlled PlayerAgent instances, keyed by combatant_id.
            Populated by the caller (e.g. ws_game or a test) before combat starts.
    """

    session_id: str
    phase: SessionStatus
    game_loop: GameLoop = field(default_factory=GameLoop)
    turn_manager: TurnManager = field(default_factory=TurnManager)
    state_data: dict[str, Any] = field(default_factory=dict)
    turn_number: int = 0
    round_number: int = 0
    is_dirty: bool = False
    # Maps combatant_id → PlayerAgent for AI-controlled companion players.
    # Type is Any to avoid circular imports; callers should use PlayerAgent instances.
    ai_players: dict[str, Any] = field(default_factory=dict)
    # Intent classifié par le MJ pour la dernière action joueur :
    # 'social' | 'environmental' | 'mixed' | None
    last_gm_intent: Optional[str] = None

    def mark_dirty(self) -> None:
        self.is_dirty = True

    def mark_clean(self) -> None:
        self.is_dirty = False


# ---------------------------------------------------------------------------
# SessionManager
# ---------------------------------------------------------------------------


class SessionManager:
    """Singleton-style registry of active game sessions.

    Typical usage::

        manager = SessionManager()

        # Open (load from DB)
        active = await manager.open_session(session_id, db)

        # Business logic uses active.turn_manager, active.game_loop, etc.

        # Transition phase
        await manager.transition_phase(session_id, SessionStatus.EXPLORATION, db)

        # Persist and remove from memory
        await manager.close_session(session_id, db)
    """

    def __init__(self) -> None:
        self._sessions: dict[str, ActiveSession] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def open_session(self, session_id: str, db: AsyncSession) -> ActiveSession:
        """Load a session from the database and register it as active.

        If the session is already in the in-memory registry it is returned
        as-is (idempotent).

        Raises:
            KeyError: If no session with *session_id* exists in the database.
        """
        if session_id in self._sessions:
            logger.debug("Session %s already active, returning cached instance.", session_id)
            return self._sessions[session_id]

        session = await self._load_session(session_id, db)
        game_state = await self._load_or_create_game_state(session_id, db)

        state_data = migrate_state_data(dict(game_state.state_data or {}))

        active = ActiveSession(
            session_id=session_id,
            phase=session.status,
            state_data=state_data,
            turn_number=game_state.turn_number,
            round_number=game_state.round_number,
        )

        # Restore turn manager from persisted state if available
        turn_data = active.state_data.get("turn_manager")
        if turn_data:
            active.turn_manager.load_dict(turn_data)

        # Restore AI companion agents from state_data["characters"].
        # Without this, after a backend restart / save reload, AI-controlled
        # characters would fall through to the "enemy monster" branch of
        # _handle_ai_turns and stop acting.
        from app.game.ai_player_manager import rebuild_ai_players
        rebuild_ai_players(active)

        self._sessions[session_id] = active
        logger.info("Session %s opened (phase=%s).", session_id, active.phase.value)
        return active

    async def close_session(self, session_id: str, db: AsyncSession) -> None:
        """Persist state and remove the session from the in-memory registry.

        No-op if the session is not currently active.
        """
        if session_id not in self._sessions:
            logger.debug("close_session: session %s not active, nothing to do.", session_id)
            return

        await self.save_state(session_id, db)
        del self._sessions[session_id]
        self._locks.pop(session_id, None)
        logger.info("Session %s closed.", session_id)

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def get_session(self, session_id: str) -> Optional[ActiveSession]:
        """Return the active session or None if it is not open."""
        return self._sessions.get(session_id)

    def is_active(self, session_id: str) -> bool:
        """Return True if the session is currently open in memory."""
        return session_id in self._sessions

    def lock_for_session(self, session_id: str) -> asyncio.Lock:
        """Return the per-session mutation lock."""
        return self._locks.setdefault(session_id, asyncio.Lock())

    @asynccontextmanager
    async def session_lock(self, session_id: str) -> AsyncIterator[None]:
        """Serialize stateful operations for one active session."""
        async with self.lock_for_session(session_id):
            yield

    @property
    def active_session_ids(self) -> list:
        """Return the list of currently active session IDs."""
        return list(self._sessions.keys())

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def save_state(self, session_id: str, db: AsyncSession) -> None:
        """Persist the current in-memory state to the database.

        Writes to both ``sessions.status`` and ``game_states.state_data``.
        Marks the session as clean after a successful save.
        """
        active = self._sessions.get(session_id)
        if active is None:
            logger.warning("save_state called for inactive session %s — skipped.", session_id)
            return

        # Embed TurnManager snapshot into state_data
        active.state_data = migrate_state_data(active.state_data)
        active.state_data["turn_manager"] = active.turn_manager.to_dict()
        active.state_data["phase"] = active.phase.value

        # Update Session.status
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if session is None:
            logger.error("save_state: session %s not found in DB.", session_id)
            return
        session.status = active.phase

        # Update GameState
        result = await db.execute(select(GameState).where(GameState.session_id == session_id))
        game_state = result.scalar_one_or_none()
        if game_state is None:
            game_state = GameState(session_id=session_id)
            db.add(game_state)

        game_state.state_data = active.state_data
        game_state.turn_number = active.turn_number
        game_state.round_number = active.round_number

        await db.commit()
        active.mark_clean()
        logger.debug("Session %s state saved.", session_id)

    # ------------------------------------------------------------------
    # Phase transitions
    # ------------------------------------------------------------------

    async def transition_phase(
        self,
        session_id: str,
        target: SessionStatus,
        db: AsyncSession,
    ) -> ActiveSession:
        """Validate and apply a phase transition for an active session.

        Updates the in-memory phase immediately and persists to the database.

        Args:
            session_id: The session to transition.
            target: The desired next phase.
            db: Async database session.

        Returns:
            The updated :class:`ActiveSession`.

        Raises:
            KeyError: If the session is not currently active.
            :class:`~app.game.game_loop.InvalidTransitionError`: If the transition
                is not allowed by the state machine.
        """
        active = self._sessions.get(session_id)
        if active is None:
            raise KeyError(f"Session '{session_id}' is not active. Call open_session first.")

        active.game_loop.validate_transition(active.phase, target)

        old_phase = active.phase
        active.phase = target
        active.mark_dirty()

        logger.info(
            "Session %s: %s → %s",
            session_id,
            old_phase.value,
            target.value,
        )

        await self.save_state(session_id, db)
        return active

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _load_session(session_id: str, db: AsyncSession) -> Session:
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if session is None:
            raise KeyError(f"Session '{session_id}' not found in database.")
        return session

    @staticmethod
    async def _load_or_create_game_state(session_id: str, db: AsyncSession) -> GameState:
        result = await db.execute(
            select(GameState).where(GameState.session_id == session_id)
        )
        game_state = result.scalar_one_or_none()
        if game_state is None:
            game_state = GameState(session_id=session_id, state_data={})
            db.add(game_state)
            await db.commit()
            await db.refresh(game_state)
        return game_state
