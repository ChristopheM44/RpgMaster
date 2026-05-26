from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

NodeStatus = Literal["visited", "known", "current", "rumored"]
RegionNodeKind = Literal[
    "settlement",
    "landmark",
    "wilderness",
    "dungeon",
    "crossroads",
    "ruin",
]
CityNodeKind = Literal[
    "district",
    "building",
    "square",
    "gate",
    "docks",
    "temple",
    "tavern",
    "shop",
    "palace",
]
MapNodeKind = Literal[
    "settlement",
    "landmark",
    "wilderness",
    "dungeon",
    "crossroads",
    "ruin",
    "district",
    "building",
    "square",
    "gate",
    "docks",
    "temple",
    "tavern",
    "shop",
    "palace",
]
EdgeKind = Literal[
    "road",
    "path",
    "river",
    "sea_route",
    "secret",
    "street",
    "alley",
]
CoastlineSide = Literal["west", "east", "north", "south"]


class MapNodePosition(BaseModel):
    x: float = Field(default=50)
    y: float = Field(default=50)

    @field_validator("x", "y", mode="before")
    @classmethod
    def clamp_percent(cls, value: Any) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = 50.0
        return max(0.0, min(100.0, parsed))


class MapNode(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    kind: MapNodeKind
    position: MapNodePosition = Field(default_factory=MapNodePosition)
    status: NodeStatus = "known"
    icon: Optional[str] = Field(default=None, max_length=80)
    description: Optional[str] = Field(default=None, max_length=280)
    short_label: Optional[str] = Field(default=None, max_length=40)
    city_id: Optional[str] = Field(default=None, max_length=80)
    scene_ids: list[str] = Field(default_factory=list, max_length=24)

    @field_validator("id", "city_id")
    @classmethod
    def clean_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip()

    @field_validator("name", "icon", "description", "short_label")
    @classmethod
    def clean_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(str(value).split())
        return cleaned or None


class MapEdge(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=80)
    from_: str = Field(alias="from", min_length=1, max_length=80)
    to: str = Field(min_length=1, max_length=80)
    kind: EdgeKind = "road"
    travel_hint: Optional[str] = Field(default=None, max_length=280)
    hidden: bool = False

    @field_validator("id", "from_", "to")
    @classmethod
    def clean_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("travel_hint")
    @classmethod
    def clean_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(str(value).split())
        return cleaned or None


# ───────────────────────── Décor visuel ──────────────────────────────────────
# Décor "set-once" décrit par le MJ à la création d'une carte.
# Toutes les positions sont en coordonnées viewBox SVG 0..100.
# Si absent, le frontend génère un décor procédural seedé sur background_seed.


class ForestSpot(BaseModel):
    """Cercle de végétation sur la carte."""
    model_config = ConfigDict(extra="ignore")

    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
    radius: float = Field(default=3.0, ge=0.5, le=12)
    opacity: float = Field(default=0.4, ge=0, le=1)


class MountainSpot(BaseModel):
    """Triangle de montagne (rendu par le frontend en SVG)."""
    model_config = ConfigDict(extra="ignore")

    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
    height: float = Field(default=5.0, ge=1, le=15)


class Coastline(BaseModel):
    """Polygone côtier (mer ou grand lac) ancré sur un bord de la carte."""
    model_config = ConfigDict(extra="ignore")

    side: CoastlineSide = "west"
    # Liste de points {x, y} (0..100) décrivant le contour terre-mer.
    # Le polygone est refermé automatiquement contre le bord choisi.
    points: list[MapNodePosition] = Field(default_factory=list, max_length=24)


class RiverPath(BaseModel):
    """Cours d'eau (rivière ou ruisseau) traversant la carte."""
    model_config = ConfigDict(extra="ignore")

    # Path SVG en coords 0..100 — ex: "M 0 76 Q 30 80 60 78 T 100 80"
    path: str = Field(min_length=1, max_length=400)
    width: float = Field(default=1.5, ge=0.2, le=6)


class MapDecor(BaseModel):
    """Décor visuel persistant d'une carte (région ou ville).

    Émis une fois par le MJ lors de la création de la carte, puis préservé
    à chaque merge. Le frontend le lit pour rendre forêts, montagnes,
    littoral et rivière. Sémantique du patch : ``None`` ⇒ ne touche pas au
    décor existant ; ``MapDecor()`` (vide) ⇒ efface le décor.
    """
    model_config = ConfigDict(extra="ignore")

    forests: list[ForestSpot] = Field(default_factory=list, max_length=64)
    mountains: list[MountainSpot] = Field(default_factory=list, max_length=24)
    coastline: Optional[Coastline] = None
    river: Optional[RiverPath] = None
    # Paths SVG décoratifs (en coords 0..100) — donnent de la texture
    # sans être des connexions graph réelles.
    decorative_roads: list[str] = Field(default_factory=list, max_length=16)


# ─────────────────────────────────────────────────────────────────────────────


class RegionMap(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default="region", min_length=1, max_length=80)
    name: str = Field(default="Région", min_length=1, max_length=120)
    current_node_id: Optional[str] = Field(default=None, max_length=80)
    nodes: list[MapNode] = Field(default_factory=list, max_length=64)
    edges: list[MapEdge] = Field(default_factory=list, max_length=128)
    background_seed: Optional[str] = Field(default=None, max_length=80)
    decor: Optional[MapDecor] = None
    updated_at: str


class CityMap(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=80)
    region_node_id: str = Field(min_length=1, max_length=80)
    name: str = Field(default="Ville", min_length=1, max_length=120)
    current_node_id: Optional[str] = Field(default=None, max_length=80)
    nodes: list[MapNode] = Field(default_factory=list, max_length=64)
    edges: list[MapEdge] = Field(default_factory=list, max_length=128)
    background_seed: Optional[str] = Field(default=None, max_length=80)
    decor: Optional[MapDecor] = None
    updated_at: str


class RegionMapPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: Optional[str] = Field(default=None, max_length=80)
    name: Optional[str] = Field(default=None, max_length=120)
    current_node_id: Optional[str] = Field(default=None, max_length=80)
    nodes_upsert: list[MapNode] = Field(default_factory=list, max_length=64)
    nodes_remove: list[str] = Field(default_factory=list, max_length=64)
    edges_upsert: list[MapEdge] = Field(default_factory=list, max_length=128)
    edges_remove: list[str] = Field(default_factory=list, max_length=128)
    background_seed: Optional[str] = Field(default=None, max_length=80)
    # None ⇒ préserver le décor existant ; valeur présente ⇒ remplacer.
    decor: Optional[MapDecor] = None


class CityMapPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    city_id: str = Field(min_length=1, max_length=80)
    region_node_id: str = Field(min_length=1, max_length=80)
    name: Optional[str] = Field(default=None, max_length=120)
    current_node_id: Optional[str] = Field(default=None, max_length=80)
    nodes_upsert: list[MapNode] = Field(default_factory=list, max_length=64)
    nodes_remove: list[str] = Field(default_factory=list, max_length=64)
    edges_upsert: list[MapEdge] = Field(default_factory=list, max_length=128)
    edges_remove: list[str] = Field(default_factory=list, max_length=128)
    background_seed: Optional[str] = Field(default=None, max_length=80)
    decor: Optional[MapDecor] = None


class NodeStatusPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scope: Literal["region", "city"]
    city_id: Optional[str] = Field(default=None, max_length=80)
    node_id: str = Field(min_length=1, max_length=80)
    status: NodeStatus
