from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_sessions():
    """List all game sessions."""
    return []


@router.post("/")
async def create_session():
    """Create a new game session."""
    return {"message": "Not implemented yet"}


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    return {"session_id": session_id}
