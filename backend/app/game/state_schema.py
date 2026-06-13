"""Partial schema and migration helpers for the JSON game state blob."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.session import SessionStatus
from app.schemas.campaign_content import normalize_content_id

STATE_SCHEMA_VERSION = 1


class CharacterState(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    hp: int | None = Field(default=None, ge=0)
    hp_max: int | None = Field(default=None, ge=0)
    level: int | None = Field(default=None, ge=1, le=20)
    xp: int | None = Field(default=None, ge=0)
    gp: int | None = Field(default=None, ge=0)
    sp: int | None = Field(default=None, ge=0)
    cp: int | None = Field(default=None, ge=0)
    pending_asi: bool | None = None
    is_ai: bool | None = None


class CombatantState(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    hp: int | None = Field(default=None, ge=0)
    hp_max: int | None = Field(default=None, ge=0)
    ac: int | None = Field(default=None, ge=0)
    is_player: bool | None = None
    is_ai: bool | None = None
    status: str | None = None


class TurnManagerState(BaseModel):
    model_config = ConfigDict(extra="allow")


class PendingEncounterState(BaseModel):
    model_config = ConfigDict(extra="allow")

    intro_played: bool | None = None
    intro_text: str | None = None
    monster_ids: list[str] = Field(default_factory=list)


class GameStateData(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: int = STATE_SCHEMA_VERSION
    phase: str | None = None
    characters: dict[str, CharacterState] = Field(default_factory=dict)
    combatants: dict[str, CombatantState] = Field(default_factory=dict)
    turn_manager: TurnManagerState | None = None
    pending_encounter: PendingEncounterState | None = None

    @field_validator("phase")
    @classmethod
    def validate_phase(cls, value: str | None) -> str | None:
        if value is None:
            return None
        allowed = {status.value for status in SessionStatus}
        if value not in allowed:
            lowered = value.lower()
            if lowered in allowed:
                return lowered
            raise ValueError(f"phase inconnue: {value}")
        return value


def _normalize_scene_ids(scene: dict[str, Any]) -> None:
    """Sanitize legacy POI/interaction/exit ids in-place to match WS identifier rules."""
    pois = scene.get("pois")
    if isinstance(pois, list):
        for idx, poi in enumerate(pois):
            if not isinstance(poi, dict):
                continue
            poi["id"] = normalize_content_id(poi.get("id")) or f"poi_{idx + 1}"
            interactions = poi.get("interactions")
            if isinstance(interactions, list):
                for j, interaction in enumerate(interactions):
                    if not isinstance(interaction, dict):
                        continue
                    interaction["id"] = (
                        normalize_content_id(interaction.get("id"), max_len=48) or f"custom_{j + 1}"
                    )
    exits = scene.get("exits")
    if isinstance(exits, list):
        for idx, exit_data in enumerate(exits):
            if not isinstance(exit_data, dict):
                continue
            exit_data["id"] = normalize_content_id(exit_data.get("id")) or f"exit_{idx + 1}"


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
    current_scene = migrated.get("current_scene")
    if isinstance(current_scene, dict):
        _normalize_scene_ids(current_scene)
    validate_state_data(migrated)
    return migrated


def validate_state_data(state_data: dict[str, Any]) -> GameStateData:
    """Validate the critical subtrees of state_data and return the parsed model."""
    return GameStateData.model_validate(state_data)
