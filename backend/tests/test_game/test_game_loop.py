"""Tests for game/game_loop.py — state machine transitions."""
from __future__ import annotations

import pytest

from app.game.game_loop import VALID_TRANSITIONS, GameLoop, InvalidTransitionError
from app.models.session import SessionStatus


@pytest.fixture
def loop() -> GameLoop:
    return GameLoop()


# ---------------------------------------------------------------------------
# can_transition
# ---------------------------------------------------------------------------


class TestCanTransition:
    def test_lobby_to_character_creation(self, loop: GameLoop) -> None:
        assert loop.can_transition(SessionStatus.LOBBY, SessionStatus.CHARACTER_CREATION) is True

    def test_lobby_to_exploration_invalid(self, loop: GameLoop) -> None:
        assert loop.can_transition(SessionStatus.LOBBY, SessionStatus.EXPLORATION) is False

    def test_character_creation_to_exploration(self, loop: GameLoop) -> None:
        assert loop.can_transition(
            SessionStatus.CHARACTER_CREATION, SessionStatus.EXPLORATION
        ) is True

    def test_character_creation_back_to_lobby(self, loop: GameLoop) -> None:
        assert loop.can_transition(
            SessionStatus.CHARACTER_CREATION, SessionStatus.LOBBY
        ) is True

    def test_exploration_to_encounter_start(self, loop: GameLoop) -> None:
        assert loop.can_transition(
            SessionStatus.EXPLORATION, SessionStatus.ENCOUNTER_START
        ) is True

    def test_encounter_start_to_combat(self, loop: GameLoop) -> None:
        assert loop.can_transition(
            SessionStatus.ENCOUNTER_START, SessionStatus.COMBAT
        ) is True

    def test_encounter_start_can_deescalate_to_exploration(self, loop: GameLoop) -> None:
        assert loop.can_transition(
            SessionStatus.ENCOUNTER_START, SessionStatus.EXPLORATION
        ) is True

    def test_encounter_start_cannot_skip_to_encounter_end(self, loop: GameLoop) -> None:
        assert loop.can_transition(
            SessionStatus.ENCOUNTER_START, SessionStatus.ENCOUNTER_END
        ) is False

    def test_combat_to_encounter_end(self, loop: GameLoop) -> None:
        assert loop.can_transition(SessionStatus.COMBAT, SessionStatus.ENCOUNTER_END) is True

    def test_combat_cannot_go_back_to_exploration(self, loop: GameLoop) -> None:
        assert loop.can_transition(SessionStatus.COMBAT, SessionStatus.EXPLORATION) is False

    def test_session_end_is_terminal(self, loop: GameLoop) -> None:
        for target in SessionStatus:
            assert loop.can_transition(SessionStatus.SESSION_END, target) is False


# ---------------------------------------------------------------------------
# validate_transition
# ---------------------------------------------------------------------------


class TestValidateTransition:
    def test_valid_transition_does_not_raise(self, loop: GameLoop) -> None:
        loop.validate_transition(SessionStatus.LOBBY, SessionStatus.CHARACTER_CREATION)

    def test_invalid_transition_raises(self, loop: GameLoop) -> None:
        with pytest.raises(InvalidTransitionError) as exc_info:
            loop.validate_transition(SessionStatus.LOBBY, SessionStatus.COMBAT)
        assert "lobby" in str(exc_info.value).lower()
        assert "combat" in str(exc_info.value).lower()

    def test_invalid_transition_error_carries_phases(self, loop: GameLoop) -> None:
        with pytest.raises(InvalidTransitionError) as exc_info:
            loop.validate_transition(SessionStatus.SESSION_END, SessionStatus.LOBBY)
        err = exc_info.value
        assert err.current == SessionStatus.SESSION_END
        assert err.target == SessionStatus.LOBBY


# ---------------------------------------------------------------------------
# get_valid_transitions
# ---------------------------------------------------------------------------


class TestGetValidTransitions:
    def test_lobby_has_one_valid_transition(self, loop: GameLoop) -> None:
        result = loop.get_valid_transitions(SessionStatus.LOBBY)
        assert result == [SessionStatus.CHARACTER_CREATION]

    def test_encounter_end_has_four_valid_transitions(self, loop: GameLoop) -> None:
        result = loop.get_valid_transitions(SessionStatus.ENCOUNTER_END)
        assert len(result) == 4

    def test_session_end_has_no_valid_transitions(self, loop: GameLoop) -> None:
        assert loop.get_valid_transitions(SessionStatus.SESSION_END) == []


# ---------------------------------------------------------------------------
# is_terminal / is_combat_phase
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_session_end_is_terminal(self, loop: GameLoop) -> None:
        assert loop.is_terminal(SessionStatus.SESSION_END) is True

    def test_exploration_is_not_terminal(self, loop: GameLoop) -> None:
        assert loop.is_terminal(SessionStatus.EXPLORATION) is False

    def test_combat_is_combat_phase(self, loop: GameLoop) -> None:
        assert loop.is_combat_phase(SessionStatus.COMBAT) is True

    def test_encounter_start_is_combat_phase(self, loop: GameLoop) -> None:
        assert loop.is_combat_phase(SessionStatus.ENCOUNTER_START) is True

    def test_exploration_is_not_combat_phase(self, loop: GameLoop) -> None:
        assert loop.is_combat_phase(SessionStatus.EXPLORATION) is False


# ---------------------------------------------------------------------------
# VALID_TRANSITIONS completeness
# ---------------------------------------------------------------------------


def test_all_statuses_in_transition_table() -> None:
    """Every SessionStatus must appear as a key in VALID_TRANSITIONS."""
    for status in SessionStatus:
        assert status in VALID_TRANSITIONS, f"Missing transition entry for {status!r}"
