import { describe, expect, it } from 'vitest'
import { buildSceneSpec } from '../adapters/sceneAdapter'
import { cellBounds, inferStairsFacing } from '../adapters/stairs'
import type { SceneElement, SceneLayout } from '../../types'

const dims = { cols: 12, rows: 12 }

function scene(elements: SceneElement[], overrides: Partial<SceneLayout> = {}): SceneLayout {
  return {
    cols: 12,
    rows: 12,
    cell_size_m: 1.5,
    scene_theme: 'dungeon',
    scene_id: 'jardin',
    pois: [],
    exits: [],
    party_positions: {},
    elements,
    ...overrides,
  }
}

function stairs(id: string, col: number, row: number, extra: Partial<SceneElement> = {}): SceneElement {
  return {
    id,
    name: 'Escalier',
    kind: 'stairs',
    geometry: { type: 'rect', col, row, width: 1, height: 1 },
    ...extra,
  } as SceneElement
}

const spec = (layout: SceneLayout) =>
  buildSceneSpec({ scene: layout, heroes: [], pois: [], selectedId: null, highlightedIds: [] })

describe('escaliers — règles pures', () => {
  it('sans facing, un escalier mène vers le bord le plus proche', () => {
    expect(inferStairsFacing({ type: 'rect', col: 4, row: 0, width: 1, height: 1 }, dims)).toBe('north')
    expect(inferStairsFacing({ type: 'rect', col: 8, row: 11, width: 1, height: 1 }, dims)).toBe('south')
    expect(inferStairsFacing({ type: 'rect', col: 11, row: 5, width: 1, height: 1 }, dims)).toBe('east')
    expect(inferStairsFacing({ type: 'rect', col: 0, row: 5, width: 1, height: 1 }, dims)).toBe('west')
  })

  it('les bornes de trémie couvrent des cellules entières (accès encastré 0.75)', () => {
    expect(cellBounds({ type: 'rect', col: 5.125, row: 6.125, width: 0.75, height: 0.75 }, dims)).toEqual({
      c0: 5,
      r0: 6,
      c1: 6,
      r1: 7,
    })
  })

  it('une descente troue le sol et place le jeton sous le sol ; une montée non', () => {
    const result = spec(
      scene([
        stairs('down', 8, 11, { facing: 'south', vertical_direction: 'down' }),
        stairs('up', 4, 0, { facing: 'north', vertical_direction: 'up' }),
      ]),
    )
    expect(result.ground.holes).toEqual(['8,11'])
    expect(result.elevationByCell['8,11']).toBeCloseTo(-0.9 / 4)
    expect(result.elevationByCell['8,11']).toBeLessThan(0)
    expect(result.elevationByCell['4,0']).toBeGreaterThan(0)
  })

  it('facing manquant résolu dans la spec (procédural toujours orienté)', () => {
    const result = spec(scene([stairs('s', 11, 3, { vertical_direction: 'down' })]))
    expect(result.elements[0]?.facing).toBe('east')
  })

  it("expose l'accès d'arrivée posé par le backend", () => {
    const result = spec(
      scene([stairs('element_retour_stairs', 8, 0, { facing: 'north', vertical_direction: 'up' })], {
        scene_id: 'caveau',
        exits: [
          {
            id: 'retour',
            label: 'Remonter',
            position: { col: 8, row: 0 },
            element_id: 'element_retour_stairs',
          },
        ],
        arrival: {
          exit_id: 'retour',
          from_scene_id: 'jardin',
          via_exit_id: 'exit_2',
          facing: 'north',
          vertical_direction: 'up',
        },
      }),
    )
    expect(result.arrival).toEqual({
      exitId: 'retour',
      col: 8,
      row: 0,
      facing: 'north',
      verticalDirection: 'up',
      fromSceneId: 'jardin',
      viaExitId: 'exit_2',
      label: 'Remonter',
    })
    expect(spec(scene([])).arrival).toBeNull()
  })
})

describe('escaliers — un accès de bord mène vers son bord', () => {
  it('ignore une orientation stockée incohérente sur un bord', async () => {
    const { resolveStairsFacing } = await import('../adapters/stairs')
    const geometry = { type: 'rect', col: 8, row: 11, width: 1, height: 1 } as const
    expect(resolveStairsFacing('north', geometry, dims)).toBe('south')
    expect(resolveStairsFacing('south', geometry, dims)).toBe('south')
    // Escalier intérieur : la valeur stockée fait foi.
    expect(resolveStairsFacing('east', { type: 'rect', col: 5, row: 5, width: 1, height: 1 }, dims)).toBe('east')
  })
})
