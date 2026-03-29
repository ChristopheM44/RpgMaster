from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_characters():
    """List all characters."""
    return []


@router.post("/")
async def create_character():
    """Create a new character."""
    return {"message": "Not implemented yet"}


@router.get("/{character_id}")
async def get_character(character_id: str):
    """Get character details."""
    return {"character_id": character_id}
