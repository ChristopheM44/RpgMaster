import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useGameStore } from '../game'

describe('useGameStore map decoration state', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('stores grid decorations and clears them outside combat', () => {
    const store = useGameStore()

    store.setGridDecoration({
      obstacles: [{ col: 1, row: 2 }],
      zones: [{ id: 'fog', name: 'Brume', kind: 'hazard', cells: [{ col: 2, row: 2 }] }],
    })

    expect(store.gridDecoration?.obstacles).toEqual([{ col: 1, row: 2 }])
    expect(store.gridDecoration?.zones?.[0]?.name).toBe('Brume')

    store.applyPhaseChange('exploration')

    expect(store.gridDecoration).toBeNull()
  })

  it('resets grid decorations with the rest of combat state', () => {
    const store = useGameStore()

    store.setGridDecoration({ obstacles: [{ col: 1, row: 1 }] })
    store.reset()

    expect(store.gridDecoration).toBeNull()
  })
})
