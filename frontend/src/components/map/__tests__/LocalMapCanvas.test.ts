import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import LocalMapCanvas from '../LocalMapCanvas.vue'
import type { SceneLayout } from '../../../types'

const scene: SceneLayout = {
  cols: 8,
  rows: 8,
  cell_size_m: 1.5,
  terrain: 'tavern_room',
  scene_theme: 'city',
  pois: [
    {
      id: 'desk',
      name: 'Bureau fermé',
      kind: 'loot',
      position: { col: 3, row: 4 },
      element_id: 'desk_element',
    },
  ],
  exits: [
    {
      id: 'front_door',
      label: "Porte d'entrée",
      position: { col: 0, row: 4 },
      element_id: 'front_door_element',
    },
  ],
  party_positions: {},
  elements: [
    {
      id: 'desk_element',
      name: 'Bureau fermé',
      kind: 'furniture',
      geometry: { type: 'rect', col: 3, row: 4, width: 1, height: 1 },
      interactive: true,
    },
    {
      id: 'front_door_element',
      name: "Porte d'entrée",
      kind: 'door',
      geometry: { type: 'rect', col: 0, row: 4, width: 0.2, height: 1 },
    },
    {
      id: 'street_axis',
      name: 'Rue pavée',
      kind: 'terrain',
      terrain_type: 'street',
      geometry: { type: 'line', from: { col: 0, row: 6 }, to: { col: 8, row: 6 } },
    },
  ],
  visual_asset: {
    provider: 'openai_compatible',
    model: 'gpt-image-1',
    status: 'ready',
    prompt: 'Top-down tavern.',
    prompt_hash: 'hash',
    url: '/map.png',
  },
}

describe('LocalMapCanvas', () => {
  it('renders scene elements and optional visual asset', () => {
    const wrapper = mount(LocalMapCanvas, {
      props: { scene, cell: 40 },
    })

    expect(wrapper.find('[data-testid="local-map-element-desk_element"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="local-map-element-front_door_element"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="local-map-element-street_axis"].terrain-street').exists()).toBe(true)
    expect(wrapper.find('img.local-map-image').attributes('src')).toBe('/map.png')
  })

  it('emits clicks for linked elements', async () => {
    const wrapper = mount(LocalMapCanvas, {
      props: { scene, cell: 40 },
    })

    await wrapper.find('[data-testid="local-map-element-front_door_element"]').trigger('click')

    expect(wrapper.emitted('elementClick')?.[0]?.[0]).toMatchObject({
      id: 'front_door_element',
      kind: 'door',
    })
  })

  it('does not infer a path only because exits exist', () => {
    const wrapper = mount(LocalMapCanvas, {
      props: {
        scene: {
          cols: 8,
          rows: 8,
          cell_size_m: 1.5,
          terrain: 'market_square',
          scene_theme: 'city',
          pois: [],
          exits: [
            { id: 'west', label: 'Sortie ouest', position: { col: 0, row: 4 } },
            { id: 'east', label: 'Sortie est', position: { col: 7, row: 4 } },
          ],
          party_positions: {},
          elements: [],
        },
        cell: 40,
      },
    })

    expect(wrapper.find('.local-map-route-layer').exists()).toBe(false)
  })
})
