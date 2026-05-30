import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import SelectionInspector from '../SelectionInspector.vue'
import { useGameStore } from '../../../stores/game'
import { useSessionStore } from '../../../stores/session'

describe('SelectionInspector', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows NPC action without an empty DD marker', () => {
    const gameStore = useGameStore()
    const sessionStore = useSessionStore()
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
            description: 'Un guide épuisé par la canicule.',
            interactions: [{ label: 'Parler', intent: 'talk' }],
          },
        ],
        exits: [],
        party_positions: {},
      },
    })
    sessionStore.selectEntity('khalid_guide')

    const wrapper = mount(SelectionInspector)

    expect(wrapper.text()).toContain('PNJ')
    expect(wrapper.text()).toContain('Action : Parler')
    expect(wrapper.text()).not.toContain('DD')
  })

  it('shows a minimal inspector for an unlinked scene element', () => {
    const gameStore = useGameStore()
    const sessionStore = useSessionStore()
    gameStore.applySceneLayout({
      scene: {
        cols: 12,
        rows: 12,
        cell_size_m: 1.5,
        scene_theme: 'city',
        pois: [],
        exits: [],
        party_positions: {},
        elements: [
          {
            id: 'grille_egout',
            name: "Grille d'égout",
            kind: 'stairs',
            geometry: { type: 'rect', col: 7, row: 8, width: 0.8, height: 0.8 },
            description: 'Une ouverture métallique suggère un accès sous la ville.',
            interactive: true,
          },
        ],
      },
    })
    sessionStore.selectEntity('grille_egout')

    const wrapper = mount(SelectionInspector)

    expect(wrapper.text()).toContain('Passage')
    expect(wrapper.text()).toContain("Grille d'égout")
    expect(wrapper.text()).toContain('Une ouverture métallique')
  })
})
