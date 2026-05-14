from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CampaignCreate(BaseModel):
    name: str
    description: str = ""


class CampaignResponse(BaseModel):
    id: str
    name: str
    description: str
    starting_level: int = 1
    session_ids: list[str]
    current_session_index: int
    character_ids: list[str]
    xp_pool: dict
    created_at: str
    updated_at: str
    tagline: str = ""
    generation_status: str = "empty"
    active_chapter: dict = Field(default_factory=dict)
    progress: dict = Field(default_factory=dict)
    counts: dict = Field(default_factory=dict)

    @classmethod
    def from_orm(cls, c, summary: Optional[dict] = None) -> CampaignResponse:
        summary = summary or {}
        return cls(
            id=c.id,
            name=c.name,
            description=c.description,
            starting_level=int(getattr(c, "starting_level", 1) or 1),
            session_ids=c.session_ids or [],
            current_session_index=c.current_session_index,
            character_ids=c.character_ids or [],
            xp_pool=c.xp_pool or {},
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
            tagline=summary.get("tagline", c.description or ""),
            generation_status=summary.get("generation_status", "empty"),
            active_chapter=summary.get("active_chapter", {}),
            progress=summary.get("progress", {"done": 0, "total": 1}),
            counts=summary.get("counts", {}),
        )


class AttachSessionBody(BaseModel):
    session_id: str


class AdvanceSessionBody(BaseModel):
    new_session_name: str


class CampaignResetResponse(BaseModel):
    campaign: CampaignResponse
    session_id: str
    characters_reset: int
    sessions_removed: int


class AwardXpBody(BaseModel):
    character_id: str
    xp: int


class ImportSourceBody(BaseModel):
    kind: str
    title: Optional[str] = None
    url: Optional[str] = None
    content: Optional[str] = None
    filename: Optional[str] = None


class ForgeDraftBody(BaseModel):
    brief: dict = Field(default_factory=dict)
    options: dict = Field(default_factory=dict)


class ValidateContractBody(BaseModel):
    player_contract: dict = Field(default_factory=dict)


class SynthesizeCanonBody(BaseModel):
    game_state: dict = Field(default_factory=dict)
    recent_messages: list[dict] = Field(default_factory=list)
