"""Game state machine — manages valid phase transitions.

Defines which transitions between SessionStatus phases are allowed and
provides helpers to validate and query them.

Pure logic: no I/O, no async, no database access.
"""
from __future__ import annotations

from typing import Dict, FrozenSet, List

from app.models.session import SessionStatus

# ---------------------------------------------------------------------------
# Transition table
# ---------------------------------------------------------------------------

#: Maps each phase to the set of phases it is allowed to transition to.
VALID_TRANSITIONS: Dict[SessionStatus, FrozenSet[SessionStatus]] = {
    SessionStatus.LOBBY: frozenset(
        [SessionStatus.CHARACTER_CREATION]
    ),
    SessionStatus.CHARACTER_CREATION: frozenset(
        [SessionStatus.EXPLORATION, SessionStatus.LOBBY]
    ),
    SessionStatus.EXPLORATION: frozenset(
        [SessionStatus.ENCOUNTER_START, SessionStatus.REST, SessionStatus.SESSION_END]
    ),
    SessionStatus.ENCOUNTER_START: frozenset(
        [SessionStatus.COMBAT]
    ),
    SessionStatus.COMBAT: frozenset(
        [SessionStatus.ENCOUNTER_END]
    ),
    SessionStatus.ENCOUNTER_END: frozenset(
        [
            SessionStatus.EXPLORATION,
            SessionStatus.REST,
            SessionStatus.LEVEL_UP,
            SessionStatus.SESSION_END,
        ]
    ),
    SessionStatus.REST: frozenset(
        [SessionStatus.EXPLORATION, SessionStatus.LEVEL_UP, SessionStatus.SESSION_END]
    ),
    SessionStatus.LEVEL_UP: frozenset(
        [SessionStatus.EXPLORATION, SessionStatus.SESSION_END]
    ),
    SessionStatus.SESSION_END: frozenset(),  # terminal state
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class InvalidTransitionError(Exception):
    """Raised when a requested phase transition is not allowed."""

    def __init__(self, current: SessionStatus, target: SessionStatus) -> None:
        valid = ", ".join(s.value for s in VALID_TRANSITIONS.get(current, frozenset()))
        super().__init__(
            f"Cannot transition from '{current.value}' to '{target.value}'. "
            f"Valid targets: [{valid or 'none'}]."
        )
        self.current = current
        self.target = target


# ---------------------------------------------------------------------------
# GameLoop
# ---------------------------------------------------------------------------


class GameLoop:
    """State machine for game phase management.

    Stateless helper — it validates transitions but does NOT hold the current
    phase itself.  The authoritative phase lives in ``Session.status`` (DB).

    Usage::

        loop = GameLoop()
        loop.validate_transition(SessionStatus.LOBBY, SessionStatus.CHARACTER_CREATION)
        # raises InvalidTransitionError if not allowed
    """

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def can_transition(self, current: SessionStatus, target: SessionStatus) -> bool:
        """Return True if the transition from *current* to *target* is allowed."""
        return target in VALID_TRANSITIONS.get(current, frozenset())

    def get_valid_transitions(self, phase: SessionStatus) -> List[SessionStatus]:
        """Return the list of valid next phases from *phase*."""
        return list(VALID_TRANSITIONS.get(phase, frozenset()))

    def is_terminal(self, phase: SessionStatus) -> bool:
        """Return True if *phase* has no valid outgoing transitions."""
        return not VALID_TRANSITIONS.get(phase)

    def is_combat_phase(self, phase: SessionStatus) -> bool:
        """Return True if the phase is part of the combat arc."""
        return phase in (
            SessionStatus.ENCOUNTER_START,
            SessionStatus.COMBAT,
            SessionStatus.ENCOUNTER_END,
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_transition(self, current: SessionStatus, target: SessionStatus) -> None:
        """Raise :class:`InvalidTransitionError` if the transition is not allowed."""
        if not self.can_transition(current, target):
            raise InvalidTransitionError(current, target)
