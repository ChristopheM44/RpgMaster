"""Pydantic schemas for SRD 5.2 reference data (monsters and spells).

These schemas validate the JSON files in this package at load-time. They are
permissive (`extra="allow"`) because the underlying data is rich and evolves
faster than the schema — unknown fields are kept on the parsed model rather
than rejected.

The schemas reflect the conventions of D&D 2024 (SRD 5.2.1), with bilingual
naming: each entry carries an English `name` (canonical) plus a `name_fr`
(used by the French-speaking GM agent and UI).
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# --- Shared ---------------------------------------------------------------

Ability = Literal["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]


class AbilityScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int


# --- Monster sub-schemas --------------------------------------------------


class Trait(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    name_fr: str
    description: str


# Action types observed in current data + a few foreseen for incoming imports.
ActionType = Literal[
    "melee_attack",
    "ranged_attack",
    "melee_or_ranged_attack",
    "melee_spell_attack",
    "ranged_spell_attack",
    "multiattack",
    "move",
    "area",
    "save",
    "recharge",
    "spellcasting",
]


class Action(BaseModel):
    """A monster action, multiattack, or legendary action.

    Most fields are optional because the shape varies a lot:
    - `melee_attack` uses attack_bonus + damage_dice + damage_type + reach_m.
    - `multiattack` uses `attacks` (list of action ids).
    - `move` / legendary actions often only have a `description`.
    - `area` actions describe a save-based AoE.
    """

    model_config = ConfigDict(extra="allow")

    name: str
    name_fr: str
    type: ActionType
    description: str | None = None
    # Attack fields
    attack_bonus: int | None = None
    targets: int | None = None
    damage_dice: str | None = None
    damage_type: str | None = None
    versatile_damage_dice: str | None = None
    reach_m: float | None = None
    range_normal_m: float | None = None
    range_long_m: float | None = None
    secondary_effect: dict[str, Any] | None = None
    # Multiattack
    attacks: list[str] | None = None
    # Save-based / area
    save: dict[str, Any] | None = None
    area_shape: str | None = None
    area_size_m: float | None = None


# --- Monster schema -------------------------------------------------------


MonsterSize = Literal["Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"]
MonsterType = Literal[
    "aberration",
    "beast",
    "celestial",
    "construct",
    "dragon",
    "elemental",
    "fey",
    "fiend",
    "giant",
    "humanoid",
    "monstrosity",
    "ooze",
    "plant",
    "undead",
]


class Speed(BaseModel):
    model_config = ConfigDict(extra="allow")

    walk: int | None = None
    climb: int | None = None
    fly: int | None = None
    swim: int | None = None
    burrow: int | None = None


class Senses(BaseModel):
    model_config = ConfigDict(extra="allow")

    passive_perception: int
    darkvision_m: int | None = None
    blindsight_m: int | None = None
    truesight_m: int | None = None
    tremorsense_m: int | None = None


class MonsterSchema(BaseModel):
    """A single monster entry from monsters.json."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    name: str
    name_fr: str
    cr: float
    xp: int
    size: MonsterSize
    type: MonsterType
    subtype: str | None = None
    alignment: str
    ac: int
    ac_source: str | None = None
    hp: int
    hit_dice: str
    speed: Speed
    ability_scores: AbilityScores
    saving_throws: dict[Ability, int] = Field(default_factory=dict)
    skills: dict[str, int] = Field(default_factory=dict)
    damage_immunities: list[str] = Field(default_factory=list)
    damage_resistances: list[str] = Field(default_factory=list)
    damage_vulnerabilities: list[str] = Field(default_factory=list)
    condition_immunities: list[str] = Field(default_factory=list)
    senses: Senses
    languages: list[str] = Field(default_factory=list)
    proficiency_bonus: int
    traits: list[Trait] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    legendary_actions: list[Action] = Field(default_factory=list)
    description: str | None = None
    # Set by the importer when a stat-block could not be fully parsed.
    parse_status: Literal["needs_review", "needs_actions", "needs_mechanics", "needs_en_name"] | None = None


# --- Spell schema ---------------------------------------------------------


SpellSchool = Literal[
    "abjuration",
    "conjuration",
    "divination",
    "enchantment",
    "evocation",
    "illusion",
    "necromancy",
    "transmutation",
]
SpellComponent = Literal["V", "S", "M"]
SpellAttackType = Literal[
    "melee_spell",
    "ranged_spell",
    "area",
    "auto_hit",
]


class SpellSave(BaseModel):
    model_config = ConfigDict(extra="allow")

    ability: Ability
    on_success: str  # "no_damage" | "half_damage" | "negates" | ...
    repeat_save: str | None = None  # "end_of_turn" | "start_of_turn" | ...
    repeat_action: str | None = None


class SpellSchema(BaseModel):
    """A single spell entry from spells.json."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    name: str
    name_fr: str
    level: int = Field(..., ge=0, le=9)
    school: SpellSchool
    casting_time: str
    components: list[SpellComponent]
    duration: str
    concentration: bool
    ritual: bool | None = None
    classes: list[str] = Field(default_factory=list)
    description: str
    # Range
    range_m: int | float | None = None
    # Attack / save / damage
    attack_type: SpellAttackType | None = None
    damage_dice: str | None = None
    damage_type: str | None = None
    save: SpellSave | None = None
    upcast_extra_dice: str | None = None
    upcast_breakpoints: list[int] | None = None
    upcast_extra_targets: int | None = None
    upcast_extra_rays: int | None = None
    upcast_extra_darts: int | None = None
    # Healing
    heal_dice: str | None = None
    heal_bonus: str | None = None
    # Area
    area_shape: str | None = None
    area_size_m: float | None = None
    area_origin: str | None = None
    # Misc effects
    targets: int | None = None
    rays: int | None = None
    darts: int | None = None
    push_m: float | None = None
    teleport_m: float | None = None
    ac_bonus: int | None = None
    bonus_action_attack: bool | None = None
    reaction_trigger: str | None = None
    condition: str | None = None
    # Set by the importer when only the descriptive text could be extracted.
    parse_status: Literal["needs_mechanics", "needs_en_name"] | None = None


__all__ = [
    "AbilityScores",
    "Action",
    "MonsterSchema",
    "Senses",
    "Speed",
    "SpellSave",
    "SpellSchema",
    "Trait",
]
