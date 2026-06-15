"""Inférence de biome régional à partir des noms/descriptions de nœuds.

Utilisé par ``app.game.gm_response_executor`` pour générer un décor
(``worldmap_builder.build_region_decor``) cohérent quand le MJ crée une
région sans fournir de champ ``decor``.

MIROIR de ``inferRegionBiome`` (frontend/src/composables/useMapDecor.ts:39-64).
Le frontend conserve sa propre copie comme repli quand le backend ne fournit
pas de décor — les deux listes de mots-clés et l'ordre de priorité DOIVENT
rester synchronisés.
"""

from __future__ import annotations

from typing import Literal

RegionBiome = Literal["coastal", "mountain", "desert", "default"]

COASTAL_KEYWORDS: tuple[str, ...] = (
    "rivage",
    "plage",
    "côte",
    "cote",
    "mer",
    "île",
    "ile",
    "baie",
    "port",
    "quai",
    "littoral",
    "grève",
    "greve",
    "anse",
    "falaise",
    "estuaire",
    "beach",
    "coast",
    "shore",
    "sea",
    "island",
    "bay",
    "harbor",
    "harbour",
)
DESERT_KEYWORDS: tuple[str, ...] = (
    "désert",
    "desert",
    "sable",
    "dune",
    "oasis",
    "aride",
    "steppe",
)
MOUNTAIN_KEYWORDS: tuple[str, ...] = (
    "mont",
    "sommet",
    "pic",
    "col",
    "massif",
    "alpin",
    "alpine",
    "crête",
    "crete",
    "mountain",
    "peak",
    "ridge",
    "pass",
    "highland",
)


def infer_region_biome(corpus: str) -> RegionBiome:
    """Infère le biome d'une région depuis un corpus de texte (ids + noms de nœuds).

    Retourne ``"default"`` (forêts) si aucun mot-clé n'est trouvé. Même ordre
    de priorité que la version frontend : côtier > désertique > montagneux > défaut.
    """
    lower = corpus.lower()
    if any(keyword in lower for keyword in COASTAL_KEYWORDS):
        return "coastal"
    if any(keyword in lower for keyword in DESERT_KEYWORDS):
        return "desert"
    if any(keyword in lower for keyword in MOUNTAIN_KEYWORDS):
        return "mountain"
    return "default"
