from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.game.event_bus import EventType, event_bus
from app.game.turn_manager import CombatantInfo
from app.models.character import Character
from app.models.session import Session, SessionStatus

router = APIRouter()


@router.get("/{session_id}/state")
async def get_game_state(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get current game state."""
    from app.api.ws_game import session_manager

    active = session_manager.get_session(session_id)
    if active:
        return {
            "session_id": session_id,
            "phase": active.phase.value,
            "turn_number": active.turn_number,
            "round_number": active.round_number,
        }

    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"session_id": session_id, "phase": session.status.value}


@router.post("/{session_id}/start")
async def start_game(session_id: str, db: AsyncSession = Depends(get_db)):
    """Start a game session — transition to EXPLORATION and set up participants."""
    from app.api.ws_game import _build_session_state_payload, session_manager

    try:
        active = await session_manager.open_session(session_id, db)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    # Already past character creation — idempotent
    if active.phase not in (SessionStatus.LOBBY, SessionStatus.CHARACTER_CREATION):
        return {
            "status": "already_started",
            "phase": active.phase.value,
            "session_id": session_id,
        }

    # Load characters for this session
    result = await db.execute(
        select(Character).where(Character.session_id == session_id)
    )
    characters = result.scalars().all()

    if not characters:
        raise HTTPException(
            status_code=400,
            detail="Aucun personnage dans cette session. Créez un personnage d'abord.",
        )

    # Force-transition to EXPLORATION (bypasses strict state-machine validation)
    active.phase = SessionStatus.EXPLORATION

    # Set up TurnManager for exploration (round-robin)
    participants = [
        CombatantInfo(
            combatant_id=c.id,
            name=c.name,
            dex_score=int(c.ability_scores.get("dex", 10)),
            is_player=True,
            is_ai_controlled=c.is_ai,
        )
        for c in characters
    ]
    active.turn_manager.setup_exploration(participants)

    # Store character snapshots in state_data for later combat use
    active.state_data["characters"] = {
        c.id: {
            "name": c.name,
            "hp": c.hp_current,
            "hp_max": c.hp_max,
            "is_ai": c.is_ai,
            "dex": int(c.ability_scores.get("dex", 10)),
        }
        for c in characters
    }
    active.mark_dirty()
    await session_manager.save_state(session_id, db)

    # Notify any already-connected WebSocket clients
    await event_bus.publish_to_session(
        session_id,
        EventType.PHASE_CHANGE,
        {"phase": SessionStatus.EXPLORATION.value},
        source="routes_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        _build_session_state_payload(session_id),
        source="routes_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {
            "text": (
                "La partie commence ! Vous vous trouvez au seuil de l'aventure. "
                "Que souhaitez-vous faire ?"
            ),
            "speaker": "Maître du Jeu",
        },
        source="routes_game",
    )

    return {
        "status": "ok",
        "phase": active.phase.value,
        "session_id": session_id,
        "characters": len(characters),
    }
