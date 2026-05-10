"""Pure grid pathfinding helpers."""
from __future__ import annotations

import heapq
from typing import Optional

from app.engine.tactical_grid import GridPosition, chebyshev_distance


def astar_path(
    start: GridPosition,
    goal: GridPosition,
    grid_cols: int,
    grid_rows: int,
    blocked: Optional[list[GridPosition]] = None,
    difficult: Optional[list[GridPosition]] = None,
) -> list[GridPosition]:
    blocked_set = {(pos.col, pos.row) for pos in blocked or []}
    difficult_set = {(pos.col, pos.row) for pos in difficult or []}
    start_key = (start.col, start.row)
    goal_key = (goal.col, goal.row)
    if goal_key in blocked_set:
        return []

    frontier: list[tuple[float, tuple[int, int]]] = [(0.0, start_key)]
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start_key: None}
    cost_so_far: dict[tuple[int, int], float] = {start_key: 0.0}

    while frontier:
        _, current = heapq.heappop(frontier)
        if current == goal_key:
            break
        for next_key in _neighbors(current, grid_cols, grid_rows):
            if next_key in blocked_set:
                continue
            move_cost = 2.0 if next_key in difficult_set else 1.0
            next_cost = cost_so_far[current] + move_cost
            if next_key not in cost_so_far or next_cost < cost_so_far[next_key]:
                cost_so_far[next_key] = next_cost
                priority = next_cost + chebyshev_distance(
                    GridPosition(*next_key),
                    goal,
                )
                heapq.heappush(frontier, (priority, next_key))
                came_from[next_key] = current

    if goal_key not in came_from:
        return []
    path: list[GridPosition] = []
    current: tuple[int, int] | None = goal_key
    while current is not None:
        path.append(GridPosition(col=current[0], row=current[1]))
        current = came_from[current]
    path.reverse()
    return path


def _neighbors(cell: tuple[int, int], grid_cols: int, grid_rows: int) -> list[tuple[int, int]]:
    col, row = cell
    result: list[tuple[int, int]] = []
    for dc in (-1, 0, 1):
        for dr in (-1, 0, 1):
            if dc == 0 and dr == 0:
                continue
            next_col = col + dc
            next_row = row + dr
            if 0 <= next_col < grid_cols and 0 <= next_row < grid_rows:
                result.append((next_col, next_row))
    return result
