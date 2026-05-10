from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import settings

_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def _validate_identifier(value: Optional[str], field_name: str) -> Optional[str]:
    if value is None:
        return None
    if not _ID_RE.fullmatch(value):
        raise ValueError(f"{field_name} doit contenir 1 à 128 caractères sûrs.")
    return value


class WsBaseMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JoinMessage(WsBaseMessage):
    type: Literal["join"]
    character_id: str

    @field_validator("character_id")
    @classmethod
    def validate_character_id(cls, value: str) -> str:
        return _validate_identifier(value, "character_id") or value


class PlayerActionMessage(WsBaseMessage):
    type: Literal["action"]
    action_type: str = Field(min_length=1, max_length=64)
    content: Optional[str] = None
    target_id: Optional[str] = None
    character_id: Optional[str] = None
    spell_id: Optional[str] = None
    slot_level: Optional[int] = Field(default=None, ge=0, le=9)
    item_id: Optional[str] = None
    hit_dice_spend: Optional[dict[str, int]] = None
    area_template: Optional[dict[str, Any]] = None
    addressed_to: Optional[str] = None
    audience: Optional[str] = Field(default=None, max_length=32)
    scene_id: Optional[str] = None

    @field_validator("action_type")
    @classmethod
    def validate_action_type(cls, value: str) -> str:
        if not re.fullmatch(r"^[a-z_]{1,64}$", value):
            raise ValueError("action_type doit être un identifiant d'action simple.")
        return value

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and len(value) > settings.max_player_action_chars:
            raise ValueError(
                f"content dépasse la limite de {settings.max_player_action_chars} caractères."
            )
        return value

    @field_validator("audience")
    @classmethod
    def validate_audience(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if value not in {"gm", "world", "party", "companion", "mixed"}:
            raise ValueError("audience invalide.")
        return value

    @field_validator(
        "target_id",
        "character_id",
        "spell_id",
        "item_id",
        "addressed_to",
        "scene_id",
    )
    @classmethod
    def validate_optional_id(cls, value: Optional[str], info) -> Optional[str]:
        return _validate_identifier(value, info.field_name)

    @field_validator("hit_dice_spend")
    @classmethod
    def validate_hit_dice_spend(
        cls,
        value: Optional[dict[str, int]],
    ) -> Optional[dict[str, int]]:
        if value is None:
            return None
        if len(value) > 12:
            raise ValueError("hit_dice_spend ne peut pas cibler plus de 12 personnages.")
        for character_id, amount in value.items():
            _validate_identifier(character_id, "hit_dice_spend key")
            if not isinstance(amount, int) or amount < 0 or amount > 20:
                raise ValueError("Chaque dépense de dé de vie doit être entre 0 et 20.")
        return value


class PingMessage(WsBaseMessage):
    type: Literal["ping"]


class ToggleAiControlMessage(WsBaseMessage):
    type: Literal["toggle_ai_control"]
    character_id: str
    is_ai: bool = False

    @field_validator("character_id")
    @classmethod
    def validate_character_id(cls, value: str) -> str:
        return _validate_identifier(value, "character_id") or value


class TriggerAiReactionsMessage(WsBaseMessage):
    type: Literal["trigger_ai_reactions"]
    character_id: Optional[str] = None

    @field_validator("character_id")
    @classmethod
    def validate_character_id(cls, value: Optional[str]) -> Optional[str]:
        return _validate_identifier(value, "character_id")
