from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/{session_id}/state")
async def get_game_state(session_id: str):
    """Get current game state."""
    return {"session_id": session_id, "phase": "lobby"}


@router.post("/{session_id}/start")
async def start_game(session_id: str):
    """Start a game session."""
    return {"message": "Not implemented yet"}
