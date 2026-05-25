// Composable Exploration V2 — adapte les POIs et sorties de scène depuis
// `gameStore.currentScene` au shape `ExPoi` consommé par les composants V2
// (SceneMap, MapLegend, SelectionInspector, RefChip).
import { computed } from 'vue'
import { useGameStore } from '../stores/game'
import type { ExPoi } from '../fixtures/exploration'
import type { PointOfInterest, SceneExit } from '../types'

// Mapping kind backend → tone V2.
function poiTone(kind: string | undefined): ExPoi['tone'] {
  switch ((kind ?? '').toLowerCase()) {
    case 'corpse':
    case 'hazard':
    case 'trap':
    case 'blood':
      return 'blood'
    case 'magic':
    case 'arcane':
    case 'rune':
    case 'portal':
      return 'arcane'
    case 'treasure':
    case 'loot':
    case 'objective':
    case 'gold':
      return 'gold'
    case 'cover':
    case 'medical':
    case 'water':
    case 'teal':
      return 'teal'
    default:
      return 'teal'
  }
}

// Coordonnées col → lettre (col 0 = A, col 1 = B, ...).
function colLetter(col: number): string {
  return String.fromCharCode(65 + Math.max(0, Math.min(25, col)))
}

function adaptPoi(p: PointOfInterest): ExPoi {
  const label = `${colLetter(p.position.col)}${p.position.row + 1}`
  const interaction = p.interactions?.[0]
  return {
    id: p.id,
    kind: 'repere',
    x: p.position.col,
    y: p.position.row,
    label,
    title: p.name,
    desc: p.description ?? '',
    skill: interaction?.label,
    tone: poiTone(p.kind),
  }
}

function adaptExit(e: SceneExit, isActive: boolean): ExPoi {
  const label = `${colLetter(e.position.col)}${e.position.row + 1}`
  return {
    id: e.id,
    kind: 'sortie',
    x: e.position.col,
    y: e.position.row,
    label,
    title: e.label,
    desc: e.description ?? '',
    dest: e.leads_to,
    tone: isActive ? 'gold' : 'teal',
    active: isActive,
  }
}

export function useExplorationPois() {
  const gameStore = useGameStore()

  const pois = computed<ExPoi[]>(() => {
    const scene = gameStore.currentScene
    if (!scene) return []
    const adaptedPois = (scene.pois ?? []).map(adaptPoi)
    const exits = scene.exits ?? []
    // Première sortie marquée active par défaut tant que le backend ne pousse
    // pas explicitement d'« exit actif ».
    const adaptedExits = exits.map((e, idx) => adaptExit(e, idx === exits.length - 1))
    return [...adaptedPois, ...adaptedExits]
  })

  const reperes = computed(() => pois.value.filter((p) => p.kind === 'repere'))
  const sorties = computed(() => pois.value.filter((p) => p.kind === 'sortie'))

  function findPoi(id: string | null | undefined): ExPoi | undefined {
    if (!id) return undefined
    return pois.value.find((p) => p.id === id)
  }

  return { pois, reperes, sorties, findPoi }
}
