"""Scene theme inference shared by opening, layout normalization and migrations."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

SCENE_THEMES = {
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
}

_DESERT_HARD = (
    "desert",
    "deserts",
    "desertique",
    "desertiques",
    "dune",
    "dunes",
    "oasis",
    "aride",
    "arides",
    "aridite",
    "canicule",
    "secheresse",
    "secheresses",
    "sahara",
)
_SAND = ("sable", "sables", "sand")
_COAST_WATER = (
    "mer",
    "ocean",
    "oceanique",
    "sea",
    "shore",
    "coast",
    "coastal",
    "cote",
    "cotes",
    "rivage",
    "rivages",
    "littoral",
    "ecume",
    "vague",
    "vagues",
    "port",
    "ports",
    "quai",
    "quais",
    "baie",
    "ile",
    "island",
    "bay",
    "harbor",
    "harbour",
)
_BEACH = ("plage", "beach", "greve", "galets")
_CITY = (
    "ville",
    "cite",
    "city",
    "street",
    "rue",
    "place",
    "town",
    "marche",
    "market",
    "auberge",
    "taverne",
    "quartier",
)
_DUNGEON = ("dungeon", "donjon", "chamber", "chambre", "salle", "crypt", "crypte")
_CAVE = ("cave", "grotte", "cavern", "caverne")
_SWAMP = ("swamp", "marais", "mud", "boue", "tourbiere")
_MOUNTAIN = ("mountain", "montagne", "peak", "pic", "sommet", "col", "massif")
_ROCKY = ("rock", "roche", "rocher", "rocheux", "cliff", "falaise", "canyon")
_PLAINS = ("plain", "plaine", "grass", "herbe", "field", "champ", "prairie")
_FOREST = ("forest", "foret", "bois", "bosquet", "clairiere", "jungle")


def normalize_theme_text(*parts: Any) -> str:
    """Return lowercase ASCII-ish text with word boundaries preserved."""
    text = " ".join(str(part or "") for part in parts)
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def infer_scene_theme(
    *parts: Any,
    fallback: str = "forest",
) -> str:
    """Infer the most coherent scene theme from canonical text.

    Desert wins over beach when the corpus talks about dunes, oasis, aridity,
    canicule, or bare sand without a coast/sea context.
    """
    corpus = normalize_theme_text(*parts)
    if not corpus:
        return fallback if fallback in SCENE_THEMES else "forest"

    has_desert_hard = _has_any(corpus, _DESERT_HARD)
    has_sand = _has_any(corpus, _SAND)
    has_coast = _has_any(corpus, _COAST_WATER)
    has_beach = _has_any(corpus, _BEACH)

    if _has_any(corpus, _DUNGEON):
        return "dungeon"
    if _has_any(corpus, _CAVE):
        return "cave"
    if _has_any(corpus, _CITY):
        return "city"
    if _has_any(corpus, _SWAMP):
        return "swamp"
    if has_desert_hard or (has_sand and not (has_coast or has_beach)):
        return "desert"
    if has_beach:
        return "beach"
    if has_coast:
        return "coastal"
    if _has_any(corpus, _MOUNTAIN):
        return "mountain"
    if _has_any(corpus, _ROCKY):
        return "rocky"
    if _has_any(corpus, _PLAINS):
        return "plains"
    if _has_any(corpus, _FOREST):
        return "forest"
    return fallback if fallback in SCENE_THEMES else "forest"


def coerce_scene_theme(
    explicit_theme: str | None,
    *context_parts: Any,
    fallback: str = "forest",
) -> str:
    """Keep valid themes unless canonical context exposes a clear contradiction."""
    current = str(explicit_theme or "").strip().lower()
    inferred = infer_scene_theme(*context_parts, fallback=fallback)
    if current not in SCENE_THEMES:
        return inferred
    if current in {"beach", "coastal"} and inferred == "desert":
        return "desert"
    return current


def _has_any(corpus: str, words: tuple[str, ...]) -> bool:
    tokens = set(corpus.split())
    return any(word in tokens for word in words)
