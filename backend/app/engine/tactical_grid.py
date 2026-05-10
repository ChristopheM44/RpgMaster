"""Tactical grid — pure D&D SRD 5.2 positioning logic.

No I/O, no async, no database. Provides:
- GridPosition: (col, row) coordinates on a 2D grid
- Chebyshev distance (D&D: diagonal movement costs same as cardinal)
- Movement validation
- Default position assignment at combat start
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

CELL_SIZE_M = 1.5  # Each grid cell = 1.5 m (= 5 ft, SRD FR 5.2.1)


@dataclass
class GridPosition:
    col: int
    row: int

    def to_dict(self) -> dict:
        return {"col": self.col, "row": self.row}

    @classmethod
    def from_dict(cls, d: dict) -> GridPosition:
        return cls(col=int(d["col"]), row=int(d["row"]))


def chebyshev_distance(a: GridPosition, b: GridPosition) -> int:
    """Chebyshev distance in cells (D&D: diagonals cost same as cardinals)."""
    return max(abs(a.col - b.col), abs(a.row - b.row))


def distance_m(a: GridPosition, b: GridPosition) -> float:
    """Distance en mètres (chaque case = 1,5 m, SRD FR 5.2.1)."""
    return chebyshev_distance(a, b) * CELL_SIZE_M


def is_adjacent(a: GridPosition, b: GridPosition) -> bool:
    """True if a and b are within 1.5 m (melee range)."""
    return chebyshev_distance(a, b) <= 1


def is_within_range(a: GridPosition, b: GridPosition, range_m: float) -> bool:
    """True if b is within range_m of a."""
    return distance_m(a, b) <= range_m


def cells_reachable(
    from_pos: GridPosition,
    speed_m: float,
    grid_cols: int,
    grid_rows: int,
    occupied: Optional[list[GridPosition]] = None,
) -> list[GridPosition]:
    """Return all grid positions reachable from from_pos with speed_m movement.

    Excludes the current position and positions occupied by other combatants.
    Uses simple range check (no pathfinding, no obstacles beyond occupied cells).
    """
    blocked = set()
    if occupied:
        for pos in occupied:
            blocked.add((pos.col, pos.row))

    max_cells = int(speed_m / CELL_SIZE_M)
    reachable = []
    for row in range(grid_rows):
        for col in range(grid_cols):
            if (col, row) == (from_pos.col, from_pos.row):
                continue
            if (col, row) in blocked:
                continue
            target = GridPosition(col=col, row=row)
            if chebyshev_distance(from_pos, target) <= max_cells:
                reachable.append(target)
    return reachable


def validate_move(
    from_pos: GridPosition,
    to_pos: GridPosition,
    speed_m: float,
    grid_cols: int,
    grid_rows: int,
    occupied: Optional[list[GridPosition]] = None,
) -> tuple[bool, str]:
    """Validate a move action.

    Returns (valid, reason). reason is empty string if valid.
    """
    if to_pos.col < 0 or to_pos.col >= grid_cols:
        return False, f"Colonne {to_pos.col} hors grille (0-{grid_cols - 1})"
    if to_pos.row < 0 or to_pos.row >= grid_rows:
        return False, f"Rangée {to_pos.row} hors grille (0-{grid_rows - 1})"

    if occupied:
        for pos in occupied:
            if pos.col == to_pos.col and pos.row == to_pos.row:
                return False, "Case occupée"

    dist = distance_m(from_pos, to_pos)
    if dist > speed_m:
        return False, f"Distance {dist} m dépasse vitesse {speed_m} m"

    return True, ""


def cells_reachable_with_pathfinding(
    from_pos: GridPosition,
    movement_m: float,
    dash_m: float,
    grid_cols: int,
    grid_rows: int,
    occupied: Optional[list[GridPosition]] = None,
    obstacles: Optional[list[GridPosition]] = None,
    difficult: Optional[list[GridPosition]] = None,
) -> dict[str, list[dict]]:
    """Return cells reachable by A* with regular movement and with dash."""
    from app.engine.pathfinding import astar_path

    blocked = list(occupied or []) + list(obstacles or [])
    free: list[dict] = []
    with_dash: list[dict] = []
    paths: dict[str, list[dict]] = {}
    for row in range(grid_rows):
        for col in range(grid_cols):
            target = GridPosition(col=col, row=row)
            if target == from_pos:
                continue
            path = astar_path(from_pos, target, grid_cols, grid_rows, blocked, difficult)
            if not path:
                continue
            cost_m = max(0, len(path) - 1) * CELL_SIZE_M
            if cost_m <= movement_m:
                free.append(target.to_dict())
                paths[f"{col},{row}"] = [step.to_dict() for step in path]
            elif cost_m <= dash_m:
                with_dash.append(target.to_dict())
                paths[f"{col},{row}"] = [step.to_dict() for step in path]
    return {"free": free, "with_dash": with_dash, "blocked_by_zoc": [], "paths": paths}


def initialize_positions(
    player_ids: list[str],
    npc_ids: list[str],
    grid_cols: int = 10,
    grid_rows: int = 8,
) -> dict[str, GridPosition]:
    """Assign starting grid positions for all combatants.

    Players start in the bottom two rows; NPCs start in the top two rows.
    Spreads combatants evenly across the columns.
    """
    positions: dict[str, GridPosition] = {}

    def spread(ids: list[str], row_start: int) -> None:
        n = len(ids)
        if n == 0:
            return
        spacing = max(1, (grid_cols - 1) // max(n - 1, 1)) if n > 1 else 0
        offset = (grid_cols - 1 - spacing * (n - 1)) // 2
        for i, cid in enumerate(ids):
            col = offset + i * spacing if n > 1 else grid_cols // 2
            col = max(0, min(col, grid_cols - 1))
            row = row_start + (i % 2)  # alternate rows to avoid stacking
            row = min(row, grid_rows - 1)
            positions[cid] = GridPosition(col=col, row=row)

    spread(player_ids, grid_rows - 2)   # players near bottom
    spread(npc_ids, 0)                   # NPCs near top

    return positions
