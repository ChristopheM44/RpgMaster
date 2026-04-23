from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.character import Character
from app.models.session import Session
from app.schemas.session import SessionCreate, SessionListResponse, SessionResponse, SessionUpdate

router = APIRouter()


@router.get("/", response_model=SessionListResponse)
async def list_sessions(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Liste toutes les sessions avec pagination."""
    total_result = await db.execute(select(func.count()).select_from(Session))
    total = total_result.scalar_one()

    result = await db.execute(
        select(Session).order_by(Session.updated_at.desc()).offset(skip).limit(limit)
    )
    sessions = result.scalars().all()

    # Batch character count per session (single query)
    session_ids = [s.id for s in sessions]
    counts: dict[str, int] = {}
    if session_ids:
        count_result = await db.execute(
            select(Character.session_id, func.count(Character.id).label("cnt"))
            .where(Character.session_id.in_(session_ids))
            .group_by(Character.session_id)
        )
        counts = {row.session_id: row.cnt for row in count_result}

    responses = [
        SessionResponse(
            id=s.id, name=s.name, status=s.status,
            created_at=s.created_at, updated_at=s.updated_at,
            character_count=counts.get(s.id, 0),
        )
        for s in sessions
    ]
    return SessionListResponse(sessions=responses, total=total)


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Crée une nouvelle session de jeu."""
    session = Session(name=payload.name)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retourne les détails d'une session."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session introuvable")
    count_result = await db.execute(
        select(func.count(Character.id)).where(Character.session_id == session_id)
    )
    return SessionResponse(
        id=session.id, name=session.name, status=session.status,
        created_at=session.created_at, updated_at=session.updated_at,
        character_count=count_result.scalar_one(),
    )


@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    payload: SessionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Met à jour le nom ou le statut d'une session."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session introuvable")

    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(session, field, value)

    await db.commit()
    await db.refresh(session)
    return session


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Supprime une session et toutes ses données associées."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session introuvable")

    await db.delete(session)
    await db.commit()
