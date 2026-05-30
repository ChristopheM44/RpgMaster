from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import settings

_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def _validate_identifier(value: str | None, field_name: str) -> str | None:
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
    content: str | None = None
    target_id: str | None = None
    character_id: str | None = None
    spell_id: str | None = None
    slot_level: int | None = Field(default=None, ge=0, le=9)
    item_id: str | None = None
    gp: int | None = Field(default=None, ge=0)
    sp: int | None = Field(default=None, ge=0)
    cp: int | None = Field(default=None, ge=0)
    mode: str | None = None
    ability: str | None = None
    abilities: list[str] | None = None
    hit_dice_spend: dict[str, int] | None = None
    area_template: dict[str, Any] | None = None
    addressed_to: str | None = None
    audience: str | None = Field(default=None, max_length=32)
    scene_id: str | None = None
    scene_poi_id: str | None = None
    scene_interaction_id: str | None = None
    scene_interaction_intent: str | None = Field(default=None, max_length=32)
    exit_id: str | None = None

    @field_validator("action_type")
    @classmethod
    def validate_action_type(cls, value: str) -> str:
        if not re.fullmatch(r"^[a-z_]{1,64}$", value):
            raise ValueError("action_type doit être un identifiant d'action simple.")
        return value

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str | None) -> str | None:
        if value is not None and len(value) > settings.max_player_action_chars:
            raise ValueError(
                f"content dépasse la limite de {settings.max_player_action_chars} caractères."
            )
        return value

    @field_validator("audience")
    @classmethod
    def validate_audience(cls, value: str | None) -> str | None:
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
        "scene_poi_id",
        "scene_interaction_id",
        "exit_id",
    )
    @classmethod
    def validate_optional_id(cls, value: str | None, info) -> str | None:
        return _validate_identifier(value, info.field_name)

    @field_validator("scene_interaction_intent")
    @classmethod
    def validate_scene_interaction_intent(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in {"approach", "talk", "examine", "listen", "search", "use", "custom"}:
            raise ValueError("scene_interaction_intent invalide.")
        return value

    @field_validator("hit_dice_spend")
    @classmethod
    def validate_hit_dice_spend(
        cls,
        value: dict[str, int] | None,
    ) -> dict[str, int] | None:
        if value is None:
            return None
        if len(value) > 12:
            raise ValueError("hit_dice_spend ne peut pas cibler plus de 12 personnages.")
        for character_id, amount in value.items():
            _validate_identifier(character_id, "hit_dice_spend key")
            if not isinstance(amount, int) or amount < 0 or amount > 20:
                raise ValueError("Chaque dépense de dé de vie doit être entre 0 et 20.")
        return value

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in {"plus_two", "plus_one_two"}:
            raise ValueError("mode ASI invalide.")
        return value

    @field_validator("ability")
    @classmethod
    def validate_ability(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in {"str", "dex", "con", "int", "wis", "cha"}:
            raise ValueError("ability invalide.")
        return value

    @field_validator("abilities")
    @classmethod
    def validate_abilities(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if len(value) > 2:
            raise ValueError("abilities ne peut pas contenir plus de 2 valeurs.")
        allowed = {"str", "dex", "con", "int", "wis", "cha"}
        if any(item not in allowed for item in value):
            raise ValueError("abilities invalide.")
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
    character_id: str | None = None

    @field_validator("character_id")
    @classmethod
    def validate_character_id(cls, value: str | None) -> str | None:
        return _validate_identifier(value, "character_id")
