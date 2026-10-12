import { describe, expect, it } from 'vitest'
import type { MapEdge, MapNode } from '../../../types'
import {
  edgeState,
  fitViewport,
  glyphFor,
  measureLabel,
  overlapArea,
  parseTravelDays,
  placeLabels,
  project,
  STATUS_PRIORITY,
  unitsPerDay,
  visibleEdges,
  zoomAt,
} from '../mapLayout'

// Région PUBLIQUE réelle de la session « Le Sanctuaire du Crépuscule Éternel »
// (critère du lot 5 : aucune étiquette chevauchante). Les deux lieux du haut sont
// à 6 unités l'un de l'autre et portent de longs noms.
const SANCTUAIRE: MapNode[] = [
  { id: 'le_porche_des_larmes', name: 'Le Porche des Larmes', kind: 'settlement', status: 'current', position: { x: 30, y: 58 } },
  { id: 'le_c_ur_du_sanctuaire', name: 'Le Cœur du Sanctuaire', kind: 'dungeon', status: 'rumored', position: { x: 68, y: 40 } },
  { id: 'porche_larmes', name: "L'entrée du Sanctuaire (Plaines du Crépuscule)", kind: 'settlement', status: 'visited', position: { x: 45, y: 58 } },
  {
    id: 'recuperer_codex_lunaire_dans',
    name: 'Récupérer le Codex Lunaire dans les profondeurs du Sanctuaire.',
    kind: 'landmark',
    status: 'rumored',
    position: { x: 62, y: 42 },
  },
]

function layout(nodes: MapNode[], width: number, height: number) {
  const view = fitViewport(nodes.map((node) => node.position), width, height)
  const requests = nodes.map((node) => {
    const point = project(view, node.position)
    const metrics = measureLabel(node.name, { fontPx: 11, maxWidth: 156 })
    return { id: node.id, ...point, width: metrics.width, height: metrics.height, radius: 17, priority: STATUS_PRIORITY[node.status] }
  })
  return { requests, placed: placeLabels(requests, { width, height }) }
}

describe('mapLayout — cadrage', () => {
  it('cadre sans déformer (échelle uniforme) et centre les lieux', () => {
    const view = fitViewport([{ x: 30, y: 58 }, { x: 68, y: 40 }], 900, 500, { padding: 50 })
    const a = project(view, { x: 30, y: 58 })
    const b = project(view, { x: 68, y: 40 })
    expect((a.x + b.x) / 2).toBeCloseTo(450)
    expect((a.y + b.y) / 2).toBeCloseTo(250)
    expect(a.x).toBeGreaterThanOrEqual(50)
    expect(b.x).toBeLessThanOrEqual(850)
  })

  it('ne zoome pas à l’absurde sur deux lieux voisins (étendue minimale)', () => {
    const view = fitViewport([{ x: 50, y: 50 }, { x: 51, y: 50 }], 800, 600, { padding: 0, minSpan: 40 })
    expect(view.scale).toBeCloseTo(600 / 40)
  })

  it('zoome autour du curseur, borné', () => {
    const view = { scale: 5, tx: 0, ty: 0 }
    const zoomed = zoomAt(view, 2, { x: 100, y: 100 }, { min: 1, max: 8 })
    expect(zoomed.scale).toBe(8)
    // Le point sous le curseur ne bouge pas.
    const world = { x: 20, y: 20 }
    expect(project(zoomed, world)).toEqual(project(view, world))
  })
})

describe('mapLayout — étiquettes', () => {
  it('Sanctuaire : aucune étiquette ne se chevauche ni ne couvre un picto', () => {
    for (const [width, height] of [[640, 580], [900, 560], [420, 360]] as const) {
      const { requests, placed } = layout(SANCTUAIRE, width, height)
      expect(placed).toHaveLength(SANCTUAIRE.length)
      for (let i = 0; i < placed.length; i++) {
        for (let j = i + 1; j < placed.length; j++) {
          expect(overlapArea(placed[i]!, placed[j]!), `${placed[i]!.id} × ${placed[j]!.id} @${width}`).toBe(0)
        }
        for (const pin of requests) {
          const box = { left: pin.x - pin.radius, top: pin.y - pin.radius, width: pin.radius * 2, height: pin.radius * 2 }
          if (pin.id !== placed[i]!.id) expect(overlapArea(placed[i]!, box)).toBe(0)
        }
      }
    }
  })

  it('un nom-phrase est coupé sur 2 lignes avec ellipse (le titre complet reste en infobulle)', () => {
    const metrics = measureLabel('Récupérer le Codex Lunaire dans les profondeurs du Sanctuaire.', { fontPx: 11, maxWidth: 156 })
    expect(metrics.lines).toHaveLength(2)
    expect(metrics.lines[1]!.endsWith('…')).toBe(true)
    expect(metrics.width).toBeLessThanOrEqual(166)
  })

  it('le lieu courant est placé en premier, sous son picto', () => {
    const { placed } = layout(SANCTUAIRE, 900, 560)
    expect(placed.find((label) => label.id === 'le_porche_des_larmes')?.side).toBe('below')
  })
})

describe('mapLayout — routes et échelle', () => {
  const byId = new Map(SANCTUAIRE.map((node) => [node.id, node]))
  const edge = (from: string, to: string, extra: Partial<MapEdge> = {}): MapEdge => ({ id: `${from}-${to}`, from, to, kind: 'road', ...extra })

  it('route parcourue / connue / rumeur selon les lieux', () => {
    expect(edgeState(edge('le_porche_des_larmes', 'porche_larmes'), byId)).toBe('traveled')
    expect(edgeState(edge('porche_larmes', 'recuperer_codex_lunaire_dans'), byId)).toBe('rumored')
  })

  it('jamais de route cachée ni vers un lieu absent', () => {
    const edges = [
      edge('le_porche_des_larmes', 'porche_larmes'),
      edge('le_porche_des_larmes', 'le_c_ur_du_sanctuaire', { hidden: true }),
      edge('porche_larmes', 'inconnu'),
    ]
    expect(visibleEdges(edges, byId).map((e) => e.id)).toEqual(['le_porche_des_larmes-porche_larmes'])
  })

  it('lit les durées de trajet, et n’invente pas d’échelle sans données', () => {
    expect(parseTravelDays('2 jours de marche.')).toBe(2)
    expect(parseTravelDays('Une demi-journée par la route côtière.')).toBe(0.5)
    expect(parseTravelDays('trois jours, la route monte')).toBe(3)
    expect(parseTravelDays('Trajet à confirmer par les choix du groupe.')).toBeNull()
    expect(unitsPerDay([edge('le_porche_des_larmes', 'porche_larmes', { travel_hint: 'Trajet à confirmer.' })], byId)).toBeNull()
    expect(unitsPerDay([edge('le_porche_des_larmes', 'porche_larmes', { travel_hint: '3 jours' })], byId)).toBeCloseTo(5)
  })
})

describe('mapLayout — pictos', () => {
  it('le nom précise le type de lieu en région, le kind en ville', () => {
    expect(glyphFor({ kind: 'settlement', name: 'Port Nyanzaru (Chult)' }, 'region')).toBe('port')
    expect(glyphFor({ kind: 'settlement', name: "L'entrée du Sanctuaire" }, 'region')).toBe('temple')
    expect(glyphFor({ kind: 'settlement', name: 'Le Porche des Larmes' }, 'region')).toBe('village')
    expect(glyphFor({ kind: 'tavern', name: 'Le Hareng Saur' }, 'city')).toBe('tavern')
    expect(glyphFor({ kind: 'gate', name: 'Porte du Nord' }, 'city')).toBe('gate')
  })
})
