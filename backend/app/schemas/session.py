from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.session import SessionStatus

# ---------------------------------------------------------------------------
# Session schemas
# ---------------------------------------------------------------------------


class SessionCreate(BaseModel):
    """Payload pour créer une nouvelle session."""

    name: str = Field(..., min_length=1, max_length=100, description="Nom de la session")


class SessionUpdate(BaseModel):
    """Payload pour mettre à jour une session (champs optionnels)."""

    name: str | None = Field(None, min_length=1, max_length=100)
    status: SessionStatus | None = None


class SessionResponse(BaseModel):
    """Réponse complète d'une session."""

    id: str
    name: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    character_count: int = 0

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    """Liste paginée de sessions."""

    sessions: list[SessionResponse]
    total: int
