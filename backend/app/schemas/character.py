from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, computed_field

from app.engine.xp import xp_to_next_level

# ---------------------------------------------------------------------------
# Sous-schémas réutilisables
# ---------------------------------------------------------------------------


class AbilityScores(BaseModel):
    """Les 6 caractéristiques D&D."""

    str_: int = Field(..., alias="str", ge=1, le=30)
    dex: int = Field(..., ge=1, le=30)
    con: int = Field(..., ge=1, le=30)
    int_: int = Field(..., alias="int", ge=1, le=30)
    wis: int = Field(..., ge=1, le=30)
    cha: int = Field(..., ge=1, le=30)

    model_config = {"populate_by_name": True}


class SpellSlotLevel(BaseModel):
    """Emplacements de sorts pour un niveau donné."""

    total: int = Field(..., ge=0)
    used: int = Field(..., ge=0)


class HitDiceState(BaseModel):
    """Dés de vie disponibles pour les repos courts."""

    die: int = Field(..., ge=4)
    total: int = Field(..., ge=0)
    used: int = Field(..., ge=0)


# ---------------------------------------------------------------------------
# Character schemas
# ---------------------------------------------------------------------------


class CharacterCreate(BaseModel):
    """Payload pour créer un personnage."""

    name: str = Field(..., min_length=1, max_length=100)
    player_name: Optional[str] = Field(None, max_length=100)
    is_ai: bool = False

    species: str = Field(..., max_length=50)
    char_class: str = Field(..., max_length=50)
    level: int = Field(1, ge=1, le=20)
    background: Optional[str] = Field(None, max_length=50)

    ability_scores: dict[str, int] = Field(
        default_factory=lambda: {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
    )
    hp_current: int = Field(0, ge=0)
    hp_max: int = Field(0, ge=0)
    hp_temp: int = Field(0, ge=0)
    xp: int = Field(0, ge=0)
    gp: int = Field(0, ge=0)
    sp: int = Field(0, ge=0)
    cp: int = Field(0, ge=0)

    equipment: list[dict[str, Any]] = Field(default_factory=list)
    spell_slots: dict[str, SpellSlotLevel] = Field(default_factory=dict)
    hit_dice: Union[HitDiceState, dict[str, Any]] = Field(default_factory=dict)  # noqa: UP007
    known_spells: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    proficiencies: dict[str, Any] = Field(default_factory=dict)
    personality: dict[str, Any] = Field(default_factory=dict)

    session_id: Optional[str] = None


class CharacterUpdate(BaseModel):
    """Payload pour mettre à jour un personnage (champs optionnels)."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    player_name: Optional[str] = Field(None, max_length=100)
    is_ai: Optional[bool] = None
    level: Optional[int] = Field(None, ge=1, le=20)
    background: Optional[str] = Field(None, max_length=50)

    ability_scores: Optional[dict[str, int]] = None
    hp_current: Optional[int] = Field(None, ge=0)
    hp_max: Optional[int] = Field(None, ge=0)
    hp_temp: Optional[int] = Field(None, ge=0)
    xp: Optional[int] = Field(None, ge=0)
    gp: Optional[int] = Field(None, ge=0)
    sp: Optional[int] = Field(None, ge=0)
    cp: Optional[int] = Field(None, ge=0)

    equipment: Optional[list[dict[str, Any]]] = None
    spell_slots: Optional[dict[str, SpellSlotLevel]] = None
    hit_dice: Optional[Union[HitDiceState, dict[str, Any]]] = None  # noqa: UP007
    known_spells: Optional[list[str]] = None
    conditions: Optional[list[str]] = None
    proficiencies: Optional[dict[str, Any]] = None
    personality: Optional[dict[str, Any]] = None

    session_id: Optional[str] = None


class CharacterResponse(BaseModel):
    """Réponse complète d'un personnage."""

    id: str
    name: str
    player_name: Optional[str]
    is_ai: bool

    species: str
    char_class: str
    level: int
    background: Optional[str]

    ability_scores: dict[str, int]
    hp_current: int
    hp_max: int
    hp_temp: int
    xp: int = 0
    gp: int = 0
    sp: int = 0
    cp: int = 0

    equipment: list[dict[str, Any]]
    spell_slots: dict[str, Any]
    hit_dice: dict[str, Any]
    known_spells: list[str]
    conditions: list[str]
    proficiencies: dict[str, Any]
    personality: dict[str, Any]

    session_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def xp_to_next_level(self) -> int:
        return xp_to_next_level(self.xp, self.level)

    @computed_field
    @property
    def pending_asi(self) -> bool:
        return bool((self.personality or {}).get("pending_asi", False))


class CharacterListResponse(BaseModel):
    """Liste paginée de personnages."""

    characters: list[CharacterResponse]
    total: int
