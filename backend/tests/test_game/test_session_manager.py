"""Tests for game/session_manager.py — active session lifecycle."""
from __future__ import annotations

import pytest
import pytest_asyncio

from app.game.game_loop import InvalidTransitionError
from app.game.session_manager import ActiveSession, SessionManager
from app.models.session import Session, SessionStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def session_in_db(db_session) -> Session:
    """Create a minimal session in the test DB and return it."""
    session = Session(name="Test Session", status=SessionStatus.LOBBY)
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


@pytest.fixture
def manager() -> SessionManager:
    return SessionManager()


# ---------------------------------------------------------------------------
# open_session
# ---------------------------------------------------------------------------


class TestOpenSession:
    async def test_open_returns_active_session(
        self, manager, session_in_db, db_session
    ) -> None:
        active = await manager.open_session(session_in_db.id, db_session)
        assert isinstance(active, ActiveSession)
        assert active.session_id == session_in_db.id
        assert active.phase == SessionStatus.LOBBY

    async def test_open_registers_session(
        self, manager, session_in_db, db_session
    ) -> None:
        await manager.open_session(session_in_db.id, db_session)
        assert manager.is_active(session_in_db.id)

    async def test_open_twice_is_idempotent(
        self, manager, session_in_db, db_session
    ) -> None:
        active1 = await manager.open_session(session_in_db.id, db_session)
        active2 = await manager.open_session(session_in_db.id, db_session)
        assert active1 is active2  # same object, not re-loaded

    async def test_open_unknown_session_raises(self, manager, db_session) -> None:
        with pytest.raises(KeyError):
            await manager.open_session("non-existent-id", db_session)


# ---------------------------------------------------------------------------
# get_session / is_active
# ---------------------------------------------------------------------------


class TestGetSession:
    async def test_get_active_session(
        self, manager, session_in_db, db_session
    ) -> None:
        await manager.open_session(session_in_db.id, db_session)
        active = manager.get_session(session_in_db.id)
        assert active is not None
        assert active.session_id == session_in_db.id

    def test_get_inactive_session_returns_none(self, manager) -> None:
        assert manager.get_session("unknown") is None

    async def test_active_session_ids(
        self, manager, session_in_db, db_session
    ) -> None:
        await manager.open_session(session_in_db.id, db_session)
        assert session_in_db.id in manager.active_session_ids


# ---------------------------------------------------------------------------
# transition_phase
# ---------------------------------------------------------------------------


class TestTransitionPhase:
    async def test_valid_transition(
        self, manager, session_in_db, db_session
    ) -> None:
        await manager.open_session(session_in_db.id, db_session)
        active = await manager.transition_phase(
            session_in_db.id, SessionStatus.CHARACTER_CREATION, db_session
        )
        assert active.phase == SessionStatus.CHARACTER_CREATION

    async def test_invalid_transition_raises(
        self, manager, session_in_db, db_session
    ) -> None:
        await manager.open_session(session_in_db.id, db_session)
        with pytest.raises(InvalidTransitionError):
            await manager.transition_phase(
                session_in_db.id, SessionStatus.COMBAT, db_session
            )

    async def test_transition_inactive_session_raises(
        self, manager, db_session
    ) -> None:
        with pytest.raises(KeyError):
            await manager.transition_phase("unknown", SessionStatus.LOBBY, db_session)

    async def test_transition_persists_to_db(
        self, manager, session_in_db, db_session
    ) -> None:
        await manager.open_session(session_in_db.id, db_session)
        await manager.transition_phase(
            session_in_db.id, SessionStatus.CHARACTER_CREATION, db_session
        )
        await db_session.refresh(session_in_db)
        assert session_in_db.status == SessionStatus.CHARACTER_CREATION


# ---------------------------------------------------------------------------
# save_state
# ---------------------------------------------------------------------------


class TestSaveState:
    async def test_save_marks_clean(
        self, manager, session_in_db, db_session
    ) -> None:
        active = await manager.open_session(session_in_db.id, db_session)
        active.mark_dirty()
        assert active.is_dirty is True
        await manager.save_state(session_in_db.id, db_session)
        assert active.is_dirty is False

    async def test_save_inactive_session_is_noop(
        self, manager, db_session
    ) -> None:
        # Should not raise
        await manager.save_state("unknown", db_session)


# ---------------------------------------------------------------------------
# close_session
# ---------------------------------------------------------------------------


class TestCloseSession:
    async def test_close_removes_from_registry(
        self, manager, session_in_db, db_session
    ) -> None:
        await manager.open_session(session_in_db.id, db_session)
        await manager.close_session(session_in_db.id, db_session)
        assert not manager.is_active(session_in_db.id)

    async def test_close_inactive_is_noop(self, manager, db_session) -> None:
        # Should not raise
        await manager.close_session("unknown", db_session)
