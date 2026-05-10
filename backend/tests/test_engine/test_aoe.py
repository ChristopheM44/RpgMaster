from app.engine.aoe import circle_cells, line_cells
from app.engine.tactical_grid import GridPosition


def test_circle_cells_radius_one_cell_covers_nine_cells() -> None:
    cells = circle_cells(GridPosition(2, 2), 1.5, 5, 5)

    assert len(cells) == 9
    assert GridPosition(2, 2) in cells
    assert GridPosition(1, 1) in cells
    assert GridPosition(4, 4) not in cells


def test_line_cells_uses_bresenham_path() -> None:
    assert line_cells(GridPosition(0, 0), GridPosition(3, 0), 4, 4) == [
        GridPosition(0, 0),
        GridPosition(1, 0),
        GridPosition(2, 0),
        GridPosition(3, 0),
    ]
