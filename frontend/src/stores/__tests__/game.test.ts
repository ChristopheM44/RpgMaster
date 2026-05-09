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

  it('restores dialogue history as dialogue entries', () => {
    const store = useGameStore()

    store.restoreHistory([
      {
        id: 'msg-1',
        role: 'gm',
        speaker: 'Azaka',
        message_type: 'dialogue',
        content: 'Je peux vous guider.',
        metadata: {
          speaker_id: 'azaka',
          speaker_kind: 'npc',
          scene_id: 'scene-1',
        },
        created_at: '2026-05-09T12:00:00Z',
      },
    ])

    expect(store.narrativeLog[0]).toMatchObject({
      type: 'dialogue',
      text: 'Je peux vous guider.',
      speaker: 'Azaka',
      speaker_id: 'azaka',
      speaker_kind: 'npc',
      entry_kind: 'dialogue',
      scene_id: 'scene-1',
    })
  })
})
