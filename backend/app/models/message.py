from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class MessageRole(str, enum.Enum):
    GM = "gm"
    PLAYER = "player"
    SYSTEM = "system"


class MessageType(str, enum.Enum):
    NARRATION = "narration"
    DIALOGUE = "dialogue"
    ACTION = "action"
    ROLL_RESULT = "roll_result"
    SYSTEM = "system"


class Message(Base):
    """Message du log narratif d'une session.

    Chaque entree dans le journal de partie : narration du MJ,
    dialogue de PNJ, action de joueur, resultat de jet de des, etc.
    """

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Qui parle et dans quel role
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    # Nom affiché : "Maitre du Jeu", "Thorin", "Système", nom du joueur, etc.
    speaker: Mapped[str] = mapped_column(String(100), nullable=False)
    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType), nullable=False, default=MessageType.NARRATION
    )

    # Contenu textuel du message
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Donnees supplementaires (resultats de jets, cibles, etc.)
    # Pour ROLL_RESULT : {"dice": "2d6+3", "rolls": [4, 5], "total": 12, "success": true}
    # Pour ACTION : {"action_type": "attack", "target": "goblin_1"}
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationship
    session: Mapped[Session] = relationship(  # noqa: F821
        "Session", back_populates="messages"
    )

    def __repr__(self) -> str:
        preview = self.content[:40] + "..." if len(self.content) > 40 else self.content
        return f"<Message id={self.id!r} role={self.role} speaker={self.speaker!r} {preview!r}>"
