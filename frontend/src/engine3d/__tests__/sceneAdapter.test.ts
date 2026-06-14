import { describe, expect, it } from 'vitest'
import { buildSceneSpec, DEFAULT_HEIGHT_M } from '../adapters/sceneAdapter'
import type { SceneLayout } from '../../types'
import type { ExHero, ExPoi } from '../../fixtures/exploration'

function makeScene(overrides: Partial<SceneLayout> = {}): SceneLayout {
  return {
    cols: 10,
    rows: 8,
    cell_size_m: 1.5,
    scene_theme: 'forest',
    scene_id: 'scene_test',
    pois: [],
    exits: [],
    party_positions: {},
    elements: [],
    ...overrides,
  }
}

function makeHero(overrides: Partial<ExHero> = {}): ExHero {
  return {
    id: 'hero_1',
    token: 'E',
    name: 'Elara',
    cls: 'Magicien',
    species: 'Elfe',
    hp: 14,
    hpMax: 20,
    ai: false,
    isMe: true,
    color: '#f0c764',
    pos: 'C4',
    x: 2,
    y: 3,
    ...overrides,
  } as ExHero
}

function makePoi(overrides: Partial<ExPoi> = {}): ExPoi {
  return {
    id: 'poi_1',
    kind: 'clue',
    x: 5,
    y: 5,
    label: 'F6',
    title: 'Indice',
    desc: '',
    iconId: 'clue',
    actionLabel: 'Examiner',
    tone: 'gold',
    ...overrides,
  } as ExPoi
}

describe('sceneAdapter.buildSceneSpec', () => {
  it('défauts sans scène : 12×12 forest, overlay vide, pas de picking cellule', () => {
    const spec = buildSceneSpec({ scene: null, heroes: [], pois: [], selectedId: null, highlightedIds: [] })
    expect(spec.ground).toMatchObject({ cols: 12, rows: 12, theme: 'forest', cellSizeM: 1.5 })
    expect(spec.overlay.cellPicking).toBe(false)
    expect(spec.tokens).toHaveLength(0)
  })

  it('hauteurs par kind miroir backend + hint LLM height_m prioritaire', () => {
    const scene = makeScene({
      elements: [
        { id: 'w1', name: 'Mur', kind: 'wall', geometry: { type: 'line', from: { col: 0, row: 0 }, to: { col: 4, row: 0 } } },
        { id: 'f1', name: 'Table', kind: 'furniture', geometry: { type: 'rect', col: 2, row: 2, width: 2, height: 1 }, height_m: 1.4 },
      ],
    })
    const spec = buildSceneSpec({ scene, heroes: [], pois: [], selectedId: null, highlightedIds: [] })
    const wall = spec.elements.find((element) => element.id === 'w1')
    const table = spec.elements.find((element) => element.id === 'f1')
    expect(wall?.heightM).toBe(DEFAULT_HEIGHT_M.wall)
    expect(table?.heightM).toBe(1.4)
  })

  it('asset_key : hint manifest prioritaire, valeur inconnue ignorée', () => {
    const scene = makeScene({
      elements: [
        {
          id: 'stairs1',
          name: 'Escalier',
          kind: 'stairs',
          asset_key: 'prop/stairs',
          geometry: { type: 'rect', col: 2, row: 2, width: 1, height: 1 },
        },
        {
          id: 'bad1',
          name: 'Table',
          kind: 'furniture',
          asset_key: 'prop/not_in_manifest',
          geometry: { type: 'rect', col: 4, row: 2, width: 1, height: 1 },
        },
      ],
    })
    const spec = buildSceneSpec({ scene, heroes: [], pois: [], selectedId: null, highlightedIds: [] })
    expect(spec.elements.find((element) => element.id === 'stairs1')?.modelKey).toBe('prop/stairs')
    expect(spec.elements.find((element) => element.id === 'bad1')?.modelKey).toBeNull()
  })

  it('ambiance : dungeon/cave → torchlit par défaut, hint LLM respecté', () => {
    const dungeon = buildSceneSpec({
      scene: makeScene({ scene_theme: 'dungeon' }),
      heroes: [], pois: [], selectedId: null, highlightedIds: [],
    })
    expect(dungeon.ground.ambiance.light).toBe('torchlit')
    expect(dungeon.ground.vegetationDensity).toBe(0)

    const night = buildSceneSpec({
      scene: makeScene({ ambiance: { light: 'night', fog_density: 0.8 } }),
      heroes: [], pois: [], selectedId: null, highlightedIds: [],
    })
    expect(night.ground.ambiance.light).toBe('night')
    expect(night.ground.ambiance.fogDensity).toBe(0.8)

    const invalid = buildSceneSpec({
      scene: makeScene({ ambiance: { light: 'neon' as never } }),
      heroes: [], pois: [], selectedId: null, highlightedIds: [],
    })
    expect(invalid.ground.ambiance.light).toBe('day')
  })

  it('éléments hidden filtrés, subtle marqué, lié à un POI → interactif', () => {
    const scene = makeScene({
      elements: [
        { id: 'hidden1', name: 'Trappe', kind: 'hazard', geometry: { type: 'rect', col: 1, row: 1, width: 1, height: 1 }, visibility: 'hidden' },
        { id: 'subtle1', name: 'Escalier discret', kind: 'stairs', geometry: { type: 'rect', col: 2, row: 1, width: 1, height: 1 }, visibility: 'subtle' },
        { id: 'linked1', name: 'Puits', kind: 'decor', geometry: { type: 'rect', col: 3, row: 1, width: 1, height: 1 } },
      ],
    })
    const pois = [makePoi({ id: 'poi_puits', elementId: 'linked1' })]
    const spec = buildSceneSpec({ scene, heroes: [], pois, selectedId: null, highlightedIds: [] })

    expect(spec.elements.find((element) => element.id === 'hidden1')).toBeUndefined()
    expect(spec.elements.find((element) => element.id === 'subtle1')?.subtle).toBe(true)
    const linked = spec.elements.find((element) => element.id === 'linked1')
    expect(linked?.interactive).toBe(true)
    expect(linked?.inspectable).toBe(true)
  })

  it('sélection : POI sélectionné → son élément lié porte selected', () => {
    const scene = makeScene({
      elements: [
        { id: 'linked1', name: 'Puits', kind: 'decor', geometry: { type: 'rect', col: 3, row: 1, width: 1, height: 1 } },
      ],
    })
    const pois = [makePoi({ id: 'poi_puits', elementId: 'linked1' })]
    const spec = buildSceneSpec({ scene, heroes: [], pois, selectedId: 'poi_puits', highlightedIds: [] })
    expect(spec.elements.find((element) => element.id === 'linked1')?.selected).toBe(true)
  })

  it('tokens : héros (modèle par classe FR, hp), POI (icône), sortie (exitActive)', () => {
    const spec = buildSceneSpec({
      scene: makeScene(),
      heroes: [makeHero()],
      pois: [makePoi(), makePoi({ id: 'sortie_est', kind: 'sortie', tone: 'gold', active: true, title: 'Sentier' })],
      selectedId: 'hero_1',
      highlightedIds: ['poi_1'],
    })
    const hero = spec.tokens.find((token) => token.id === 'hero_1')
    expect(hero).toMatchObject({
      kind: 'hero',
      modelKey: 'char/mage',
      selected: true,
      hpRatio: 0.7,
      accent: '#f0c764',
    })
    const poi = spec.tokens.find((token) => token.id === 'poi_1')
    expect(poi).toMatchObject({ kind: 'poi', iconId: 'clue', highlighted: true })
    const exit = spec.tokens.find((token) => token.id === 'sortie_est')
    expect(exit).toMatchObject({ kind: 'exit', exitActive: true })
  })

  it('PNJ : POI kind npc → personnage 3D teal avec nameplate sans HP', () => {
    const spec = buildSceneSpec({
      scene: makeScene(),
      heroes: [],
      pois: [makePoi({ id: 'garde_pont', kind: 'npc', title: 'Garde du pont', desc: 'Un soldat en faction.', tone: 'teal' })],
      selectedId: null,
      highlightedIds: [],
    })
    const npc = spec.tokens.find((token) => token.id === 'garde_pont')
    expect(npc).toMatchObject({
      kind: 'npc',
      modelKey: 'char/knight',
      accent: '#4fd8c0',
      hpRatio: null,
      iconId: null,
      initials: 'GA',
    })
  })

  it('ennemi : POI kind enemy → personnage 3D blood, modèle monstre', () => {
    const spec = buildSceneSpec({
      scene: makeScene(),
      heroes: [],
      pois: [
        makePoi({ id: 'gob_1', kind: 'enemy', title: 'Gobelin embusqué', tone: 'blood' }),
        makePoi({ id: 'loup_1', kind: 'enemy', title: 'Loup affamé', tone: 'blood' }),
      ],
      selectedId: null,
      highlightedIds: [],
    })
    const gobelin = spec.tokens.find((token) => token.id === 'gob_1')
    expect(gobelin).toMatchObject({ kind: 'npc', accent: '#e84545', modelKey: 'monster/skeleton_minion' })
    // Bête sans modèle crédible → pion procédural (modelKey null), mais bien un personnage.
    const loup = spec.tokens.find((token) => token.id === 'loup_1')
    expect(loup).toMatchObject({ kind: 'npc', accent: '#e84545', modelKey: null })
  })

  it('chevauchement : deux héros sur la même cellule → offsets distincts', () => {
    const spec = buildSceneSpec({
      scene: makeScene(),
      heroes: [makeHero({ id: 'h1', x: 4, y: 4 }), makeHero({ id: 'h2', x: 4, y: 4 })],
      pois: [],
      selectedId: null,
      highlightedIds: [],
    })
    const h1 = spec.tokens.find((token) => token.id === 'h1')
    const h2 = spec.tokens.find((token) => token.id === 'h2')
    expect(h1?.offsetX ?? 0).toBe(0) // premier par id → centre
    expect(h2?.offsetX !== undefined || h2?.offsetZ !== undefined).toBe(true)
  })

  it('scatterBlockedCells couvre éléments et tokens', () => {
    const scene = makeScene({
      elements: [
        { id: 'f1', name: 'Table', kind: 'furniture', geometry: { type: 'rect', col: 6, row: 2, width: 2, height: 1 } },
      ],
    })
    const spec = buildSceneSpec({
      scene,
      heroes: [makeHero({ x: 2, y: 3 })],
      pois: [makePoi({ x: 5, y: 5 })],
      selectedId: null,
      highlightedIds: [],
    })
    expect(spec.scatterBlockedCells).toContain('2,3')
    expect(spec.scatterBlockedCells).toContain('5,5')
    expect(spec.scatterBlockedCells).toContain('6,2')
    expect(spec.scatterBlockedCells).toContain('7,2')
  })

  it('elevationByCell : stairs/terrain portent (elevation+height, max), wall ignoré', () => {
    const scene = makeScene({
      elements: [
        { id: 's1', name: 'Escalier', kind: 'stairs', geometry: { type: 'rect', col: 2, row: 2, width: 2, height: 1 }, height_m: 1.2 },
        { id: 't1', name: 'Plateforme', kind: 'terrain', geometry: { type: 'rect', col: 3, row: 2, width: 1, height: 1 }, elevation_m: 2, height_m: 0.02 },
        { id: 'w1', name: 'Mur', kind: 'wall', geometry: { type: 'rect', col: 5, row: 5, width: 1, height: 1 } },
        { id: 't2', name: 'Sol plat', kind: 'terrain', geometry: { type: 'rect', col: 7, row: 7, width: 1, height: 1 } },
      ],
    })
    const spec = buildSceneSpec({ scene, heroes: [], pois: [], selectedId: null, highlightedIds: [] })
    expect(spec.elevationByCell['2,2']).toBe(1.2)
    // Conflit stairs (1.2) vs plateforme (2.02) sur la même cellule → max.
    expect(spec.elevationByCell['3,2']).toBe(2.02)
    expect(spec.elevationByCell['5,5']).toBeUndefined() // mur : on ne marche pas dessus
    expect(spec.elevationByCell['7,7']).toBeUndefined() // terrain plat (0.02 m) : carte creuse
  })

  it('visual_asset : url seulement si status ready', () => {
    const ready = buildSceneSpec({
      scene: makeScene({ visual_asset: { provider: 'x', model: 'y', status: 'ready', prompt: '', prompt_hash: 'h', url: 'http://img' } }),
      heroes: [], pois: [], selectedId: null, highlightedIds: [],
    })
    expect(ready.ground.visualAssetUrl).toBe('http://img')

    const generating = buildSceneSpec({
      scene: makeScene({ visual_asset: { provider: 'x', model: 'y', status: 'generating', prompt: '', prompt_hash: 'h', url: 'http://img' } }),
      heroes: [], pois: [], selectedId: null, highlightedIds: [],
    })
    expect(generating.ground.visualAssetUrl).toBeNull()
  })
})
