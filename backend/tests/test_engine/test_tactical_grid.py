"""initialize_positions / nearest_free_cell — unicité des cellules de départ.

Avant durcissement, deux combattants pouvaient partager une cellule (positions
d'exploration dupliquées, ou spread sur une grille trop petite) — empilés au
même point sur la battlemap 3D.
"""

from __future__ import annotations

from app.engine.tactical_grid import GridPosition, initialize_positions, nearest_free_cell


def _cells(positions: dict[str, GridPosition]) -> list[tuple[int, int]]:
    return [(p.col, p.row) for p in positions.values()]


def test_nearest_free_cell_returns_start_when_free() -> None:
    cell = nearest_free_cell(GridPosition(col=4, row=3), set(), 10, 8)
    assert (cell.col, cell.row) == (4, 3)


def test_nearest_free_cell_scans_ring_deterministically() -> None:
    occupied = {(4, 3)}
    cell = nearest_free_cell(GridPosition(col=4, row=3), occupied, 10, 8)
    # Premier libre du ring r=1 en balayage row-major : (3, 2).
    assert (cell.col, cell.row) == (3, 2)


def test_nearest_free_cell_respects_grid_bounds() -> None:
    occupied = {(0, 0)}
    cell = nearest_free_cell(GridPosition(col=0, row=0), occupied, 10, 8)
    assert 0 <= cell.col < 10 and 0 <= cell.row < 8
    assert (cell.col, cell.row) != (0, 0)


def test_duplicate_exploration_positions_get_unique_cells() -> None:
    exploration = {
        "thorvald": {"col": 5, "row": 6},
        "elara": {"col": 5, "row": 6},
        "solana": {"col": 5, "row": 6},
    }
    positions = initialize_positions(["thorvald", "elara", "solana"], ["gob_1"], 10, 8, exploration)
    cells = _cells(positions)
    assert len(cells) == len(set(cells)), "aucune cellule partagée"
    assert (positions["thorvald"].col, positions["thorvald"].row) == (5, 6), (
        "le premier placé garde sa cellule d'exploration"
    )


def test_saturated_small_grid_still_yields_unique_cells() -> None:
    players = [f"p{i}" for i in range(5)]
    npcs = [f"m{i}" for i in range(4)]
    positions = initialize_positions(players, npcs, 3, 3)
    cells = _cells(positions)
    assert len(cells) == 9
    assert len(set(cells)) == 9, "grille 3×3 saturée → 9 cellules distinctes"


def test_initialize_positions_is_deterministic() -> None:
    kwargs = dict(
        player_ids=["a", "b", "c"],
        npc_ids=["x", "y"],
        grid_cols=10,
        grid_rows=8,
        exploration_positions={"a": {"col": 2, "row": 7}, "b": {"col": 2, "row": 7}},
    )
    first = initialize_positions(**kwargs)
    second = initialize_positions(**kwargs)
    assert _cells(first) == _cells(second)


def test_enemies_spread_near_top_players_near_bottom() -> None:
    positions = initialize_positions(["p1", "p2"], ["m1", "m2"], 10, 8)
    assert all(positions[p].row >= 6 for p in ("p1", "p2"))
    assert all(positions[m].row <= 1 for m in ("m1", "m2"))
