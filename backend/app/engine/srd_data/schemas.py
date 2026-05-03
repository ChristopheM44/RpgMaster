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

from typing import Any, Dict, List, Literal, Optional, Union

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
    description: Optional[str] = None
    # Attack fields
    attack_bonus: Optional[int] = None
    targets: Optional[int] = None
    damage_dice: Optional[str] = None
    damage_type: Optional[str] = None
    versatile_damage_dice: Optional[str] = None
    reach_m: Optional[float] = None
    range_normal_m: Optional[float] = None
    range_long_m: Optional[float] = None
    secondary_effect: Optional[Dict[str, Any]] = None
    # Multiattack
    attacks: Optional[List[str]] = None
    # Save-based / area
    save: Optional[Dict[str, Any]] = None
    area_shape: Optional[str] = None
    area_size_m: Optional[float] = None


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

    walk: Optional[int] = None
    climb: Optional[int] = None
    fly: Optional[int] = None
    swim: Optional[int] = None
    burrow: Optional[int] = None


class Senses(BaseModel):
    model_config = ConfigDict(extra="allow")

    passive_perception: int
    darkvision_m: Optional[int] = None
    blindsight_m: Optional[int] = None
    truesight_m: Optional[int] = None
    tremorsense_m: Optional[int] = None


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
    subtype: Optional[str] = None
    alignment: str
    ac: int
    ac_source: Optional[str] = None
    hp: int
    hit_dice: str
    speed: Speed
    ability_scores: AbilityScores
    saving_throws: Dict[Ability, int] = Field(default_factory=dict)
    skills: Dict[str, int] = Field(default_factory=dict)
    damage_immunities: List[str] = Field(default_factory=list)
    damage_resistances: List[str] = Field(default_factory=list)
    damage_vulnerabilities: List[str] = Field(default_factory=list)
    condition_immunities: List[str] = Field(default_factory=list)
    senses: Senses
    languages: List[str] = Field(default_factory=list)
    proficiency_bonus: int
    traits: List[Trait] = Field(default_factory=list)
    actions: List[Action] = Field(default_factory=list)
    legendary_actions: List[Action] = Field(default_factory=list)
    description: Optional[str] = None
    # Set by the importer when a stat-block could not be fully parsed.
    parse_status: Optional[
        Literal["needs_review", "needs_actions", "needs_mechanics", "needs_en_name"]
    ] = None


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
    repeat_save: Optional[str] = None  # "end_of_turn" | "start_of_turn" | ...
    repeat_action: Optional[str] = None


class SpellSchema(BaseModel):
    """A single spell entry from spells.json."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    name: str
    name_fr: str
    level: int = Field(..., ge=0, le=9)
    school: SpellSchool
    casting_time: str
    components: List[SpellComponent]
    duration: str
    concentration: bool
    ritual: Optional[bool] = None
    classes: List[str] = Field(default_factory=list)
    description: str
    # Range
    range_m: Optional[Union[int, float]] = None
    # Attack / save / damage
    attack_type: Optional[SpellAttackType] = None
    damage_dice: Optional[str] = None
    damage_type: Optional[str] = None
    save: Optional[SpellSave] = None
    upcast_extra_dice: Optional[str] = None
    upcast_breakpoints: Optional[List[int]] = None
    upcast_extra_targets: Optional[int] = None
    upcast_extra_rays: Optional[int] = None
    upcast_extra_darts: Optional[int] = None
    # Healing
    heal_dice: Optional[str] = None
    heal_bonus: Optional[str] = None
    # Area
    area_shape: Optional[str] = None
    area_size_m: Optional[float] = None
    area_origin: Optional[str] = None
    # Misc effects
    targets: Optional[int] = None
    rays: Optional[int] = None
    darts: Optional[int] = None
    push_m: Optional[float] = None
    teleport_m: Optional[float] = None
    ac_bonus: Optional[int] = None
    bonus_action_attack: Optional[bool] = None
    reaction_trigger: Optional[str] = None
    condition: Optional[str] = None
    # Set by the importer when only the descriptive text could be extracted.
    parse_status: Optional[Literal["needs_mechanics", "needs_en_name"]] = None


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
