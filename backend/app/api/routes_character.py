from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.engine.dice import roll
from app.engine.spells import FULL_CASTER_SLOTS, HALF_CASTER_SLOTS
from app.models.character import Character
from app.schemas.character import (
    CharacterCreate,
    CharacterListResponse,
    CharacterResponse,
    CharacterUpdate,
)

# ── Equipment SRD helpers ───────────────────────────────────────────────────────

_ARMOR_CATEGORIES = {"light", "medium", "heavy"}

_EQUIPMENT_JSON_PATH = Path(__file__).parent.parent / "engine" / "srd_data" / "equipment.json"
_EQUIPMENT_LOOKUP: Optional[Dict[str, Any]] = None

# Noms français pour les items génériques / spéciaux non présents dans equipment.json
_SPECIAL_ITEM_NAMES: Dict[str, str] = {
    "simple_weapon": "Arme courante",
    "martial_weapon": "Arme de guerre",
    "druidic_focus": "Focalisateur druidique",
    "holy_symbol": "Symbole sacré",
    "arcane_focus": "Focalisateur arcanique",
    "component_pouch": "Bourse de composants",
    "musical_instrument": "Instrument de musique",
    "thieves_tools": "Outils de voleur",
    "scimitar": "Cimeterre",
    "bolts": "Carreaux d'arbalète",
    "arrows": "Flèches",
}


def _get_equipment_lookup() -> Dict[str, Any]:
    """Charge equipment.json et retourne un dict id → données complètes de l'item."""
    global _EQUIPMENT_LOOKUP
    if _EQUIPMENT_LOOKUP is not None:
        return _EQUIPMENT_LOOKUP
    try:
        with _EQUIPMENT_JSON_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        _EQUIPMENT_LOOKUP = {}
        return _EQUIPMENT_LOOKUP
    lookup: Dict[str, Any] = {}
    for subcategory in data.get("weapons", {}).values():
        for item in subcategory:
            lookup[item["id"]] = item
    for subcategory in data.get("armor", {}).values():
        for item in subcategory:
            lookup[item["id"]] = item
    for kit in data.get("adventurer_kits", []):
        lookup[kit["id"]] = kit
    _EQUIPMENT_LOOKUP = lookup
    return _EQUIPMENT_LOOKUP


def _resolve_equipment(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enrichit chaque item avec les données SRD (name_fr, category, base_ac…) et
    initialise equipped=True pour la première armure et le premier bouclier."""
    lookup = _get_equipment_lookup()
    resolved: List[Dict[str, Any]] = []
    armor_equipped = False
    shield_equipped = False

    for raw in items:
        item_id: str = str(raw.get("id", ""))
        srd = lookup.get(item_id, {})

        enriched = dict(raw)

        # name_fr : SRD > données reçues > map spéciaux > id humanisé
        if not enriched.get("name_fr"):
            enriched["name_fr"] = (
                srd.get("name_fr")
                or _SPECIAL_ITEM_NAMES.get(item_id)
                or item_id.replace("_", " ").title()
            )

        # Copier les champs SRD si présents (category, base_ac, dex_cap…)
        for field in ("category", "base_ac", "dex_cap", "damage_dice", "damage_type", "properties"):
            if field not in enriched and field in srd:
                enriched[field] = srd[field]

        # Auto-équiper la première armure et le premier bouclier
        category = enriched.get("category", "")
        if category in _ARMOR_CATEGORIES and not armor_equipped:
            enriched["equipped"] = True
            armor_equipped = True
        elif category == "shield" and not shield_equipped:
            enriched["equipped"] = True
            shield_equipped = True
        elif "equipped" not in enriched:
            enriched["equipped"] = False

        resolved.append(enriched)
    return resolved


_FULL_CASTERS = {"wizard", "cleric", "druid", "bard", "sorcerer"}
_HALF_CASTERS = {"paladin", "ranger"}


def _init_spell_slots(char_class: str, level: int) -> Dict[str, Dict[str, int]]:
    """Retourne les emplacements de sorts initiaux (tous unused) selon la classe et le niveau."""
    cls = char_class.lower()
    if cls in _FULL_CASTERS:
        slot_table = FULL_CASTER_SLOTS.get(level, {})
    elif cls in _HALF_CASTERS:
        slot_table = HALF_CASTER_SLOTS.get(level, {})
    elif cls == "warlock":
        # Pact Magic : 1 emplacement niveau 1 au niveau 1
        slot_table = {1: 1}
    else:
        return {}
    return {str(slot_lvl): {"total": count, "used": 0} for slot_lvl, count in slot_table.items()}


class InventoryActionRequest(BaseModel):
    item_id: str


def _find_item(equipment: List[Dict[str, Any]], item_id: str) -> Tuple[int, Optional[Dict[str, Any]]]:
    for i, item in enumerate(equipment):
        if item.get("id") == item_id:
            return i, item
    return -1, None

router = APIRouter()


@router.get("/", response_model=CharacterListResponse)
async def list_characters(
    skip: int = 0,
    limit: int = 20,
    session_id: Optional[str] = Query(None, description="Filtrer par session"),
    db: AsyncSession = Depends(get_db),
):
    """Liste tous les personnages avec pagination, filtrage optionnel par session."""
    query = select(Character)
    count_query = select(func.count()).select_from(Character)

    if session_id is not None:
        query = query.where(Character.session_id == session_id)
        count_query = count_query.where(Character.session_id == session_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    result = await db.execute(
        query.order_by(Character.created_at.asc()).offset(skip).limit(limit)
    )
    characters = result.scalars().all()

    return CharacterListResponse(characters=list(characters), total=total)


@router.post("/", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
async def create_character(
    payload: CharacterCreate,
    db: AsyncSession = Depends(get_db),
):
    """Crée un nouveau personnage."""
    data = payload.model_dump()
    if data.get("equipment"):
        data["equipment"] = _resolve_equipment(data["equipment"])
    # Auto-initialiser les emplacements de sorts si non fournis
    if not data.get("spell_slots"):
        data["spell_slots"] = _init_spell_slots(data["char_class"], data["level"])
    character = Character(**data)
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(
    character_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retourne les détails d'un personnage."""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if character is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personnage introuvable")
    return character


@router.put("/{character_id}", response_model=CharacterResponse)
async def update_character(
    character_id: str,
    payload: CharacterUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Met à jour un personnage (champs partiels acceptés)."""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if character is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personnage introuvable")

    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(character, field, value)

    await db.commit()
    await db.refresh(character)
    return character


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(
    character_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Supprime un personnage."""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if character is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personnage introuvable")

    await db.delete(character)
    await db.commit()


# ── Inventory endpoints ─────────────────────────────────────────────────────────


@router.post("/{character_id}/inventory/equip", response_model=CharacterResponse)
async def equip_item(
    character_id: str,
    payload: InventoryActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Équipe ou retire un objet (toggle). Pour les armures, une seule peut être équipée."""
    result = await db.execute(select(Character).where(Character.id == character_id))
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personnage introuvable")

    equipment: List[Dict[str, Any]] = list(char.equipment or [])
    idx, item = _find_item(equipment, payload.item_id)
    if idx == -1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objet introuvable dans l'inventaire")

    new_equipped = not item.get("equipped", False)

    # Si on équipe une armure, retirer les autres armures
    if new_equipped and item.get("category", "") in _ARMOR_CATEGORIES:
        for i, eq in enumerate(equipment):
            if i != idx and eq.get("category", "") in _ARMOR_CATEGORIES:
                equipment[i] = {**eq, "equipped": False}

    equipment[idx] = {**item, "equipped": new_equipped}
    char.equipment = equipment
    await db.commit()
    await db.refresh(char)
    return char


@router.post("/{character_id}/inventory/use", response_model=CharacterResponse)
async def use_item(
    character_id: str,
    payload: InventoryActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Utilise un objet consommable (potion = soin). Décrémente la quantité."""
    result = await db.execute(select(Character).where(Character.id == character_id))
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personnage introuvable")

    equipment: List[Dict[str, Any]] = list(char.equipment or [])
    idx, item = _find_item(equipment, payload.item_id)
    if idx == -1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objet introuvable dans l'inventaire")

    item_id_lower = (item.get("id") or "").lower()
    item_name_lower = (item.get("name_fr") or "").lower()
    is_healing_potion = "potion" in item_id_lower or "potion" in item_name_lower
    if is_healing_potion:
        heal_result = roll("2d4+2")
        new_hp = min(char.hp_max, char.hp_current + heal_result.total)
        char.hp_current = new_hp

    qty = int(item.get("quantity", 1))
    if qty > 1:
        equipment[idx] = {**item, "quantity": qty - 1}
    else:
        equipment.pop(idx)

    char.equipment = equipment
    await db.commit()
    await db.refresh(char)
    return char


@router.post("/{character_id}/inventory/drop", response_model=CharacterResponse)
async def drop_item(
    character_id: str,
    payload: InventoryActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Lâche un objet : le retire définitivement de l'inventaire."""
    result = await db.execute(select(Character).where(Character.id == character_id))
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personnage introuvable")

    equipment: List[Dict[str, Any]] = list(char.equipment or [])
    idx, _ = _find_item(equipment, payload.item_id)
    if idx == -1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objet introuvable dans l'inventaire")

    equipment.pop(idx)
    char.equipment = equipment
    await db.commit()
    await db.refresh(char)
    return char
