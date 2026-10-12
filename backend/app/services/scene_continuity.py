"""Continuité spatiale entre deux scènes locales.

Quand le groupe quitte une scène par une sortie, la scène d'arrivée doit en
garder la trace : on arrive par le bord OPPOSÉ (sortie nord → arrivée sud), au
sens vertical INVERSÉ (descendre un escalier → arriver au pied d'un escalier
qui remonte), et le groupe apparaît à côté de cet accès.

Fonctions pures (aucune I/O), appliquées en un point unique —
``GMResponseExecutor._apply_scene_layout`` — par lequel passent les quatre
producteurs de carte (LLM ``scene_layout``, ``scene_builder``, donjon,
scène de repli du pipeline).

En deux temps, car la normalisation reconstruit le layout :
1. ``prepare_arrival`` (layout BRUT) : repère la sortie de départ, place ou crée
   la sortie retour, fixe facing / vertical_direction / kind.
2. ``finalize_arrival`` (layout NORMALISÉ) : pose ``layout["arrival"]`` et place
   le groupe à côté de l'accès.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.services import local_map_service as lms

PENDING_DEPARTURE_KEY = "pending_departure"

OPPOSITE_FACING = {"north": "south", "south": "north", "east": "west", "west": "east"}
INVERSE_VERTICAL = {"up": "down", "down": "up", "level": "level"}
# Pas vers l'intérieur de la carte depuis un bord (col, row).
_INWARD_STEP = {"north": (0, 1), "south": (0, -1), "west": (1, 0), "east": (-1, 0)}


def slug(value: Any) -> str:
    ascii_text = (
        unicodedata.normalize("NFKD", str(value or "").strip().lower())
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")


def _dims(scene: dict[str, Any]) -> tuple[int, int]:
    def _int(value: Any) -> int:
        try:
            return max(3, min(24, int(value)))
        except (TypeError, ValueError):
            return 12

    return _int(scene.get("cols", 12)), _int(scene.get("rows", 12))


def _exits(scene: dict[str, Any]) -> list[dict[str, Any]]:
    return [exit_ for exit_ in scene.get("exits") or [] if isinstance(exit_, dict)]


def _match_by_target(exits: list[dict[str, Any]], target_id: Any) -> dict[str, Any] | None:
    target = slug(target_id)
    if not target:
        return None
    for exit_ in exits:
        if slug(exit_.get("leads_to")) == target:
            return exit_
    for exit_ in exits:
        leads = slug(exit_.get("leads_to"))
        if len(leads) >= 4 and (leads in target or target in leads):
            return exit_
    return None


def find_departure_exit(
    old_scene: dict[str, Any],
    new_scene_id: Any,
    pending: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Sortie empruntée dans l'ancienne scène.

    Priorité au départ mémorisé au moment du voyage (clic sur une sortie ou
    texte reconnu), sinon correspondance ``leads_to`` ↔ id de la nouvelle scène.
    Voyage en texte libre sans correspondance : ``None`` (aucune contrainte).
    """
    exits = _exits(old_scene)
    if isinstance(pending, dict) and pending.get("from_scene_id") == old_scene.get("scene_id"):
        for exit_ in exits:
            if exit_.get("id") == pending.get("exit_id"):
                return exit_
    return _match_by_target(exits, new_scene_id)


def departure_orientation(
    old_scene: dict[str, Any],
    exit_: dict[str, Any],
) -> tuple[str | None, str]:
    """(facing, vertical_direction) de la sortie de départ, élément d'accès d'abord."""
    cols, rows = _dims(old_scene)
    element_id = exit_.get("element_id")
    element = next(
        (
            item
            for item in old_scene.get("elements") or []
            if isinstance(item, dict) and element_id and item.get("id") == element_id
        ),
        None,
    )
    # Une sortie de bord s'ouvre sur SON bord, quoi qu'en dise une valeur stockée
    # (scènes sauvées avant la correction de l'inférence, hint LLM incohérent).
    position = exit_.get("position")
    borders = lms.border_facings(position, cols, rows) if isinstance(position, dict) else []
    facing = (element or {}).get("facing") or lms.infer_exit_facing(exit_, cols, rows)
    if borders and facing not in borders:
        facing = lms.infer_exit_facing({**exit_, "facing": None}, cols, rows)
    if facing not in OPPOSITE_FACING:
        facing = None
    vertical = (element or {}).get("vertical_direction") or exit_.get("vertical_direction")
    if vertical not in INVERSE_VERTICAL:
        corpus = lms._exit_corpus(exit_)
        is_stairs = (element or {}).get("kind") == "stairs" or lms._exit_access_kind(corpus) == (
            "stairs"
        )
        vertical = lms.infer_vertical_direction(corpus) if is_stairs else "level"
    return facing, vertical


def _edge_position(facing: str, along: int, cols: int, rows: int) -> dict[str, int]:
    if facing in {"north", "south"}:
        col = max(1, min(cols - 2, along))
        return {"col": col, "row": 0 if facing == "north" else rows - 1}
    row = max(1, min(rows - 2, along))
    return {"col": 0 if facing == "west" else cols - 1, "row": row}


def _on_edge(position: Any, facing: str, cols: int, rows: int) -> bool:
    if not isinstance(position, dict):
        return False
    return facing in lms.border_facings(position, cols, rows)


def prepare_arrival(
    old_scene: Any,
    raw_layout: dict[str, Any],
    pending: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Ajuste la sortie retour du layout BRUT ; renvoie la méta d'arrivée ou ``None``."""
    if not isinstance(old_scene, dict) or not isinstance(raw_layout, dict):
        return None
    old_id = old_scene.get("scene_id")
    new_id = raw_layout.get("scene_id")
    if not old_id or (new_id and slug(new_id) == slug(old_id)):
        return None
    departure = find_departure_exit(old_scene, new_id, pending)
    if departure is None:
        return None

    facing, vertical = departure_orientation(old_scene, departure)
    arrival_facing = OPPOSITE_FACING.get(facing or "")
    arrival_vertical = INVERSE_VERTICAL.get(vertical, "level")
    cols, rows = _dims(raw_layout)

    exits = raw_layout.setdefault("exits", [])
    if not isinstance(exits, list):
        exits = raw_layout["exits"] = []
    arrival = _match_by_target(_exits(raw_layout), old_id)
    if arrival is None:
        arrival = {
            "id": "exit_retour",
            "label": {"up": "Remonter", "down": "Redescendre"}.get(
                arrival_vertical, "Revenir sur ses pas"
            ),
            "leads_to": str(old_id),
            "description": "Le chemin par lequel le groupe est arrivé.",
        }
        if any(isinstance(e, dict) and e.get("id") == "exit_retour" for e in exits):
            arrival["id"] = f"exit_retour_{slug(old_id)[:24]}"
        exits.append(arrival)

    if arrival_facing:
        if not _on_edge(arrival.get("position"), arrival_facing, cols, rows):
            departure_pos = departure.get("position") or {}
            along_key = "col" if arrival_facing in {"north", "south"} else "row"
            default_along = (cols if along_key == "col" else rows) // 2
            try:
                along = int(departure_pos.get(along_key, default_along))
            except (TypeError, ValueError):
                along = default_along
            arrival["position"] = _edge_position(arrival_facing, along, cols, rows)
            # L'ancien accès ne correspond plus : il sera recréé au bon endroit.
            _drop_stale_access(raw_layout, arrival.pop("element_id", None))
        arrival["placement"] = "edge"
        arrival["facing"] = arrival_facing
    elif not isinstance(arrival.get("position"), dict):
        arrival["position"] = {"col": cols // 2, "row": rows - 1}
        arrival["placement"] = "edge"

    if arrival_vertical in {"up", "down"}:
        arrival["vertical_direction"] = arrival_vertical
        arrival["kind"] = "stairs"

    return {
        "exit_id": str(arrival.get("id") or ""),
        "from_scene_id": str(old_id),
        "via_exit_id": str(departure.get("id") or ""),
        "facing": arrival_facing,
        "vertical_direction": arrival_vertical,
    }


# Murs d'enceinte générés par enrich_scene_layout (et leurs segments découpés).
_AUTO_BOUNDARY_WALL_RE = re.compile(r"^wall_(?:north|south|east|west)(?:_seg_\d+)?$|^wall_corner_")


def _drop_stale_access(raw_layout: dict[str, Any], element_id: Any) -> None:
    """Retire l'accès orphelin d'une sortie déplacée (layout déjà enrichi en amont).

    Certains producteurs (salles de donjon) enrichissent avant
    ``_apply_scene_layout`` : la porte/l'escalier de l'ancienne position et la
    brèche du mur resteraient sinon en place. Les murs d'enceinte automatiques
    sont retirés pour être reconstruits avec la bonne ouverture.
    """
    elements = raw_layout.get("elements")
    if not isinstance(elements, list) or not elements:
        return
    linked = {
        str(item.get("element_id"))
        for key in ("pois", "exits")
        for item in raw_layout.get(key) or []
        if isinstance(item, dict) and item.get("element_id")
    }
    kept = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        element_key = str(element.get("id") or "")
        if (
            element_id
            and element_key == str(element_id)
            and element.get("kind") in {"door", "stairs"}
            and element_key not in linked
        ):
            continue
        if _AUTO_BOUNDARY_WALL_RE.match(element_key):
            continue
        kept.append(element)
    raw_layout["elements"] = kept


def finalize_arrival(
    layout: dict[str, Any],
    arrival: dict[str, Any] | None,
    old_scene: Any = None,
    party_ids: list[str] | None = None,
) -> None:
    """Pose ``layout["arrival"]`` et regroupe le groupe à côté de l'accès d'arrivée.

    Membres placés : ceux du layout, sinon de l'ancienne scène, sinon ``party_ids``.
    """
    if not arrival or not isinstance(layout, dict):
        return
    exit_ = next((e for e in _exits(layout) if e.get("id") == arrival.get("exit_id")), None)
    if exit_ is None:
        return
    layout["arrival"] = dict(arrival)

    members = list((layout.get("party_positions") or {}).keys())
    if not members and isinstance(old_scene, dict):
        members = list((old_scene.get("party_positions") or {}).keys())
    if not members:
        members = [str(char_id) for char_id in party_ids or []]
    if not members:
        return
    cols, rows = _dims(layout)
    position = exit_.get("position") or {}
    try:
        start_col = int(position.get("col", cols // 2))
        start_row = int(position.get("row", rows // 2))
    except (TypeError, ValueError):
        return
    step = _INWARD_STEP.get(str(arrival.get("facing") or ""), (0, 0))
    origin = (start_col + step[0], start_row + step[1])

    blocked = _blocked_cells(layout, cols, rows)
    spots = _nearest_free_cells(origin, blocked, cols, rows, len(members))
    positions = dict(layout.get("party_positions") or {})
    for char_id, (col, row) in zip(members, spots, strict=False):
        positions[char_id] = {"col": col, "row": row}
    layout["party_positions"] = positions


def _blocked_cells(layout: dict[str, Any], cols: int, rows: int) -> set[tuple[int, int]]:
    blocked: set[tuple[int, int]] = set()
    for element in layout.get("elements") or []:
        if not isinstance(element, dict):
            continue
        if element.get("blocks_movement") or element.get("kind") == "stairs":
            for cell in lms.element_grid_cells(element, cols, rows):
                blocked.add((int(cell["col"]), int(cell["row"])))
    for key in ("pois", "exits"):
        for item in layout.get(key) or []:
            pos = item.get("position") if isinstance(item, dict) else None
            if isinstance(pos, dict):
                try:
                    blocked.add((int(pos["col"]), int(pos["row"])))
                except (KeyError, TypeError, ValueError):
                    continue
    return blocked


def _nearest_free_cells(
    origin: tuple[int, int],
    blocked: set[tuple[int, int]],
    cols: int,
    rows: int,
    count: int,
) -> list[tuple[int, int]]:
    ox = max(0, min(cols - 1, origin[0]))
    oy = max(0, min(rows - 1, origin[1]))
    found: list[tuple[int, int]] = []
    for radius in range(max(cols, rows)):
        ring = [
            (x, y)
            for y in range(oy - radius, oy + radius + 1)
            for x in range(ox - radius, ox + radius + 1)
            if max(abs(x - ox), abs(y - oy)) == radius
            and 0 <= x < cols
            and 0 <= y < rows
            and (x, y) not in blocked
        ]
        ring.sort(key=lambda cell: (abs(cell[0] - ox) + abs(cell[1] - oy), cell[1], cell[0]))
        for cell in ring:
            found.append(cell)
            if len(found) >= count:
                return found
    return found


def remember_departure(
    state_data: dict[str, Any],
    *,
    destination_node_id: Any = None,
    exit_id: Any = None,
) -> None:
    """Mémorise la sortie empruntée au moment où un voyage est détecté.

    ``prepare_arrival`` la retrouve même si la scène suivante porte un id que le
    LLM a inventé (sans lien avec ``leads_to``). Clé hors payload public.
    """
    scene = state_data.get("current_scene")
    if not isinstance(scene, dict) or not scene.get("scene_id"):
        return
    exits = _exits(scene)
    chosen = None
    if exit_id:
        chosen = next((e for e in exits if e.get("id") == exit_id), None)
    if chosen is None and destination_node_id:
        chosen = next((e for e in exits if e.get("id") == destination_node_id), None)
        chosen = chosen or _match_by_target(exits, destination_node_id)
    if chosen is None:
        state_data.pop(PENDING_DEPARTURE_KEY, None)
        return
    state_data[PENDING_DEPARTURE_KEY] = {
        "from_scene_id": scene.get("scene_id"),
        "exit_id": chosen.get("id"),
    }


def forget_departure(state_data: dict[str, Any]) -> None:
    state_data.pop(PENDING_DEPARTURE_KEY, None)
