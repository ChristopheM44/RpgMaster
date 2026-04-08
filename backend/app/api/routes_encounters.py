"""REST endpoints for encounter management (preset listing + dynamic generation)."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.engine.encounter_builder import BuiltEncounter
from app.services.encounter_service import encounter_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class EncounterEntrySchema(BaseModel):
    monster_id: str
    count: int
    name_fr: str
    cr: float
    xp_each: int
    ac: int
    hp: int
    attack_bonus: int
    damage_notation: str


class BuiltEncounterSchema(BaseModel):
    entries: list[EncounterEntrySchema]
    total_xp_raw: int
    total_xp_adjusted: int
    difficulty: str
    xp_budget: int

    @classmethod
    def from_built(cls, enc: BuiltEncounter) -> BuiltEncounterSchema:
        return cls(
            entries=[
                EncounterEntrySchema(
                    monster_id=e.monster_id,
                    count=e.count,
                    name_fr=e.name_fr,
                    cr=e.cr,
                    xp_each=e.xp_each,
                    ac=e.ac,
                    hp=e.hp,
                    attack_bonus=e.attack_bonus,
                    damage_notation=e.damage_notation,
                )
                for e in enc.entries
            ],
            total_xp_raw=enc.total_xp_raw,
            total_xp_adjusted=enc.total_xp_adjusted,
            difficulty=enc.difficulty,
            xp_budget=enc.xp_budget,
        )


class PresetSummary(BaseModel):
    id: str
    name: str
    description: str
    terrain: str
    difficulty: str
    min_level: int
    max_level: int
    tags: list[str]
    monster_summary: str  # human-readable e.g. "3× Gobelin + 1× Hobgobelin"


def _monster_summary(preset: dict[str, Any]) -> str:
    parts = []
    for slot in preset.get("monsters", []):
        mid = slot["monster_id"]
        count = slot.get("count", 1)
        monster = encounter_service._monsters_by_id.get(mid)
        name = monster.get("name_fr", mid) if monster else mid
        parts.append(f"{count}× {name}")
    return " + ".join(parts) if parts else "?"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[PresetSummary])
async def list_presets(
    min_level: Optional[int] = Query(None, description="Niveau minimum du groupe"),
    max_level: Optional[int] = Query(None, description="Niveau maximum du groupe"),
    terrain: Optional[str] = Query(None, description="Terrain (forest, dungeon, road...)"),
    difficulty: Optional[str] = Query(None, description="Difficulté (easy, medium, hard, deadly)"),
) -> list[PresetSummary]:
    """List available pre-built encounters, with optional filters."""
    # Ensure data is loaded so _monsters_by_id is populated
    encounter_service._ensure_loaded()
    presets = encounter_service.list_presets(
        min_level=min_level,
        max_level=max_level,
        terrain=terrain,
        difficulty=difficulty,
    )
    return [
        PresetSummary(
            id=p["id"],
            name=p["name"],
            description=p["description"],
            terrain=p.get("terrain", "unknown"),
            difficulty=p.get("difficulty", "medium"),
            min_level=p.get("min_level", 1),
            max_level=p.get("max_level", 10),
            tags=p.get("tags", []),
            monster_summary=_monster_summary(p),
        )
        for p in presets
    ]


@router.get("/generate", response_model=BuiltEncounterSchema)
async def generate_encounter(
    party_levels: str = Query(
        "1,1,1,1",
        description="Niveaux des personnages séparés par virgule (ex: 3,3,4,2)",
    ),
    difficulty: str = Query("medium", description="Difficulté cible (easy|medium|hard|deadly)"),
) -> BuiltEncounterSchema:
    """Dynamically generate a balanced encounter for the given party."""
    try:
        levels = [int(x.strip()) for x in party_levels.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="party_levels doit être une liste d'entiers séparés par virgule",
        )

    if not levels:
        raise HTTPException(status_code=422, detail="party_levels ne peut pas être vide")

    valid_difficulties = {"easy", "medium", "hard", "deadly"}
    if difficulty not in valid_difficulties:
        raise HTTPException(
            status_code=422,
            detail=f"difficulty doit être parmi: {', '.join(sorted(valid_difficulties))}",
        )

    encounter = encounter_service.generate(levels, difficulty)
    return BuiltEncounterSchema.from_built(encounter)


@router.get("/{encounter_id}", response_model=BuiltEncounterSchema)
async def get_preset_encounter(encounter_id: str) -> BuiltEncounterSchema:
    """Return a pre-built encounter by id."""
    encounter_service._ensure_loaded()
    encounter = encounter_service.build_from_preset(encounter_id)
    if encounter is None:
        raise HTTPException(status_code=404, detail=f"Encounter '{encounter_id}' introuvable")
    return BuiltEncounterSchema.from_built(encounter)
