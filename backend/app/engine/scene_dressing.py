"""Habillage par type de lieu — une bibliothèque a des rayonnages, une taverne un comptoir.

Aucune I/O. ``dress_scene`` reconnaît le type de lieu (bibliothèque, taverne, temple,
crypte, forge, réserve, dortoir, chambre, salle du trône, serre ; campement et marché
en extérieur) et renvoie des éléments de mobilier déterministes (graine = scene_id) :
pièces murales (rayonnages, comptoir, lits…) collées aux murs et tournées vers la
pièce, pièces centrales (tables, colonnes, sarcophages…) avec allées dégagées.

Invariants (testés) :
- jamais sur une sortie, un repère (POI), une position de groupe ni un élément existant ;
- sorties, accès et repères gardent une case libre autour d'eux ;
- toutes les cases importantes (sorties, POI, groupe) restent reliées entre elles :
  une pièce qui couperait un passage est abandonnée ;
- idempotent : ids ``dress_*`` ; une scène déjà habillée n'est pas rehabillée.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from math import ceil
from typing import Any, Literal

from app.engine.prop_catalog import match_prop, match_tint, normalize_words
from app.engine.scene_primitives import seed_int

DRESSING_ID_PREFIX = "dress_"

Slot = Literal["wall", "far_wall", "center", "corner", "beside"]


@dataclass(frozen=True)
class Piece:
    name: str
    asset_key: str
    kind: str
    slot: Slot
    # Pièce murale : longueur le long du mur et profondeur vers la pièce (cases,
    # fractions admises : 0,6 = rayonnage plaqué ; 2 = lit tête au mur).
    # Pièce centrale : empreinte (col × row).
    length: int = 1
    depth: float = 1
    count: int = 1
    opaque: bool = False
    tinted: bool = False
    # Slot « beside » : collée à une pièce déjà posée de ce nom (chaise ↔ table).
    anchor: str | None = None


@dataclass(frozen=True)
class PlaceType:
    id: str
    keywords: tuple[str, ...]
    interior: bool
    pieces: tuple[Piece, ...]


PLACE_TYPES: tuple[PlaceType, ...] = (
    PlaceType(
        "library",
        ("biblioth", "archive", "scriptorium", "rayonnage", "grimoire", "lutrin", "library"),
        True,
        (
            Piece(
                "Rayonnage de livres",
                "proc/bookcase",
                "furniture",
                "wall",
                2,
                0.6,
                count=6,
                opaque=True,
            ),
            Piece("Table de lecture", "prop/table_long", "furniture", "center", 2, 1, count=2),
            Piece(
                "Chaise", "prop/chair", "furniture", "beside", count=3, anchor="Table de lecture"
            ),
        ),
    ),
    PlaceType(
        "tavern",
        ("taverne", "auberge", "estaminet", "cabaret", "gargote", "tavern", "inn "),
        True,
        (
            Piece("Comptoir", "prop/table_long", "furniture", "far_wall", 3, 0.9),
            Piece("Tonnelet", "prop/keg", "furniture", "wall", count=2),
            Piece("Tonneau", "prop/barrel_small", "furniture", "corner", count=2),
            Piece("Table", "prop/table_small", "furniture", "center", count=3),
            Piece("Tabouret", "prop/stool", "furniture", "beside", count=4, anchor="Table"),
        ),
    ),
    PlaceType(
        "temple",
        (
            "temple",
            "chapelle",
            "sanctuaire",
            "eglise",
            "cathedrale",
            "oratoire",
            "monastere",
            "abbaye",
            "shrine",
        ),
        True,
        (
            Piece("Autel", "proc/altar", "furniture", "far_wall", 2),
            Piece("Colonne", "prop/pillar", "cover", "center", count=4, opaque=True),
            Piece("Statue votive", "prop/statue", "decor", "corner", count=2),
            Piece("Banc de prière", "prop/chair", "furniture", "center", count=2),
        ),
    ),
    PlaceType(
        "crypt",
        (
            "crypte",
            "caveau",
            "ossuaire",
            "catacombe",
            "mausolee",
            "necropole",
            "sepulcre",
            "crypt",
        ),
        True,
        (
            Piece("Sarcophage", "proc/sarcophagus", "furniture", "center", 1, 2, count=3),
            Piece("Pilier", "prop/pillar", "cover", "center", count=2, opaque=True),
            Piece("Urne funéraire", "prop/pot", "decor", "wall", count=3),
        ),
    ),
    PlaceType(
        "forge",
        ("forge", "fonderie", "smithy", "forgeron"),
        True,
        (
            Piece("Enclume", "proc/anvil", "furniture", "center"),
            Piece("Établi", "prop/table_long", "furniture", "wall", 2, 0.9),
            Piece("Foyer de forge", "prop/campfire", "furniture", "far_wall"),
            Piece("Tonneau", "prop/barrel_small", "furniture", "corner", count=2),
        ),
    ),
    PlaceType(
        "storage",
        (
            "entrepot",
            "cellier",
            "reserve ",
            "reserves ",
            "grenier",
            "remise",
            "hangar",
            "warehouse",
            "cellar",
            "storeroom",
        ),
        True,
        (
            Piece("Caisses empilées", "prop/crates_stacked", "cover", "wall", count=3, opaque=True),
            Piece("Tonneau", "prop/barrel_large", "cover", "corner", count=3),
            Piece("Étagère", "prop/shelf_large", "furniture", "wall", 2, 0.5, count=2),
        ),
    ),
    PlaceType(
        "barracks",
        ("caserne", "dortoir", "chambree", "corps de garde", "barracks"),
        True,
        (
            Piece("Couchette", "prop/bed_frame", "furniture", "wall", 1, 2, count=4),
            Piece("Coffre", "prop/chest", "furniture", "wall", count=2),
            Piece("Table", "prop/table_medium", "furniture", "center"),
            Piece("Tabouret", "prop/stool", "furniture", "beside", count=2, anchor="Table"),
        ),
    ),
    PlaceType(
        "bedroom",
        ("chambre", "alcove", "bedroom"),
        True,
        (
            Piece("Lit", "prop/bed_frame", "furniture", "wall", 1, 2),
            Piece("Armoire", "proc/bookcase", "furniture", "wall", 1, 0.6, opaque=True),
            Piece("Coffre", "prop/chest", "furniture", "wall"),
            Piece("Petite table", "prop/table_small", "furniture", "corner"),
        ),
    ),
    PlaceType(
        "throne",
        ("salle du trone", "trone", "salle d audience", "throne"),
        True,
        (
            Piece("Trône", "prop/chair", "furniture", "far_wall"),
            Piece("Colonne", "prop/pillar", "cover", "center", count=4, opaque=True),
            Piece("Statue", "prop/statue", "decor", "corner", count=2),
        ),
    ),
    PlaceType(
        "garden",
        ("jardin", "serre", "verger", "garden", "greenhouse"),
        True,
        (
            Piece(
                "Arbre", "nature/tree_dark", "decor", "corner", count=4, opaque=True, tinted=True
            ),
            Piece("Buisson", "nature/bush", "decor", "wall", count=4, tinted=True),
        ),
    ),
    PlaceType(
        "camp",
        ("campement", "bivouac", "camp "),
        False,
        (
            Piece("Tente", "prop/tent", "furniture", "corner", count=2, opaque=True),
            Piece("Feu de camp", "prop/campfire", "furniture", "center"),
            Piece("Rondin", "nature/log", "decor", "center", count=2),
            Piece("Caisses", "prop/crates_stacked", "cover", "wall"),
        ),
    ),
    PlaceType(
        "market",
        ("marche ", "place du marche", "bazar", "foire", "souk", "market"),
        False,
        (
            Piece("Étal", "prop/table_medium", "furniture", "center", 2, 1, count=3),
            Piece("Caisses de marchandises", "prop/crates_stacked", "cover", "center", count=2),
            Piece("Tonneau", "prop/barrel_small", "cover", "corner", count=2),
        ),
    ),
)

_PLACE_BY_ID = {place.id: place for place in PLACE_TYPES}

# Poids des sources de texte : la description et le terrain décrivent le lieu ;
# un repère ou un meuble aussi ; une sortie peut nommer un AUTRE lieu.
_WEIGHT_DESCRIPTION = 3
_WEIGHT_CONTENT = 2
_WEIGHT_EXIT = 1
_MIN_SCORE = 2
# Lieu déjà meublé par le MJ (≥ N meubles du même registre) : on n'en rajoute pas.
_ALREADY_FURNISHED = 3

# Kinds dont la case est un accès : on garde ses abords libres.
_ACCESS_KINDS = {"door", "stairs", "window"}

Cell = tuple[int, int]


def is_dressed(layout: dict[str, Any]) -> bool:
    return any(
        isinstance(element, dict) and str(element.get("id") or "").startswith(DRESSING_ID_PREFIX)
        for element in layout.get("elements") or []
    )


def detect_place_type(layout: dict[str, Any], *, interior: bool) -> str | None:
    """Type de lieu le plus probable (pondéré par la source du texte), sinon ``None``."""
    sources: list[tuple[int, Any]] = [
        (_WEIGHT_DESCRIPTION, layout.get("description")),
        (_WEIGHT_DESCRIPTION, layout.get("terrain")),
        (_WEIGHT_DESCRIPTION, layout.get("title")),
    ]
    for poi in layout.get("pois") or []:
        if isinstance(poi, dict):
            sources.append((_WEIGHT_CONTENT, poi.get("name")))
    for element in layout.get("elements") or []:
        if not isinstance(element, dict):
            continue
        weight = _WEIGHT_EXIT if element.get("kind") in _ACCESS_KINDS else _WEIGHT_CONTENT
        sources.append((weight, element.get("name")))
    for exit_ in layout.get("exits") or []:
        if isinstance(exit_, dict):
            sources.append((_WEIGHT_EXIT, exit_.get("label")))

    scores: dict[str, int] = {}
    for weight, text in sources:
        words = normalize_words(str(text or ""))
        for place in PLACE_TYPES:
            if place.interior != interior:
                continue
            if any(f" {keyword}" in words for keyword in place.keywords):
                scores[place.id] = scores.get(place.id, 0) + weight
    if not scores:
        return None
    best = max(PLACE_TYPES, key=lambda place: scores.get(place.id, 0))
    return best.id if scores.get(best.id, 0) >= _MIN_SCORE else None


def dress_scene(
    layout: dict[str, Any],
    *,
    interior: bool,
    occupied: set[Cell],
    access_cells: set[Cell],
    blocking: set[Cell],
) -> list[dict[str, Any]]:
    """Éléments d'habillage pour ``layout`` (liste vide si lieu non reconnu).

    ``occupied`` : cases déjà prises par un élément ; ``access_cells`` : cases de
    portes/escaliers ; ``blocking`` : cases qui bloquent déjà le déplacement.
    """
    if is_dressed(layout):
        return []
    place_id = detect_place_type(layout, interior=interior)
    if place_id is None:
        return []
    place = _PLACE_BY_ID[place_id]
    if _furnishing_count(layout, place) >= _ALREADY_FURNISHED:
        return []
    cols = int(layout.get("cols") or 12)
    rows = int(layout.get("rows") or 12)
    if cols < 6 or rows < 6:
        return []

    rng = random.Random(seed_int(f"dressing|{layout.get('scene_id') or ''}|{place_id}"))
    important = _important_cells(layout, cols, rows)
    reserved = _reserved_cells(important, access_cells, cols, rows)
    if not layout.get("party_positions"):
        # Sans position de groupe, le client aligne les héros sur la rangée centrale.
        reserved |= {(col, rows // 2) for col in range(cols)}
    taken = set(occupied) | set(important)
    blocked = set(blocking)
    entrance = _entrance_side(layout, cols, rows)
    tint = match_tint(_tint_corpus(layout))

    placer = _Placer(cols, rows, taken, reserved, blocked, important, rng)
    elements: list[dict[str, Any]] = []
    for piece in place.pieces:
        for _ in range(piece.count):
            placed = placer.place(piece, entrance)
            if placed is None:
                break
            geometry, facing = placed
            element: dict[str, Any] = {
                "id": f"{DRESSING_ID_PREFIX}{len(elements) + 1}",
                "name": piece.name,
                "kind": piece.kind,
                "geometry": geometry,
                "blocks_movement": True,
                "opaque": piece.opaque,
                "interactive": False,
                "asset_key": piece.asset_key,
            }
            if facing:
                element["facing"] = facing
            if piece.tinted and tint:
                element["tint"] = tint
            elements.append(element)
    return elements


def _furnishing_count(layout: dict[str, Any], place: PlaceType) -> int:
    keys = {piece.asset_key for piece in place.pieces}
    return sum(
        1
        for element in layout.get("elements") or []
        if isinstance(element, dict)
        and (element.get("asset_key") in keys or match_prop(str(element.get("name") or "")) in keys)
    )


# ─── Placement ───────────────────────────────────────────────────────────────


class _Placer:
    def __init__(
        self,
        cols: int,
        rows: int,
        taken: set[Cell],
        reserved: set[Cell],
        blocked: set[Cell],
        important: set[Cell],
        rng: random.Random,
    ) -> None:
        self.cols = cols
        self.rows = rows
        self.taken = taken
        self.reserved = reserved
        self.blocked = blocked
        self.important = important
        self.rng = rng
        # Une case de marge autour de chaque pièce posée : allées dégagées.
        self.margin: set[Cell] = set()
        self.cells_by_name: dict[str, list[Cell]] = {}
        # Cases importantes déjà reliées avant habillage : elles doivent le rester.
        self.baseline = self._reachable_important(self.blocked)

    def place(self, piece: Piece, entrance: str | None) -> tuple[dict[str, Any], str | None] | None:
        for cells, geometry, facing in self._candidates(piece, entrance):
            if not self._fits(cells, use_margin=piece.slot != "beside"):
                continue
            if not self._keeps_connectivity(cells):
                continue
            self.taken.update(cells)
            self.blocked.update(cells)
            self.margin.update(_ring(cells, self.cols, self.rows))
            self.cells_by_name.setdefault(piece.name, []).extend(cells)
            return geometry, facing
        return None

    def _fits(self, cells: list[Cell], *, use_margin: bool) -> bool:
        return all(
            0 <= col < self.cols
            and 0 <= row < self.rows
            and (col, row) not in self.taken
            and (col, row) not in self.reserved
            and (not use_margin or (col, row) not in self.margin)
            for col, row in cells
        )

    def _reachable_important(self, blocked: set[Cell]) -> set[Cell]:
        if not self.important:
            return set()
        # Une case importante occupée (couvert d'un POI) reste une destination.
        passable_blocked = blocked - self.important
        start = min(self.important)
        return self.important & _flood(start, passable_blocked, self.cols, self.rows)

    def _keeps_connectivity(self, cells: list[Cell]) -> bool:
        if len(self.important) < 2:
            return True
        return self.baseline <= self._reachable_important(self.blocked | set(cells))

    def _candidates(self, piece: Piece, entrance: str | None):
        if piece.slot in ("wall", "far_wall"):
            sides = ["north", "south", "west", "east"]
            if piece.slot == "far_wall":
                far = _OPPOSITE.get(entrance or "", "north")
                sides = [far]
            else:
                self.rng.shuffle(sides)
            slots = []
            for side in sides:
                along = self.cols if side in ("north", "south") else self.rows
                starts = list(range(1, along - piece.length))
                if piece.slot == "far_wall":
                    middle = (along - piece.length) / 2
                    starts.sort(key=lambda start: abs(start - middle))
                else:
                    self.rng.shuffle(starts)
                slots.extend((side, start) for start in starts)
            if piece.slot == "wall":
                self.rng.shuffle(slots)
            for side, start in slots:
                yield _wall_slot(side, start, piece, self.cols, self.rows)
            return
        if piece.slot == "beside":
            anchor_cells = set(self.cells_by_name.get(piece.anchor or "", []))
            # Case voisine → face tournée vers la pièce d'ancrage (chaise vers la table).
            options: dict[Cell, str] = {}
            for col, row in sorted(anchor_cells):
                for (dc, dr), facing in _NEIGHBOR_FACING:
                    cell = (col - dc, row - dr)
                    if cell not in anchor_cells:
                        options.setdefault(cell, facing)
            ordered = sorted(options)
            self.rng.shuffle(ordered)
            for cell in ordered:
                yield [cell], _rect_geometry(cell[0], cell[1], 1, 1, inset=0.2), options[cell]
            return
        if piece.slot == "corner":
            corners = [
                (1, 1),
                (self.cols - 2, 1),
                (1, self.rows - 2),
                (self.cols - 2, self.rows - 2),
            ]
            self.rng.shuffle(corners)
            for col, row in corners:
                for dc, dr in ((0, 0), (1, 0), (0, 1), (-1, 0), (0, -1)):
                    cell = (col + dc, row + dr)
                    yield [cell], _rect_geometry(cell[0], cell[1], 1, 1, inset=0.1), None
            return
        # Centre : au moins 2 cases des murs, ordre mélangé (déterministe).
        width, height = piece.length, piece.depth
        origins = [
            (col, row)
            for row in range(2, self.rows - 1 - height)
            for col in range(2, self.cols - 1 - width)
        ]
        self.rng.shuffle(origins)
        for col, row in origins:
            cells = [(col + dc, row + dr) for dr in range(height) for dc in range(width)]
            yield cells, _rect_geometry(col, row, width, height, inset=0.08), None


_OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}
# (décalage vers la pièce d'ancrage, face correspondante) — ligne +1 = sud.
_NEIGHBOR_FACING: tuple[tuple[tuple[int, int], str], ...] = (
    ((1, 0), "east"),
    ((-1, 0), "west"),
    ((0, 1), "south"),
    ((0, -1), "north"),
)
# Face de la pièce murale : vers l'intérieur de la pièce.
_FACING_FROM_WALL = {"north": "south", "south": "north", "west": "east", "east": "west"}


def _wall_slot(
    side: str, start: int, piece: Piece, cols: int, rows: int
) -> tuple[list[Cell], dict[str, Any], str]:
    """Pièce plaquée contre ``side`` : ``length`` cases le long du mur, ``depth`` vers la pièce."""
    length = piece.length
    inset = 0.05
    reach = max(1, ceil(piece.depth))
    thickness = min(piece.depth, reach - 2 * inset)
    span = length - 2 * inset
    if side == "north":
        cells = [(start + i, d) for i in range(length) for d in range(reach)]
        geometry = _rect(start + inset, inset, span, thickness)
    elif side == "south":
        cells = [(start + i, rows - 1 - d) for i in range(length) for d in range(reach)]
        geometry = _rect(start + inset, rows - inset - thickness, span, thickness)
    elif side == "west":
        cells = [(d, start + i) for i in range(length) for d in range(reach)]
        geometry = _rect(inset, start + inset, thickness, span)
    else:
        cells = [(cols - 1 - d, start + i) for i in range(length) for d in range(reach)]
        geometry = _rect(cols - inset - thickness, start + inset, thickness, span)
    return cells, geometry, _FACING_FROM_WALL[side]


def _rect_geometry(col: int, row: int, width: int, height: int, *, inset: float) -> dict[str, Any]:
    return _rect(col + inset, row + inset, width - 2 * inset, height - 2 * inset)


def _rect(col: float, row: float, width: float, height: float) -> dict[str, Any]:
    return {
        "type": "rect",
        "col": round(col, 3),
        "row": round(row, 3),
        "width": round(width, 3),
        "height": round(height, 3),
    }


def _ring(cells: list[Cell], cols: int, rows: int) -> set[Cell]:
    ring: set[Cell] = set()
    for col, row in cells:
        for dc in (-1, 0, 1):
            for dr in (-1, 0, 1):
                cell = (col + dc, row + dr)
                if 0 <= cell[0] < cols and 0 <= cell[1] < rows:
                    ring.add(cell)
    return ring


def _flood(start: Cell, blocked: set[Cell], cols: int, rows: int) -> set[Cell]:
    seen = {start}
    queue = deque([start])
    while queue:
        col, row = queue.popleft()
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            cell = (col + dc, row + dr)
            if (
                0 <= cell[0] < cols
                and 0 <= cell[1] < rows
                and cell not in seen
                and cell not in blocked
            ):
                seen.add(cell)
                queue.append(cell)
    return seen


def _cell_of(raw: Any, cols: int, rows: int) -> Cell | None:
    if not isinstance(raw, dict):
        return None
    try:
        col, row = int(raw.get("col")), int(raw.get("row"))
    except (TypeError, ValueError):
        return None
    if 0 <= col < cols and 0 <= row < rows:
        return (col, row)
    return None


def _important_cells(layout: dict[str, Any], cols: int, rows: int) -> set[Cell]:
    cells: set[Cell] = set()
    for collection in ("pois", "exits"):
        for item in layout.get(collection) or []:
            if isinstance(item, dict):
                cell = _cell_of(item.get("position"), cols, rows)
                if cell:
                    cells.add(cell)
    positions = layout.get("party_positions")
    if isinstance(positions, dict):
        for raw in positions.values():
            cell = _cell_of(raw, cols, rows)
            if cell:
                cells.add(cell)
    return cells


def _reserved_cells(
    important: set[Cell], access_cells: set[Cell], cols: int, rows: int
) -> set[Cell]:
    reserved: set[Cell] = set()
    for cell in important | access_cells:
        reserved |= _ring([cell], cols, rows)
    return reserved


def _entrance_side(layout: dict[str, Any], cols: int, rows: int) -> str | None:
    """Bord de l'accès d'arrivée (ou de la première sortie) : l'autel fait face."""
    exits = [exit_ for exit_ in layout.get("exits") or [] if isinstance(exit_, dict)]
    arrival = layout.get("arrival")
    if isinstance(arrival, dict):
        exits.sort(key=lambda exit_: exit_.get("id") != arrival.get("exit_id"))
    for exit_ in exits:
        cell = _cell_of(exit_.get("position"), cols, rows)
        if cell is None:
            continue
        col, row = cell
        distances = {"north": row, "south": rows - 1 - row, "west": col, "east": cols - 1 - col}
        return min(distances, key=lambda side: distances[side])
    return None


def _tint_corpus(layout: dict[str, Any]) -> str:
    parts: list[Any] = [layout.get("description")]
    parts.extend(poi.get("name") for poi in layout.get("pois") or [] if isinstance(poi, dict))
    parts.extend(
        element.get("name")
        for element in layout.get("elements") or []
        if isinstance(element, dict) and element.get("kind") not in {"wall", "door", "stairs"}
    )
    return " ".join(str(part or "") for part in parts)
