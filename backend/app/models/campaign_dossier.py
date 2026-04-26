from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class CampaignDossier(Base):
    """Private campaign dossier paired with a public player contract."""

    __tablename__ = "campaign_dossiers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    campaign_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Public, spoiler-free block exposed to players.
    player_contract: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Private GM-only dossier. Never returned by player-facing endpoints.
    gm_dossier: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    played_canon: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    import_sources: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    active_chapter_id: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    generation_status: Mapped[str] = mapped_column(String(20), nullable=False, default="empty")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    campaign: Mapped[Campaign] = relationship(  # noqa: F821
        "Campaign",
        back_populates="dossier",
    )

    def __repr__(self) -> str:
        return (
            f"<CampaignDossier id={self.id!r} campaign_id={self.campaign_id!r} "
            f"status={self.generation_status!r}>"
        )
