import type {
  PointOfInterest,
  ScenePoiInteraction,
  ScenePoiInteractionIntent,
} from '../types'
import {
  isRpgMapIconId,
  semanticRoleForPoi,
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

/**
 * Génère des prompts naturalistes variés selon l'intention et le nom du POI.
 * Les variantes gardent le registre à la première personne du singulier,
 * avec suffisamment de détails pour que le MJ comprenne l'intention sans
 * que la phrase ressemble à une commande de jeu textuel.
 */
export function buildScenePoiInteractionPrompt(
  poiName: string,
  interaction?: ScenePoiInteraction,
): string {
  if (interaction?.prompt?.trim()) return interaction.prompt.trim()

  switch (interaction?.intent) {
    case 'approach':
      return `Je m'approche de ${poiName} pour mieux voir ce qu'il y a là-bas.`
    case 'talk':
      return `Je m'avance vers ${poiName} et lui adresse la parole.`
    case 'listen':
      return `Je tends l'oreille vers ${poiName}, cherchant à saisir ce qui s'y dit ou s'y passe.`
    case 'search':
      return `Je fouille méthodiquement les alentours de ${poiName} à la recherche d'indices.`
    case 'use':
      return `J'essaie d'interagir avec ${poiName}.`
    case 'examine':
      return `Je m'arrête devant ${poiName} et l'examine attentivement.`
    case 'custom':
      return `${interaction.label} : ${poiName}.`
    default:
      return `Je m'arrête devant ${poiName} et l'examine attentivement.`
  }
}

// Préfixe directionnel d'interface explicitement nommé (« Vers », « Direction »,
// « Accès », « Passage »), retiré UNIQUEMENT s'il est suivi d'une préposition ou
// d'un article — preuve qu'il introduit une destination et n'est pas le nom du
// lieu lui-même (« Passage souterrain », « Accès est » restent intacts).
const EXIT_PREFIX_RE =
  /^(?:vers|direction|acc[èe]s|passage)(?=\s*:?\s+(?:vers|jusqu|à|a|au|aux|du|de|des|en|dans|le|la|les|l['’]))\s*:?\s+/i

// Préposition de mouvement résiduelle en tête après strip (« aux Égouts »,
// « vers les caves ») : on enchaîne « Je me dirige … » sans réinjecter « vers ».
const EXIT_RESIDUAL_PREP_RE = /^(?:vers|jusqu['’]?\s*[àa]|aux?|à|a|dans|en)\s+/i

// Le libellé porte déjà une structure de déplacement (verbe réfléchi en tête,
// « en direction … », ou préposition de mouvement interne) → on l'émet tel quel
// pour ne jamais fabriquer de doublon « vers … vers » (« Continuer vers X »,
// « Retour aux X », « S'enfoncer dans X »).
const EXIT_HAS_MOVEMENT_RE = /^(?:s['’]\w|en\s+direction\b)|\b(?:vers|jusqu|aux?|dans)\b/i

/**
 * Retire un préfixe directionnel d'interface en tête de libellé de sortie.
 * Ne strippe que les amorces explicitement nommées et seulement quand elles
 * introduisent une destination ; retombe sur l'original si le strip vide tout.
 */
export function cleanExitLabel(label: string): string {
  const trimmed = (label ?? '').trim()
  const stripped = trimmed.replace(EXIT_PREFIX_RE, '').trim()
  return stripped || trimmed
}

/**
 * Construit la phrase joueur pour un clic de sortie, partagée par le chemin
 * mobile (GameSessionView) et le chemin desktop (ExplorationLayout). Trois cas,
 * dont le pire reste « grammatical mais bref » — jamais un doublon de
 * préposition ni un nom de lieu tronqué :
 *  1. préfixe directionnel nommé → on le retire et on préfixe « Je me dirige vers » ;
 *  2. structure de déplacement déjà présente → libellé tel quel ;
 *  3. nom de lieu nu → on préfixe « Je me dirige vers ».
 */
export function buildSceneExitPrompt(label: string): string {
  const trimmed = (label ?? '').trim()
  if (EXIT_PREFIX_RE.test(trimmed)) {
    const rest = cleanExitLabel(trimmed)
    return EXIT_RESIDUAL_PREP_RE.test(rest)
      ? `Je me dirige ${rest}.`
      : `Je me dirige vers ${rest}.`
  }
  if (EXIT_HAS_MOVEMENT_RE.test(trimmed)) {
    return `${trimmed}.`
  }
  return `Je me dirige vers ${trimmed}.`
}

function defaultInteractionsForPoi(poi: PointOfInterest): ResolvedScenePoiInteraction[] {
  const role = semanticRoleForPoi(poi)

  if (role === 'enemy') {
    return [
      makeInteraction('examine', 'Observer', 'clue'),
      makeInteraction('approach', 'Se diriger vers', 'exit-dir'),
    ]
  }

  if (role === 'npc') {
    return [
      makeInteraction('approach', 'Se diriger vers', 'exit-dir'),
      makeInteraction('talk', 'Parler', 'npc'),
      makeInteraction('examine', 'Observer', 'clue'),
      makeInteraction('listen', 'Écouter', 'clue'),
    ]
  }

  if (role === 'hazard') {
    return [
      makeInteraction('examine', 'Observer à distance', 'trap-danger'),
      makeInteraction('approach', 'Contourner', 'exit-dir'),
    ]
  }
  if (role === 'cover') {
    return [
      makeInteraction('approach', 'Se mettre à couvert', 'c-half-cover'),
      makeInteraction('examine', 'Examiner', 'clue'),
    ]
  }
  if (role === 'loot') {
    return [
      makeInteraction('examine', 'Examiner', 'clue'),
      makeInteraction('search', 'Fouiller', 'chest'),
      makeInteraction('use', 'Utiliser', 'door'),
    ]
  }
  if (role === 'clue') {
    return [
      makeInteraction('examine', 'Examiner', 'clue'),
      makeInteraction('search', 'Fouiller', 'poi'),
    ]
  }
  if (role === 'exit' || role === 'passage') {
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
      ...(item.mechanics ? { mechanics: item.mechanics } : {}),
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
