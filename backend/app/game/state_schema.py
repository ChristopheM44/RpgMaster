"""Partial schema and migration helpers for the JSON game state blob."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.session import SessionStatus

STATE_SCHEMA_VERSION = 1


class CharacterState(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: Optional[str] = None
    hp: Optional[int] = Field(default=None, ge=0)
    hp_max: Optional[int] = Field(default=None, ge=0)
    is_ai: Optional[bool] = None


class CombatantState(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: Optional[str] = None
    hp: Optional[int] = Field(default=None, ge=0)
    hp_max: Optional[int] = Field(default=None, ge=0)
    ac: Optional[int] = Field(default=None, ge=0)
    is_player: Optional[bool] = None
    is_ai: Optional[bool] = None
    status: Optional[str] = None


class TurnManagerState(BaseModel):
    model_config = ConfigDict(extra="allow")


class PendingEncounterState(BaseModel):
    model_config = ConfigDict(extra="allow")

    intro_played: Optional[bool] = None
    intro_text: Optional[str] = None
    monster_ids: list[str] = Field(default_factory=list)


class GameStateData(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: int = STATE_SCHEMA_VERSION
    phase: Optional[str] = None
    characters: dict[str, CharacterState] = Field(default_factory=dict)
    combatants: dict[str, CombatantState] = Field(default_factory=dict)
    turn_manager: Optional[TurnManagerState] = None
    pending_encounter: Optional[PendingEncounterState] = None

    @field_validator("phase")
    @classmethod
    def validate_phase(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        allowed = {status.value for status in SessionStatus}
        if value not in allowed:
            lowered = value.lower()
            if lowered in allowed:
                return lowered
            raise ValueError(f"phase inconnue: {value}")
        return value


def migrate_state_data(raw: Any) -> dict[str, Any]:
    """Return a versioned state dict while preserving unknown game data."""
    if not isinstance(raw, dict):
        raw = {}
    migrated = dict(raw)
    version = int(migrated.get("schema_version") or 0)
    if version < STATE_SCHEMA_VERSION:
        migrated["schema_version"] = STATE_SCHEMA_VERSION
    phase = migrated.get("phase")
    if isinstance(phase, str):
        lowered = phase.lower()
        if lowered in {status.value for status in SessionStatus}:
            migrated["phase"] = lowered
    validate_state_data(migrated)
    return migrated


def validate_state_data(state_data: dict[str, Any]) -> GameStateData:
    """Validate the critical subtrees of state_data and return the parsed model."""
    return GameStateData.model_validate(state_data)
