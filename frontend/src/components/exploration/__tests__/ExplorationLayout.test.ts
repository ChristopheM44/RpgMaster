import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

import ExplorationLayout from '../ExplorationLayout.vue'
import { useGameStore } from '../../../stores/game'

const MapColumnStub = {
  props: ['fullscreen'],
  emits: ['act', 'approach', 'openSheet', 'toggleFullscreen'],
  template: `
    <div data-testid="map-stub" :data-fullscreen="fullscreen ? 'true' : 'false'">
      <button data-testid="act-poi" @click="$emit('act', 'khalid_guide')">act</button>
      <button data-testid="approach-poi" @click="$emit('approach', 'dalle_fendue')">approach</button>
      <button data-testid="toggle-fullscreen" @click="$emit('toggleFullscreen')">fullscreen</button>
    </div>
  `,
}

describe('ExplorationLayout', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('emits desktop POI actions with scene interaction metadata', async () => {
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
            interactions: [
              {
                id: 'talk_khalid',
                label: 'Parler',
                intent: 'talk',
                prompt: 'Je salue Khalid.',
              },
            ],
          },
          {
            id: 'dalle_fendue',
            name: 'Dalle fendue',
            kind: 'clue',
            icon: 'clue',
            position: { col: 6, row: 7 },
          },
        ],
        exits: [],
        party_positions: {},
      },
    })

    const wrapper = mount(ExplorationLayout, {
      global: {
        stubs: {
          MapColumn: MapColumnStub,
          NarrativeColumn: true,
          BottomBar: true,
        },
      },
    })

    await wrapper.find('[data-testid="act-poi"]').trigger('click')
    await wrapper.find('[data-testid="approach-poi"]').trigger('click')

    const emitted = wrapper.emitted('action') ?? []
    expect(emitted[0]).toEqual([
      'free_text',
      'Je salue Khalid.',
      'khalid_guide',
      {
        scene_poi_id: 'khalid_guide',
        scene_interaction_id: 'talk_khalid',
        scene_interaction_intent: 'talk',
      },
    ])
    expect(emitted[1]).toEqual([
      'free_text',
      "Je m'approche de Dalle fendue pour mieux voir ce qu'il y a là-bas.",
      undefined,
      {
        scene_poi_id: 'dalle_fendue',
        scene_interaction_intent: 'approach',
      },
    ])
  })

  it('toggles the exploration map fullscreen state and closes it with Escape', async () => {
    const wrapper = mount(ExplorationLayout, {
      global: {
        stubs: {
          MapColumn: MapColumnStub,
          NarrativeColumn: true,
          BottomBar: true,
        },
      },
    })

    expect(wrapper.find('[data-testid="map-stub"]').attributes('data-fullscreen')).toBe('false')

    await wrapper.find('[data-testid="toggle-fullscreen"]').trigger('click')
    expect(wrapper.find('[data-testid="map-stub"]').attributes('data-fullscreen')).toBe('true')

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await nextTick()

    expect(wrapper.find('[data-testid="map-stub"]').attributes('data-fullscreen')).toBe('false')
    wrapper.unmount()
  })
})
