import { describe, expect, it } from 'vitest'
import { resolveTokenOverlaps } from '../adapters/tokenCollision'
import type { TokenSpec } from '../types'

function token(overrides: Partial<TokenSpec> & Pick<TokenSpec, 'id' | 'kind'>): TokenSpec {
  return {
    name: overrides.id,
    col: 4,
    row: 4,
    accent: '#4fd8c0',
    modelKey: null,
    initials: '',
    hpRatio: null,
    selected: false,
    highlighted: false,
    active: false,
    targetable: null,
    defeated: false,
    iconId: null,
    exitActive: false,
    ...overrides,
  } as TokenSpec
}

describe('resolveTokenOverlaps', () => {
  it('cellule unique → aucun offset (specs inchangées)', () => {
    const tokens = [token({ id: 'a', kind: 'hero' }), token({ id: 'b', kind: 'poi', col: 5 })]
    const resolved = resolveTokenOverlaps(tokens)
    expect(resolved[0]?.offsetX).toBeUndefined()
    expect(resolved[1]?.offsetX).toBeUndefined()
  })

  it('le personnage prioritaire reste au centre, les autres en anneau', () => {
    const resolved = resolveTokenOverlaps([
      token({ id: 'poi_1', kind: 'poi' }),
      token({ id: 'hero_1', kind: 'hero' }),
      token({ id: 'npc_1', kind: 'npc' }),
    ])
    const byId = Object.fromEntries(resolved.map((t) => [t.id, t]))
    expect(byId.hero_1?.offsetX).toBeUndefined()
    expect(byId.npc_1?.offsetX).toBeDefined()
    expect(byId.poi_1?.offsetX).toBeDefined()
    // Offsets distincts entre les deux décalés.
    expect(`${byId.npc_1?.offsetX},${byId.npc_1?.offsetZ}`).not.toBe(
      `${byId.poi_1?.offsetX},${byId.poi_1?.offsetZ}`,
    )
  })

  it('offsets bornés : le token reste dans sa cellule (|offset| ≤ 0.5)', () => {
    const tokens = ['a', 'b', 'c', 'd', 'e'].map((id) => token({ id, kind: 'combatant' }))
    for (const resolved of resolveTokenOverlaps(tokens)) {
      expect(Math.abs(resolved.offsetX ?? 0)).toBeLessThan(0.5)
      expect(Math.abs(resolved.offsetZ ?? 0)).toBeLessThan(0.5)
    }
  })

  it('déterministe et insensible à l\'ordre d\'entrée', () => {
    const tokens = [
      token({ id: 'b', kind: 'npc' }),
      token({ id: 'a', kind: 'npc' }),
      token({ id: 'h', kind: 'hero' }),
    ]
    const first = resolveTokenOverlaps(tokens)
    const second = resolveTokenOverlaps([...tokens].reverse())
    const pick = (list: TokenSpec[], id: string) => {
      const found = list.find((t) => t.id === id)
      return `${found?.offsetX ?? 0},${found?.offsetZ ?? 0}`
    }
    for (const id of ['a', 'b', 'h']) {
      expect(pick(first, id)).toBe(pick(second, id))
    }
    expect(pick(first, 'h')).toBe('0,0') // héros au centre quel que soit l'ordre
  })

  it('n=2 : un seul décalé, plein nord de l\'anneau', () => {
    const resolved = resolveTokenOverlaps([
      token({ id: 'hero_1', kind: 'hero' }),
      token({ id: 'npc_1', kind: 'npc' }),
    ])
    const npc = resolved.find((t) => t.id === 'npc_1')
    expect(npc?.offsetX).toBeCloseTo(0, 5)
    expect(npc?.offsetZ).toBeCloseTo(-0.3, 5)
  })

  it('l\'ordre de sortie préserve l\'ordre d\'entrée (pas de tri du tableau)', () => {
    const resolved = resolveTokenOverlaps([
      token({ id: 'z_poi', kind: 'poi' }),
      token({ id: 'a_hero', kind: 'hero' }),
    ])
    expect(resolved.map((t) => t.id)).toEqual(['z_poi', 'a_hero'])
  })
})
