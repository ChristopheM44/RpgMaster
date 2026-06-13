import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import Battlemap from '../Battlemap.vue'
import { useCharacterStore } from '../../../stores/character'
import { useGameStore } from '../../../stores/game'
import type { CombatantState, SceneLayout } from '../../../types'
import type { PickResult, RuntimeCallbacks, SceneSpec } from '../../../engine3d/types'

// Le moteur WebGL est mocké : les tests pilotent les callbacks de picking
// exactement comme le ferait un clic 3D, et inspectent la spec passée.
const { runtimeMock, harness } = vi.hoisted(() => {
  const runtimeMock = {
    update: vi.fn<(spec: SceneSpec) => void>(),
    moveToken: vi.fn(),
    projectCell: vi.fn(() => ({ x: 0, y: 0 })),
    projectToken: vi.fn(() => ({ x: 0, y: 0 })),
    setZoomPreset: vi.fn(),
    setRunning: vi.fn(),
    setBrightness: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
  }
  const harness: { callbacks: RuntimeCallbacks | null } = { callbacks: null }
  return { runtimeMock, harness }
})

vi.mock('../../../engine3d', () => ({
  createSceneRuntime: (_canvas: HTMLCanvasElement, callbacks: RuntimeCallbacks) => {
    harness.callbacks = callbacks
    return runtimeMock
  },
}))

async function flushEngineBoot(): Promise<void> {
  // Laisse l'import dynamique du moteur (mocké) se résoudre.
  await new Promise((resolve) => setTimeout(resolve, 0))
}

function latestSpec(): SceneSpec {
  return runtimeMock.update.mock.calls.at(-1)?.[0] as SceneSpec
}

function pickOnMap(pick: PickResult): void {
  harness.callbacks?.onClick?.(pick, { x: 0, y: 0 })
}

function hoverOnMap(pick: PickResult | null): void {
  harness.callbacks?.onHover?.(pick, { x: 0, y: 0 })
}

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
    runtimeMock.update.mockClear()
    harness.callbacks = null
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
    await flushEngineBoot()
    expect(harness.callbacks).not.toBeNull()

    expect(wrapper.text()).toContain('Porte de chêne')
    expect(wrapper.text()).toContain('Puits scellé')
    expect(wrapper.find('[data-testid="legend-icon-exit-door"][data-icon-id="door"]').exists()).toBe(true)
    const exitToken = latestSpec().tokens.find((token) => token.id === 'door')
    expect(exitToken?.kind).toBe('exit')
    expect(exitToken?.iconId).toBe('door')

    pickOnMap({ type: 'token', id: 'door', tokenKind: 'exit' })
    await wrapper.vm.$nextTick()

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
    await flushEngineBoot()

    pickOnMap({ type: 'token', id: 'well', tokenKind: 'poi' })
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('scenePoi')).toBeUndefined()
    expect(wrapper.find('[data-testid="legend-icon-poi-well"][data-icon-id="trap-danger"]').exists()).toBe(true)
    const wellToken = latestSpec().tokens.find((token) => token.id === 'well')
    expect(wellToken?.kind).toBe('poi')
    expect(wellToken?.iconId).toBe('trap-danger')
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
    await flushEngineBoot()

    pickOnMap({ type: 'token', id: 'toben', tokenKind: 'npc' })
    await wrapper.vm.$nextTick()

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

  it('renders hostile and cover POIs semantically and hides duplicate exit POIs', async () => {
    const wrapper = mount(Battlemap, {
      props: {
        mode: 'exploration',
        sceneLayout: dockScene,
      },
    })
    await flushEngineBoot()

    expect(wrapper.find('[data-testid="legend-icon-poi-bandit_2"][data-icon-id="c-enemy"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="legend-icon-poi-barrels"][data-icon-id="c-half-cover"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="legend-icon-exit-dock_gate"][data-icon-id="door"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="legend-icon-poi-dock_gate"]').exists()).toBe(false)

    const spec = latestSpec()
    const poiTokens = spec.tokens.filter((token) => token.kind === 'poi')
    // L'ennemi est rendu en personnage 3D (kind npc, accent blood), plus en marqueur.
    expect(spec.tokens.find((token) => token.id === 'bandit_2')).toMatchObject({
      kind: 'npc',
      accent: '#e84545',
    })
    expect(poiTokens.find((token) => token.id === 'barrels')?.iconId).toBe('c-half-cover')
    // Le POI doublon de sortie n'existe que comme token de sortie sur la carte.
    expect(poiTokens.map((token) => token.id)).not.toContain('dock_gate')
    expect(spec.tokens.find((token) => token.id === 'dock_gate')?.kind).toBe('exit')
  })

  it('merges custom POI interactions with defaults and prioritizes custom intents', async () => {
    const wrapper = mount(Battlemap, {
      props: {
        mode: 'exploration',
        sceneLayout: scene,
      },
    })
    await flushEngineBoot()

    pickOnMap({ type: 'token', id: 'chest', tokenKind: 'poi' })
    await wrapper.vm.$nextTick()

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
    gameStore.setReachableCells({
      hero: {
        free: [{ col: 1, row: 0 }, { col: 1, row: 1 }],
        with_dash: [],
        paths: { '1,0': [{ col: 0, row: 0 }, { col: 1, row: 0 }] },
      },
    })

    const wrapper = mount(Battlemap, {
      props: {
        myCharacterId: 'hero',
        isMyTurn: true,
        speedM: 9,
        interactionMode: 'move',
      },
    })
    await flushEngineBoot()

    expect(wrapper.text()).toContain('Brasier')
    expect(wrapper.text()).toContain('Obstacles')
    expect(wrapper.find('[data-testid="legend-icon-zone-fire"][data-icon-id="c-danger-zone"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="legend-icon-obstacles"][data-icon-id="c-obstacle"]').exists()).toBe(true)
    expect(latestSpec().overlay.reachable).toEqual([{ col: 1, row: 0 }, { col: 1, row: 1 }])

    // handleCellClick priorise obstacle puis zone avant les cases accessibles.
    pickOnMap({ type: 'cell', col: 2, row: 2 })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Décor tactique')

    pickOnMap({ type: 'cell', col: 1, row: 2 })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Zone tactique de type hazard')

    pickOnMap({ type: 'cell', col: 1, row: 0 })
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('move')).toBeUndefined()
    expect(wrapper.text()).toContain('Déplacement préparé')
    // Path preview : chemin A* backend consommé tel quel (départ inclus).
    expect(latestSpec().overlay.path).toEqual([{ col: 0, row: 0 }, { col: 1, row: 0 }])

    // Destination atteignable sans entrée paths → fallback ligne Chebyshev.
    pickOnMap({ type: 'cell', col: 1, row: 1 })
    await wrapper.vm.$nextTick()
    expect(latestSpec().overlay.path).toEqual([{ col: 0, row: 0 }, { col: 1, row: 1 }])

    pickOnMap({ type: 'cell', col: 1, row: 0 })
    await wrapper.vm.$nextTick()
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
    await flushEngineBoot()

    const goblinToken = latestSpec().tokens.find((token) => token.id === 'goblin')
    expect(goblinToken?.kind).toBe('combatant')
    expect(goblinToken?.targetable).toBe('attack')

    pickOnMap({ type: 'token', id: 'goblin', tokenKind: 'combatant' })
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('target')).toBeUndefined()
    expect(wrapper.text()).toContain('Confirmer attaque')

    await wrapper.find('[data-testid="map-confirm"]').trigger('click')

    expect(wrapper.emitted('target')).toEqual([['goblin', 'attack']])
  })

  it('aims an area spell: hover previews, out-of-range invalid, click+confirm emits castAt', async () => {
    const gameStore = useGameStore()
    gameStore.setGridConfig({ cols: 10, rows: 8, cell_size_m: 1.5 })
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
        variant: 'lean',
        myCharacterId: 'hero',
        isMyTurn: true,
        speedM: 9,
        interactionMode: 'spell',
        pendingSpell: { rangeM: 4.5, shape: 'sphere', sizeM: 1.5, origin: 'point' as const },
      },
    })
    await flushEngineBoot()

    // Survol dans la portée (3 cellules × 1.5 m = 4.5 m) → gabarit valide.
    hoverOnMap({ type: 'cell', col: 3, row: 0 })
    await wrapper.vm.$nextTick()
    let aoe = latestSpec().overlay.aoe
    expect(aoe?.valid).toBe(true)
    expect(aoe?.center).toEqual({ col: 3, row: 0 })
    expect(aoe?.cells).toContainEqual({ col: 3, row: 0 })
    expect(aoe?.cells).toContainEqual({ col: 2, row: 1 }) // rayon 1 cellule

    // Hors de portée → invalide (teinte muted), pas de confirmation possible.
    hoverOnMap({ type: 'cell', col: 6, row: 6 })
    await wrapper.vm.$nextTick()
    aoe = latestSpec().overlay.aoe
    expect(aoe?.valid).toBe(false)
    expect(wrapper.find('[data-testid="lean-confirm-cast"]').exists()).toBe(false)

    // Clic d'ancrage sur une cellule valide → mini-panel arcane → castAt.
    pickOnMap({ type: 'cell', col: 3, row: 0 })
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('castAt')).toBeUndefined()

    await wrapper.find('[data-testid="lean-confirm-cast"]').trigger('click')
    // Le gobelin est sous le gabarit → désigné cible la plus proche du centre.
    expect(wrapper.emitted('castAt')).toEqual([[3, 0, 'goblin']])
  })
})
