from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Character(Base):
    """Personnage joueur (humain ou IA) dans une session."""

    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Qui controle ce personnage
    player_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Identite D&D
    species: Mapped[str] = mapped_column(String(50), nullable=False)
    char_class: Mapped[str] = mapped_column(String(50), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    background: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Caracteristiques (STR, DEX, CON, INT, WIS, CHA)
    # Stockees en JSON : {"str": 15, "dex": 12, "con": 14, "int": 10, "wis": 13, "cha": 8}
    ability_scores: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Points de vie
    hp_current: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hp_max: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hp_temp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Equipement, sorts, conditions (JSON blobs)
    # equipment: [{"id": "longsword", "equipped": true}, ...]
    equipment: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # spell_slots: {"1": {"total": 2, "used": 1}, "2": {...}}
    spell_slots: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # known_spells: ["fire_bolt", "magic_missile", ...]
    known_spells: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # conditions: ["poisoned", "prone"] — noms des conditions actives
    conditions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # proficiencies: {"skills": ["athletics", "stealth"], "weapons": ["martial"], ...}
    proficiencies: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Pour les personnages IA : traits de personnalite
    # {"traits": ["brave", "greedy"], "bonds": "...", "flaws": "..."}
    personality: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # FK session (nullable : un personnage peut exister sans session active)
    session_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    session: Mapped[Optional[Session]] = relationship(  # noqa: F821
        "Session", back_populates="characters"
    )

    def __repr__(self) -> str:
        return (
            f"<Character id={self.id!r} name={self.name!r} "
            f"class={self.char_class!r} level={self.level}>"
        )
