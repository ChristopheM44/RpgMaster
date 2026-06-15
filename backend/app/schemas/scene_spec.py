"""Schéma SceneSpec — contrat LLM pour décrire l'intention d'une scène.

Le MJ émet un ``SceneSpec`` (thème, taille, enclos, points d'intérêt, sorties,
intention tactique) — jamais de coordonnées ``col``/``row``. C'est
``app.engine.scene_builder.build_scene`` qui transforme ce spec en géométrie
12x12 déterministe conforme au schéma canonique attendu par
``GMResponseExecutor._normalize_scene_layout``.
"""

from __future__ import annotations

from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Doit rester synchronisé avec app.game.scene_theme.SCENE_THEMES.
SceneThemeName = Literal[
    "forest",
    "beach",
    "coastal",
    "rocky",
    "mountain",
    "dungeon",
    "cave",
    "city",
    "plains",
    "swamp",
    "desert",
]
SceneSize = Literal["small", "medium", "large"]
SceneEnclosure = Literal["interior", "exterior"]
SceneZone = Literal["center", "north", "south", "east", "west", "ne", "nw", "se", "sw"]
SceneDirection = Literal["north", "south", "east", "west"]
SceneFeatureKind = Literal["cover", "hazard", "clue", "loot", "enemy", "npc", "decor"]

_SCENE_THEME_VALUES = frozenset(get_args(SceneThemeName))
_DEFAULT_THEME: SceneThemeName = "dungeon"

# Icônes POI associées à chaque nature de feature (cf. gm_narrate.txt — catégories visuelles).
SCENE_FEATURE_ICONS: dict[str, str] = {
    "cover": "c-half-cover",
    "hazard": "trap-danger",
    "clue": "clue",
    "loot": "chest",
    "enemy": "c-enemy",
    "npc": "npc",
    "decor": "marker",
}


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    return cleaned or None


class SceneFeatureSpec(BaseModel):
    """Point d'intérêt tactique ou narratif à placer dans la scène."""

    model_config = ConfigDict(extra="ignore")

    kind: SceneFeatureKind
    name: str = Field(min_length=1, max_length=80)
    zone: SceneZone = "center"
    note: str | None = Field(default=None, max_length=200)

    @field_validator("name", mode="before")
    @classmethod
    def _clean_name(cls, value: object) -> object:
        cleaned = _clean_text(value)
        return cleaned if cleaned else value

    @field_validator("note", mode="before")
    @classmethod
    def _clean_note(cls, value: object) -> object:
        return _clean_text(value)


class SceneExitSpec(BaseModel):
    """Sortie de la scène — placée sur un bord de grille par le builder."""

    model_config = ConfigDict(extra="ignore")

    label: str = Field(min_length=1, max_length=80)
    direction: SceneDirection
    leads_to: str = Field(default="", max_length=80)
    description: str | None = Field(default=None, max_length=200)
    # Si renseigné, le builder émet placement="embedded" + element_id au lieu
    # de placer la sortie sur une cellule de bord.
    embedded_element: str | None = Field(default=None, max_length=80)

    @field_validator("label", mode="before")
    @classmethod
    def _clean_label(cls, value: object) -> object:
        cleaned = _clean_text(value)
        return cleaned if cleaned else value

    @field_validator("description", mode="before")
    @classmethod
    def _clean_description(cls, value: object) -> object:
        return _clean_text(value)

    @field_validator("leads_to", "embedded_element", mode="before")
    @classmethod
    def _clean_ids(cls, value: object) -> object:
        if value is None:
            return value
        return str(value).strip()


class SceneSpec(BaseModel):
    """Intention de scène — traduite en géométrie par ``scene_builder.build_scene``."""

    model_config = ConfigDict(extra="ignore")

    theme: SceneThemeName = _DEFAULT_THEME
    size: SceneSize = "medium"
    enclosure: SceneEnclosure = "exterior"
    description: str = Field(default="", max_length=600)
    features: list[SceneFeatureSpec] = Field(default_factory=list, max_length=8)
    exits: list[SceneExitSpec] = Field(default_factory=list, max_length=4)
    tactical_intent: str | None = Field(default=None, max_length=240)

    @field_validator("theme", mode="before")
    @classmethod
    def _coerce_theme(cls, value: object) -> str:
        text = (_clean_text(value) or "").lower()
        return text if text in _SCENE_THEME_VALUES else _DEFAULT_THEME

    @field_validator("description", mode="before")
    @classmethod
    def _clean_description(cls, value: object) -> object:
        cleaned = _clean_text(value)
        return cleaned or ""

    @field_validator("tactical_intent", mode="before")
    @classmethod
    def _clean_tactical_intent(cls, value: object) -> object:
        return _clean_text(value)
