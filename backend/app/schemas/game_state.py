from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# GameState schemas
# ---------------------------------------------------------------------------


class GameStateUpdate(BaseModel):
    """Payload pour mettre à jour l'état du jeu."""

    turn_number: int = Field(..., ge=0)
    round_number: int = Field(..., ge=0)
    state_data: dict[str, Any] = Field(default_factory=dict)


class GameStateResponse(BaseModel):
    """Réponse complète de l'état du jeu."""

    id: str
    session_id: str
    turn_number: int
    round_number: int
    state_data: dict[str, Any]
    updated_at: datetime

    model_config = {"from_attributes": True}
