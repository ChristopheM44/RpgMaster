"""Unit tests for path_cost_m, the real production movement-cost function.

path_cost_m lives in app/game/tactical_combat.py (not app/engine/) but is pure
logic — no I/O, no async, no database — so it is testable from test_engine/
like any engine helper. It backs calculate_reachable_cells, which is the actual
reachability computation used in combat (the now-removed
cells_reachable_with_pathfinding in app/engine/tactical_grid.py was dead code
with a separate, buggy cost recomputation).
"""

from app.engine.tactical_grid import CELL_SIZE_M, GridPosition
from app.game.tactical_combat import path_cost_m


def test_path_cost_m_single_point_path_is_free() -> None:
    # A path containing only the start cell means no movement happened.
    assert path_cost_m([GridPosition(0, 0)]) == 0.0


def test_path_cost_m_empty_path_is_free() -> None:
    assert path_cost_m([]) == 0.0


def test_path_cost_m_straight_path_without_difficult_terrain() -> None:
    path = [
        GridPosition(0, 0),
        GridPosition(1, 0),
        GridPosition(2, 0),
        GridPosition(3, 0),
    ]

    # 3 steps taken (start excluded), each costing 1 cell -> 3 * CELL_SIZE_M.
    assert path_cost_m(path) == 3 * CELL_SIZE_M


def test_path_cost_m_diagonal_step_costs_same_as_cardinal() -> None:
    # D&D SRD: diagonal movement costs the same as cardinal (Chebyshev distance).
    path = [GridPosition(0, 0), GridPosition(1, 1), GridPosition(2, 2)]

    assert path_cost_m(path) == 2 * CELL_SIZE_M


def test_path_cost_m_difficult_terrain_doubles_cost_for_traversed_cell() -> None:
    path = [
        GridPosition(0, 0),
        GridPosition(1, 0),
        GridPosition(2, 0),
        GridPosition(3, 0),
    ]
    # Only the middle cell (2, 0) is difficult terrain.
    difficult = [GridPosition(2, 0)]

    # Steps: (1,0) normal=1 cell, (2,0) difficult=2 cells, (3,0) normal=1 cell
    # => 4 cells * CELL_SIZE_M.
    assert path_cost_m(path, difficult) == 4 * CELL_SIZE_M


def test_path_cost_m_all_difficult_terrain_doubles_entire_path_cost() -> None:
    path = [
        GridPosition(0, 0),
        GridPosition(1, 0),
        GridPosition(2, 0),
        GridPosition(3, 0),
    ]
    difficult = [GridPosition(1, 0), GridPosition(2, 0), GridPosition(3, 0)]

    # 3 steps, each difficult (2 cells) -> 6 cells * CELL_SIZE_M, i.e. exactly
    # double the plain straight-path cost.
    assert path_cost_m(path, difficult) == 6 * CELL_SIZE_M
    assert path_cost_m(path, difficult) == 2 * path_cost_m(path)


def test_path_cost_m_difficult_terrain_at_start_cell_is_not_counted() -> None:
    # Difficult terrain applies when entering a cell, not when leaving it — the
    # start cell's own terrain never affects movement cost since path[1:]
    # excludes it.
    path = [GridPosition(0, 0), GridPosition(1, 0), GridPosition(2, 0)]
    difficult_start_only = [GridPosition(0, 0)]

    assert path_cost_m(path, difficult_start_only) == 2 * CELL_SIZE_M


def test_path_cost_m_difficult_cell_not_on_path_does_not_affect_cost() -> None:
    # difficult terrain that the path never actually crosses must not inflate cost.
    path = [GridPosition(0, 0), GridPosition(1, 0)]
    unrelated_difficult = [GridPosition(5, 5)]

    assert path_cost_m(path, unrelated_difficult) == 1 * CELL_SIZE_M


def test_path_cost_m_none_difficult_behaves_like_no_difficult_terrain() -> None:
    path = [GridPosition(0, 0), GridPosition(1, 0), GridPosition(2, 0)]

    assert path_cost_m(path, None) == path_cost_m(path)
    assert path_cost_m(path, None) == 2 * CELL_SIZE_M
