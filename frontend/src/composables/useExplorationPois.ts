// Composable Exploration V2 — adapte les POIs et sorties de scène depuis
// `gameStore.currentScene` au shape `ExPoi` consommé par les composants V2
// (SceneMap, MapLegend, SelectionInspector, RefChip).
import { computed } from 'vue'
import { useGameStore } from '../stores/game'
import type { ExPoi } from '../fixtures/exploration'
import type { PointOfInterest, SceneExit } from '../types'
import {
  iconForExit,
  iconForPoi,
  semanticRoleForPoi,
  type PoiSemanticRole,
} from '../icons/rpgMapIcons'

// Mapping kind backend → tone V2.
function poiTone(role: PoiSemanticRole): ExPoi['tone'] {
  switch (role) {
    case 'enemy':
    case 'hazard':
      return 'blood'
    case 'clue':
    case 'loot':
      return 'gold'
    case 'npc':
    case 'cover':
    case 'safe':
      return 'teal'
    case 'fog':
    case 'light':
    case 'passage':
    case 'ruins':
    case 'unknown':
    case 'exit':
    case 'point':
      return 'teal'
    default:
      return 'teal'
  }
}

function roleToKind(role: PoiSemanticRole): ExPoi['kind'] {
  switch (role) {
    case 'enemy':
      return 'hazard'
    case 'npc':
      return 'npc'
    case 'hazard':
      return 'hazard'
    case 'cover':
      return 'cover'
    case 'loot':
      return 'loot'
    case 'exit':
      return 'exit'
    case 'passage':
      return 'passage'
    case 'clue':
      return 'clue'
    case 'fog':
      return 'fog'
    case 'light':
      return 'light'
    case 'ruins':
      return 'ruins'
    case 'safe':
      return 'safe'
    case 'unknown':
      return 'unknown'
    case 'point':
      return 'point'
  }
}

function defaultActionLabel(kind: ExPoi['kind']): string {
  switch (kind) {
    case 'npc':
      return 'Parler'
    case 'loot':
      return 'Fouiller'
    case 'hazard':
      return 'Examiner'
    case 'cover':
      return 'Observer'
    case 'sortie':
      return "S'y diriger"
    default:
      return 'Examiner'
  }
}

// Coordonnées col → lettre (col 0 = A, col 1 = B, ...).
function colLetter(col: number): string {
  return String.fromCharCode(65 + Math.max(0, Math.min(25, col)))
}

function adaptPoi(p: PointOfInterest): ExPoi {
  const label = `${colLetter(p.position.col)}${p.position.row + 1}`
  const interaction = p.interactions?.[0]
  const interactionDc = (interaction as { dc?: unknown } | undefined)?.dc
  const role = semanticRoleForPoi(p)
  const kind = roleToKind(role)
  const actionLabel = interaction?.label ?? defaultActionLabel(kind)
  return {
    id: p.id,
    kind,
    x: p.position.col,
    y: p.position.row,
    label,
    title: p.name,
    desc: p.description ?? '',
    skill: actionLabel,
    dc: typeof interactionDc === 'number' ? interactionDc : undefined,
    iconId: iconForPoi(p),
    actionLabel,
    interactionId: interaction?.id,
    prompt: interaction?.prompt,
    intent: interaction?.intent,
    rawKind: p.kind,
    rawIcon: p.icon,
    elementId: p.element_id,
    state: p.state,
    visibility: p.visibility,
    discovered: p.discovered,
    physicalState: p.physical_state,
    facts: p.facts,
    tone: poiTone(role),
  }
}

function adaptExit(e: SceneExit): ExPoi {
  const label = `${colLetter(e.position.col)}${e.position.row + 1}`
  const isActive = e.active ?? true
  return {
    id: e.id,
    kind: 'sortie',
    x: e.position.col,
    y: e.position.row,
    label,
    title: e.label,
    desc: e.description ?? '',
    dest: e.leads_to,
    iconId: iconForExit(e),
    elementId: e.element_id,
    actionLabel: "S'y diriger",
    tone: isActive ? 'gold' : 'teal',
    active: isActive,
  }
}

export function useExplorationPois() {
  const gameStore = useGameStore()

  const pois = computed<ExPoi[]>(() => {
    const scene = gameStore.currentScene
    if (!scene) return []
    const adaptedPois = (scene.pois ?? [])
      .filter((poi) => poi.visibility !== 'hidden' || poi.discovered === true)
      .map(adaptPoi)
    const exits = scene.exits ?? []
    const adaptedExits = exits.map(adaptExit)
    return [...adaptedPois, ...adaptedExits]
  })

  const reperes = computed(() => pois.value.filter((p) => p.kind !== 'sortie'))
  const sorties = computed(() => pois.value.filter((p) => p.kind === 'sortie'))

  function findPoi(id: string | null | undefined): ExPoi | undefined {
    if (!id) return undefined
    return pois.value.find((p) => p.id === id)
  }

  return { pois, reperes, sorties, findPoi }
}
