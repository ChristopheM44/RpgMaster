"""Pure zone-of-control helpers."""
from __future__ import annotations

from app.engine.tactical_grid import GridPosition, is_adjacent


def cells_in_zoc_of(position: GridPosition, grid_cols: int, grid_rows: int) -> list[GridPosition]:
    cells: list[GridPosition] = []
    for row in range(grid_rows):
        for col in range(grid_cols):
            candidate = GridPosition(col=col, row=row)
            if candidate != position and is_adjacent(position, candidate):
                cells.append(candidate)
    return cells


def can_leave_zoc(has_disengaged: bool) -> bool:
    return has_disengaged
