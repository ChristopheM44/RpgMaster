from app.engine.aoe import circle_cells, cone_cells, line_cells
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


# --- cone_cells: cardinals + diagonal, proving the cone widens perpendicular to
# its facing axis (not always on the column axis) and never gets a phantom
# direction component on a perfectly straight cardinal cone.


def test_cone_cells_east_widens_vertically_not_horizontally() -> None:
    # origin (2,2) -> target due East (7,2): pure horizontal facing.
    # The cone must advance on columns and widen on rows around the centerline,
    # never spreading further along the column axis than the facing itself.
    cells = cone_cells(GridPosition(2, 2), GridPosition(7, 2), 1.5, 6, 6)
    coords = {(c.col, c.row) for c in cells}

    assert coords == {(3, 1), (3, 2), (3, 3)}
    # Old buggy implementation always spread on the column axis regardless of
    # facing, which would (wrongly) include cells like (4, 2) for a 1-cell-deep
    # cone, or omit (3, 1)/(3, 3) — neither of which should be true here.
    assert (2, 2) not in coords  # origin itself is never included


def test_cone_cells_west_is_mirror_of_east() -> None:
    # West must be the horizontal mirror of East around the same origin: same
    # perpendicular (row) widening, opposite advance direction. Pinning the
    # absolute West shape too (not just the East/West relation) matters: the old
    # code's row-direction bias was the same regardless of column direction, so
    # a relation-only check would not have caught it.
    origin = GridPosition(2, 2)
    east_cells = cone_cells(origin, GridPosition(7, 2), 1.5, 6, 6)
    west_cells = cone_cells(origin, GridPosition(-3, 2), 1.5, 6, 6)
    east = {(c.col - origin.col, c.row - origin.row) for c in east_cells}
    west = {(c.col - origin.col, c.row - origin.row) for c in west_cells}

    assert west == {(-1, -1), (-1, 0), (-1, 1)}
    assert west == {(-dc, dr) for dc, dr in east}


def test_cone_cells_north_widens_horizontally_not_vertically() -> None:
    # origin (2,2) -> target due North (2,-3): pure vertical facing (row
    # decreases). The cone must advance on rows and widen on columns — this is
    # the case the old code got most wrong, since direction_row was never 0 and
    # spread was hardcoded onto the column axis regardless of facing.
    cells = cone_cells(GridPosition(2, 2), GridPosition(2, -3), 1.5, 6, 6)
    coords = {(c.col, c.row) for c in cells}

    assert coords == {(1, 1), (2, 1), (3, 1)}
    assert (2, 2) not in coords


def test_cone_cells_south_is_mirror_of_north() -> None:
    # Same rationale as the West/East pair: pin the absolute South shape too,
    # since a relation-only check would not catch a bias shared by both directions.
    origin = GridPosition(2, 2)
    north_cells = cone_cells(origin, GridPosition(2, -3), 1.5, 6, 6)
    south_cells = cone_cells(origin, GridPosition(2, 7), 1.5, 6, 6)
    north = {(c.col - origin.col, c.row - origin.row) for c in north_cells}
    south = {(c.col - origin.col, c.row - origin.row) for c in south_cells}

    assert south == {(-1, 1), (0, 1), (1, 1)}
    assert south == {(dc, -dr) for dc, dr in north}


def test_cone_cells_east_and_north_are_rotations_of_each_other() -> None:
    # Rotating every East cell -90deg around the shared origin (dc, dr) -> (dr, -dc)
    # must reproduce the North cone exactly. This is the strongest no-bias proof:
    # the shape itself is identical, just rotated, with no cardinal favored.
    origin = GridPosition(5, 5)
    east_offsets = {
        (c.col - origin.col, c.row - origin.row)
        for c in cone_cells(origin, GridPosition(10, 5), 3.0, 12, 12)
    }
    north_offsets = {
        (c.col - origin.col, c.row - origin.row)
        for c in cone_cells(origin, GridPosition(5, 0), 3.0, 12, 12)
    }

    rotated_east = {(dr, -dc) for dc, dr in east_offsets}
    assert rotated_east == north_offsets


def test_cone_cells_diagonal_widens_along_perpendicular_diagonal() -> None:
    # origin (2,2) -> target North-East (7,-3): diagonal facing. Perpendicular
    # to a NE diagonal is the NW/SE diagonal, so the cone must widen along that
    # axis, not along a single row or column.
    cells = cone_cells(GridPosition(2, 2), GridPosition(7, -3), 1.5, 8, 8)
    coords = {(c.col, c.row) for c in cells}

    assert coords == {(2, 0), (3, 1), (4, 2)}
    assert (2, 2) not in coords


def test_cone_cells_target_on_origin_returns_empty() -> None:
    assert cone_cells(GridPosition(2, 2), GridPosition(2, 2), 1.5, 6, 6) == []
