import { describe, expect, it } from 'vitest'
import { buildCombatSpec, type CombatAdapterInput } from '../adapters/combatAdapter'
import type { CombatantState } from '../../types'

function combatant(overrides: Partial<CombatantState> = {}): CombatantState {
  return {
    id: 'goblin',
    name: 'Gobelin',
    initiative: 12,
    hp_current: 7,
    hp_max: 7,
    kind: 'monster',
    conditions: [],
    is_ai: true,
    is_active: false,
    position: { col: 5, row: 3 },
    ac: 13,
    ...overrides,
  } as CombatantState
}

function makeInput(overrides: Partial<CombatAdapterInput> = {}): CombatAdapterInput {
  return {
    scene: null,
    gridConfig: { cols: 10, rows: 8, cell_size_m: 1.5, scene_theme: 'dungeon' },
    isExploration: false,
    combatants: [],
    classById: {},
    myCharacterId: 'hero_1',
    selectedCombatantId: null,
    interactionMode: 'inspect',
    reachableFree: [],
    gridDecoration: { obstacles: [], zones: [] },
    partyMarkers: [],
    pois: [],
    exits: [],
    pendingMove: null,
    pendingPath: [],
    pendingAoe: null,
    selectedElementId: null,
    ...overrides,
  }
}

describe('combatAdapter.buildCombatSpec', () => {
  it('dimensions et thème depuis gridConfig en combat, cellPicking actif', () => {
    const spec = buildCombatSpec(makeInput())
    expect(spec.ground).toMatchObject({ cols: 10, rows: 8, theme: 'dungeon', cellSizeM: 1.5 })
    expect(spec.overlay.cellPicking).toBe(true)
    expect(spec.ground.ambiance.light).toBe('torchlit')
  })

  it('combattants : accents sémantiques, modèle squelette, état actif/vaincu', () => {
    const spec = buildCombatSpec(makeInput({
      combatants: [
        combatant({ id: 'hero_1', name: 'Thorvald', kind: 'pc', is_ai: false, hp_current: 9, hp_max: 12, position: { col: 2, row: 2 }, is_active: true }),
        combatant({ id: 'elara', name: 'Elara', kind: 'pc', is_ai: true, position: { col: 3, row: 2 } }),
        combatant({ id: 'skel', name: 'Squelette gardien', position: { col: 6, row: 4 } }),
        combatant({ id: 'down', name: 'Gobelin', hp_current: 0, position: { col: 7, row: 4 } }),
      ],
      classById: { hero_1: 'fighter', elara: 'wizard' },
    }))
    const byId = Object.fromEntries(spec.tokens.map((token) => [token.id, token]))

    expect(byId.hero_1).toMatchObject({ accent: '#f0c764', modelKey: 'char/knight', active: true, hpRatio: 0.75 })
    expect(byId.elara).toMatchObject({ accent: '#c090ff', modelKey: 'char/mage' })
    expect(byId.skel?.modelKey).toBe('monster/skeleton_warrior')
    expect(byId.down).toMatchObject({ defeated: true, hpRatio: 0 })
    expect(byId.skel?.accent).toBe('#e84545')
  })

  it('ciblage : monstres vivants ciblables en mode attack/spell uniquement', () => {
    const base = {
      combatants: [
        combatant({ id: 'skel', position: { col: 6, row: 4 } }),
        combatant({ id: 'down', hp_current: 0, position: { col: 7, row: 4 } }),
        combatant({ id: 'hero_1', kind: 'pc', is_ai: false, position: { col: 2, row: 2 } }),
      ],
    }
    const attack = buildCombatSpec(makeInput({ ...base, interactionMode: 'attack' }))
    expect(attack.tokens.find((token) => token.id === 'skel')?.targetable).toBe('attack')
    expect(attack.tokens.find((token) => token.id === 'down')?.targetable).toBeNull()
    expect(attack.tokens.find((token) => token.id === 'hero_1')?.targetable).toBeNull()

    const inspect = buildCombatSpec(makeInput(base))
    expect(inspect.tokens.find((token) => token.id === 'skel')?.targetable).toBeNull()
  })

  it('overlay : reachable→emphasis move, destination, zones, obstacles', () => {
    const spec = buildCombatSpec(makeInput({
      interactionMode: 'move',
      reachableFree: [{ col: 1, row: 1 }, { col: 2, row: 1 }],
      pendingMove: { col: 2, row: 1 },
      gridDecoration: {
        obstacles: [{ col: 9, row: 7 }],
        zones: [{ id: 'fire', name: 'Brasier', cells: [{ col: 4, row: 4 }], icon: 'c-danger-zone' }],
      },
    }))
    expect(spec.overlay.reachable).toHaveLength(2)
    expect(spec.overlay.reachableEmphasis).toBe('move')
    expect(spec.overlay.destination).toEqual({ col: 2, row: 1 })
    expect(spec.overlay.path).toEqual([])
    expect(spec.overlay.zones[0]).toMatchObject({ id: 'fire', icon: 'c-danger-zone' })
    expect(spec.overlay.obstacles).toEqual([{ col: 9, row: 7 }])
    expect(spec.scatterBlockedCells).toContain('9,7')
  })

  it('mode exploration : partyMarkers → héros (gold moi / arcane IA / teal allié)', () => {
    const spec = buildCombatSpec(makeInput({
      isExploration: true,
      scene: {
        cols: 12, rows: 12, cell_size_m: 1.5, scene_theme: 'city',
        pois: [], exits: [], party_positions: {},
      },
      gridConfig: null,
      partyMarkers: [
        { id: 'hero_1', name: 'Thorvald', col: 2, row: 2, isMe: true, isAi: false },
        { id: 'elara', name: 'Elara', col: 3, row: 2, isMe: false, isAi: true },
        { id: 'vael', name: 'Vael', col: 4, row: 2, isMe: false, isAi: false },
      ],
      classById: { hero_1: 'fighter' },
    }))
    expect(spec.ground.cols).toBe(12)
    const byId = Object.fromEntries(spec.tokens.map((token) => [token.id, token]))
    expect(byId.hero_1).toMatchObject({ kind: 'hero', accent: '#f0c764', modelKey: 'char/knight' })
    expect(byId.elara?.accent).toBe('#c090ff')
    expect(byId.vael?.accent).toBe('#4fd8c0')
  })

  it('POI/sorties pré-adaptés → tokens avec icône et exitActive', () => {
    const spec = buildCombatSpec(makeInput({
      pois: [{ id: 'autel', name: 'Autel', col: 4, row: 2, iconId: 'poi', tone: 'gold' }],
      exits: [{ id: 'porte', label: 'Porte nord', col: 5, row: 0, iconId: 'door', active: true }],
    }))
    const poi = spec.tokens.find((token) => token.id === 'autel')
    const exit = spec.tokens.find((token) => token.id === 'porte')
    expect(poi).toMatchObject({ kind: 'poi', iconId: 'poi', accent: '#f0c764' })
    expect(exit).toMatchObject({ kind: 'exit', exitActive: true, iconId: 'door' })
  })

  it('elevationByCell : même carte que sceneAdapter depuis les éléments de scène', () => {
    const spec = buildCombatSpec(makeInput({
      scene: {
        cols: 10, rows: 8, cell_size_m: 1.5, scene_theme: 'dungeon',
        pois: [], exits: [], party_positions: {},
        elements: [
          { id: 's1', name: 'Escalier', kind: 'stairs', geometry: { type: 'rect', col: 4, row: 4, width: 1, height: 1 }, height_m: 0.8 },
        ],
      },
    }))
    expect(spec.elevationByCell['4,4']).toBe(0.8)
  })

  it('pendingAoe → overlay.aoe (gabarit pré-calculé passé tel quel)', () => {
    const aoe = {
      cells: [{ col: 4, row: 4 }, { col: 5, row: 4 }],
      center: { col: 4, row: 4 },
      valid: false,
    }
    const spec = buildCombatSpec(makeInput({ pendingAoe: aoe }))
    expect(spec.overlay.aoe).toEqual(aoe)
    expect(buildCombatSpec(makeInput()).overlay.aoe).toBeNull()
  })

  it('pendingPath → overlay.path (chemin prévisualisé)', () => {
    const spec = buildCombatSpec(makeInput({
      pendingMove: { col: 3, row: 1 },
      pendingPath: [{ col: 1, row: 1 }, { col: 2, row: 1 }, { col: 3, row: 1 }],
    }))
    expect(spec.overlay.path).toEqual([
      { col: 1, row: 1 },
      { col: 2, row: 1 },
      { col: 3, row: 1 },
    ])
  })

  it('POI role npc/enemy → personnages 3D (teal/blood), parité sceneAdapter', () => {
    const spec = buildCombatSpec(makeInput({
      pois: [
        { id: 'toben', name: 'Toben le tavernier', col: 2, row: 3, iconId: 'npc', tone: 'teal', role: 'npc' },
        { id: 'gob', name: 'Gobelin embusqué', col: 6, row: 1, iconId: 'enemy', tone: 'blood', role: 'enemy' },
      ],
    }))
    const toben = spec.tokens.find((token) => token.id === 'toben')
    expect(toben).toMatchObject({ kind: 'npc', accent: '#4fd8c0', modelKey: 'char/rogue', hpRatio: null })
    const gob = spec.tokens.find((token) => token.id === 'gob')
    expect(gob).toMatchObject({ kind: 'npc', accent: '#e84545', modelKey: 'monster/skeleton_minion' })
  })
})
