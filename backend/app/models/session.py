from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class SessionStatus(str, enum.Enum):
    LOBBY = "lobby"
    CHARACTER_CREATION = "character_creation"
    EXPLORATION = "exploration"
    ENCOUNTER_START = "encounter_start"
    COMBAT = "combat"
    ENCOUNTER_END = "encounter_end"
    REST = "rest"
    LEVEL_UP = "level_up"
    SESSION_END = "session_end"


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), nullable=False, default=SessionStatus.LOBBY
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    characters: Mapped[list[Character]] = relationship(  # noqa: F821
        "Character", back_populates="session", cascade="all, delete-orphan"
    )
    game_state: Mapped[GameState] = relationship(  # noqa: F821
        "GameState", back_populates="session", uselist=False, cascade="all, delete-orphan"
    )
    messages: Mapped[list[Message]] = relationship(  # noqa: F821
        "Message", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Session id={self.id!r} name={self.name!r} status={self.status}>"
