import type {
  PointOfInterest,
  ScenePoiInteraction,
  ScenePoiInteractionIntent,
} from '../types'
import {
  isRpgMapIconId,
  type RpgMapIconId,
} from '../icons/rpgMapIcons'

export interface ResolvedScenePoiInteraction extends ScenePoiInteraction {
  id: string
  iconId: RpgMapIconId
}

const MAX_INTERACTIONS = 5
const VALID_INTENTS = new Set<ScenePoiInteractionIntent>([
  'approach',
  'talk',
  'examine',
  'listen',
  'search',
  'use',
  'custom',
])

export function resolveScenePoiInteractions(poi: PointOfInterest): ResolvedScenePoiInteraction[] {
  const sceneActions = sanitizeSceneInteractions(poi.interactions)
  const defaults = defaultInteractionsForPoi(poi)
  const merged: ResolvedScenePoiInteraction[] = []
  const seenIds = new Set<string>()
  const seenIntents = new Set<ScenePoiInteractionIntent>()

  for (const action of [...sceneActions, ...defaults]) {
    if (seenIds.has(action.id)) continue
    if (action.intent !== 'custom' && seenIntents.has(action.intent)) continue

    seenIds.add(action.id)
    if (action.intent !== 'custom') seenIntents.add(action.intent)
    merged.push(action)
    if (merged.length >= MAX_INTERACTIONS) break
  }

  return merged
}

export function buildScenePoiInteractionPrompt(
  poiName: string,
  interaction?: ScenePoiInteraction,
): string {
  if (interaction?.prompt?.trim()) return interaction.prompt.trim()

  switch (interaction?.intent) {
    case 'approach':
      return `Je me dirige vers ${poiName}.`
    case 'talk':
      return `Je m'approche de ${poiName} et lui adresse la parole.`
    case 'listen':
      return `J'écoute ce que ${poiName} dit ou laisse paraître.`
    case 'search':
      return `Je fouille autour de ${poiName}.`
    case 'use':
      return `J'interagis avec ${poiName}.`
    case 'examine':
      return `J'examine ${poiName}.`
    case 'custom':
      return `${interaction.label} : ${poiName}.`
    default:
      return `J'examine ${poiName}.`
  }
}

function defaultInteractionsForPoi(poi: PointOfInterest): ResolvedScenePoiInteraction[] {
  if (isNpcPoi(poi)) {
    return [
      makeInteraction('approach', 'Se diriger vers', 'exit-dir'),
      makeInteraction('talk', 'Parler', 'npc'),
      makeInteraction('examine', 'Observer', 'clue'),
      makeInteraction('listen', 'Écouter', 'clue'),
    ]
  }

  const key = searchableText(poi)
  if (containsAny(key, ['hazard', 'danger', 'trap', 'piege', 'menace'])) {
    return [
      makeInteraction('examine', 'Observer à distance', 'trap-danger'),
      makeInteraction('approach', 'Contourner', 'exit-dir'),
    ]
  }
  if (containsAny(key, ['chest', 'coffre', 'loot', 'treasure', 'tresor', 'item', 'objet'])) {
    return [
      makeInteraction('examine', 'Examiner', 'clue'),
      makeInteraction('search', 'Fouiller', 'chest'),
      makeInteraction('use', 'Utiliser', 'door'),
    ]
  }
  if (containsAny(key, ['clue', 'indice', 'hint', 'trace', 'examiner', 'investigate'])) {
    return [
      makeInteraction('examine', 'Examiner', 'clue'),
      makeInteraction('search', 'Fouiller', 'poi'),
    ]
  }
  if (containsAny(key, ['door', 'porte', 'gate', 'portail', 'passage', 'secret', 'hidden', 'cache'])) {
    return [
      makeInteraction('approach', 'Se diriger vers', 'exit-dir'),
      makeInteraction('examine', 'Examiner', 'clue'),
      makeInteraction('use', 'Interagir', 'door'),
    ]
  }

  return [
    makeInteraction('approach', 'Se diriger vers', 'exit-dir'),
    makeInteraction('examine', 'Examiner', 'poi'),
  ]
}

function sanitizeSceneInteractions(value: unknown): ResolvedScenePoiInteraction[] {
  if (!Array.isArray(value)) return []

  const result: ResolvedScenePoiInteraction[] = []
  value.forEach((raw, index) => {
    if (!raw || typeof raw !== 'object') return
    const item = raw as Partial<ScenePoiInteraction>
    const label = typeof item.label === 'string' ? item.label.trim() : ''
    if (!label) return

    const intent = VALID_INTENTS.has(item.intent as ScenePoiInteractionIntent)
      ? item.intent as ScenePoiInteractionIntent
      : 'custom'
    const id = typeof item.id === 'string' && item.id.trim()
      ? item.id.trim()
      : `custom-${index}-${intent}`
    const prompt = typeof item.prompt === 'string' && item.prompt.trim()
      ? item.prompt.trim()
      : undefined

    result.push({
      id,
      label,
      intent,
      ...(prompt ? { prompt } : {}),
      ...(typeof item.icon === 'string' && item.icon.trim() ? { icon: item.icon.trim() } : {}),
      ...(typeof item.default === 'boolean' ? { default: item.default } : {}),
      iconId: resolveInteractionIcon(item.icon, intent),
    })
  })

  return result
}

function makeInteraction(
  intent: ScenePoiInteractionIntent,
  label: string,
  iconId: RpgMapIconId,
): ResolvedScenePoiInteraction {
  return {
    id: intent,
    label,
    intent,
    icon: iconId,
    default: true,
    iconId,
  }
}

function resolveInteractionIcon(icon: unknown, intent: ScenePoiInteractionIntent): RpgMapIconId {
  if (isRpgMapIconId(icon)) return icon
  if (typeof icon === 'string') {
    const normalized = icon.trim().toLowerCase().replace(/_/g, '-')
    if (isRpgMapIconId(normalized)) return normalized
  }

  switch (intent) {
    case 'approach':
      return 'exit-dir'
    case 'talk':
      return 'npc'
    case 'listen':
    case 'examine':
      return 'clue'
    case 'search':
      return 'poi'
    case 'use':
      return 'door'
    case 'custom':
      return 'poi'
  }
}

function isNpcPoi(poi: PointOfInterest): boolean {
  return containsAny(searchableText(poi), ['npc', 'pnj', 'personnage', 'villager', 'merchant', 'marchand'])
}

function searchableText(poi: PointOfInterest): string {
  return normalizeText([poi.kind, poi.icon, poi.name, poi.description].filter(Boolean).join(' '))
}

function containsAny(search: string, needles: string[]): boolean {
  return needles.some((needle) => search.includes(normalizeText(needle)))
}

function normalizeText(value: string): string {
  return value
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .replace(/[_-]+/g, ' ')
    .trim()
}
