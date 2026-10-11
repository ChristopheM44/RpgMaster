import { describe, expect, it } from 'vitest'
import { distanceOutsideBoard, terrainHeight, valueNoise } from '../utils/terrain'
import { cutawayNormal } from '../layers/ElementsLayer'
import { BIOME_3D } from '../core/ThemeProvider'
import type { SceneElementGeometry } from '../../types'

const dims = { cols: 12, rows: 12 }
const opts = { halfW: 6, halfH: 6, relief: 2, seed: 42 }

describe('terrain prolongé', () => {
  it('le plateau reste plat, le relief monte au-delà de son bord', () => {
    expect(terrainHeight(0, 0, opts)).toBe(0)
    expect(terrainHeight(5.9, -5.9, opts)).toBe(0)
    expect(terrainHeight(6.2, 0, opts)).toBeLessThan(0.2) // rampe douce au bord
    const far = [terrainHeight(14, 3, opts), terrainHeight(-12, 10, opts), terrainHeight(2, 16, opts)]
    expect(Math.max(...far)).toBeGreaterThan(0.5)
  })

  it('déterministe et sans relief pour une plaine (relief 0)', () => {
    expect(terrainHeight(14, 3, opts)).toBe(terrainHeight(14, 3, opts))
    expect(terrainHeight(14, 3, { ...opts, relief: 0 })).toBe(0)
    expect(Math.abs(valueNoise(3.3, 7.1, 9))).toBeLessThanOrEqual(1)
  })

  it('distance au plateau', () => {
    expect(distanceOutsideBoard(0, 0, 6, 6)).toBe(0)
    expect(distanceOutsideBoard(9, 0, 6, 6)).toBe(3)
    expect(distanceOutsideBoard(9, 10, 6, 6)).toBe(5)
  })
})

describe('biomes', () => {
  it('albédo naturel : plus aucun sol quasi noir (luminance > 25 %)', () => {
    for (const [theme, biome] of Object.entries(BIOME_3D)) {
      const hex = biome.ground.replace('#', '')
      const [r, g, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
      const luminance = 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
      expect(luminance, theme).toBeGreaterThan(0.25)
    }
  })
})

describe('murs en coupe', () => {
  const line = (from: [number, number], to: [number, number]): SceneElementGeometry => ({
    type: 'line',
    from: { col: from[0], row: from[1] },
    to: { col: to[0], row: to[1] },
  })

  it('normale sortante pour les murs de bord, aucune pour un mur intérieur', () => {
    expect(cutawayNormal({ kind: 'wall', geometry: line([0, 12], [12, 12]) }, dims)).toEqual({ x: 0, z: 1, hide: false })
    expect(cutawayNormal({ kind: 'wall', geometry: line([12, 0], [12, 12]) }, dims)).toEqual({ x: 1, z: 0, hide: false })
    expect(cutawayNormal({ kind: 'wall', geometry: line([3, 6], [9, 6]) }, dims)).toBeNull()
  })

  it('coin = diagonale, torche murale masquée, mobilier jamais coupé', () => {
    const corner = cutawayNormal({ kind: 'wall', geometry: { type: 'rect', col: 11.4, row: 11.4, width: 0.6, height: 0.6 } }, dims)
    expect(corner?.x).toBeCloseTo(Math.SQRT1_2)
    expect(corner?.z).toBeCloseTo(Math.SQRT1_2)
    expect(cutawayNormal({ kind: 'light', geometry: { type: 'rect', col: 11.7, row: 5, width: 0.3, height: 0.3 } }, dims)?.hide).toBe(true)
    expect(cutawayNormal({ kind: 'furniture', geometry: { type: 'rect', col: 11, row: 5, width: 1, height: 1 } }, dims)).toBeNull()
  })
})

describe('lieu clos par scène', () => {
  it('une taverne en thème city devient un intérieur à plancher, sans terrain ni végétation', async () => {
    const { biomeFor } = await import('../core/ThemeProvider')
    const tavern = biomeFor('city', true)
    expect(tavern.enclosed).toBe(true)
    expect(tavern.groundStyle).toBe('planks')
    expect(tavern.relief).toBe(0)
    expect(tavern.scatter).toEqual([])
    expect(biomeFor('city').enclosed).toBe(false)
    expect(biomeFor('dungeon', true)).toBe(BIOME_3D.dungeon)
  })

  it('indice backend `interior` prioritaire, sinon murs sur au moins 3 bords', async () => {
    const { isEnclosedScene } = await import('../adapters/sceneAdapter')
    const wall = (id: string, from: [number, number], to: [number, number]) => ({
      id, name: id, kind: 'wall', geometry: line(from, to), terrainType: null, heightM: 2.5, elevationM: 0,
      subtle: false, interactive: false, inspectable: false, selected: false, modelKey: null, facing: null,
      verticalDirection: null,
    })
    const three = [wall('n', [0, 0], [12, 0]), wall('s', [0, 12], [12, 12]), wall('w', [0, 0], [0, 12])]
    expect(isEnclosedScene(null, three, dims)).toBe(true)
    expect(isEnclosedScene(null, three.slice(0, 2), dims)).toBe(false)
    expect(isEnclosedScene({ interior: false } as never, three, dims)).toBe(false)
    expect(isEnclosedScene({ interior: true } as never, [], dims)).toBe(true)
  })
})

function line(from: [number, number], to: [number, number]): SceneElementGeometry {
  return { type: 'line', from: { col: from[0], row: from[1] }, to: { col: to[0], row: to[1] } }
}
