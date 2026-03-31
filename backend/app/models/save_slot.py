from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class SaveSlot(Base):
    """Sauvegarde nommee d'un etat de jeu complet.

    Capture un instantane de l'etat de session, du GameState et de tous
    les personnages, permettant de restaurer la partie a ce point precise.
    """

    __tablename__ = "save_slots"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Snapshot de la phase de session
    phase: Mapped[str] = mapped_column(String(50), nullable=False)

    # Compteurs de progression
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Copie de GameState.state_data au moment de la sauvegarde
    state_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Snapshots de tous les personnages de la session :
    # [{"id": "...", "name": "...", "hp_current": 30, "hp_max": 45,
    #   "ability_scores": {...}, "equipment": [...], "spell_slots": {...},
    #   "conditions": [...], "level": 1, ...}, ...]
    characters_snapshot: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationship
    session: Mapped[Optional[Session]] = relationship(  # noqa: F821
        "Session", back_populates="save_slots"
    )

    def __repr__(self) -> str:
        return (
            f"<SaveSlot id={self.id!r} name={self.name!r} "
            f"session={self.session_id!r} phase={self.phase!r}>"
        )
