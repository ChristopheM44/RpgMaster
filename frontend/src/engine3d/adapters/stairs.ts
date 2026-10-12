// Escaliers — règles PURES partagées par les adapters (sol troué, élévation)
// et la fabrique procédurale (géométrie). Sans three : testable sans WebGL.
//
// Convention : `facing` = bord/direction vers lequel l'escalier MÈNE.
// - up   : volée qui MONTE vers `facing` (marches au-dessus du sol).
// - down : TRÉMIE creusée dans le sol, marches qui S'ENFONCENT vers `facing`.
// - level/null : rendu comme une montée basse.
// Avant 2026-10, `down` était une montée tournée de 180° (rampe pointant vers
// la salle) et surélevait le jeton de 0,4 m.

import type { SceneElementFacing, SceneElementGeometry } from '../../types'
import type { ElementSpec, GridDims, GridPoint } from '../types'

/**
 * Descente d'une trémie par cellule de longueur (mètres) et nombre de marches.
 * Pente volontairement douce (~30°) : plus raide, la caméra par défaut (~35°
 * au-dessus de l'horizon) passe par-dessus les marches et ne voit que le fond.
 */
export const STAIRWELL_DROP_M_PER_CELL = 0.9
export const STAIRWELL_STEPS = 4
/** Hauteur visuelle minimale d'une volée montante (mètres). */
export const RISING_STAIRS_MIN_RISE_M = 1.2
export const RISING_STAIRS_STEPS = 5

/** Vecteur monde unitaire (X = est, Z = sud) d'une direction cardinale. */
export const FACING_VECTOR: Record<SceneElementFacing, { x: number; z: number }> = {
  north: { x: 0, z: -1 },
  south: { x: 0, z: 1 },
  east: { x: 1, z: 0 },
  west: { x: -1, z: 0 },
}

export function isStairwell(spec: Pick<ElementSpec, 'kind' | 'verticalDirection'>): boolean {
  return spec.kind === 'stairs' && spec.verticalDirection === 'down'
}

/** Bornes entières (cellules complètes) couvertes par une géométrie. */
export function cellBounds(geometry: SceneElementGeometry, dims: GridDims): {
  c0: number
  r0: number
  c1: number
  r1: number
} {
  let minCol: number
  let minRow: number
  let maxCol: number
  let maxRow: number
  if (geometry.type === 'rect') {
    minCol = geometry.col
    minRow = geometry.row
    maxCol = geometry.col + geometry.width
    maxRow = geometry.row + geometry.height
  } else if (geometry.type === 'ellipse') {
    minCol = geometry.col - geometry.radius_col
    minRow = geometry.row - geometry.radius_row
    maxCol = geometry.col + geometry.radius_col
    maxRow = geometry.row + geometry.radius_row
  } else {
    minCol = Math.min(geometry.from.col, geometry.to.col)
    minRow = Math.min(geometry.from.row, geometry.to.row)
    maxCol = Math.max(geometry.from.col, geometry.to.col)
    maxRow = Math.max(geometry.from.row, geometry.to.row)
  }
  const c0 = clamp(Math.floor(minCol + 1e-6), 0, dims.cols - 1)
  const r0 = clamp(Math.floor(minRow + 1e-6), 0, dims.rows - 1)
  const c1 = clamp(Math.ceil(maxCol - 1e-6), c0 + 1, dims.cols)
  const r1 = clamp(Math.ceil(maxRow - 1e-6), r0 + 1, dims.rows)
  return { c0, r0, c1, r1 }
}

/**
 * Direction d'un escalier sans `facing` explicite : le bord de grille le plus
 * proche (un accès de bord mène hors de la carte), nord/sud d'abord à égalité.
 */
export function inferStairsFacing(geometry: SceneElementGeometry, dims: GridDims): SceneElementFacing {
  const { c0, r0, c1, r1 } = cellBounds(geometry, dims)
  const distances: [number, SceneElementFacing][] = [
    [r0, 'north'],
    [dims.rows - r1, 'south'],
    [c0, 'west'],
    [dims.cols - c1, 'east'],
  ]
  let best = distances[0]!
  for (const entry of distances) if (entry[0] < best[0]) best = entry
  return best[1]
}

/**
 * Direction effective d'un escalier : un accès sur un bord mène vers CE bord,
 * même si la valeur stockée dit autre chose (scènes sauvées avant la correction
 * de l'inférence, hint LLM incohérent) ; sinon valeur stockée, sinon déduite.
 */
export function resolveStairsFacing(
  stored: SceneElementFacing | null,
  geometry: SceneElementGeometry,
  dims: GridDims,
): SceneElementFacing {
  const { c0, r0, c1, r1 } = cellBounds(geometry, dims)
  const borders: SceneElementFacing[] = []
  if (r0 === 0) borders.push('north')
  if (r1 === dims.rows) borders.push('south')
  if (c0 === 0) borders.push('west')
  if (c1 === dims.cols) borders.push('east')
  if (stored && (borders.length === 0 || borders.includes(stored))) return stored
  return borders[0] ?? stored ?? inferStairsFacing(geometry, dims)
}

/** Cellules retirées du sol pour une trémie. */
export function stairwellCells(spec: Pick<ElementSpec, 'geometry'>, dims: GridDims): GridPoint[] {
  const { c0, r0, c1, r1 } = cellBounds(spec.geometry, dims)
  const cells: GridPoint[] = []
  for (let row = r0; row < r1; row++) for (let col = c0; col < c1; col++) cells.push({ col, row })
  return cells
}

/** Clés "col,row" de toutes les trémies — trous dans le sol. */
export function stairwellHoleKeys(elements: ElementSpec[], dims: GridDims): string[] {
  const keys = new Set<string>()
  for (const element of elements) {
    if (!isStairwell(element)) continue
    for (const cell of stairwellCells(element, dims)) keys.add(`${cell.col},${cell.row}`)
  }
  return [...keys]
}

/** Longueur (cellules) d'une trémie dans le sens de la descente. */
export function stairwellLength(spec: Pick<ElementSpec, 'geometry' | 'facing'>, dims: GridDims): number {
  const { c0, r0, c1, r1 } = cellBounds(spec.geometry, dims)
  const facing = spec.facing ?? inferStairsFacing(spec.geometry, dims)
  return facing === 'north' || facing === 'south' ? r1 - r0 : c1 - c0
}

/** Profondeur totale (mètres) d'une trémie. */
export function stairwellDepthM(spec: Pick<ElementSpec, 'geometry' | 'facing'>, dims: GridDims): number {
  return STAIRWELL_DROP_M_PER_CELL * stairwellLength(spec, dims)
}

/** Surface (mètres) d'une case de trémie : la première marche, sous le sol. */
export function stairwellSurfaceM(spec: Pick<ElementSpec, 'geometry' | 'facing'>, dims: GridDims): number {
  return -stairwellDepthM(spec, dims) / STAIRWELL_STEPS
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}
