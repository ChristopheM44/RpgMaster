import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import SceneMap from '../SceneMap.vue'
import { useGameStore } from '../../../stores/game'
import { useSessionStore } from '../../../stores/session'

describe('SceneMap', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('selects the linked POI when clicking a linked scene element', async () => {
    const gameStore = useGameStore()
    const sessionStore = useSessionStore()
    gameStore.applySceneLayout({
      scene: {
        cols: 12,
        rows: 12,
        cell_size_m: 1.5,
        scene_theme: 'city',
        pois: [
          {
            id: 'vibration_sol',
            name: 'Vibration anormale',
            kind: 'clue',
            position: { col: 4, row: 4 },
            element_id: 'element_vibration_sol',
          },
        ],
        exits: [],
        party_positions: {},
        elements: [
          {
            id: 'element_vibration_sol',
            name: 'Vibration anormale',
            kind: 'decor',
            geometry: { type: 'rect', col: 4, row: 4, width: 1, height: 1 },
            interactive: true,
          },
        ],
      },
    })

    const wrapper = mount(SceneMap)
    await wrapper.find('[data-testid="local-map-element-element_vibration_sol"]').trigger('click')

    expect(sessionStore.selectedId).toBe('vibration_sol')
  })
})
