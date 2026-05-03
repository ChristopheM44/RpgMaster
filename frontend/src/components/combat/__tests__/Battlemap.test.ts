import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import Battlemap from '../Battlemap.vue'
import { useCharacterStore } from '../../../stores/character'
import { useGameStore } from '../../../stores/game'
import type { CombatantState, SceneLayout } from '../../../types'

const scene: SceneLayout = {
  cols: 8,
  rows: 8,
  cell_size_m: 1.5,
  terrain: 'stone_chamber',
  pois: [
    {
      id: 'well',
      name: 'Puits scellé',
      kind: 'hazard',
      icon: 'mist',
      position: { col: 4, row: 4 },
      description: 'Une brume froide sort de la margelle.',
      action_hint: "L'examiner avant de s'approcher.",
    },
    {
      id: 'toben',
      name: 'Toben',
      kind: 'npc',
      icon: 'npc',
      position: { col: 2, row: 3 },
      description: 'Un vieil habitué nerveux.',
    },
    {
      id: 'chest',
      name: 'Coffre rouillé',
      kind: 'loot',
      icon: 'chest',
      position: { col: 3, row: 5 },
      interactions: [
        {
          id: 'force-open',
          label: 'Forcer',
          intent: 'use',
          prompt: "Je tente de forcer le coffre rouillé.",
          icon: 'door',
        },
        {
          id: 'empty-label',
          label: '',
          intent: 'custom',
        },
      ],
    },
  ],
  exits: [
    {
      id: 'door',
      label: 'Porte de chêne',
      position: { col: 7, row: 4 },
      leads_to: 'bandit_room',
      description: 'Une porte renforcée vers la salle voisine.',
    },
  ],
  party_positions: {
    hero: { col: 1, row: 4 },
  },
}

const dockScene: SceneLayout = {
  cols: 10,
  rows: 8,
  cell_size_m: 1.5,
  terrain: 'dock_ambush',
  pois: [
    {
      id: 'bandit_2',
      name: 'Bandit 2 (retrait)',
      kind: 'enemy',
      icon: 'bandit',
      position: { col: 6, row: 2 },
      description: 'Pres de la porte de quai. Evalue une fuite.',
    },
    {
      id: 'barrels',
      name: 'Tonnes de the',
      kind: 'cover',
      icon: 'barrel',
      position: { col: 3, row: 4 },
      description: "Barricade instable. Risque d'effondrement.",
    },
    {
      id: 'dock_gate',
      name: 'Porte de quai (issue)',
      kind: 'exit',
      icon: 'gate',
      position: { col: 7, row: 1 },
      description: 'Ouverte sur la ruelle.',
    },
  ],
  exits: [
    {
      id: 'dock_gate',
      label: 'Porte de quai (vers la ruelle)',
      position: { col: 7, row: 1 },
      leads_to: 'souk_streets',
      description: 'Ouverte, mais surveillee par les dockers.',
    },
  ],
  party_positions: {},
}

function combatant(overrides: Partial<CombatantState>): CombatantState {
  return {
    id: 'hero',
    name: 'Thorvald',
    initiative: 12,
    hp_current: 12,
    hp_max: 12,
    kind: 'pc',
    conditions: [],
    is_ai: false,
    is_active: true,
    position: { col: 0, row: 0 },
    ac: 16,
    ...overrides,
  }
}

describe('Battlemap', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const store = new Map<string, string>()
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: vi.fn((key: string) => store.get(key) ?? null),
        setItem: vi.fn((key: string, value: string) => store.set(key, value)),
        clear: vi.fn(() => store.clear()),
      },
    })
  })

  it('renders scene legend and confirms exits only after selection', async () => {
    const charStore = useCharacterStore()
    charStore.sessionCharacters = [{ id: 'hero', name: 'Thorvald' } as any]

    const wrapper = mount(Battlemap, {
      props: {
        mode: 'exploration',
        sceneLayout: scene,
        myCharacterId: 'hero',
      },
    })

    expect(wrapper.text()).toContain('Porte de chêne')
    expect(wrapper.text()).toContain('Puits scellé')
    expect(wrapper.find('[data-testid="legend-icon-exit-door"][data-icon-id="door"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="map-icon-exit-door"][data-icon-id="door"]').exists()).toBe(true)

    await wrapper.find('button[aria-label="Porte de chêne"]').trigger('click')

    expect(wrapper.emitted('sceneExit')).toBeUndefined()
    expect(wrapper.text()).toContain('Une porte renforcée')

    await wrapper.find('[data-testid="map-confirm"]').trigger('click')

    expect(wrapper.emitted('sceneExit')).toEqual([[scene.exits[0]!.id, scene.exits[0]!.label]])
  })

  it('shows standard POI actions and emits the chosen interaction after selection', async () => {
    const wrapper = mount(Battlemap, {
      props: {
        mode: 'exploration',
        sceneLayout: scene,
      },
    })

    await wrapper.find('button[aria-label="Puits scellé"]').trigger('click')

    expect(wrapper.emitted('scenePoi')).toBeUndefined()
    expect(wrapper.find('[data-testid="legend-icon-poi-well"][data-icon-id="trap-danger"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="map-icon-poi-well"][data-icon-id="trap-danger"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Une brume froide')
    expect(wrapper.text()).toContain('Observer à distance')
    expect(wrapper.text()).toContain('Contourner')

    await wrapper.find('[data-testid="map-poi-action-examine"]').trigger('click')

    expect(wrapper.emitted('scenePoi')).toEqual([[
      scene.pois[0]!.id,
      scene.pois[0]!.name,
      {
        id: 'examine',
        label: 'Observer à distance',
        intent: 'examine',
        icon: 'trap-danger',
        default: true,
      },
    ]])
  })

  it('shows contextual NPC actions after selecting an NPC POI', async () => {
    const wrapper = mount(Battlemap, {
      props: {
        mode: 'exploration',
        sceneLayout: scene,
      },
    })

    await wrapper.find('button[aria-label="Toben"]').trigger('click')

    expect(wrapper.emitted('scenePoi')).toBeUndefined()
    expect(wrapper.text()).toContain('Se diriger vers')
    expect(wrapper.text()).toContain('Parler')
    expect(wrapper.text()).toContain('Observer')
    expect(wrapper.text()).toContain('Écouter')

    await wrapper.find('[data-testid="map-poi-action-talk"]').trigger('click')

    expect(wrapper.emitted('scenePoi')).toEqual([[
      'toben',
      'Toben',
      {
        id: 'talk',
        label: 'Parler',
        intent: 'talk',
        icon: 'npc',
        default: true,
      },
    ]])
  })

  it('renders hostile and cover POIs semantically and hides duplicate exit POIs', () => {
    const wrapper = mount(Battlemap, {
      props: {
        mode: 'exploration',
        sceneLayout: dockScene,
      },
    })

    expect(wrapper.find('[data-testid="legend-icon-poi-bandit_2"][data-icon-id="c-enemy"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="map-icon-poi-bandit_2"][data-icon-id="c-enemy"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="legend-icon-poi-barrels"][data-icon-id="c-half-cover"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="legend-icon-exit-dock_gate"][data-icon-id="door"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="legend-icon-poi-dock_gate"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="map-icon-poi-dock_gate"]').exists()).toBe(false)
  })

  it('merges custom POI interactions with defaults and prioritizes custom intents', async () => {
    const wrapper = mount(Battlemap, {
      props: {
        mode: 'exploration',
        sceneLayout: scene,
      },
    })

    await wrapper.find('button[aria-label="Coffre rouillé"]').trigger('click')

    expect(wrapper.text()).toContain('Forcer')
    expect(wrapper.text()).toContain('Examiner')
    expect(wrapper.text()).toContain('Fouiller')
    expect(wrapper.text()).not.toContain('Utiliser')

    await wrapper.find('[data-testid="map-poi-action-force-open"]').trigger('click')

    expect(wrapper.emitted('scenePoi')).toEqual([[
      'chest',
      'Coffre rouillé',
      {
        id: 'force-open',
        label: 'Forcer',
        intent: 'use',
        prompt: "Je tente de forcer le coffre rouillé.",
        icon: 'door',
      },
    ]])
  })

  it('prepares movement and emits move after confirmation', async () => {
    const gameStore = useGameStore()
    gameStore.setGridConfig({ cols: 5, rows: 5, cell_size_m: 1.5 })
    gameStore.setCombatants([
      combatant({ id: 'hero', name: 'Thorvald', kind: 'pc', position: { col: 0, row: 0 } }),
      combatant({
        id: 'goblin',
        name: 'Gobelin',
        kind: 'monster',
        hp_current: 7,
        hp_max: 7,
        is_active: false,
        position: { col: 3, row: 0 },
        ac: 13,
      }),
    ])
    gameStore.setGridDecoration({
      obstacles: [{ col: 2, row: 2 }],
      zones: [{ id: 'fire', name: 'Brasier', kind: 'hazard', cells: [{ col: 1, row: 2 }] }],
    })

    const wrapper = mount(Battlemap, {
      props: {
        myCharacterId: 'hero',
        isMyTurn: true,
        speedM: 9,
        interactionMode: 'move',
      },
    })

    expect(wrapper.text()).toContain('Brasier')
    expect(wrapper.text()).toContain('Obstacles')
    expect(wrapper.find('[data-testid="legend-icon-zone-fire"][data-icon-id="c-danger-zone"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="legend-icon-obstacles"][data-icon-id="c-obstacle"]').exists()).toBe(true)

    await wrapper.find('button[aria-label="B1"]').trigger('click')

    expect(wrapper.emitted('move')).toBeUndefined()
    expect(wrapper.text()).toContain('Déplacement préparé')

    await wrapper.find('[data-testid="map-confirm"]').trigger('click')

    expect(wrapper.emitted('move')).toEqual([[1, 0]])
  })

  it('selects an attack target and confirms before emitting target', async () => {
    const gameStore = useGameStore()
    gameStore.setGridConfig({ cols: 5, rows: 5, cell_size_m: 1.5 })
    gameStore.setCombatants([
      combatant({ id: 'hero', name: 'Thorvald', kind: 'pc', position: { col: 0, row: 0 } }),
      combatant({
        id: 'goblin',
        name: 'Gobelin',
        kind: 'monster',
        hp_current: 7,
        hp_max: 7,
        is_active: false,
        position: { col: 3, row: 0 },
        ac: 13,
      }),
    ])

    const wrapper = mount(Battlemap, {
      props: {
        myCharacterId: 'hero',
        isMyTurn: true,
        speedM: 9,
        interactionMode: 'attack',
      },
    })

    await wrapper.find('button[aria-label="D1"]').trigger('click')

    expect(wrapper.emitted('target')).toBeUndefined()
    expect(wrapper.find('[data-testid="map-icon-target-goblin"][data-icon-id="c-atk-target"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Confirmer attaque')

    await wrapper.find('[data-testid="map-confirm"]').trigger('click')

    expect(wrapper.emitted('target')).toEqual([['goblin', 'attack']])
  })
})
