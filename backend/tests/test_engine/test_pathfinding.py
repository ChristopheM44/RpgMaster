from app.engine.pathfinding import astar_path
from app.engine.tactical_grid import GridPosition


def test_astar_path_avoids_blocked_cells() -> None:
    path = astar_path(
        GridPosition(0, 0),
        GridPosition(2, 0),
        3,
        3,
        blocked=[GridPosition(1, 0)],
    )

    assert path[0] == GridPosition(0, 0)
    assert path[-1] == GridPosition(2, 0)
    assert GridPosition(1, 0) not in path


def test_astar_path_returns_empty_when_goal_blocked() -> None:
    assert astar_path(
        GridPosition(0, 0),
        GridPosition(1, 1),
        3,
        3,
        blocked=[GridPosition(1, 1)],
    ) == []
