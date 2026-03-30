from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.message import MessageRole, MessageType

# ---------------------------------------------------------------------------
# Message schemas
# ---------------------------------------------------------------------------


class MessageCreate(BaseModel):
    """Payload pour enregistrer un message dans le log narratif."""

    role: MessageRole
    speaker: str = Field(..., min_length=1, max_length=100)
    message_type: MessageType = MessageType.NARRATION
    content: str = Field(..., min_length=1)
    metadata_: Optional[dict[str, Any]] = Field(None, alias="metadata")

    model_config = {"populate_by_name": True}


class MessageResponse(BaseModel):
    """Réponse complète d'un message."""

    id: str
    session_id: str
    role: MessageRole
    speaker: str
    message_type: MessageType
    content: str
    metadata_: Optional[dict[str, Any]] = Field(None, alias="metadata")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class MessageListResponse(BaseModel):
    """Liste paginée de messages."""

    messages: list[MessageResponse]
    total: int
