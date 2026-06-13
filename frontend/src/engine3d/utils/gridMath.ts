// Convention monde : X = colonnes (est), Z = rangées (sud), Y = haut.
// 1 unité monde = 1 cellule ; origine au centre de la grille.
// Les mètres se convertissent via cell_size_m (1 cellule = cell_size_m mètres).

import type { GridDims, GridPoint } from '../types'

/** Centre d'une cellule (indices entiers) en coordonnées monde. */
export function cellCenterToWorld(col: number, row: number, dims: GridDims): { x: number; z: number } {
  return { x: col + 0.5 - dims.cols / 2, z: row + 0.5 - dims.rows / 2 }
}

/**
 * Point de grille continu (coins/fractions, ex. géométries d'éléments où
 * rect(col,row) est un coin et line(from/to) des intersections) → monde.
 */
export function gridPointToWorld(col: number, row: number, dims: GridDims): { x: number; z: number } {
  return { x: col - dims.cols / 2, z: row - dims.rows / 2 }
}

/** Cellule contenant un point monde, ou null hors grille. */
export function worldToCell(x: number, z: number, dims: GridDims): GridPoint | null {
  const col = Math.floor(x + dims.cols / 2)
  const row = Math.floor(z + dims.rows / 2)
  if (col < 0 || row < 0 || col >= dims.cols || row >= dims.rows) return null
  return { col, row }
}

export function gridDiagonal(dims: GridDims): number {
  return Math.hypot(dims.cols, dims.rows)
}

export function metersToWorld(meters: number, cellSizeM: number): number {
  return meters / Math.max(0.1, cellSizeM)
}

export function clampCell(point: GridPoint, dims: GridDims): GridPoint {
  return {
    col: Math.max(0, Math.min(dims.cols - 1, Math.round(point.col))),
    row: Math.max(0, Math.min(dims.rows - 1, Math.round(point.row))),
  }
}

export function cellKey(point: GridPoint): string {
  return `${point.col},${point.row}`
}

/**
 * Ligne de cellules façon Chebyshev (diagonale puis droite), départ inclus.
 * Fallback de preview quand le backend n'a pas fourni de chemin A* — même
 * esprit que `line_cells` de app/engine/aoe.py.
 */
export function chebyshevLine(from: GridPoint, to: GridPoint): GridPoint[] {
  const cells: GridPoint[] = [{ col: from.col, row: from.row }]
  let col = from.col
  let row = from.row
  let guard = 0
  while ((col !== to.col || row !== to.row) && guard < 128) {
    col += Math.sign(to.col - col)
    row += Math.sign(to.row - row)
    cells.push({ col, row })
    guard += 1
  }
  return cells
}

/** Cellules entières couvertes par un rect de grille (coin + dimensions). */
export function rectCells(col: number, row: number, width: number, height: number, dims: GridDims): GridPoint[] {
  const cells: GridPoint[] = []
  const c0 = Math.max(0, Math.floor(col))
  const r0 = Math.max(0, Math.floor(row))
  const c1 = Math.min(dims.cols - 1, Math.ceil(col + width) - 1)
  const r1 = Math.min(dims.rows - 1, Math.ceil(row + height) - 1)
  for (let r = r0; r <= r1; r++) {
    for (let c = c0; c <= c1; c++) cells.push({ col: c, row: r })
  }
  return cells
}
