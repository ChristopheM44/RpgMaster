import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import MapTabs from '../MapTabs.vue'
import { useGameStore } from '../../../stores/game'

describe('MapTabs', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('enables region and city tabs when maps are hydrated', () => {
    const store = useGameStore()
    store.applyRegionMap({
      region_map: {
        id: 'region',
        name: 'Route des Brumes',
        current_node_id: 'camp',
        nodes: [
          {
            id: 'camp',
            name: 'Camp',
            kind: 'landmark',
            position: { x: 40, y: 60 },
            status: 'current',
            city_id: 'camp',
          },
        ],
        edges: [],
        updated_at: '2026-05-10T00:00:00Z',
      },
      active_city_id: 'camp',
    })
    store.applyCityMap({
      city_map: {
        id: 'camp',
        region_node_id: 'camp',
        name: 'Camp',
        current_node_id: 'feu',
        nodes: [
          {
            id: 'feu',
            name: 'Feu de camp',
            kind: 'square',
            position: { x: 50, y: 50 },
            status: 'current',
          },
        ],
        edges: [],
        updated_at: '2026-05-10T00:00:00Z',
      },
      active_city_id: 'camp',
    })

    const wrapper = mount(MapTabs, {
      props: { sessionId: 'session-1' },
    })
    const buttons = wrapper.findAll('button')

    expect(buttons.find((button) => button.text() === 'Région')?.attributes('disabled'))
      .toBeUndefined()
    expect(buttons.find((button) => button.text() === 'Ville')?.attributes('disabled'))
      .toBeUndefined()
  })
})
