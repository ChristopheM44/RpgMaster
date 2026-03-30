from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status

router = APIRouter()

_SRD_DIR = Path(__file__).parent.parent / "engine" / "srd_data"


@lru_cache(maxsize=8)
def _load(filename: str) -> Any:
    """Charge et met en cache un fichier JSON SRD."""
    path = _SRD_DIR / filename
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _get_by_id(collection: list[dict], item_id: str) -> dict:
    for item in collection:
        if item.get("id") == item_id:
            return item
    return None


def _flatten_equipment(data: dict) -> list[dict]:
    """Aplatit la structure imbriquée weapons/armor (dict de listes) en liste plate."""
    result: list[dict] = []
    weapons = data.get("weapons", {})
    if isinstance(weapons, dict):
        for lst in weapons.values():
            result.extend(lst)
    elif isinstance(weapons, list):
        result.extend(weapons)

    armor = data.get("armor", {})
    if isinstance(armor, dict):
        for lst in armor.values():
            result.extend(lst)
    elif isinstance(armor, list):
        result.extend(armor)

    kits = data.get("adventurer_kits", [])
    result.extend(kits)
    return result


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------


@router.get("/classes")
async def list_classes():
    data = _load("classes.json")
    return {"classes": data.get("classes", data), "total": len(data.get("classes", data))}


@router.get("/classes/{class_id}")
async def get_class(class_id: str):
    data = _load("classes.json")
    items = data.get("classes", data)
    item = _get_by_id(items, class_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classe introuvable")
    return item


# ---------------------------------------------------------------------------
# Espèces
# ---------------------------------------------------------------------------


@router.get("/species")
async def list_species():
    data = _load("species.json")
    items = data.get("species", data)
    return {"species": items, "total": len(items)}


@router.get("/species/{species_id}")
async def get_species(species_id: str):
    data = _load("species.json")
    items = data.get("species", data)
    item = _get_by_id(items, species_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Espèce introuvable")
    return item


# ---------------------------------------------------------------------------
# Sorts
# ---------------------------------------------------------------------------


@router.get("/spells")
async def list_spells(level: int = None, char_class: str = None):
    data = _load("spells.json")
    items: list[dict] = data.get("spells", data)
    if level is not None:
        items = [s for s in items if s.get("level") == level]
    if char_class is not None:
        items = [s for s in items if char_class in s.get("classes", [])]
    return {"spells": items, "total": len(items)}


@router.get("/spells/{spell_id}")
async def get_spell(spell_id: str):
    data = _load("spells.json")
    items = data.get("spells", data)
    item = _get_by_id(items, spell_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sort introuvable")
    return item


# ---------------------------------------------------------------------------
# Monstres
# ---------------------------------------------------------------------------


@router.get("/monsters")
async def list_monsters(max_cr: float = None):
    data = _load("monsters.json")
    items: list[dict] = data.get("monsters", data)
    if max_cr is not None:
        items = [m for m in items if m.get("cr", 999) <= max_cr]
    return {"monsters": items, "total": len(items)}


@router.get("/monsters/{monster_id}")
async def get_monster(monster_id: str):
    data = _load("monsters.json")
    items = data.get("monsters", data)
    item = _get_by_id(items, monster_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monstre introuvable")
    return item


# ---------------------------------------------------------------------------
# Équipement
# ---------------------------------------------------------------------------


@router.get("/equipment")
async def list_equipment(category: str = None):
    data = _load("equipment.json")
    all_items = _flatten_equipment(data)

    if category is not None:
        all_items = [e for e in all_items if e.get("category") == category]

    return {"equipment": all_items, "total": len(all_items)}


@router.get("/equipment/{item_id}")
async def get_equipment(item_id: str):
    data = _load("equipment.json")
    all_items = _flatten_equipment(data)

    item = _get_by_id(all_items, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Équipement introuvable")
    return item
