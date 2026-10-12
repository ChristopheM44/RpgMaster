// Vocabulaire d'indicateurs (lot 3) — règles PURES partagées par les adapters :
// sens d'une sortie (voyager / monter / descendre), bord vers lequel elle mène,
// nature d'un repère. Le rendu (chevrons, bannières, losanges) vit dans les couches.

import type { SceneElementFacing } from '../../types'
import type { ElementSpec, ExitDirection, GridDims, PoiRole } from '../types'

/** Bord de grille touché par la case (le plus proche), ou null pour une case intérieure. */
export function borderFacingForCell(col: number, row: number, dims: GridDims): SceneElementFacing | null {
  const distances: [number, SceneElementFacing][] = [
    [row, 'north'],
    [dims.rows - 1 - row, 'south'],
    [col, 'west'],
    [dims.cols - 1 - col, 'east'],
  ]
  let best = distances[0]!
  for (const entry of distances) if (entry[0] < best[0]) best = entry
  return best[0] <= 0 ? best[1] : null
}

/**
 * Sens et direction d'une sortie : un escalier lié dit monter/descendre et son
 * `facing` ; sinon c'est un voyage vers le bord de la case.
 */
export function exitIndicator(
  col: number,
  row: number,
  element: Pick<ElementSpec, 'kind' | 'facing' | 'verticalDirection'> | undefined,
  dims: GridDims,
): { direction: ExitDirection; facing: SceneElementFacing | null } {
  const facing = element?.facing ?? borderFacingForCell(col, row, dims)
  if (element?.kind === 'stairs') {
    if (element.verticalDirection === 'down') return { direction: 'down', facing }
    if (element.verticalDirection === 'up') return { direction: 'up', facing }
  }
  return { direction: 'travel', facing }
}

export function poiRoleFor(kind: string): PoiRole {
  switch (kind) {
    case 'clue':
    case 'loot':
    case 'hazard':
    case 'cover':
      return kind
    default:
      return 'point'
  }
}
