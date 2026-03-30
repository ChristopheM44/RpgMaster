from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.character import Character
from app.schemas.character import (
    CharacterCreate,
    CharacterListResponse,
    CharacterResponse,
    CharacterUpdate,
)

router = APIRouter()


@router.get("/", response_model=CharacterListResponse)
async def list_characters(
    skip: int = 0,
    limit: int = 20,
    session_id: Optional[str] = Query(None, description="Filtrer par session"),
    db: AsyncSession = Depends(get_db),
):
    """Liste tous les personnages avec pagination, filtrage optionnel par session."""
    query = select(Character)
    count_query = select(func.count()).select_from(Character)

    if session_id is not None:
        query = query.where(Character.session_id == session_id)
        count_query = count_query.where(Character.session_id == session_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    result = await db.execute(
        query.order_by(Character.created_at.asc()).offset(skip).limit(limit)
    )
    characters = result.scalars().all()

    return CharacterListResponse(characters=list(characters), total=total)


@router.post("/", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
async def create_character(
    payload: CharacterCreate,
    db: AsyncSession = Depends(get_db),
):
    """Crée un nouveau personnage."""
    character = Character(**payload.model_dump())
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(
    character_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retourne les détails d'un personnage."""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if character is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personnage introuvable")
    return character


@router.put("/{character_id}", response_model=CharacterResponse)
async def update_character(
    character_id: str,
    payload: CharacterUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Met à jour un personnage (champs partiels acceptés)."""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if character is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personnage introuvable")

    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(character, field, value)

    await db.commit()
    await db.refresh(character)
    return character


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(
    character_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Supprime un personnage."""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if character is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personnage introuvable")

    await db.delete(character)
    await db.commit()
