"""Phase 2b — extract mechanical fields from spell descriptions.

Reads the FR description of every spell flagged ``parse_status:
needs_mechanics`` and tries to recover the structured fields the GM engine
needs to actually resolve the spell:

- ``attack_type`` (melee_spell / ranged_spell)
- ``damage_dice`` + ``damage_type``
- ``save`` (ability + on_success outcome)
- ``area_shape`` + ``area_size_m`` (sphere, cube, cone, line, cylinder, emanation)
- ``upcast_extra_dice`` + ``upcast_breakpoints`` for cantrips
- ``upcast_extra_dice`` for leveled-spell upcasts
- ``upcast_extra_targets`` for "+1 target per level" upcasts
- ``heal_dice`` for healing spells

Spells that gain at least one mechanical field have their ``parse_status``
removed. Spells where nothing could be extracted keep the flag for human
review.

Usage::

    cd backend && source .venv/bin/activate
    python -m scripts.enrich_spells_mechanics            # writes spells.json
    python -m scripts.enrich_spells_mechanics --dry-run  # only prints summary
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.engine.srd_data.schemas import SpellSchema  # noqa: E402

SPELLS_JSON = BACKEND_DIR / "app" / "engine" / "srd_data" / "spells.json"

# --- Translation tables (subset of those in the import scripts) ----------

DAMAGE_FR_TO_EN: Dict[str, str] = {
    "acide": "acid",
    "contondants": "bludgeoning",
    "contondant": "bludgeoning",
    "feu": "fire",
    "force": "force",
    "foudre": "lightning",
    "froid": "cold",
    "nécrotique": "necrotic",
    "nécrotiques": "necrotic",
    "perforant": "piercing",
    "perforants": "piercing",
    "poison": "poison",
    "psychique": "psychic",
    "psychiques": "psychic",
    "radiant": "radiant",
    "radiants": "radiant",
    "tonnerre": "thunder",
    "tranchant": "slashing",
    "tranchants": "slashing",
}

ABILITY_FR_TO_EN: Dict[str, str] = {
    "Force": "strength",
    "Dextérité": "dexterity",
    "Constitution": "constitution",
    "Intelligence": "intelligence",
    "Sagesse": "wisdom",
    "Charisme": "charisma",
}

AREA_SHAPE_FR_TO_EN: Dict[str, str] = {
    "Sphère": "sphere",
    "Cube": "cube",
    "Cône": "cone",
    "Cylindre": "cylinder",
    "Ligne": "line",
    "Émanation": "emanation",
}

# --- Regex patterns -------------------------------------------------------

# Damage: "1d8 dégâts de foudre" or "1d12 dégâts d'acide" — stop at ';' or ','
# or a sentence end so we don't accidentally chain two damage clauses.
DAMAGE_RE = re.compile(
    r"(\d+d\d+(?:\s*\+\s*\d+)?)"
    r"\s+dégâts"
    r"\s+(?:de|d['’])\s*"
    r"(?P<dtype>"
    + "|".join(sorted(DAMAGE_FR_TO_EN.keys(), key=len, reverse=True))
    + r")"
)

# Spell attack types.
RANGED_SPELL_RE = re.compile(r"attaque\s+de\s+sort\s+à\s+distance", re.IGNORECASE)
MELEE_SPELL_RE = re.compile(r"attaque\s+de\s+sort\s+au\s+corps\s+à\s+corps", re.IGNORECASE)

# Saving throw: "jet de sauvegarde de Sagesse" or "JS Sagesse"
SAVE_RE = re.compile(
    r"(?:jet\s+de\s+sauvegarde|JS)\s+de?\s*"
    r"(?P<ab>Force|Dextérité|Constitution|Intelligence|Sagesse|Charisme)",
    re.IGNORECASE,
)

# Area: "Sphère de 6 m de rayon", "Cube de 4,5 m", "Cône de X m"
AREA_RE = re.compile(
    r"(?P<shape>Sphère|Cube|Cône|Cylindre|Ligne|Émanation)"
    r"[^.\n]{0,80}?"
    r"(\d+(?:[,.]\d+)?)\s*m"
)

# Cantrip upcast — the FR phrasing has weird soft-hyphen artifacts
# (`augmen tent`, `aug mentent`), so we are deliberately loose around verb forms.
CANTRIP_UPCAST_RE = re.compile(
    r"Amélioration\s+de\s+sort\s+mineur.{0,80}?"
    r"(?P<extra>\d+d\d+)"
    r".{0,80}?niveaux?\s+5"
    r"\s*\((\d+d\d+)\)"
    r"[^,]*,\s*11\s*\((\d+d\d+)\)"
    r"[^,]*?17\s*\((\d+d\d+)\)",
    re.DOTALL,
)

# Slot upcast — damage scaling.
SLOT_UPCAST_DICE_RE = re.compile(
    r"Emplacement\s+de\s+niveau\s+supérieur"
    r"\.?\s*Les\s+dégâts(?:\s+\w+){0,5}\s+augmentent"
    r"(?:\s+(?:chacun|chacune))?\s+de\s+(?P<extra>\d+d\d+)",
    re.IGNORECASE | re.DOTALL,
)

# Slot upcast — additional targets ("Vous pouvez affecter une cible
# supplémentaire par niveau d'emplacement au-delà du Xe").
SLOT_UPCAST_TARGETS_RE = re.compile(
    r"(?:cibler|affecter|une\s+\w+\s+supplémentaire).{0,40}?"
    r"par\s+niveau\s+d['’]emplacement\s+au-delà\s+du\s+\d+e",
    re.IGNORECASE | re.DOTALL,
)

# Healing: "récupère 1d8 + ton modificateur points de vie", "regagne X PV",
# "regagne 2d4 + 2 points de vie".
HEAL_RE = re.compile(
    r"(?:récupère|regagne|reçoit)\s+"
    r"(?P<dice>\d+d\d+(?:\s*\+\s*[\d\w]+)?)"
    r"\s+(?:points\s+de\s+vie|PV|pv)",
    re.IGNORECASE,
)

# On-success outcome.
HALF_DMG_RE = re.compile(r"(?:la\s+moitié|demi[- ]dégâts)", re.IGNORECASE)
NO_EFFECT_RE = re.compile(
    r"(?:n['’]est\s+pas\s+affectée?|le\s+sort\s+prend\s+fin|aucun\s+effet)",
    re.IGNORECASE,
)

# --- Extraction -----------------------------------------------------------


def extract_mechanics(spell: Dict[str, Any]) -> Dict[str, Any]:
    """Return the new fields to merge into ``spell``."""
    desc = spell.get("description", "") or ""
    desc = re.sub(r"\s+", " ", desc)  # collapse whitespace artifacts

    out: Dict[str, Any] = {}

    # Attack type ---------------------------------------------------------
    if MELEE_SPELL_RE.search(desc):
        out["attack_type"] = "melee_spell"
    elif RANGED_SPELL_RE.search(desc):
        out["attack_type"] = "ranged_spell"

    # Damage dice + type --------------------------------------------------
    dmg = DAMAGE_RE.search(desc)
    if dmg:
        out["damage_dice"] = re.sub(r"\s+", "", dmg.group(1))
        out["damage_type"] = DAMAGE_FR_TO_EN[dmg.group("dtype").lower()]

    # Save ----------------------------------------------------------------
    sv = SAVE_RE.search(desc)
    if sv:
        save_block: Dict[str, Any] = {
            "ability": ABILITY_FR_TO_EN[sv.group("ab").capitalize()],
        }
        # Determine on_success heuristically.
        # Prefer "half_damage" if the description mentions "moitié" or
        # "demi-dégâts" together with damage. Else fall back to "negates".
        tail = desc[sv.end():sv.end() + 400]
        if HALF_DMG_RE.search(tail) and "damage_dice" in out:
            save_block["on_success"] = "half_damage"
        elif NO_EFFECT_RE.search(tail):
            save_block["on_success"] = "no_effect"
        else:
            save_block["on_success"] = (
                "no_damage" if "damage_dice" in out else "negates"
            )
        out["save"] = save_block
        # If we have a save and no attack_type was found, mark it as area-style.
        if "attack_type" not in out:
            out["attack_type"] = "area"

    # Area shape + size ---------------------------------------------------
    area = AREA_RE.search(desc)
    if area:
        out["area_shape"] = AREA_SHAPE_FR_TO_EN[area.group("shape")]
        out["area_size_m"] = float(area.group(2).replace(",", "."))

    # Cantrip upcast (only meaningful if there's damage_dice) --------------
    if spell.get("level") == 0 and "damage_dice" in out:
        cu = CANTRIP_UPCAST_RE.search(desc)
        if cu:
            out["upcast_extra_dice"] = cu.group("extra")
            out["upcast_breakpoints"] = [5, 11, 17]

    # Leveled-spell upcast (damage scaling) -------------------------------
    if spell.get("level", 0) > 0:
        su = SLOT_UPCAST_DICE_RE.search(desc)
        if su:
            out["upcast_extra_dice"] = su.group("extra")
        elif SLOT_UPCAST_TARGETS_RE.search(desc):
            out["upcast_extra_targets"] = 1

    # Healing -------------------------------------------------------------
    heal = HEAL_RE.search(desc)
    if heal:
        out["heal_dice"] = re.sub(r"\s+", "", heal.group("dice"))

    return out


# --- Driver ---------------------------------------------------------------


# Tokens that indicate a spell has *some* mechanical resolution surface.
# A spell whose description contains none of these is a pure utility spell —
# its description is the mechanic, no structured fields are expected.
MECH_KEYWORDS_RE = re.compile(
    r"\bdégâts\b|jet\s+de\s+sauvegarde|\bJS\s+(?:For|Dex|Con|Int|Sag|Cha|Force|Dex|Const)|"
    r"récupère\s+\d+|regagne\s+\d+|points\s+de\s+vie|\bPV\b|attaque\s+de\s+sort",
    re.IGNORECASE,
)


def enrich(spells: List[Dict[str, Any]]) -> Tuple[int, int, List[str], List[str], int]:
    """Mutate ``spells`` in place.

    Returns ``(enriched, still_flagged, sample_filled, still_ids, utility_unflagged)``.
    """
    enriched = 0
    still_ids: List[str] = []
    utility_unflagged = 0
    sample_filled: List[str] = []
    for s in spells:
        if s.get("parse_status") != "needs_mechanics":
            continue
        new_fields = extract_mechanics(s)
        # Apply fields without overwriting curated values.
        for k, v in new_fields.items():
            if s.get(k) in (None, [], {}, ""):
                s[k] = v
        # Drop the flag if at least one of the load-bearing fields is now set.
        load_bearing = ("damage_dice", "save", "attack_type",
                        "heal_dice", "upcast_extra_targets")
        if any(s.get(k) for k in load_bearing):
            del s["parse_status"]
            enriched += 1
            if len(sample_filled) < 6:
                sample_filled.append(s["id"])
            continue
        # No mechanical surface in the description? Treat as utility-only.
        desc = re.sub(r"\s+", " ", s.get("description", "") or "")
        if not MECH_KEYWORDS_RE.search(desc):
            del s["parse_status"]
            utility_unflagged += 1
            continue
        # Otherwise we couldn't extract anything despite mechanical hints.
        still_ids.append(s["id"])
    return enriched, len(still_ids), sample_filled, still_ids, utility_unflagged


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--show-stuck", action="store_true",
                   help="Print all spell ids still flagged after enrichment")
    args = p.parse_args()

    payload = json.loads(SPELLS_JSON.read_text(encoding="utf-8"))
    spells = payload["spells"]

    enriched, still, sample_filled, still_ids, utility_unflagged = enrich(spells)
    print(f"Spells enriched with mechanics: {enriched}")
    print(f"Utility-only spells unflagged (description = mechanic): {utility_unflagged}")
    print(f"Spells still flagged needs_mechanics: {still}")
    print(f"Sample of newly-filled entries: {sample_filled}")
    if args.show_stuck:
        for sid in still_ids:
            print(f"  - {sid}")

    # Validate.
    errors = []
    for s in spells:
        try:
            SpellSchema.model_validate(s)
        except Exception as e:
            errors.append((s.get("id", "?"), str(e)[:200]))
    if errors:
        print(f"\n✘ {len(errors)} validation errors:")
        for sid, err in errors[:10]:
            print(f"   - {sid}: {err}")
        return 2

    if args.dry_run:
        print("Dry run — not writing spells.json")
        return 0

    SPELLS_JSON.write_text(
        json.dumps({"spells": spells}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\n✔ Wrote spells.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
