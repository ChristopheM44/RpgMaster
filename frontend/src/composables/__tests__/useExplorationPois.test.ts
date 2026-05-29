import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useGameStore } from '../../stores/game'
import { useExplorationPois } from '../useExplorationPois'

describe('useExplorationPois', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('preserves NPC and clue semantics from scene POIs', () => {
    const gameStore = useGameStore()
    gameStore.applySceneLayout({
      scene: {
        cols: 12,
        rows: 12,
        cell_size_m: 1.5,
        scene_theme: 'desert',
        pois: [
          {
            id: 'khalid_guide',
            name: 'Khalid le Guide',
            kind: 'npc',
            icon: 'npc',
            position: { col: 5, row: 5 },
            description: 'Un homme brûlé par le soleil.',
            interactions: [
              {
                label: 'Parler',
                intent: 'talk',
                prompt: "Je m'approche de Khalid et lui parle.",
              },
            ],
          },
          {
            id: 'corps_corrompu',
            name: 'Cadavre anormal',
            kind: 'clue',
            icon: 'clue',
            position: { col: 4, row: 4 },
            description: 'Des veines noires parcourent la peau.',
          },
        ],
        exits: [
          {
            id: 'route_oasis',
            label: "Vers l'Oasis",
            position: { col: 11, row: 7 },
            leads_to: 'Oasis',
          },
        ],
        party_positions: {},
      },
    })

    const { pois, reperes, sorties } = useExplorationPois()
    const npc = pois.value.find((p) => p.id === 'khalid_guide')
    const clue = pois.value.find((p) => p.id === 'corps_corrompu')

    expect(npc).toMatchObject({
      kind: 'npc',
      iconId: 'npc',
      actionLabel: 'Parler',
      prompt: "Je m'approche de Khalid et lui parle.",
    })
    expect(clue).toMatchObject({ kind: 'clue', iconId: 'clue', actionLabel: 'Examiner' })
    expect(reperes.value).toHaveLength(2)
    expect(sorties.value).toHaveLength(1)
  })
})
