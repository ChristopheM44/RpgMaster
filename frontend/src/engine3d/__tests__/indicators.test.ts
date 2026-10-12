import { describe, expect, it } from 'vitest'
import { borderFacingForCell, exitIndicator, poiRoleFor } from '../adapters/indicators'
import { describe as describeLabel } from '../layers/LabelLayer'
import { buildSceneSpec } from '../adapters/sceneAdapter'
import type { TokenSpec } from '../types'
import type { ExHero, ExPoi } from '../../fixtures/exploration'
import type { SceneLayout } from '../../types'

const dims = { cols: 12, rows: 12 }

function token(overrides: Partial<TokenSpec>): TokenSpec {
  return {
    id: 't', kind: 'hero', name: 'Thorvald', col: 5, row: 5, accent: '#f0c764', modelKey: null, initials: 'T',
    hpRatio: 1, selected: false, highlighted: false, active: false, targetable: null, defeated: false,
    iconId: null, exitActive: false, ...overrides,
  }
}

describe('sens des sorties', () => {
  it('un escalier lié dit monter/descendre et sa direction ; sinon voyage vers le bord', () => {
    expect(exitIndicator(8, 11, { kind: 'stairs', facing: 'south', verticalDirection: 'down' }, dims))
      .toEqual({ direction: 'down', facing: 'south' })
    expect(exitIndicator(4, 0, { kind: 'stairs', facing: 'north', verticalDirection: 'up' }, dims))
      .toEqual({ direction: 'up', facing: 'north' })
    expect(exitIndicator(11, 3, undefined, dims)).toEqual({ direction: 'travel', facing: 'east' })
    expect(exitIndicator(5, 5, undefined, dims)).toEqual({ direction: 'travel', facing: null })
  })

  it('bord touché par une case', () => {
    expect(borderFacingForCell(0, 6, dims)).toBe('west')
    expect(borderFacingForCell(6, 11, dims)).toBe('south')
    expect(borderFacingForCell(6, 6, dims)).toBeNull()
  })

  it('nature des repères', () => {
    expect(poiRoleFor('clue')).toBe('clue')
    expect(poiRoleFor('hazard')).toBe('hazard')
    expect(poiRoleFor('fog')).toBe('point')
  })
})

describe('étiquettes', () => {
  it('bannière de sortie : sens, kicker et teinte d’arrivée', () => {
    const down = describeLabel(token({ kind: 'exit', name: 'Caveau', exitActive: true, exitDirection: 'down' }))
    expect(down?.kind).toBe('banner')
    expect(down?.glyph).toBe('↓')
    expect(down?.kicker).toBe('Descendre')
    const arrival = describeLabel(token({ kind: 'exit', name: 'Jardin', exitActive: true, exitDirection: 'up', arrival: true }))
    expect(arrival?.className).toContain('is-arrival')
    expect(arrival?.kicker).toBe('Arrivée · monter')
  })

  it('un danger n’a pas d’étiquette (il se lit au sol), un indice si', () => {
    expect(describeLabel(token({ kind: 'poi', poiRole: 'hazard' }))).toBeNull()
    expect(describeLabel(token({ kind: 'poi', poiRole: 'clue', name: 'Stèle' }))?.glyph).toBe('✦')
  })

  it('nom coloré par rôle, état vaincu et tour actif', () => {
    expect(describeLabel(token({ role: 'enemy', defeated: true }))?.className).toContain('e3d-role-enemy is-defeated')
    expect(describeLabel(token({ role: 'you', active: true }))?.className).toContain('e3d-role-you is-active')
  })
})

describe('adapter exploration — rôles', () => {
  it('héros, PNJ, ennemi, sortie et repère portent leur rôle', () => {
    const scene: SceneLayout = {
      cols: 12, rows: 12, cell_size_m: 1.5, scene_theme: 'dungeon', scene_id: 'jardin', pois: [], party_positions: {},
      exits: [{ id: 'exit_2', label: 'Caveau', position: { col: 8, row: 11 }, element_id: 'st' }],
      elements: [{ id: 'st', name: 'Escalier', kind: 'stairs', geometry: { type: 'rect', col: 8, row: 11, width: 1, height: 1 }, facing: 'south', vertical_direction: 'down' }],
      arrival: { exit_id: 'exit_2', from_scene_id: 'caveau' },
    }
    const hero = { id: 'h', token: 'T', name: 'Thorvald', cls: 'Guerrier', species: 'humain', hp: 10, hpMax: 10, ai: false, isMe: true, color: '#f0c764', pos: 'A1', x: 2, y: 2 } as ExHero
    const poi = (p: Partial<ExPoi>) => ({ id: 'p', kind: 'clue', x: 4, y: 4, label: 'E5', title: 'Stèle', desc: '', tone: 'gold', ...p }) as ExPoi
    const spec = buildSceneSpec({
      scene,
      heroes: [hero],
      pois: [
        poi({ id: 'npc', kind: 'npc', title: 'Odran', x: 6, y: 6 }),
        poi({ id: 'gob', kind: 'enemy', title: 'Gobelin', x: 7, y: 7 }),
        poi({ id: 'clue' }),
        poi({ id: 'exit_2', kind: 'sortie', title: 'Caveau', x: 8, y: 11, elementId: 'st', active: true }),
      ],
      selectedId: null,
      highlightedIds: [],
    })
    const byId = Object.fromEntries(spec.tokens.map((t) => [t.id, t]))
    expect(byId.h?.role).toBe('you')
    expect(byId.npc?.role).toBe('npc')
    expect(byId.gob?.role).toBe('enemy')
    expect(byId.clue?.poiRole).toBe('clue')
    expect(byId.exit_2).toMatchObject({ exitDirection: 'down', exitFacing: 'south', arrival: true })
  })
})
