"""Equipment — weapons, armor, and AC calculation (pure D&D SRD 5.2 logic).

Covers:
- Weapon stat blocks (simple/martial, melee/ranged, properties)
- Armor stat blocks (light/medium/heavy/shield)
- Attack bonus and damage notation computation for a given combatant
- Armor Class calculation (unarmored, light, medium, heavy, with/without shield)

No I/O, no async, no database access.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.engine.ability_checks import ability_modifier, proficiency_bonus


# ---------------------------------------------------------------------------
# Weapon data classes
# ---------------------------------------------------------------------------


@dataclass
class WeaponStats:
    """Mechanical stat block for a weapon."""

    name: str
    category: str               # "simple" or "martial"
    damage_dice: str            # e.g. "1d6"  – passed directly to roll_damage()
    damage_type: str            # "piercing" | "slashing" | "bludgeoning"
    properties: List[str]       # SRD property tags (see WEAPON_PROPERTIES)
    range_normal: Optional[int] # None for melee-only weapons; feet
    range_long: Optional[int]   # long range imposes disadvantage
    versatile_dice: Optional[str]  # two-handed damage, e.g. "1d8" for longsword
    weight: float               # pounds
    cost_gp: float              # gold pieces


# SRD 5.2 weapon property names (informational – used by consumers)
WEAPON_PROPERTIES = frozenset({
    "ammunition",   # requires ammo; use DEX for ranged attack
    "finesse",      # choose STR or DEX for attack & damage
    "heavy",        # small/tiny creatures have disadvantage
    "light",        # can be used with two-weapon fighting
    "loading",      # one attack per action regardless of number of attacks
    "reach",        # +5 ft reach
    "thrown",       # can be thrown (uses same ability as melee)
    "two-handed",   # requires two hands
    "versatile",    # can be used one- or two-handed (versatile_dice)
})

# ---------------------------------------------------------------------------
# Weapon catalogue (SRD 5.2 subset — simple + martial relevant to 4 classes)
# ---------------------------------------------------------------------------

_WEAPONS: Dict[str, WeaponStats] = {
    # ---- Simple melee ----
    "club": WeaponStats(
        name="Club", category="simple",
        damage_dice="1d4", damage_type="bludgeoning",
        properties=["light"], range_normal=None, range_long=None,
        versatile_dice=None, weight=2.0, cost_gp=0.1,
    ),
    "dagger": WeaponStats(
        name="Dagger", category="simple",
        damage_dice="1d4", damage_type="piercing",
        properties=["finesse", "light", "thrown"],
        range_normal=20, range_long=60,
        versatile_dice=None, weight=1.0, cost_gp=2.0,
    ),
    "handaxe": WeaponStats(
        name="Handaxe", category="simple",
        damage_dice="1d6", damage_type="slashing",
        properties=["light", "thrown"],
        range_normal=20, range_long=60,
        versatile_dice=None, weight=2.0, cost_gp=5.0,
    ),
    "javelin": WeaponStats(
        name="Javelin", category="simple",
        damage_dice="1d6", damage_type="piercing",
        properties=["thrown"],
        range_normal=30, range_long=120,
        versatile_dice=None, weight=2.0, cost_gp=0.5,
    ),
    "light_hammer": WeaponStats(
        name="Light Hammer", category="simple",
        damage_dice="1d4", damage_type="bludgeoning",
        properties=["light", "thrown"],
        range_normal=20, range_long=60,
        versatile_dice=None, weight=2.0, cost_gp=2.0,
    ),
    "mace": WeaponStats(
        name="Mace", category="simple",
        damage_dice="1d6", damage_type="bludgeoning",
        properties=[], range_normal=None, range_long=None,
        versatile_dice=None, weight=4.0, cost_gp=5.0,
    ),
    "quarterstaff": WeaponStats(
        name="Quarterstaff", category="simple",
        damage_dice="1d6", damage_type="bludgeoning",
        properties=["versatile"],
        range_normal=None, range_long=None,
        versatile_dice="1d8", weight=4.0, cost_gp=0.2,
    ),
    "sickle": WeaponStats(
        name="Sickle", category="simple",
        damage_dice="1d4", damage_type="slashing",
        properties=["light"], range_normal=None, range_long=None,
        versatile_dice=None, weight=2.0, cost_gp=1.0,
    ),
    "spear": WeaponStats(
        name="Spear", category="simple",
        damage_dice="1d6", damage_type="piercing",
        properties=["thrown", "versatile"],
        range_normal=20, range_long=60,
        versatile_dice="1d8", weight=3.0, cost_gp=1.0,
    ),
    # ---- Simple ranged ----
    "light_crossbow": WeaponStats(
        name="Light Crossbow", category="simple",
        damage_dice="1d8", damage_type="piercing",
        properties=["ammunition", "loading", "two-handed"],
        range_normal=80, range_long=320,
        versatile_dice=None, weight=5.0, cost_gp=25.0,
    ),
    "shortbow": WeaponStats(
        name="Shortbow", category="simple",
        damage_dice="1d6", damage_type="piercing",
        properties=["ammunition", "two-handed"],
        range_normal=80, range_long=320,
        versatile_dice=None, weight=2.0, cost_gp=25.0,
    ),
    # ---- Martial melee ----
    "battleaxe": WeaponStats(
        name="Battleaxe", category="martial",
        damage_dice="1d8", damage_type="slashing",
        properties=["versatile"],
        range_normal=None, range_long=None,
        versatile_dice="1d10", weight=4.0, cost_gp=10.0,
    ),
    "greataxe": WeaponStats(
        name="Greataxe", category="martial",
        damage_dice="1d12", damage_type="slashing",
        properties=["heavy", "two-handed"],
        range_normal=None, range_long=None,
        versatile_dice=None, weight=7.0, cost_gp=30.0,
    ),
    "greatsword": WeaponStats(
        name="Greatsword", category="martial",
        damage_dice="2d6", damage_type="slashing",
        properties=["heavy", "two-handed"],
        range_normal=None, range_long=None,
        versatile_dice=None, weight=6.0, cost_gp=50.0,
    ),
    "longsword": WeaponStats(
        name="Longsword", category="martial",
        damage_dice="1d8", damage_type="slashing",
        properties=["versatile"],
        range_normal=None, range_long=None,
        versatile_dice="1d10", weight=3.0, cost_gp=15.0,
    ),
    "rapier": WeaponStats(
        name="Rapier", category="martial",
        damage_dice="1d8", damage_type="piercing",
        properties=["finesse"],
        range_normal=None, range_long=None,
        versatile_dice=None, weight=2.0, cost_gp=25.0,
    ),
    "shortsword": WeaponStats(
        name="Shortsword", category="martial",
        damage_dice="1d6", damage_type="piercing",
        properties=["finesse", "light"],
        range_normal=None, range_long=None,
        versatile_dice=None, weight=2.0, cost_gp=10.0,
    ),
    "war_pick": WeaponStats(
        name="War Pick", category="martial",
        damage_dice="1d8", damage_type="piercing",
        properties=[], range_normal=None, range_long=None,
        versatile_dice=None, weight=2.0, cost_gp=5.0,
    ),
    "warhammer": WeaponStats(
        name="Warhammer", category="martial",
        damage_dice="1d8", damage_type="bludgeoning",
        properties=["versatile"],
        range_normal=None, range_long=None,
        versatile_dice="1d10", weight=2.0, cost_gp=15.0,
    ),
    # ---- Martial ranged ----
    "hand_crossbow": WeaponStats(
        name="Hand Crossbow", category="martial",
        damage_dice="1d6", damage_type="piercing",
        properties=["ammunition", "light", "loading"],
        range_normal=30, range_long=120,
        versatile_dice=None, weight=3.0, cost_gp=75.0,
    ),
    "longbow": WeaponStats(
        name="Longbow", category="martial",
        damage_dice="1d8", damage_type="piercing",
        properties=["ammunition", "heavy", "two-handed"],
        range_normal=150, range_long=600,
        versatile_dice=None, weight=2.0, cost_gp=50.0,
    ),
}


def get_weapon(weapon_name: str) -> WeaponStats:
    """Return a weapon's stat block by name (case-insensitive, spaces → underscores).

    Raises:
        ValueError: if the weapon is not in the catalogue.
    """
    key = weapon_name.lower().replace(" ", "_")
    if key not in _WEAPONS:
        raise ValueError(
            f"Unknown weapon '{weapon_name}'. "
            f"Valid weapons: {sorted(_WEAPONS.keys())}"
        )
    return _WEAPONS[key]


# ---------------------------------------------------------------------------
# Armor data class
# ---------------------------------------------------------------------------


@dataclass
class ArmorStats:
    """Mechanical stat block for a piece of armor or a shield."""

    name: str
    category: str           # "light" | "medium" | "heavy" | "shield"
    base_ac: int            # base AC (or bonus for shields)
    dex_cap: Optional[int]  # max DEX bonus allowed (None = uncapped)
    strength_requirement: int   # minimum STR score (0 = none)
    stealth_disadvantage: bool
    weight: float
    cost_gp: float


# ---------------------------------------------------------------------------
# Armor catalogue (SRD 5.2)
# ---------------------------------------------------------------------------

_ARMORS: Dict[str, ArmorStats] = {
    # ---- Light armor (DEX mod, uncapped) ----
    "padded": ArmorStats(
        name="Padded", category="light",
        base_ac=11, dex_cap=None,
        strength_requirement=0, stealth_disadvantage=True,
        weight=8.0, cost_gp=5.0,
    ),
    "leather": ArmorStats(
        name="Leather", category="light",
        base_ac=11, dex_cap=None,
        strength_requirement=0, stealth_disadvantage=False,
        weight=10.0, cost_gp=10.0,
    ),
    "studded_leather": ArmorStats(
        name="Studded Leather", category="light",
        base_ac=12, dex_cap=None,
        strength_requirement=0, stealth_disadvantage=False,
        weight=13.0, cost_gp=45.0,
    ),
    # ---- Medium armor (DEX mod capped at +2) ----
    "hide": ArmorStats(
        name="Hide", category="medium",
        base_ac=12, dex_cap=2,
        strength_requirement=0, stealth_disadvantage=False,
        weight=12.0, cost_gp=10.0,
    ),
    "chain_shirt": ArmorStats(
        name="Chain Shirt", category="medium",
        base_ac=13, dex_cap=2,
        strength_requirement=0, stealth_disadvantage=False,
        weight=20.0, cost_gp=50.0,
    ),
    "scale_mail": ArmorStats(
        name="Scale Mail", category="medium",
        base_ac=14, dex_cap=2,
        strength_requirement=0, stealth_disadvantage=True,
        weight=45.0, cost_gp=50.0,
    ),
    "breastplate": ArmorStats(
        name="Breastplate", category="medium",
        base_ac=14, dex_cap=2,
        strength_requirement=0, stealth_disadvantage=False,
        weight=20.0, cost_gp=400.0,
    ),
    "half_plate": ArmorStats(
        name="Half Plate", category="medium",
        base_ac=15, dex_cap=2,
        strength_requirement=0, stealth_disadvantage=True,
        weight=40.0, cost_gp=750.0,
    ),
    # ---- Heavy armor (no DEX bonus) ----
    "ring_mail": ArmorStats(
        name="Ring Mail", category="heavy",
        base_ac=14, dex_cap=0,
        strength_requirement=0, stealth_disadvantage=True,
        weight=40.0, cost_gp=30.0,
    ),
    "chain_mail": ArmorStats(
        name="Chain Mail", category="heavy",
        base_ac=16, dex_cap=0,
        strength_requirement=13, stealth_disadvantage=True,
        weight=55.0, cost_gp=75.0,
    ),
    "splint": ArmorStats(
        name="Splint", category="heavy",
        base_ac=17, dex_cap=0,
        strength_requirement=15, stealth_disadvantage=True,
        weight=60.0, cost_gp=200.0,
    ),
    "plate": ArmorStats(
        name="Plate", category="heavy",
        base_ac=18, dex_cap=0,
        strength_requirement=15, stealth_disadvantage=True,
        weight=65.0, cost_gp=1500.0,
    ),
    # ---- Shield (+2 AC bonus, stacks with armor) ----
    "shield": ArmorStats(
        name="Shield", category="shield",
        base_ac=2, dex_cap=None,
        strength_requirement=0, stealth_disadvantage=False,
        weight=6.0, cost_gp=10.0,
    ),
}


def get_armor(armor_name: str) -> ArmorStats:
    """Return an armor's stat block by name (case-insensitive, spaces → underscores).

    Raises:
        ValueError: if the armor is not in the catalogue.
    """
    key = armor_name.lower().replace(" ", "_")
    if key not in _ARMORS:
        raise ValueError(
            f"Unknown armor '{armor_name}'. "
            f"Valid armors: {sorted(_ARMORS.keys())}"
        )
    return _ARMORS[key]


# ---------------------------------------------------------------------------
# AC calculation
# ---------------------------------------------------------------------------


@dataclass
class ACResult:
    """Breakdown of a character's Armor Class."""

    total: int
    base: int           # base AC before shield
    shield_bonus: int   # 0 or 2
    dex_applied: int    # DEX modifier actually applied (may be capped or zero)
    armor_name: Optional[str]
    has_shield: bool
    stealth_disadvantage: bool
    breakdown: str


def compute_ac(
    dex_score: int,
    armor: Optional[ArmorStats] = None,
    has_shield: bool = False,
) -> ACResult:
    """Compute a character's Armor Class.

    SRD 5.2 rules:
    - Unarmored:      AC = 10 + DEX mod
    - Light armor:    AC = base_ac + DEX mod  (uncapped)
    - Medium armor:   AC = base_ac + min(DEX mod, 2)
    - Heavy armor:    AC = base_ac            (DEX ignored)
    - Shield:        +2 to any of the above

    Args:
        dex_score:  Character's DEX score.
        armor:      Equipped armor (None = unarmored).
        has_shield: Whether the character is wielding a shield.

    Returns:
        ACResult with full breakdown.
    """
    dex_mod = ability_modifier(dex_score)
    shield_bonus = 2 if has_shield else 0
    stealth_disadv = False

    if armor is None:
        # Unarmored default
        base = 10
        dex_applied = dex_mod
        armor_name = None
    elif armor.category == "shield":
        # Shield passed as armor is an error — treat as unarmored + shield
        base = 10
        dex_applied = dex_mod
        armor_name = None
        has_shield = True
        shield_bonus = 2
    else:
        if armor.dex_cap is None:
            # Light armor: full DEX
            dex_applied = dex_mod
        else:
            # Medium: capped; Heavy (cap=0): zero
            dex_applied = min(dex_mod, armor.dex_cap)
        base = armor.base_ac
        armor_name = armor.name
        stealth_disadv = armor.stealth_disadvantage

    total = base + dex_applied + shield_bonus

    parts = []
    if armor_name:
        parts.append(f"{armor_name} ({base})")
    else:
        parts.append(f"Unarmored ({base})")
    if dex_applied != 0:
        sign = "+" if dex_applied >= 0 else ""
        parts.append(f"DEX {sign}{dex_applied}")
    if shield_bonus:
        parts.append(f"Shield +{shield_bonus}")
    breakdown = f"AC {total} = " + " + ".join(parts)

    return ACResult(
        total=total,
        base=base,
        shield_bonus=shield_bonus,
        dex_applied=dex_applied,
        armor_name=armor_name,
        has_shield=has_shield,
        stealth_disadvantage=stealth_disadv,
        breakdown=breakdown,
    )


# ---------------------------------------------------------------------------
# Attack stats computation
# ---------------------------------------------------------------------------


@dataclass
class AttackStats:
    """Computed attack parameters for one weapon, ready for roll_attack / roll_damage."""

    weapon_name: str
    attack_bonus: int       # total modifier to the attack roll
    damage_notation: str    # e.g. "1d8+3" — pass directly to roll_damage()
    damage_type: str
    is_finesse: bool
    uses_dex: bool          # True if DEX was chosen (finesse or ranged)
    two_handed: bool        # True if using versatile weapon two-handed
    breakdown: str          # human-readable summary


def weapon_attack_stats(
    weapon: WeaponStats,
    str_score: int,
    dex_score: int,
    proficient: bool,
    level: int,
    two_handed: bool = False,
    prefer_dex: bool = False,
) -> AttackStats:
    """Compute attack bonus and damage notation for a weapon.

    SRD 5.2 rules:
    - Melee weapons use STR mod (or DEX if finesse and higher / preferred).
    - Ranged weapons (ammunition property) use DEX mod.
    - Thrown weapons use the same ability as the melee attack.
    - Finesse weapons allow choosing STR or DEX for both attack and damage.
    - Proficiency bonus is added when proficient.
    - Versatile weapons can be wielded two-handed for the alternate damage die.

    Args:
        weapon:      Weapon stat block.
        str_score:   Attacker's STR score.
        dex_score:   Attacker's DEX score.
        proficient:  Whether the attacker is proficient with this weapon.
        level:       Character level (for proficiency bonus).
        two_handed:  Use the versatile damage die (ignored if not versatile).
        prefer_dex:  For finesse weapons, prefer DEX over STR even if STR is higher.

    Raises:
        ValueError: if two_handed=True but the weapon has no versatile property.
    """
    if two_handed and "versatile" not in weapon.properties and "two-handed" not in weapon.properties:
        raise ValueError(
            f"'{weapon.name}' cannot be used two-handed "
            "(no 'versatile' or 'two-handed' property)."
        )

    str_mod = ability_modifier(str_score)
    dex_mod = ability_modifier(dex_score)
    prof = proficiency_bonus(level) if proficient else 0

    is_ranged = "ammunition" in weapon.properties
    is_finesse = "finesse" in weapon.properties

    if is_ranged:
        uses_dex = True
    elif is_finesse:
        # Choose whichever is higher; prefer_dex breaks ties in favour of DEX
        uses_dex = dex_mod > str_mod or (prefer_dex and dex_mod == str_mod)
    else:
        uses_dex = False

    ability_mod = dex_mod if uses_dex else str_mod
    attack_bonus = ability_mod + prof

    # Damage die
    if two_handed and weapon.versatile_dice:
        damage_die = weapon.versatile_dice
    else:
        damage_die = weapon.damage_dice

    # Build damage notation: "<die>+<mod>" or "<die>-<mod>" or just "<die>"
    if ability_mod > 0:
        damage_notation = f"{damage_die}+{ability_mod}"
    elif ability_mod < 0:
        damage_notation = f"{damage_die}{ability_mod}"  # already has "-"
    else:
        damage_notation = damage_die

    ability_label = "DEX" if uses_dex else "STR"
    sign = f"+{attack_bonus}" if attack_bonus >= 0 else str(attack_bonus)
    prof_str = f" (+{prof} prof)" if prof else ""
    breakdown = (
        f"{weapon.name}: attack {sign} [{ability_label}{'+' if ability_mod >= 0 else ''}"
        f"{ability_mod}{prof_str}], damage {damage_notation} {weapon.damage_type}"
    )

    return AttackStats(
        weapon_name=weapon.name,
        attack_bonus=attack_bonus,
        damage_notation=damage_notation,
        damage_type=weapon.damage_type,
        is_finesse=is_finesse,
        uses_dex=uses_dex,
        two_handed=two_handed and "two-handed" in weapon.properties or (
            two_handed and "versatile" in weapon.properties
        ),
        breakdown=breakdown,
    )


# ---------------------------------------------------------------------------
# Proficiency helpers
# ---------------------------------------------------------------------------


def is_weapon_proficient(weapon: WeaponStats, armor_proficiencies: List[str]) -> bool:
    """Return True if a weapon category is covered by the given proficiency list.

    Args:
        weapon:               Weapon to check.
        armor_proficiencies:  List from ClassFeatures.weapon_proficiencies
                              (e.g. ``["simple", "martial"]`` for Fighter).
    """
    profs = [p.lower() for p in armor_proficiencies]
    # Direct category match ("simple" or "martial")
    if weapon.category in profs:
        return True
    # Named weapon proficiency (e.g. "longswords", "rapiers")
    weapon_key = weapon.name.lower()
    weapon_key_plural = weapon_key + "s"
    return weapon_key in profs or weapon_key_plural in profs


def is_armor_proficient(armor: ArmorStats, armor_proficiencies: List[str]) -> bool:
    """Return True if a character is proficient with the given armor.

    Args:
        armor:               Armor to check.
        armor_proficiencies: List from ClassFeatures.armor_proficiencies
                             (e.g. ``["light", "medium", "shields"]`` for Cleric).
    """
    if armor.category == "shield":
        return "shields" in [p.lower() for p in armor_proficiencies]
    return armor.category in [p.lower() for p in armor_proficiencies]
