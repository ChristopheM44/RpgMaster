from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class GameState(Base):
    """Etat complet du jeu pour une session (blob JSON authoratif).

    Relation one-to-one avec Session.
    Contient tout ce qui est necessaire pour reprendre une partie :
    positions, initiative, etat des PNJs, phase courante, etc.
    """

    __tablename__ = "game_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Compteurs de progression
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Blob JSON de l'etat complet :
    # {
    #   "phase": "combat",
    #   "initiative_order": [{"character_id": "...", "roll": 18}, ...],
    #   "current_turn_index": 0,
    #   "npcs": [{"id": "goblin_1", "hp": 3, "conditions": [], ...}],
    #   "environment": {"location": "Foret sombre", "description": "..."},
    #   "context_summary": "Les aventuriers ont trouve une caverne...",
    #   "pending_effects": [],
    # }
    state_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationship
    session: Mapped[Session] = relationship(  # noqa: F821
        "Session", back_populates="game_state"
    )

    def __repr__(self) -> str:
        return (
            f"<GameState session_id={self.session_id!r} "
            f"turn={self.turn_number} round={self.round_number}>"
        )
