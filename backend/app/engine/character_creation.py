"""Character creation — pure D&D SRD 5.2 logic.

Covers:
- Point buy stat system (27-point budget, base scores 8–15)
- Species ability score bonuses and traits (Human, Elf, Dwarf)
- Class features at level 1 (Fighter, Wizard, Rogue, Cleric)
- HP calculation (max at level 1, average formula for higher levels)
- Character blueprint assembly

No I/O, no async, no database access.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional

from app.engine.ability_checks import Ability, ability_modifier
from app.engine.ability_checks import proficiency_bonus as _prof_bonus


# ---------------------------------------------------------------------------
# Point buy
# ---------------------------------------------------------------------------

POINT_BUY_BUDGET: int = 27

# SRD 5.2 point buy cost table (base scores 8–15, before species bonuses)
POINT_BUY_COST: Dict[int, int] = {
    8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9,
}

VALID_SPECIES = frozenset({
    "human", "elf", "dwarf", "halfling", "gnome", "half_elf", "half_orc", "tiefling",
})
VALID_CLASSES = frozenset({
    "fighter", "wizard", "rogue", "cleric",
    "barbarian", "bard", "druid", "monk", "paladin", "ranger", "sorcerer", "warlock",
})


def point_buy_cost(score: int) -> int:
    """Return the point buy cost for a base ability score (8–15).

    Raises:
        ValueError: if score is outside the valid 8–15 range.
    """
    if score not in POINT_BUY_COST:
        raise ValueError(
            f"Point buy score must be between 8 and 15, got {score}"
        )
    return POINT_BUY_COST[score]


def roll_ability_scores(rng: random.Random | None = None) -> List[int]:
    """Roll six ability scores using the 4d6-drop-lowest method.

    For each of the six scores: roll four d6, discard the lowest, sum the rest.

    Args:
        rng: Optional :class:`random.Random` instance for reproducibility in tests.
             Defaults to the module-level RNG.

    Returns:
        List of six integers (each in range 3–18).
    """
    _rng = rng or random
    results: List[int] = []
    for _ in range(6):
        rolls = [_rng.randint(1, 6) for _ in range(4)]
        rolls.sort()
        results.append(sum(rolls[1:]))  # drop lowest
    return results


def validate_point_buy(scores: Dict[str, int]) -> int:
    """Validate a complete set of 6 base ability scores against the point buy budget.

    Args:
        scores: Mapping of ability name (e.g. ``"strength"``) to base score (8–15).

    Returns:
        Total points spent (≤ 27).

    Raises:
        ValueError: if abilities are missing/extra, any score is out of range,
                    or total cost exceeds 27.
    """
    expected = {a.value for a in Ability}
    given = {k.lower() for k in scores}
    missing = expected - given
    extra = given - expected
    if missing or extra:
        raise ValueError(
            f"Expected abilities {sorted(expected)}; missing={sorted(missing)}, extra={sorted(extra)}"
        )

    total = sum(point_buy_cost(v) for v in scores.values())  # raises on out-of-range
    if total > POINT_BUY_BUDGET:
        raise ValueError(
            f"Point buy cost {total} exceeds budget of {POINT_BUY_BUDGET}"
        )
    return total


# ---------------------------------------------------------------------------
# Ability scores
# ---------------------------------------------------------------------------


@dataclass
class AbilityScores:
    """The six ability scores of a D&D character."""

    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int

    def get(self, ability: Ability) -> int:
        """Return the score for the given Ability."""
        return getattr(self, ability.value)

    def modifier(self, ability: Ability) -> int:
        """Return the ability modifier for the given Ability."""
        return ability_modifier(self.get(ability))

    def apply_bonuses(self, bonuses: Dict[str, int]) -> "AbilityScores":
        """Return a new AbilityScores with the given bonuses added (hard cap 20).

        Args:
            bonuses: mapping of ability name to integer bonus (e.g. ``{"dexterity": 2}``).

        Raises:
            ValueError: if an unknown ability name is given.
        """
        d = self.as_dict()
        for key, bonus in bonuses.items():
            key = key.lower()
            if key not in d:
                raise ValueError(f"Unknown ability: '{key}'")
            d[key] = min(20, d[key] + bonus)
        return AbilityScores(**d)

    def as_dict(self) -> Dict[str, int]:
        """Return a plain dict representation."""
        return {
            "strength": self.strength,
            "dexterity": self.dexterity,
            "constitution": self.constitution,
            "intelligence": self.intelligence,
            "wisdom": self.wisdom,
            "charisma": self.charisma,
        }


# ---------------------------------------------------------------------------
# Species traits
# ---------------------------------------------------------------------------


@dataclass
class SpeciesTraits:
    """Mechanical traits granted by a character's species."""

    name: str
    ability_bonuses: Dict[str, int]     # e.g. {"dexterity": 2, "intelligence": 1}
    speed: float                        # vitesse de déplacement de base en mètres
    size: str                           # "Medium" or "Small"
    darkvision_m: float                 # 0 = pas de vision dans le noir
    traits: List[str]                   # feature names
    skill_proficiencies: List[str]      # bonus skill proficiencies granted by species
    languages: List[str]


_SPECIES_DATA: Dict[str, SpeciesTraits] = {
    # Standard Human: +1 to every ability score
    "human": SpeciesTraits(
        name="Human",
        ability_bonuses={a.value: 1 for a in Ability},
        speed=9,
        size="Medium",
        darkvision_m=0,
        traits=["Extra Language", "Versatility"],
        skill_proficiencies=[],
        languages=["common"],
    ),
    # High Elf: +2 DEX, +1 INT
    "elf": SpeciesTraits(
        name="Elf",
        ability_bonuses={"dexterity": 2, "intelligence": 1},
        speed=9,
        size="Medium",
        darkvision_m=18,
        traits=[
            "Darkvision",
            "Keen Senses",
            "Fey Ancestry",
            "Trance",
            "Elf Weapon Training",
            "Cantrip",
        ],
        skill_proficiencies=["perception"],
        languages=["common", "elvish"],
    ),
    # Mountain Dwarf: +2 CON, +2 STR
    "dwarf": SpeciesTraits(
        name="Dwarf",
        ability_bonuses={"constitution": 2, "strength": 2},
        speed=7.5,
        size="Medium",
        darkvision_m=18,
        traits=[
            "Darkvision",
            "Dwarven Resilience",
            "Dwarven Combat Training",
            "Tool Proficiency",
            "Stonecunning",
        ],
        skill_proficiencies=[],
        languages=["common", "dwarvish"],
    ),
    # Lightfoot Halfling: +2 DEX
    "halfling": SpeciesTraits(
        name="Halfling",
        ability_bonuses={"dexterity": 2},
        speed=7.5,
        size="Small",
        darkvision_m=0,
        traits=["Lucky", "Brave", "Halfling Nimbleness", "Naturally Stealthy"],
        skill_proficiencies=[],
        languages=["common", "halfling"],
    ),
    # Forest Gnome: +2 INT
    "gnome": SpeciesTraits(
        name="Gnome",
        ability_bonuses={"intelligence": 2},
        speed=7.5,
        size="Small",
        darkvision_m=18,
        traits=["Darkvision", "Gnome Cunning", "Natural Illusionist", "Speak with Small Beasts"],
        skill_proficiencies=[],
        languages=["common", "gnomish"],
    ),
    # Half-Elf: +2 CHA, +1 STR, +1 CON (simplifié — SRD: +2 CHA + 2×+1 au choix)
    "half_elf": SpeciesTraits(
        name="Half-Elf",
        ability_bonuses={"charisma": 2, "strength": 1, "constitution": 1},
        speed=9,
        size="Medium",
        darkvision_m=18,
        traits=["Darkvision", "Fey Ancestry", "Skill Versatility"],
        skill_proficiencies=[],
        languages=["common", "elvish"],
    ),
    # Half-Orc: +2 STR, +1 CON
    "half_orc": SpeciesTraits(
        name="Half-Orc",
        ability_bonuses={"strength": 2, "constitution": 1},
        speed=9,
        size="Medium",
        darkvision_m=18,
        traits=["Darkvision", "Menacing", "Relentless Endurance", "Savage Attacks"],
        skill_proficiencies=["intimidation"],
        languages=["common", "orc"],
    ),
    # Tiefling: +1 INT, +2 CHA
    "tiefling": SpeciesTraits(
        name="Tiefling",
        ability_bonuses={"intelligence": 1, "charisma": 2},
        speed=9,
        size="Medium",
        darkvision_m=18,
        traits=["Darkvision", "Hellish Resistance", "Infernal Legacy"],
        skill_proficiencies=[],
        languages=["common", "infernal"],
    ),
}


def get_species_traits(species_name: str) -> SpeciesTraits:
    """Return traits for a species by name.

    Args:
        species_name: ``"human"``, ``"elf"``, or ``"dwarf"`` (case-insensitive).

    Raises:
        ValueError: if the species is not recognised.
    """
    key = species_name.lower()
    if key not in _SPECIES_DATA:
        raise ValueError(
            f"Unknown species '{species_name}'. Valid: {sorted(VALID_SPECIES)}"
        )
    return _SPECIES_DATA[key]


# ---------------------------------------------------------------------------
# Class features
# ---------------------------------------------------------------------------


@dataclass
class ClassFeatures:
    """Features and proficiencies granted by a class at level 1."""

    name: str
    hit_die: int                            # e.g. 10 for Fighter (d10)
    saving_throw_proficiencies: List[str]   # ability names
    armor_proficiencies: List[str]
    weapon_proficiencies: List[str]
    skill_choices: List[str]                # pool from which to choose
    num_skill_choices: int                  # how many to pick
    level_1_features: List[str]             # feature names at level 1
    spellcasting_ability: Optional[str]     # None for non-casters
    caster_type: Optional[str]              # "full", "half", "third", "warlock", or None


_CLASS_DATA: Dict[str, ClassFeatures] = {
    "fighter": ClassFeatures(
        name="Fighter",
        hit_die=10,
        saving_throw_proficiencies=["strength", "constitution"],
        armor_proficiencies=["light", "medium", "heavy", "shields"],
        weapon_proficiencies=["simple", "martial"],
        skill_choices=[
            "acrobatics", "animal_handling", "athletics", "history",
            "insight", "intimidation", "perception", "survival",
        ],
        num_skill_choices=2,
        level_1_features=["Fighting Style", "Second Wind"],
        spellcasting_ability=None,
        caster_type=None,
    ),
    "wizard": ClassFeatures(
        name="Wizard",
        hit_die=6,
        saving_throw_proficiencies=["intelligence", "wisdom"],
        armor_proficiencies=[],
        weapon_proficiencies=[
            "daggers", "darts", "slings", "quarterstaffs", "light crossbows",
        ],
        skill_choices=[
            "arcana", "history", "insight", "investigation", "medicine", "religion",
        ],
        num_skill_choices=2,
        level_1_features=["Spellcasting", "Arcane Recovery"],
        spellcasting_ability="intelligence",
        caster_type="full",
    ),
    "rogue": ClassFeatures(
        name="Rogue",
        hit_die=8,
        saving_throw_proficiencies=["dexterity", "intelligence"],
        armor_proficiencies=["light"],
        weapon_proficiencies=[
            "simple", "hand crossbows", "longswords", "rapiers", "shortswords",
        ],
        skill_choices=[
            "acrobatics", "athletics", "deception", "insight", "intimidation",
            "investigation", "perception", "performance", "persuasion",
            "sleight_of_hand", "stealth",
        ],
        num_skill_choices=4,
        level_1_features=["Expertise", "Sneak Attack (1d6)", "Thieves' Cant"],
        spellcasting_ability=None,
        caster_type=None,
    ),
    "cleric": ClassFeatures(
        name="Cleric",
        hit_die=8,
        saving_throw_proficiencies=["wisdom", "charisma"],
        armor_proficiencies=["light", "medium", "shields"],
        weapon_proficiencies=["simple"],
        skill_choices=["history", "insight", "medicine", "persuasion", "religion"],
        num_skill_choices=2,
        level_1_features=["Spellcasting", "Divine Domain", "Channel Divinity"],
        spellcasting_ability="wisdom",
        caster_type="full",
    ),
    "barbarian": ClassFeatures(
        name="Barbarian",
        hit_die=12,
        saving_throw_proficiencies=["strength", "constitution"],
        armor_proficiencies=["light", "medium", "shields"],
        weapon_proficiencies=["simple", "martial"],
        skill_choices=[
            "animal_handling", "athletics", "intimidation", "nature", "perception", "survival",
        ],
        num_skill_choices=2,
        level_1_features=["Rage", "Unarmored Defense"],
        spellcasting_ability=None,
        caster_type=None,
    ),
    "bard": ClassFeatures(
        name="Bard",
        hit_die=8,
        saving_throw_proficiencies=["dexterity", "charisma"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "hand_crossbows", "longswords", "rapiers", "shortswords"],
        skill_choices=[
            "acrobatics", "animal_handling", "arcana", "athletics", "deception", "history",
            "insight", "intimidation", "investigation", "medicine", "nature", "perception",
            "performance", "persuasion", "religion", "sleight_of_hand", "stealth", "survival",
        ],
        num_skill_choices=3,
        level_1_features=["Spellcasting", "Bardic Inspiration (d6)"],
        spellcasting_ability="charisma",
        caster_type="full",
    ),
    "druid": ClassFeatures(
        name="Druid",
        hit_die=8,
        saving_throw_proficiencies=["intelligence", "wisdom"],
        armor_proficiencies=["light", "medium", "shields"],
        weapon_proficiencies=["clubs", "daggers", "darts", "javelins", "maces", "quarterstaffs",
                              "scimitars", "sickles", "slings", "spears"],
        skill_choices=[
            "arcana", "animal_handling", "insight", "medicine", "nature",
            "perception", "religion", "survival",
        ],
        num_skill_choices=2,
        level_1_features=["Druidic", "Spellcasting"],
        spellcasting_ability="wisdom",
        caster_type="full",
    ),
    "monk": ClassFeatures(
        name="Monk",
        hit_die=8,
        saving_throw_proficiencies=["strength", "dexterity"],
        armor_proficiencies=[],
        weapon_proficiencies=["simple", "shortswords"],
        skill_choices=["acrobatics", "athletics", "history", "insight", "religion", "stealth"],
        num_skill_choices=2,
        level_1_features=["Unarmored Defense", "Martial Arts"],
        spellcasting_ability=None,
        caster_type=None,
    ),
    "paladin": ClassFeatures(
        name="Paladin",
        hit_die=10,
        saving_throw_proficiencies=["wisdom", "charisma"],
        armor_proficiencies=["light", "medium", "heavy", "shields"],
        weapon_proficiencies=["simple", "martial"],
        skill_choices=["athletics", "insight", "intimidation", "medicine", "persuasion", "religion"],
        num_skill_choices=2,
        level_1_features=["Divine Sense", "Lay on Hands"],
        spellcasting_ability="charisma",
        caster_type="half",
    ),
    "ranger": ClassFeatures(
        name="Ranger",
        hit_die=10,
        saving_throw_proficiencies=["strength", "dexterity"],
        armor_proficiencies=["light", "medium", "shields"],
        weapon_proficiencies=["simple", "martial"],
        skill_choices=[
            "animal_handling", "athletics", "insight", "investigation",
            "nature", "perception", "stealth", "survival",
        ],
        num_skill_choices=3,
        level_1_features=["Favored Enemy", "Natural Explorer"],
        spellcasting_ability="wisdom",
        caster_type="half",
    ),
    "sorcerer": ClassFeatures(
        name="Sorcerer",
        hit_die=6,
        saving_throw_proficiencies=["constitution", "charisma"],
        armor_proficiencies=[],
        weapon_proficiencies=["daggers", "darts", "slings", "quarterstaffs", "light_crossbows"],
        skill_choices=["arcana", "deception", "insight", "intimidation", "persuasion", "religion"],
        num_skill_choices=2,
        level_1_features=["Spellcasting", "Sorcerous Origin"],
        spellcasting_ability="charisma",
        caster_type="full",
    ),
    "warlock": ClassFeatures(
        name="Warlock",
        hit_die=8,
        saving_throw_proficiencies=["wisdom", "charisma"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple"],
        skill_choices=[
            "arcana", "deception", "history", "intimidation",
            "investigation", "nature", "religion",
        ],
        num_skill_choices=2,
        level_1_features=["Otherworldly Patron", "Pact Magic"],
        spellcasting_ability="charisma",
        caster_type="warlock",
    ),
}


def get_class_features(class_name: str) -> ClassFeatures:
    """Return features for a class by name.

    Args:
        class_name: ``"fighter"``, ``"wizard"``, ``"rogue"``, or ``"cleric"``
                    (case-insensitive).

    Raises:
        ValueError: if the class is not recognised.
    """
    key = class_name.lower()
    if key not in _CLASS_DATA:
        raise ValueError(
            f"Unknown class '{class_name}'. Valid: {sorted(VALID_CLASSES)}"
        )
    return _CLASS_DATA[key]


# ---------------------------------------------------------------------------
# HP calculation
# ---------------------------------------------------------------------------


def hp_at_level(class_name: str, con_score: int, level: int = 1) -> int:
    """Calculate maximum HP for a character at the given level.

    SRD 5.2 rules:
    - Level 1:  hit_die + CON modifier  (always maximum)
    - Level 2+: add (hit_die // 2 + 1) + CON modifier per additional level

    The CON modifier is applied every level, so increasing CON is retroactive.

    Args:
        class_name: Class name (determines hit die).
        con_score:  Constitution score (used to derive modifier).
        level:      Character level (1–20).

    Returns:
        Maximum hit points (minimum 1).

    Raises:
        ValueError: if level is outside 1–20.
    """
    if level < 1 or level > 20:
        raise ValueError(f"Level must be 1–20, got {level}")

    features = get_class_features(class_name)
    con_mod = ability_modifier(con_score)
    hd = features.hit_die

    # Level 1: always maximum die value
    hp = hd + con_mod
    # Level 2+: average roll per level (floor(hd/2) + 1)
    avg_per_level = hd // 2 + 1
    for _ in range(level - 1):
        hp += avg_per_level + con_mod

    return max(1, hp)


# ---------------------------------------------------------------------------
# Character blueprint
# ---------------------------------------------------------------------------


@dataclass
class CharacterBlueprint:
    """Complete mechanical summary of a level-1 character, ready for play."""

    name: str
    species: str
    character_class: str
    level: int
    base_scores: AbilityScores       # as entered via point buy (before bonuses)
    final_scores: AbilityScores      # after species ability bonuses
    species_traits: SpeciesTraits
    class_features: ClassFeatures
    max_hp: int
    proficiency_bonus: int


def build_character(
    name: str,
    species_name: str,
    class_name: str,
    base_scores: AbilityScores,
    level: int = 1,
    validate_scores: bool = True,
) -> CharacterBlueprint:
    """Assemble a complete CharacterBlueprint from its components.

    Args:
        name:             Character name.
        species_name:     ``"human"``, ``"elf"``, or ``"dwarf"``.
        class_name:       ``"fighter"``, ``"wizard"``, ``"rogue"``, or ``"cleric"``.
        base_scores:      Ability scores before species bonuses (point buy values).
        level:            Starting level (default 1).
        validate_scores:  When True, validate base_scores against the 27-point budget.

    Returns:
        CharacterBlueprint with all derived values populated.
    """
    if validate_scores:
        validate_point_buy(base_scores.as_dict())

    traits = get_species_traits(species_name)
    features = get_class_features(class_name)
    final = base_scores.apply_bonuses(traits.ability_bonuses)
    hp = hp_at_level(class_name, final.constitution, level)
    prof = _prof_bonus(level)

    return CharacterBlueprint(
        name=name,
        species=species_name.lower(),
        character_class=class_name.lower(),
        level=level,
        base_scores=base_scores,
        final_scores=final,
        species_traits=traits,
        class_features=features,
        max_hp=hp,
        proficiency_bonus=prof,
    )
