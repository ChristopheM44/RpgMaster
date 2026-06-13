// Gabarits de zone d'effet PURS — miroir strict de backend/app/engine/aoe.py
// (mêmes arrondis : trunc(size_m / cell_size_m), max(0,…) cercle, max(1,…)
// cube/cône ; ligne en Bresenham). Toute divergence casse la parité testée
// contre les fixtures de tests/test_engine/test_aoe.py.

import type { GridDims, GridPoint } from '../types'

export interface AoeInput {
  /** area_shape SRD : sphere|cylinder|emanation|cube|square|line|cone. */
  shape: string
  sizeM: number
  cellSizeM: number
  /** Cellule du lanceur. */
  origin: GridPoint
  /** Cellule visée. */
  target: GridPoint
  dims: GridDims
}

export function aoeCells(input: AoeInput): GridPoint[] {
  switch (input.shape) {
    case 'sphere':
    case 'cylinder':
      return circleCells(input.target, input.sizeM, input.cellSizeM, input.dims)
    case 'emanation':
      // Émanation : rayonne depuis le lanceur, pas depuis le point visé.
      return circleCells(input.origin, input.sizeM, input.cellSizeM, input.dims)
    case 'cube':
    case 'square':
      return cubeCells(input.target, input.sizeM, input.cellSizeM, input.dims)
    case 'line':
      return lineCells(input.origin, input.target)
    case 'cone':
      return coneCells(input.origin, input.target, input.sizeM, input.cellSizeM, input.dims)
    default:
      return []
  }
}

/** Disque Chebyshev — parité circle_cells (ordre row-major). */
export function circleCells(
  origin: GridPoint,
  radiusM: number,
  cellSizeM: number,
  dims: GridDims,
): GridPoint[] {
  const radiusCells = Math.max(0, Math.trunc(radiusM / cellSizeM))
  const cells: GridPoint[] = []
  for (let row = 0; row < dims.rows; row++) {
    for (let col = 0; col < dims.cols; col++) {
      if (Math.max(Math.abs(col - origin.col), Math.abs(row - origin.row)) <= radiusCells) {
        cells.push({ col, row })
      }
    }
  }
  return cells
}

/** Carré ancré coin haut-gauche sur la cellule visée — parité cube_cells. */
export function cubeCells(
  origin: GridPoint,
  sizeM: number,
  cellSizeM: number,
  dims: GridDims,
): GridPoint[] {
  const sizeCells = Math.max(1, Math.trunc(sizeM / cellSizeM))
  const cells: GridPoint[] = []
  for (let row = origin.row; row < Math.min(dims.rows, origin.row + sizeCells); row++) {
    for (let col = origin.col; col < Math.min(dims.cols, origin.col + sizeCells); col++) {
      cells.push({ col, row })
    }
  }
  return cells
}

/** Ligne de Bresenham origin→target incluses — parité line_cells. */
export function lineCells(origin: GridPoint, target: GridPoint): GridPoint[] {
  const cells: GridPoint[] = []
  const dx = Math.abs(target.col - origin.col)
  const dy = -Math.abs(target.row - origin.row)
  const sx = origin.col < target.col ? 1 : -1
  const sy = origin.row < target.row ? 1 : -1
  let err = dx + dy
  let col = origin.col
  let row = origin.row
  for (;;) {
    cells.push({ col, row })
    if (col === target.col && row === target.row) return cells
    const e2 = 2 * err
    if (e2 >= dy) {
      err += dy
      col += sx
    }
    if (e2 <= dx) {
      err += dx
      row += sy
    }
  }
}

/** Cône par quadrant, s'élargissant d'une cellule par pas — parité cone_cells. */
export function coneCells(
  origin: GridPoint,
  target: GridPoint,
  lengthM: number,
  cellSizeM: number,
  dims: GridDims,
): GridPoint[] {
  const lengthCells = Math.max(1, Math.trunc(lengthM / cellSizeM))
  const directionCol = target.col >= origin.col ? 1 : -1
  const directionRow = target.row >= origin.row ? 1 : -1
  const cells: GridPoint[] = []
  for (let step = 1; step <= lengthCells; step++) {
    const centerCol = origin.col + directionCol * step
    const centerRow = origin.row + directionRow * step
    for (let spread = -step; spread <= step; spread++) {
      const col = centerCol + spread
      const row = centerRow
      if (col >= 0 && col < dims.cols && row >= 0 && row < dims.rows) {
        cells.push({ col, row })
      }
    }
  }
  return cells
}
