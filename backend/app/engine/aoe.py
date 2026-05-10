"""Pure area-template cell selection helpers."""
from __future__ import annotations

from app.engine.tactical_grid import CELL_SIZE_M, GridPosition, chebyshev_distance


def circle_cells(
    origin: GridPosition,
    radius_m: float,
    grid_cols: int,
    grid_rows: int,
) -> list[GridPosition]:
    radius_cells = max(0, int(radius_m / CELL_SIZE_M))
    return [
        GridPosition(col=col, row=row)
        for row in range(grid_rows)
        for col in range(grid_cols)
        if chebyshev_distance(origin, GridPosition(col=col, row=row)) <= radius_cells
    ]


def cube_cells(
    origin: GridPosition,
    size_m: float,
    grid_cols: int,
    grid_rows: int,
) -> list[GridPosition]:
    size_cells = max(1, int(size_m / CELL_SIZE_M))
    return [
        GridPosition(col=col, row=row)
        for row in range(origin.row, min(grid_rows, origin.row + size_cells))
        for col in range(origin.col, min(grid_cols, origin.col + size_cells))
    ]


def line_cells(
    origin: GridPosition,
    target: GridPosition,
    grid_cols: int,
    grid_rows: int,
) -> list[GridPosition]:
    del grid_cols, grid_rows
    cells: list[GridPosition] = []
    dx = abs(target.col - origin.col)
    dy = -abs(target.row - origin.row)
    sx = 1 if origin.col < target.col else -1
    sy = 1 if origin.row < target.row else -1
    err = dx + dy
    col, row = origin.col, origin.row
    while True:
        cells.append(GridPosition(col=col, row=row))
        if col == target.col and row == target.row:
            return cells
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            col += sx
        if e2 <= dx:
            err += dx
            row += sy


def cone_cells(
    origin: GridPosition,
    target: GridPosition,
    length_m: float,
    grid_cols: int,
    grid_rows: int,
) -> list[GridPosition]:
    length_cells = max(1, int(length_m / CELL_SIZE_M))
    direction_col = 1 if target.col >= origin.col else -1
    direction_row = 1 if target.row >= origin.row else -1
    cells: list[GridPosition] = []
    for step in range(1, length_cells + 1):
        center_col = origin.col + direction_col * step
        center_row = origin.row + direction_row * step
        for spread in range(-step, step + 1):
            candidate = GridPosition(col=center_col + spread, row=center_row)
            if 0 <= candidate.col < grid_cols and 0 <= candidate.row < grid_rows:
                cells.append(candidate)
    return cells
