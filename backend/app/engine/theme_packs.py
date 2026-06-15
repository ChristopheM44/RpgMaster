"""Packs de thèmes — palette d'assets et d'ambiance par défaut pour ``scene_builder``.

Aucune I/O. Chaque pack couvre une valeur de ``SceneThemeName``
(cf. ``app.schemas.scene_spec`` / ``app.game.scene_theme.SCENE_THEMES``) et fournit
des ``asset_key`` valides selon ``SCENE_ASSET_KEYS``
(``app.services.local_map_service``) — la variété de flore d'ambiance (arbres,
buissons, fleurs...) est gérée côté frontend par ``BIOME_3D`` /
``ScatterKind`` à partir de ``scene_theme`` + ``vegetation_density``, donc les
packs n'ont pas besoin de référencer ces assets de scatter.

``ambiance`` et ``vegetation_density`` sont des MIROIRS de
``_THEME_FOG_DENSITY`` / ``_THEME_VEGETATION_DENSITY``
(``app.services.local_map_service``) — modifier les deux ensemble.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemePack:
    """Palette d'assets et d'ambiance par défaut pour un thème de scène."""

    terrain: str
    cover_assets: tuple[str, ...]
    hazard_assets: tuple[str, ...]
    decor_assets: tuple[str, ...]
    cover_label: str
    hazard_label: str
    decor_label: str
    ambiance: dict[str, object]
    vegetation_density: float


THEME_PACKS: dict[str, ThemePack] = {
    "dungeon": ThemePack(
        terrain="stone",
        cover_assets=("prop/pillar", "prop/rubble_large", "prop/crates_stacked"),
        hazard_assets=(),
        decor_assets=("prop/barrel_large", "prop/shelf_small", "prop/statue"),
        cover_label="Bloc de pierre effondré",
        hazard_label="Dalle suspecte",
        decor_label="Débris épars",
        ambiance={"light": "torchlit", "fog_density": 0.25},
        vegetation_density=0.0,
    ),
    "cave": ThemePack(
        terrain="stone",
        cover_assets=("prop/rubble_large", "nature/rock_large_a", "nature/rock_large_b"),
        hazard_assets=(),
        decor_assets=("nature/rock_small_a", "nature/rock_small_b", "prop/obelisk"),
        cover_label="Bloc rocheux effondré",
        hazard_label="Faille suspecte",
        decor_label="Éboulis de pierre",
        ambiance={"light": "torchlit", "fog_density": 0.35},
        vegetation_density=0.0,
    ),
    "forest": ThemePack(
        terrain="grass",
        cover_assets=("nature/rock_large_a", "nature/rock_large_b"),
        hazard_assets=(),
        decor_assets=("nature/rock_small_a", "nature/rock_small_b", "prop/campfire"),
        cover_label="Tronc renversé",
        hazard_label="Fourré de ronces",
        decor_label="Souche moussue",
        ambiance={"light": "day", "fog_density": 0.2},
        vegetation_density=0.8,
    ),
    "plains": ThemePack(
        terrain="grass",
        cover_assets=("nature/rock_large_a", "nature/rock_large_b"),
        hazard_assets=(),
        decor_assets=("nature/rock_small_a", "nature/rock_small_b", "prop/tent"),
        cover_label="Talus herbeux",
        hazard_label="Terrier dissimulé",
        decor_label="Pierre isolée",
        ambiance={"light": "day", "fog_density": 0.15},
        vegetation_density=0.4,
    ),
    "mountain": ThemePack(
        terrain="rock",
        cover_assets=("nature/rock_large_a", "nature/rock_large_b"),
        hazard_assets=(),
        decor_assets=("nature/rock_small_a", "nature/rock_small_b"),
        cover_label="Bloc erratique",
        hazard_label="Pierrier instable",
        decor_label="Cairn de pierres",
        ambiance={"light": "day", "fog_density": 0.25},
        vegetation_density=0.25,
    ),
    "rocky": ThemePack(
        terrain="rock",
        cover_assets=("nature/rock_large_a", "nature/rock_large_b"),
        hazard_assets=(),
        decor_assets=("nature/rock_small_a", "nature/rock_small_b"),
        cover_label="Affleurement rocheux",
        hazard_label="Crevasse étroite",
        decor_label="Roche éclatée",
        ambiance={"light": "day", "fog_density": 0.15},
        vegetation_density=0.25,
    ),
    "desert": ThemePack(
        terrain="sand",
        cover_assets=("nature/rock_large_a", "nature/rock_large_b"),
        hazard_assets=(),
        decor_assets=("nature/rock_small_a", "nature/rock_small_b"),
        cover_label="Dune affaissée",
        hazard_label="Sable mouvant",
        decor_label="Roche érodée",
        ambiance={"light": "day", "fog_density": 0.15},
        vegetation_density=0.15,
    ),
    "beach": ThemePack(
        terrain="sand",
        cover_assets=("nature/rock_large_a", "nature/rock_large_b"),
        hazard_assets=(),
        decor_assets=("nature/rock_small_a", "nature/rock_small_b"),
        cover_label="Rocher couvert d'algues",
        hazard_label="Bassin de marée",
        decor_label="Bois flotté",
        ambiance={"light": "day", "fog_density": 0.15},
        vegetation_density=0.3,
    ),
    "coastal": ThemePack(
        terrain="rock",
        cover_assets=("nature/rock_large_a", "nature/rock_large_b"),
        hazard_assets=(),
        decor_assets=("nature/rock_small_a", "nature/rock_small_b"),
        cover_label="Bloc de falaise",
        hazard_label="Embruns glissants",
        decor_label="Galets épars",
        ambiance={"light": "day", "fog_density": 0.15},
        vegetation_density=0.3,
    ),
    "swamp": ThemePack(
        terrain="mud",
        cover_assets=("nature/rock_large_a", "nature/rock_large_b"),
        hazard_assets=(),
        decor_assets=("nature/rock_small_a", "nature/rock_small_b"),
        cover_label="Souche immergée",
        hazard_label="Vasière profonde",
        decor_label="Roseaux flétris",
        ambiance={"light": "overcast", "fog_density": 0.4},
        vegetation_density=0.6,
    ),
    "city": ThemePack(
        terrain="stone",
        cover_assets=("prop/crates_stacked", "prop/barrel_large"),
        hazard_assets=(),
        decor_assets=("prop/barrel_small", "prop/crates_stacked", "prop/statue"),
        cover_label="Étal renversé",
        hazard_label="Pavé descellé",
        decor_label="Caisses de marchandises",
        ambiance={"light": "day", "fog_density": 0.15},
        vegetation_density=0.05,
    ),
    "wilderness": ThemePack(
        terrain="grass",
        cover_assets=("nature/rock_large_a", "nature/rock_large_b"),
        hazard_assets=(),
        decor_assets=("nature/rock_small_a", "nature/rock_small_b"),
        cover_label="Rocher affleurant",
        hazard_label="Fourré de ronces",
        decor_label="Pierre moussue",
        ambiance={"light": "day", "fog_density": 0.1},
        vegetation_density=0.4,
    ),
    "default": ThemePack(
        terrain="ground",
        cover_assets=("prop/crates_stacked", "prop/barrel_large"),
        hazard_assets=(),
        decor_assets=("prop/crates_stacked", "prop/barrel_small"),
        cover_label="Amas de débris",
        hazard_label="Zone instable",
        decor_label="Détritus",
        ambiance={"light": "day", "fog_density": 0.1},
        vegetation_density=0.1,
    ),
}


def resolve_theme_pack(theme: str, enclosure: str) -> ThemePack:
    """Pack de thème pour ``theme``, avec repli déterministe selon ``enclosure``."""
    pack = THEME_PACKS.get(theme)
    if pack is not None:
        return pack
    if enclosure == "interior":
        return THEME_PACKS["dungeon"]
    return THEME_PACKS["wilderness"]
