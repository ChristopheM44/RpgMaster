from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Campaign(Base):
    """Une campagne groupe plusieurs sessions D&D avec progression persistante.

    Les personnages survivants progressent (XP, niveau, équipement)
    d'une session à l'autre.
    """

    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    # Ordered list of session IDs  [session_id_1, session_id_2, ...]
    session_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Index of the current active session (0-based)
    current_session_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Character IDs that persist across sessions (the party)
    character_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # XP totals per character: {"char_id": xp_total}
    xp_pool: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        n = len(self.session_ids)
        return (
            f"<Campaign id={self.id!r} name={self.name!r} "
            f"sessions={n} current={self.current_session_index}>"
        )
