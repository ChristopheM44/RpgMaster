from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes_character import _init_spell_slots, _resolve_equipment
from app.db.database import get_db
from app.models.character import Character
from app.schemas.character import CharacterResponse

router = APIRouter()

_PREGENS_PATH = Path(__file__).parent.parent / "engine" / "srd_data" / "pregens.json"
_PREGENS_DATA: Optional[List[Dict[str, Any]]] = None


def _load_pregens() -> List[Dict[str, Any]]:
    global _PREGENS_DATA
    if _PREGENS_DATA is not None:
        return _PREGENS_DATA
    with _PREGENS_PATH.open(encoding="utf-8") as fh:
        _PREGENS_DATA = json.load(fh)["pregens"]
    return _PREGENS_DATA


# ── Schemas ────────────────────────────────────────────────────────────────────


class PregenTemplate(BaseModel):
    """Vue simplifiée d'un personnage prétiré pour l'affichage UI."""

    class_id: str
    class_name_fr: str
    name: str
    description: str
    species: str
    background: str
    ability_scores: Dict[str, int]
    hp_max: int


class PregenSelectBody(BaseModel):
    session_id: str
    name: Optional[str] = None
    player_name: Optional[str] = None
    is_ai: bool = False


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.get("/pregenerated", response_model=List[PregenTemplate])
async def list_pregenerated():
    """Retourne les 12 templates de personnages prétirés (sans créer en DB)."""
    pregens = _load_pregens()
    return [
        PregenTemplate(
            class_id=p["class_id"],
            class_name_fr=p["class_name_fr"],
            name=p["name"],
            description=p["description"],
            species=p["species"],
            background=p["background"],
            ability_scores=p["ability_scores"],
            hp_max=p["hp_max"],
        )
        for p in pregens
    ]


@router.post(
    "/pregenerated/{class_id}",
    response_model=CharacterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_from_pregen(
    class_id: str,
    body: PregenSelectBody,
    db: AsyncSession = Depends(get_db),
):
    """Instancie un personnage depuis un template prétiré et le sauvegarde en DB."""
    pregens = _load_pregens()
    template = next((p for p in pregens if p["class_id"] == class_id), None)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Personnage prétiré introuvable : {class_id}",
        )

    name = (body.name or "").strip() or template["name"]
    equipment = _resolve_equipment(template["equipment"])
    spell_slots = _init_spell_slots(class_id, 1)

    character = Character(
        name=name,
        player_name=body.player_name,
        is_ai=body.is_ai,
        species=template["species"],
        char_class=class_id,
        level=1,
        background=template["background"],
        ability_scores=template["ability_scores"],
        hp_current=template["hp_max"],
        hp_max=template["hp_max"],
        hp_temp=0,
        equipment=equipment,
        spell_slots=spell_slots,
        known_spells=template["known_spells"],
        conditions=[],
        proficiencies=template["proficiencies"],
        personality={},
        session_id=body.session_id,
    )

    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character
