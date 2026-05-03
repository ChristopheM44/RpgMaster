import { describe, expect, it } from 'vitest'

import { iconForPoi } from '../rpgMapIcons'
import type { PointOfInterest } from '../../types'

function poi(overrides: Partial<PointOfInterest>): PointOfInterest {
  return {
    id: 'poi',
    name: 'Repere',
    kind: 'point',
    position: { col: 0, row: 0 },
    ...overrides,
  }
}

describe('rpgMapIcons', () => {
  it('keeps hostile POIs as enemies even when their description mentions a door', () => {
    expect(iconForPoi(poi({
      id: 'bandit_2',
      name: 'Bandit 2 (retrait)',
      kind: 'enemy',
      icon: 'bandit',
      description: 'Pres de la porte de quai. Evalue une fuite.',
    }))).toBe('c-enemy')
  })

  it('maps cover and barrel hints to tactical cover', () => {
    expect(iconForPoi(poi({
      id: 'barrels',
      name: 'Tonnes de the',
      kind: 'cover',
      icon: 'barrel',
    }))).toBe('c-half-cover')
  })

  it('maps gate and door hints to a door icon', () => {
    expect(iconForPoi(poi({
      id: 'dock_gate',
      name: 'Porte de quai',
      kind: 'exit',
      icon: 'gate',
    }))).toBe('door')
  })

  it('keeps explicit NPCs as NPCs even with spy hints', () => {
    expect(iconForPoi(poi({
      id: 'bandit_leader',
      name: 'Emissaire Zhentarim',
      kind: 'npc',
      icon: 'spy',
    }))).toBe('npc')
  })
})
