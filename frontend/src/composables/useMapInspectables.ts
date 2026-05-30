import { computed } from 'vue'
import { useGameStore } from '../stores/game'
import type { SceneElement, SceneElementGeometry } from '../types'
import type { ExHero, ExPoi } from '../fixtures/exploration'

export type MapInspectableType = 'hero' | 'poi' | 'element'
export type MapInspectableTone = 'blood' | 'arcane' | 'teal' | 'gold' | 'text'

export interface MapInspectableEntity {
  entityType: MapInspectableType
  id: string
  kind: string
  label: string
  title: string
  description: string
  coordinate: string
  tone: MapInspectableTone
  actionLabel?: string
  destination?: string
  linkedEntityId?: string
}

export function coordinateFromGrid(col: number, row: number): string {
  const letter = String.fromCharCode(65 + Math.max(0, Math.min(25, Math.floor(col))))
  return `${letter}${Math.max(1, Math.floor(row) + 1)}`
}

export function elementCenter(geometry: SceneElementGeometry): { col: number; row: number } {
  if (geometry.type === 'line') {
    return {
      col: (geometry.from.col + geometry.to.col) / 2,
      row: (geometry.from.row + geometry.to.row) / 2,
    }
  }
  if (geometry.type === 'rect') {
    return {
      col: geometry.col + geometry.width / 2,
      row: geometry.row + geometry.height / 2,
    }
  }
  return { col: geometry.col, row: geometry.row }
}

export function entityForHero(hero: ExHero): MapInspectableEntity {
  return {
    entityType: 'hero',
    id: hero.id,
    kind: hero.ai ? 'companion' : 'player',
    label: hero.isMe ? 'Vous' : hero.ai ? 'Compagnon IA' : 'Allié',
    title: hero.name,
    description: `Niv.1 · ${hero.cls} · ${hero.species} · ${hero.hp}/${hero.hpMax} PV`,
    coordinate: hero.pos,
    tone: hero.isMe ? 'gold' : hero.ai ? 'arcane' : 'teal',
  }
}

export function entityForPoi(poi: ExPoi): MapInspectableEntity {
  return {
    entityType: 'poi',
    id: poi.id,
    kind: poi.kind,
    label: labelForPoiKind(poi.kind),
    title: poi.title,
    description: poi.desc,
    coordinate: poi.label,
    tone: poi.tone === 'text' ? 'text' : poi.tone,
    actionLabel: poi.actionLabel ?? poi.skill,
    destination: poi.dest,
    linkedEntityId: poi.elementId,
  }
}

export function entityForElement(
  element: SceneElement,
  linkedEntityId?: string | null,
): MapInspectableEntity {
  const center = elementCenter(element.geometry)
  const label = labelForElement(element)
  return {
    entityType: 'element',
    id: element.id,
    kind: element.kind,
    label,
    title: element.name,
    description: element.description ?? '',
    coordinate: coordinateFromGrid(center.col, center.row),
    tone: toneForElement(element),
    linkedEntityId: linkedEntityId ?? undefined,
  }
}

export function useMapInspectables() {
  const gameStore = useGameStore()
  const elements = computed(() => gameStore.currentScene?.elements ?? [])

  function findElement(id: string | null | undefined): SceneElement | undefined {
    if (!id) return undefined
    return elements.value.find((element) => element.id === id)
  }

  function linkedEntityIdForElement(elementId: string): string | null {
    const scene = gameStore.currentScene
    const poi = scene?.pois?.find((item) => item.element_id === elementId)
    if (poi) return poi.id
    const exit = scene?.exits?.find((item) => item.element_id === elementId)
    return exit?.id ?? null
  }

  return {
    elements,
    findElement,
    linkedEntityIdForElement,
  }
}

function labelForPoiKind(kind: ExPoi['kind']): string {
  switch (kind) {
    case 'npc':
      return 'PNJ'
    case 'clue':
      return 'Indice'
    case 'hazard':
      return 'Danger'
    case 'cover':
      return 'Couvert'
    case 'loot':
      return 'Butin'
    case 'sortie':
      return 'Sortie'
    case 'passage':
      return 'Passage'
    case 'fog':
      return 'Brouillard'
    case 'light':
      return 'Lumière'
    case 'ruins':
      return 'Vestiges'
    case 'safe':
      return 'Refuge'
    case 'unknown':
      return 'Inconnu'
    case 'exit':
      return 'Issue'
    default:
      return 'Repère'
  }
}

function labelForElement(element: SceneElement): string {
  if (element.kind === 'stairs') {
    return element.visibility === 'subtle' && !element.discovered ? 'Passage suspect' : 'Passage'
  }
  switch (element.kind) {
    case 'door':
      return 'Porte'
    case 'window':
      return 'Ouverture'
    case 'furniture':
      return 'Décor'
    case 'cover':
      return 'Couvert'
    case 'hazard':
      return 'Danger'
    case 'light':
      return 'Lumière'
    case 'terrain':
      return 'Terrain'
    case 'wall':
      return 'Obstacle'
    default:
      return 'Repère'
  }
}

function toneForElement(element: SceneElement): MapInspectableTone {
  switch (element.kind) {
    case 'hazard':
      return 'blood'
    case 'stairs':
      return 'arcane'
    case 'door':
    case 'light':
      return 'gold'
    case 'cover':
    case 'window':
    case 'furniture':
      return 'teal'
    default:
      return 'text'
  }
}
