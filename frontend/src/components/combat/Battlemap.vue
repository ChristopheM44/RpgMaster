<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useCharacterStore } from '../../stores/character'
import { useGameStore } from '../../stores/game'
import RpgMapIcon from '../common/RpgMapIcon.vue'
import Scene3DCanvas from '../scene3d/Scene3DCanvas.vue'
import { buildCombatSpec } from '../../engine3d/adapters/combatAdapter'
import { aoeCells } from '../../engine3d/adapters/aoe'
import type { PickResult } from '../../engine3d/types'
import { chebyshevLine } from '../../engine3d/utils/gridMath'
import {
  resolveScenePoiInteractions,
  type ResolvedScenePoiInteraction,
} from '../../utils/scenePoiInteractions'
import {
  iconForCombatZone,
  iconForCombatant,
  iconForExit,
  iconForPartyMember,
  iconForPoi,
  semanticRoleForPoi,
  type RpgMapIconId,
} from '../../icons/rpgMapIcons'
import type {
  CombatantState,
  GridPosition,
  PendingSpellAim,
  PointOfInterest,
  ScenePoiInteraction,
  SceneExit,
  SceneElement,
  SceneLayout,
  SceneTheme,
} from '../../types'

type MapInteractionMode = 'inspect' | 'move' | 'attack' | 'spell'
type MapZoom = 'normal' | 'large'
type SelectionKind = 'poi' | 'exit' | 'party' | 'combatant' | 'move' | 'obstacle' | 'zone'


interface SelectedThing {
  kind: SelectionKind
  id: string
  name: string
  position: GridPosition
  description: string
  meta?: string
  actionLabel?: string
  actions?: ResolvedScenePoiInteraction[]
  iconId: RpgMapIconId
  iconLabel?: string
}

interface LegendEntry {
  id: string
  kind: SelectionKind | 'reachable'
  label: string
  detail: string
  iconId: RpgMapIconId
  tone: 'gold' | 'teal' | 'arcane' | 'blood' | 'green' | 'muted'
  position?: GridPosition
}

interface PartyMarker {
  id: string
  name: string
  position: GridPosition
  token: string
  iconId: RpgMapIconId
}

const props = withDefaults(defineProps<{
  mode?: 'combat' | 'exploration'
  /** 'lean' hides the internal header and side panel — used by V2 CombatLayout. */
  variant?: 'standard' | 'lean'
  sceneLayout?: SceneLayout | null
  myCharacterId?: string
  isMyTurn?: boolean
  speedM?: number
  interactionMode?: MapInteractionMode
  /** Sort à aire en cours de visée (CombatLayout V2) — null sinon. */
  pendingSpell?: PendingSpellAim | null
  panelHeight?: string
}>(), {
  mode: 'combat',
  variant: 'standard',
  sceneLayout: null,
  interactionMode: 'inspect',
  pendingSpell: null,
  panelHeight: undefined,
})

const isLean = computed(() => props.variant === 'lean')

const emit = defineEmits<{
  move: [col: number, row: number]
  sceneExit: [exitId: string, label: string]
  scenePoi: [poiId: string, name: string, interaction?: ScenePoiInteraction]
  target: [targetId: string, mode: MapInteractionMode]
  modeChange: [mode: MapInteractionMode]
  flee: [exitId: string]
  /** Sort à aire confirmé : cellule centrale du gabarit + cible la plus proche dessous. */
  castAt: [col: number, row: number, targetId: string | undefined]
}>()

const gameStore = useGameStore()
const charStore = useCharacterStore()

const isCollapsed = ref(false)
const isFullscreen = ref(false)
const zoom = ref<MapZoom>('normal')
const selected = ref<SelectedThing | null>(null)

const isExploration = computed(() => props.mode === 'exploration')
const activeScene = computed(() => props.sceneLayout ?? gameStore.currentScene)
const storagePrefix = computed(() => `rpg.map.${props.mode}`)

const cols = computed(() => isExploration.value ? activeScene.value?.cols ?? 8 : gameStore.gridConfig?.cols ?? 10)
const rows = computed(() => isExploration.value ? activeScene.value?.rows ?? 8 : gameStore.gridConfig?.rows ?? 8)
const cellSizeM = computed(() => isExploration.value ? activeScene.value?.cell_size_m ?? 1.5 : gameStore.gridConfig?.cell_size_m ?? 1.5)
const mapTitle = computed(() => isExploration.value ? 'Carte de scène' : 'Battlemap tactique')
const terrainLabel = computed(() => activeScene.value?.terrain?.replaceAll('_', ' ') ?? 'lieu actuel')

const cellMap = computed(() => {
  const map: Record<string, CombatantState> = {}
  if (isExploration.value) return map
  for (const combatant of gameStore.combatants) {
    if (combatant.position) map[positionKey(combatant.position)] = combatant
  }
  return map
})

const exitMap = computed(() => {
  const map: Record<string, SceneExit> = {}
  for (const exit of activeScene.value?.exits ?? []) {
    if (exit.position) map[positionKey(exit.position)] = exit
  }
  return map
})

const displayPois = computed(() => {
  const exits = activeScene.value?.exits ?? []
  return (activeScene.value?.pois ?? []).filter((poi) => !isDuplicateExitPoi(poi, exits))
})

const poiMap = computed(() => {
  const map: Record<string, PointOfInterest> = {}
  for (const poi of displayPois.value) {
    if (poi.position) map[positionKey(poi.position)] = poi
  }
  return map
})

const partyMap = computed(() => {
  const map: Record<string, PartyMarker> = {}
  for (const marker of partyMarkers.value) map[positionKey(marker.position)] = marker
  return map
})

const partyMarkers = computed<PartyMarker[]>(() => {
  const positions = activeScene.value?.party_positions ?? {}
  return Object.entries(positions).map(([id, position]) => {
    const character = charStore.sessionCharacters.find((c) => c.id === id)
    const name = character?.name ?? id.replaceAll('_', ' ')
    return {
      id,
      name,
      position,
      token: tokenForName(name),
      iconId: iconForPartyMember({
        isCurrentPlayer: id === props.myCharacterId,
        isAi: Boolean(character?.is_ai),
      }),
    }
  })
})

const myPos = computed((): GridPosition | null => {
  const me = gameStore.combatants.find((c) => c.id === props.myCharacterId)
  return me?.position ?? null
})

const reachableCells = computed((): Set<string> => {
  if (isExploration.value || !props.isMyTurn || !props.myCharacterId) return new Set()
  const reachable = gameStore.reachableCells[props.myCharacterId]
  return new Set((reachable?.free ?? []).map(positionKey))
})

/** Chemin prévisualisé vers la destination en attente : A* backend si fourni
 *  (reachableCells.paths, départ inclus), sinon ligne Chebyshev. */
const pendingPath = computed((): GridPosition[] => {
  if (isExploration.value || selected.value?.kind !== 'move' || !props.myCharacterId) return []
  const destination = selected.value.position
  const fromStore = gameStore.reachableCells[props.myCharacterId]?.paths?.[positionKey(destination)]
  if (fromStore?.length) return fromStore
  return myPos.value ? chebyshevLine(myPos.value, destination) : []
})

// ── Visée de sort à aire (gabarit AoE) ───────────────────────────────────────
/** Cellule cliquée pour ancrer le gabarit ; le survol prévisualise avant le clic. */
const aimedCell = ref<GridPosition | null>(null)
const hoveredCell = ref<GridPosition | null>(null)

watch(() => [props.pendingSpell, props.interactionMode], () => {
  aimedCell.value = null
  hoveredCell.value = null
})

const aoePreview = computed((): { cells: GridPosition[]; center: GridPosition; valid: boolean } | null => {
  const spell = props.pendingSpell
  if (!spell || isExploration.value || !myPos.value) return null
  const center = spell.origin === 'self' ? myPos.value : aimedCell.value ?? hoveredCell.value
  if (!center) return null
  const valid =
    spell.origin === 'self'
    || distanceCells(myPos.value, center) * cellSizeM.value <= Math.max(spell.rangeM, cellSizeM.value)
  const cells = aoeCells({
    shape: spell.shape,
    sizeM: spell.sizeM,
    cellSizeM: cellSizeM.value,
    origin: { col: myPos.value.col, row: myPos.value.row },
    target: { col: center.col, row: center.row },
    dims: { cols: cols.value, rows: rows.value },
  })
  return { cells, center, valid }
})

/** Confirmation possible : sort self (gabarit fixe) ou cellule ancrée valide. */
const aoeReadyToCast = computed(() => {
  const preview = aoePreview.value
  if (!preview || !props.pendingSpell) return false
  if (props.pendingSpell.origin === 'self') return true
  return aimedCell.value !== null && preview.valid
})

function confirmCastAt() {
  const preview = aoePreview.value
  if (!preview || !aoeReadyToCast.value) return
  const covered = new Set(preview.cells.map((cell) => positionKey(cell)))
  const candidates = gameStore.combatants.filter(
    (c) => c.kind === 'monster' && c.hp_current > 0 && c.position && covered.has(positionKey(c.position)),
  )
  candidates.sort(
    (a, b) => distanceCells(a.position!, preview.center) - distanceCells(b.position!, preview.center),
  )
  emit('castAt', preview.center.col, preview.center.row, candidates[0]?.id)
  aimedCell.value = null
}


const obstacles = computed(() => isExploration.value ? [] : gameStore.gridDecoration?.obstacles ?? [])
const zones = computed(() => isExploration.value ? [] : gameStore.gridDecoration?.zones ?? [])
const obstacleSet = computed(() => new Set(obstacles.value.map(positionKey)))
const zoneByCell = computed(() => {
  const map: Record<string, { id: string; name: string; kind?: string; icon?: string; type?: string }> = {}
  for (const zone of zones.value) {
    for (const cell of zone.cells) map[positionKey(cell)] = zone
  }
  return map
})

const activeModeLabel = computed(() => {
  if (props.interactionMode === 'attack') return 'Ciblage attaque'
  if (props.interactionMode === 'spell') return 'Ciblage sort'
  if (props.interactionMode === 'move') return 'Déplacement'
  return 'Inspection'
})

const summary = computed(() => {
  if (isExploration.value) {
    const pois = displayPois.value.length
    const exits = activeScene.value?.exits.length ?? 0
    const party = partyMarkers.value.length
    return `${party} héros · ${pois} repères · ${exits} sorties`
  }
  const enemies = gameStore.combatants.filter((c) => c.kind === 'monster' && c.hp_current > 0).length
  const allies = gameStore.combatants.filter((c) => c.kind === 'pc').length
  return `${allies} alliés · ${enemies} ennemis · ${reachableCells.value.size} cases accessibles`
})

const theme = computed<SceneTheme>(() => {
  return activeScene.value?.scene_theme ?? (gameStore.gridConfig as any)?.scene_theme ?? 'forest'
})



const legendEntries = computed<LegendEntry[]>(() => {
  if (isExploration.value) {
    return [
      ...partyMarkers.value.map((marker) => ({
        id: `party-${marker.id}`,
        kind: 'party' as const,
        label: marker.name,
        detail: marker.id === props.myCharacterId
          ? 'Position du joueur'
          : marker.iconId === 'ai-companion' ? 'Compagnon IA' : 'Membre du groupe',
        iconId: marker.iconId,
        tone: marker.id === props.myCharacterId
          ? 'gold' as const
          : marker.iconId === 'ai-companion' ? 'arcane' as const : 'teal' as const,
        position: marker.position,
      })),
      ...(activeScene.value?.exits ?? []).map((exit) => ({
        id: `exit-${exit.id}`,
        kind: 'exit' as const,
        label: exit.label,
        detail: exit.description || (exit.leads_to ? `Vers ${exit.leads_to}` : 'Sortie possible'),
        iconId: iconForExit(exit),
        tone: 'teal' as const,
        position: exit.position,
      })),
      ...displayPois.value.map((poi) => ({
        id: `poi-${poi.id}`,
        kind: 'poi' as const,
        label: poi.name,
        detail: poi.description || defaultPoiDescription(poi),
        iconId: iconForPoi(poi),
        tone: toneForPoi(poi),
        position: poi.position,
      })),
    ]
  }

  const combatants = gameStore.combatants.map((combatant) => ({
    id: `combatant-${combatant.id}`,
    kind: 'combatant' as const,
    label: combatant.name,
    detail: combatant.kind === 'monster'
      ? `Ennemi · PV ${combatant.hp_current}/${combatant.hp_max}`
      : `Allié · PV ${combatant.hp_current}/${combatant.hp_max}`,
    iconId: iconForCombatant(combatant),
    tone: combatant.kind === 'monster' ? 'blood' as const : 'arcane' as const,
    position: combatant.position,
  })).filter((entry) => entry.position)

  const zoneEntries = zones.value.map((zone) => ({
    id: `zone-${zone.id}`,
    kind: 'zone' as const,
    label: zone.name,
    detail: zone.kind ? `Zone ${zone.kind}` : 'Zone tactique',
    iconId: iconForCombatZone(zone),
    tone: 'gold' as const,
    position: zone.cells[0],
  })).filter((entry) => entry.position)

  return [
    ...combatants,
    ...zoneEntries,
    ...(obstacles.value.length
      ? [{
          id: 'obstacles',
          kind: 'obstacle' as const,
          label: 'Obstacles',
          detail: `${obstacles.value.length} case${obstacles.value.length > 1 ? 's' : ''}`,
          iconId: 'c-obstacle' as const,
          tone: 'muted' as const,
          position: obstacles.value[0],
        }]
      : []),
    ...(reachableCells.value.size
      ? [{
          id: 'reachable',
          kind: 'reachable' as const,
          label: 'Déplacement',
          detail: `${reachableCells.value.size} cases accessibles`,
          iconId: 'c-move-tile' as const,
          tone: 'green' as const,
        }]
      : []),
  ]
})

const pendingMoveDistance = computed((): string => {
  const sel = selected.value
  if (!sel || sel.kind !== 'move' || !myPos.value) return ''
  return formatMeters(distanceCells(myPos.value, sel.position) * cellSizeM.value)
})

const selectedElementId = computed(() => {
  const current = selected.value
  if (!current) return null
  if (current.kind === 'poi') {
    return displayPois.value.find((poi) => poi.id === current.id)?.element_id ?? null
  }
  if (current.kind === 'exit') {
    return (activeScene.value?.exits ?? []).find((exit) => exit.id === current.id)?.element_id ?? null
  }
  return null
})

// ─── Pont vers le moteur 3D ──────────────────────────────────────────────────

const scene3dRef = ref<InstanceType<typeof Scene3DCanvas> | null>(null)

const classById = computed<Record<string, string>>(() => {
  const map: Record<string, string> = {}
  for (const character of charStore.sessionCharacters) map[character.id] = character.char_class
  return map
})

const combatSpec = computed(() => buildCombatSpec({
  scene: activeScene.value,
  gridConfig: gameStore.gridConfig,
  isExploration: isExploration.value,
  combatants: gameStore.combatants,
  classById: classById.value,
  myCharacterId: props.myCharacterId ?? null,
  selectedCombatantId: gameStore.selectedCombatantId,
  interactionMode: props.interactionMode,
  reachableFree: !isExploration.value && props.isMyTurn && props.myCharacterId
    ? gameStore.reachableCells[props.myCharacterId]?.free ?? []
    : [],
  gridDecoration: {
    obstacles: obstacles.value,
    zones: zones.value.map((zone) => ({
      id: zone.id,
      name: zone.name,
      cells: zone.cells,
      icon: iconForCombatZone(zone),
    })),
  },
  partyMarkers: isExploration.value
    ? partyMarkers.value.map((marker) => ({
        id: marker.id,
        name: marker.name,
        col: marker.position.col,
        row: marker.position.row,
        isMe: marker.id === props.myCharacterId,
        isAi: marker.iconId === 'ai-companion',
      }))
    : [],
  pois: displayPois.value
    .filter((poi) => poi.position)
    .map((poi) => ({
      id: poi.id,
      name: poi.name,
      col: poi.position.col,
      row: poi.position.row,
      iconId: iconForPoi(poi),
      tone: toneForPoi(poi),
      elementId: poi.element_id ?? null,
      role: semanticRoleForPoi(poi),
    })),
  exits: (activeScene.value?.exits ?? [])
    .filter((exit) => exit.position)
    .map((exit) => ({
      id: exit.id,
      label: exit.label,
      col: exit.position.col,
      row: exit.position.row,
      iconId: iconForExit(exit),
      active: exit.active ?? true,
      elementId: exit.element_id ?? null,
    })),
  pendingMove: selected.value?.kind === 'move' ? selected.value.position : null,
  pendingPath: pendingPath.value,
  pendingAoe: aoePreview.value,
  selectedElementId: selectedElementId.value,
}))

/** Route un pick 3D vers les sélecteurs historiques (priorités préservées). */
function onMapPick(pick: PickResult): void {
  if (pick.type === 'cell') {
    handleCellClick(pick.col, pick.row)
    return
  }
  // Visée AoE : cliquer un combattant ancre le gabarit sur sa cellule.
  if (props.pendingSpell && props.interactionMode === 'spell' && pick.type === 'token') {
    const combatant = gameStore.combatants.find((item) => item.id === pick.id)
    if (combatant?.position && props.pendingSpell.origin === 'point') {
      aimedCell.value = combatant.position
      return
    }
  }
  if (pick.type === 'element') {
    const element = (activeScene.value?.elements ?? []).find((item) => item.id === pick.id)
    if (element) selectSceneElement(element)
    return
  }
  if (pick.tokenKind === 'combatant') {
    const combatant = gameStore.combatants.find((item) => item.id === pick.id)
    if (combatant) selectCombatant(combatant)
  } else if (pick.tokenKind === 'exit') {
    const exit = (activeScene.value?.exits ?? []).find((item) => item.id === pick.id)
    if (exit) selectExit(exit)
  } else if (pick.tokenKind === 'poi' || pick.tokenKind === 'npc') {
    const poi = displayPois.value.find((item) => item.id === pick.id)
    if (poi) selectPoi(poi)
  } else {
    const marker = partyMarkers.value.find((item) => item.id === pick.id)
    if (marker) selectParty(marker)
  }
}

/** Survol : prévisualise le gabarit AoE avant le clic d'ancrage. */
function onMapHover(pick: PickResult | null): void {
  if (!props.pendingSpell || props.interactionMode !== 'spell') {
    hoveredCell.value = null
    return
  }
  if (!pick) {
    hoveredCell.value = null
    return
  }
  if (pick.type === 'cell') {
    hoveredCell.value = { col: pick.col, row: pick.row }
  } else if (pick.type === 'token') {
    const combatant = gameStore.combatants.find((item) => item.id === pick.id)
    if (combatant?.position) hoveredCell.value = combatant.position
  }
}

onMounted(loadPreferences)

watch(storagePrefix, () => {
  selected.value = null
  loadPreferences()
})

watch(
  () => [cols.value, rows.value, props.mode],
  () => {
    selected.value = null
  },
)

watch([isCollapsed, zoom], () => {
  savePreference('collapsed', isCollapsed.value ? '1' : '0')
  savePreference('zoom', zoom.value)
  scene3dRef.value?.setZoomPreset(zoom.value === 'large' ? 'close' : 'normal')
})

function loadPreferences() {
  isCollapsed.value = readPreference('collapsed') === '1'
  zoom.value = readPreference('zoom') === 'large' ? 'large' : 'normal'
}

function readPreference(key: string): string | null {
  try {
    return window.localStorage.getItem(`${storagePrefix.value}.${key}`)
  } catch {
    return null
  }
}

function savePreference(key: string, value: string) {
  try {
    window.localStorage.setItem(`${storagePrefix.value}.${key}`, value)
  } catch {
    // localStorage can be unavailable in private contexts.
  }
}

function positionKey(position: GridPosition): string {
  return `${position.col},${position.row}`
}

function distanceCells(a: GridPosition, b: GridPosition): number {
  return Math.max(Math.abs(a.col - b.col), Math.abs(a.row - b.row))
}

function formatMeters(value: number): string {
  return Number.isInteger(value) ? `${value} m` : `${value.toFixed(1)} m`
}


function tokenForName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  const letters = parts.length > 1 ? parts.map((p) => p[0]).join('') : name.slice(0, 2)
  return letters.toUpperCase()
}


function clampPosition(position: GridPosition): GridPosition {
  return {
    col: Math.max(0, Math.min(position.col, cols.value - 1)),
    row: Math.max(0, Math.min(position.row, rows.value - 1)),
  }
}


function isDuplicateExitPoi(poi: PointOfInterest, exits: SceneExit[]): boolean {
  const role = semanticRoleForPoi(poi)
  if (role !== 'exit' && role !== 'passage') return false
  return exits.some((exit) =>
    exit.id === poi.id
    || Boolean(exit.position && positionKey(exit.position) === positionKey(poi.position)),
  )
}

function toneForPoi(poi: PointOfInterest): LegendEntry['tone'] {
  const role = semanticRoleForPoi(poi)
  if (role === 'enemy' || role === 'hazard') return 'blood'
  if (role === 'npc' || role === 'exit' || role === 'passage') return 'teal'
  if (role === 'clue') return 'arcane'
  if (role === 'cover' || role === 'unknown' || role === 'fog') return 'muted'
  if (role === 'safe') return 'green'
  return 'gold'
}

function defaultPoiDescription(poi: PointOfInterest): string {
  const kind = poi.kind.replaceAll('_', ' ')
  const role = semanticRoleForPoi(poi)
  if (role === 'enemy') return `${poi.name} représente une présence hostile à surveiller avant d'agir.`
  if (role === 'cover') return `${poi.name} peut servir de couvert ou gêner les déplacements.`
  if (toneForPoi(poi) === 'blood') return `${poi.name} semble pouvoir poser un risque. Inspectez avant d'agir.`
  if (kind.includes('passage')) return `${poi.name} peut indiquer un passage ou une ligne de fuite.`
  if (kind.includes('clue') || kind.includes('indice')) return `${poi.name} mérite une observation attentive.`
  return `${poi.name} est un repère notable de la scène.`
}

function selectPoi(poi: PointOfInterest) {
  const actions = resolveScenePoiInteractions(poi)
  selected.value = {
    kind: 'poi',
    id: poi.id,
    name: poi.name,
    position: poi.position,
    description: poi.description || defaultPoiDescription(poi),
    meta: poi.kind.replaceAll('_', ' '),
    actions,
    iconId: iconForPoi(poi),
    iconLabel: poi.name,
  }
}

function selectExit(exit: SceneExit) {
  selected.value = {
    kind: 'exit',
    id: exit.id,
    name: exit.label,
    position: exit.position,
    description: exit.description || (exit.leads_to ? `Cette sortie semble mener vers ${exit.leads_to}.` : 'Cette sortie permet de changer de zone.'),
    meta: exit.leads_to ? `Destination : ${exit.leads_to}` : 'Sortie',
    actionLabel: "S'y diriger",
    iconId: iconForExit(exit),
    iconLabel: exit.label,
  }
}

function selectParty(marker: PartyMarker) {
  selected.value = {
    kind: 'party',
    id: marker.id,
    name: marker.name,
    position: marker.position,
    description: marker.id === props.myCharacterId
      ? 'Votre position actuelle dans la scène.'
      : marker.iconId === 'ai-companion'
        ? 'Un compagnon IA présent dans la scène.'
        : 'Un membre du groupe présent dans la scène.',
    meta: 'Groupe',
    iconId: marker.iconId,
    iconLabel: marker.name,
  }
}

function selectCombatant(combatant: CombatantState) {
  gameStore.setSelectedCombatant(combatant.id)
  const isTarget = canTargetCombatant(combatant)
  selected.value = {
    kind: 'combatant',
    id: combatant.id,
    name: combatant.name,
    position: combatant.position ?? { col: 0, row: 0 },
    description: combatant.kind === 'monster'
      ? `${combatant.name} est une cible hostile. PV ${combatant.hp_current}/${combatant.hp_max}, CA ${combatant.ac}.`
      : `${combatant.name} est un allié. PV ${combatant.hp_current}/${combatant.hp_max}, CA ${combatant.ac}.`,
    meta: combatant.kind === 'monster' ? 'Ennemi' : 'Allié',
    actionLabel: isTarget && props.interactionMode === 'attack'
      ? 'Confirmer attaque'
      : isTarget && props.interactionMode === 'spell'
        ? 'Choisir comme cible'
        : undefined,
    iconId: combatSelectionIcon(combatant),
    iconLabel: combatant.name,
  }
}

function selectMove(position: GridPosition) {
  const distance = myPos.value ? distanceCells(myPos.value, position) * cellSizeM.value : 0
  selected.value = {
    kind: 'move',
    id: positionKey(position),
    name: 'Destination',
    position,
    description: `Déplacement préparé vers ${coordinateLabel(position)}. Distance estimée : ${formatMeters(distance)}.`,
    meta: props.isMyTurn ? 'Case accessible' : 'Déplacement indisponible',
    actionLabel: props.isMyTurn ? 'Confirmer déplacement' : undefined,
    iconId: 'c-move-dest',
  }
}

function selectObstacle(position: GridPosition) {
  selected.value = {
    kind: 'obstacle',
    id: positionKey(position),
    name: 'Obstacle',
    position,
    description: 'Cette case représente un obstacle ou un couvert visible sur la carte.',
    meta: 'Décor tactique',
    iconId: 'c-obstacle',
  }
}

function selectZone(position: GridPosition, zone: { id: string; name: string; kind?: string; icon?: string; type?: string }) {
  selected.value = {
    kind: 'zone',
    id: zone.id,
    name: zone.name,
    position,
    description: zone.kind ? `Zone tactique de type ${zone.kind}.` : 'Zone tactique visible sur la carte.',
    meta: 'Zone',
    iconId: iconForCombatZone(zone),
    iconLabel: zone.name,
  }
}

function selectSceneElement(element: SceneElement) {
  const linkedExit = (activeScene.value?.exits ?? []).find((exit) => exit.element_id === element.id)
  if (linkedExit) {
    selectExit(linkedExit)
    return
  }
  const linkedPoi = displayPois.value.find((poi) => poi.element_id === element.id)
  if (linkedPoi) {
    selectPoi(linkedPoi)
    return
  }

  const position = elementAnchorPosition(element)
  selected.value = {
    kind: element.kind === 'hazard' ? 'zone' : 'obstacle',
    id: element.id,
    name: element.name,
    position,
    description: element.description || 'Élément physique notable de la carte locale.',
    meta: element.kind.replaceAll('_', ' '),
    iconId: element.kind === 'hazard' ? 'c-danger-zone' : 'c-obstacle',
    iconLabel: element.name,
  }
}

function elementAnchorPosition(element: SceneElement): GridPosition {
  const geometry = element.geometry
  if (geometry.type === 'line') {
    return clampPosition({
      col: Math.floor((geometry.from.col + geometry.to.col) / 2),
      row: Math.floor((geometry.from.row + geometry.to.row) / 2),
    })
  }
  if (geometry.type === 'rect') {
    return clampPosition({
      col: Math.floor(geometry.col + geometry.width / 2),
      row: Math.floor(geometry.row + geometry.height / 2),
    })
  }
  return clampPosition({
    col: Math.floor(geometry.col),
    row: Math.floor(geometry.row),
  })
}

function canTargetCombatant(combatant: CombatantState): boolean {
  return combatant.kind === 'monster' && combatant.id !== props.myCharacterId && combatant.hp_current > 0
}

function combatSelectionIcon(combatant: CombatantState): RpgMapIconId {
  if (canTargetCombatant(combatant) && props.interactionMode === 'attack') return 'c-atk-target'
  if (canTargetCombatant(combatant) && props.interactionMode === 'spell') return 'c-spell-target'
  if (combatant.is_active) return 'c-active-turn'
  if (combatant.id === gameStore.selectedCombatantId) return 'c-selection'
  return iconForCombatant(combatant)
}


function isLegendEntrySelected(entry: LegendEntry): boolean {
  if (!selected.value) return false
  if (entry.kind !== selected.value.kind) return false
  if (entry.id.endsWith(selected.value.id)) return true
  return Boolean(entry.position && positionKey(entry.position) === positionKey(selected.value.position))
}


function handleCellClick(col: number, row: number) {
  const position = { col, row }
  const key = positionKey(position)
  if (isExploration.value) {
    if (exitMap.value[key]) selectExit(exitMap.value[key]!)
    else if (poiMap.value[key]) selectPoi(poiMap.value[key]!)
    else if (partyMap.value[key]) selectParty(partyMap.value[key]!)
    return
  }

  // Visée de sort à aire : le clic ancre le gabarit, rien d'autre.
  if (props.pendingSpell && props.interactionMode === 'spell') {
    if (props.pendingSpell.origin === 'point') aimedCell.value = position
    return
  }

  const combatant = cellMap.value[key]
  if (combatant) {
    selectCombatant(combatant)
    return
  }
  if (obstacleSet.value.has(key)) {
    selectObstacle(position)
    return
  }
  const zone = zoneByCell.value[key]
  if (zone) {
    selectZone(position, zone)
    return
  }
  if (reachableCells.value.has(key)) {
    // Toujours prévisualiser la destination — en lean, la confirmation passe
    // par le mini-panel flottant qui s'affiche sur la carte.
    selectMove(position)
  }
}

function selectLegend(entry: LegendEntry) {
  if (!entry.position) return
  if (entry.kind === 'poi') {
    const poi = displayPois.value.find((p) => p.position && positionKey(p.position) === positionKey(entry.position!))
    if (poi) selectPoi(poi)
  } else if (entry.kind === 'exit') {
    const exit = (activeScene.value?.exits ?? []).find((e) => e.position && positionKey(e.position) === positionKey(entry.position!))
    if (exit) selectExit(exit)
  } else if (entry.kind === 'party') {
    const marker = partyMarkers.value.find((p) => p.position && positionKey(p.position) === positionKey(entry.position!))
    if (marker) selectParty(marker)
  } else if (entry.kind === 'combatant') {
    const combatant = gameStore.combatants.find((c) => c.position && positionKey(c.position) === positionKey(entry.position!))
    if (combatant) selectCombatant(combatant)
  } else if (entry.kind === 'zone') {
    const zone = zones.value.find((z) => z.cells.some((c) => positionKey(c) === positionKey(entry.position!)))
    if (zone) selectZone(entry.position, zone)
  } else if (entry.kind === 'obstacle') {
    selectObstacle(entry.position)
  }
}

const isStandingOnSelectedExit = computed(() => {
  if (selected.value?.kind !== 'exit' || !myPos.value) return false
  const exitPos = selected.value.position
  return myPos.value.col === exitPos.col && myPos.value.row === exitPos.row
})

const resolvedActionLabel = computed(() => {
  const current = selected.value
  if (!current) return undefined
  if (current.kind === 'exit') {
    if (!isExploration.value) {
      return isStandingOnSelectedExit.value ? 'Fuir le combat' : undefined
    }
    return "S'y diriger"
  }
  return current.actionLabel
})

function confirmFlee() {
  const current = selected.value
  if (!current || current.kind !== 'exit') return
  emit('flee', current.id)
  selected.value = null
}

function confirmSelection() {
  const current = selected.value
  if (!current) return
  if (current.kind === 'exit') {
    if (!isExploration.value) {
      if (isStandingOnSelectedExit.value) {
        confirmFlee()
      }
    } else {
      const exit = (activeScene.value?.exits ?? []).find((e) => e.id === current.id)
      emit('sceneExit', current.id, exit?.label ?? current.name)
    }
  } else if (current.kind === 'poi') {
    emit('scenePoi', current.id, current.name)
  } else if (current.kind === 'move') {
    emit('move', current.position.col, current.position.row)
  } else if (current.kind === 'combatant' && (props.interactionMode === 'attack' || props.interactionMode === 'spell')) {
    emit('target', current.id, props.interactionMode)
  }
}

function selectPoiAction(action: ResolvedScenePoiInteraction) {
  const current = selected.value
  if (!current || current.kind !== 'poi') return
  const interaction: ScenePoiInteraction = {
    ...(action.id ? { id: action.id } : {}),
    label: action.label,
    intent: action.intent,
    ...(action.prompt ? { prompt: action.prompt } : {}),
    ...(action.icon ? { icon: action.icon } : {}),
    ...(action.default !== undefined ? { default: action.default } : {}),
    ...(action.mechanics ? { mechanics: action.mechanics } : {}),
  }
  emit('scenePoi', current.id, current.name, interaction)
}

function coordinateLabel(position: GridPosition): string {
  return `${String.fromCharCode(65 + position.col)}${position.row + 1}`
}

function markerToneStyle(tone: LegendEntry['tone']) {
  const styles = {
    gold: { color: 'var(--color-gold)', borderColor: 'rgba(240,199,100,0.42)', background: 'rgba(240,199,100,0.1)' },
    teal: { color: 'var(--color-teal)', borderColor: 'rgba(79,216,192,0.46)', background: 'rgba(79,216,192,0.1)' },
    arcane: { color: 'var(--color-arcane)', borderColor: 'rgba(192,144,255,0.46)', background: 'rgba(192,144,255,0.1)' },
    blood: { color: 'var(--color-blood-light)', borderColor: 'rgba(232,69,69,0.46)', background: 'rgba(232,69,69,0.12)' },
    green: { color: 'var(--color-green)', borderColor: 'rgba(111,217,111,0.38)', background: 'rgba(111,217,111,0.08)' },
    muted: { color: 'var(--color-text-muted)', borderColor: 'rgba(247,236,208,0.18)', background: 'rgba(247,236,208,0.05)' },
  }
  return styles[tone]
}
</script>

<template>
  <section
    class="rpg-map-shell flex min-h-0 flex-1 flex-col overflow-hidden border"
    :class="[
      isExploration ? 'is-exploration' : 'is-combat',
      isFullscreen ? 'fixed inset-3 z-[60] rounded-lg shadow-2xl' : 'rounded-none',
      isCollapsed ? 'shrink-0 flex-none' : '',
    ]"
    :style="{
      height: isFullscreen || isCollapsed ? undefined : panelHeight ?? (isExploration ? 'min(54vh, 520px)' : undefined),
    }"
  >
    <div
      v-if="!isLean"
      class="rpg-border flex shrink-0 flex-wrap items-center justify-between gap-3 border-b px-4 py-3"
    >
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <div class="rpg-eyebrow" :class="isExploration ? 'rpg-text-gold' : 'rpg-text-blood-light'">
            {{ mapTitle }}
          </div>
          <span
            class="rpg-border-strong rpg-text-muted rounded border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em]"
          >{{ activeModeLabel }}</span>
        </div>
        <div class="rpg-text-muted mt-1 truncate text-xs capitalize">
          {{ cols * cellSizeM }} × {{ rows * cellSizeM }} m
          <template v-if="isExploration"> · {{ terrainLabel }}</template>
          · {{ summary }}
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <button
          v-if="!isExploration && interactionMode !== 'inspect'"
          class="rpg-btn-tonal tone-gold !px-3 !py-1.5 !text-[10px]"
          type="button"
          @click="emit('modeChange', 'inspect')"
        >Inspection</button>
        <button
          class="rpg-btn-secondary !px-3 !py-1.5 !text-[10px]"
          type="button"
          data-testid="map-zoom"
          @click="zoom = zoom === 'normal' ? 'large' : 'normal'"
        >{{ zoom === 'normal' ? 'Agrandir' : 'Normal' }}</button>
        <button
          class="rpg-btn-secondary !px-3 !py-1.5 !text-[10px]"
          type="button"
          data-testid="map-fullscreen"
          @click="isFullscreen = !isFullscreen"
        >{{ isFullscreen ? 'Fenêtre' : 'Plein écran' }}</button>
        <button
          class="rpg-btn-tonal tone-gold !px-3 !py-1.5 !text-[10px]"
          type="button"
          data-testid="map-collapse"
          @click="isCollapsed = !isCollapsed"
        >{{ isCollapsed ? 'Déplier' : 'Replier' }}</button>
      </div>
    </div>

    <div v-if="!isCollapsed" class="flex min-h-0 flex-1 flex-col lg:flex-row">
      <div class="flex min-h-0 flex-1 overflow-hidden p-3">
        <Scene3DCanvas
          ref="scene3dRef"
          class="rpg-map-grid-frame"
          data-testid="battlemap-grid"
          :spec="combatSpec"
          @pick="onMapPick"
          @hover="onMapHover"
        >
          <!-- Mini-panel flottant de confirmation (lean seulement) -->
          <Transition name="move-confirm">
            <div
              v-if="isLean && selected?.kind === 'move'"
              class="move-confirm-wrapper"
            >
              <div class="move-confirm-panel flex items-center gap-2">
                <!-- Info destination -->
                <div class="move-confirm-info">
                  <span class="move-confirm-icon">✥</span>
                  <div>
                    <div class="move-confirm-label">Déplacement</div>
                    <div class="move-confirm-dest">
                      {{ coordinateLabel(selected.position) }}
                      <span v-if="pendingMoveDistance" class="move-confirm-dist">{{ pendingMoveDistance }}</span>
                    </div>
                  </div>
                </div>
                <!-- Actions -->
                <button
                  class="move-confirm-btn move-confirm-btn--ok"
                  type="button"
                  data-testid="lean-confirm-move"
                  @click="confirmSelection"
                >Confirmer ✓</button>
                <button
                  class="move-confirm-btn move-confirm-btn--cancel"
                  type="button"
                  data-testid="lean-cancel-move"
                  @click="selected = null"
                >✕</button>
              </div>
            </div>
          </Transition>

          <!-- Mini-panel flottant de confirmation pour SORT À AIRE (lean seulement) -->
          <Transition name="move-confirm">
            <div
              v-if="isLean && pendingSpell && aoeReadyToCast"
              class="move-confirm-wrapper"
            >
              <div class="move-confirm-panel flex items-center gap-2" style="border-color: var(--color-arcane); box-shadow: 0 4px 24px rgba(192, 144, 255, 0.25);">
                <!-- Info gabarit -->
                <div class="move-confirm-info" style="border-right-color: rgba(192, 144, 255, 0.2);">
                  <span class="move-confirm-icon" style="color: var(--color-arcane);">✦</span>
                  <div>
                    <div class="move-confirm-label" style="color: var(--color-arcane);">Zone d'effet</div>
                    <div class="move-confirm-dest">
                      {{ aoePreview ? coordinateLabel(aoePreview.center) : '' }}
                    </div>
                  </div>
                </div>
                <!-- Actions -->
                <button
                  class="move-confirm-btn"
                  style="background: rgba(192, 144, 255, 0.15); border-color: rgba(192, 144, 255, 0.5); color: var(--color-arcane);"
                  type="button"
                  data-testid="lean-confirm-cast"
                  @click="confirmCastAt"
                >Lancer ✦</button>
                <button
                  class="move-confirm-btn move-confirm-btn--cancel"
                  type="button"
                  data-testid="lean-cancel-cast"
                  @click="aimedCell = null"
                >✕</button>
              </div>
            </div>
          </Transition>

          <!-- Mini-panel flottant de confirmation pour FUITE (lean seulement, en combat) -->
          <Transition name="move-confirm">
            <div
              v-if="isLean && !isExploration && selected?.kind === 'exit' && isStandingOnSelectedExit"
              class="move-confirm-wrapper"
            >
              <div class="move-confirm-panel flex items-center gap-2" style="border-color: var(--color-blood); box-shadow: 0 4px 24px rgba(232, 69, 69, 0.25);">
                <!-- Info fuite -->
                <div class="move-confirm-info" style="border-right-color: rgba(232, 69, 69, 0.2);">
                  <span class="move-confirm-icon" style="color: var(--color-blood-light);">🏃</span>
                  <div>
                    <div class="move-confirm-label" style="color: var(--color-blood-light);">Fuir le Combat</div>
                    <div class="move-confirm-dest" style="color: var(--color-parchment);">
                      {{ selected.name }}
                    </div>
                  </div>
                </div>
                <!-- Actions -->
                <button
                  class="move-confirm-btn"
                  style="background: rgba(232, 69, 69, 0.15); border-color: rgba(232, 69, 69, 0.5); color: var(--color-blood-light);"
                  type="button"
                  data-testid="lean-confirm-flee"
                  @click="confirmFlee"
                >Fuir ✓</button>
                <button
                  class="move-confirm-btn move-confirm-btn--cancel"
                  type="button"
                  data-testid="lean-cancel-flee"
                  @click="selected = null"
                >✕</button>
              </div>
            </div>
          </Transition>
        </Scene3DCanvas>
      </div>

      <aside
        v-if="!isLean"
        class="rpg-map-side-panel flex max-h-[48%] min-h-[210px] shrink-0 flex-col border-t lg:max-h-none lg:w-[320px] lg:border-l lg:border-t-0"
      >
        <div class="rpg-border border-b p-4">
          <div class="rpg-eyebrow rpg-text-gold mb-2">Sélection</div>
          <template v-if="selected">
            <div class="flex items-start justify-between gap-3">
              <div class="flex min-w-0 items-start gap-2.5">
                <RpgMapIcon
                  class="mt-0.5 rounded border border-parchment/10 bg-black/20"
                  :data-testid="`selection-icon-${selected.kind}`"
                  :icon-id="selected.iconId"
                  :size="28"
                  state="active"
                  :label="selected.iconLabel ?? selected.name"
                />
                <div class="min-w-0">
                  <h3 class="truncate font-display text-base font-bold text-parchment">{{ selected.name }}</h3>
                  <p class="rpg-text-muted mt-0.5 text-xs capitalize">
                    {{ selected.meta }} · {{ coordinateLabel(selected.position) }}
                  </p>
                </div>
              </div>
              <span
                class="rpg-map-coordinate-chip rounded border px-2 py-1 font-mono text-[10px]"
              >{{ coordinateLabel(selected.position) }}</span>
            </div>
            <p class="rpg-text-secondary mt-3 text-sm leading-relaxed">
              {{ selected.description }}
            </p>
            <div
              v-if="selected.kind === 'poi' && selected.actions?.length"
              class="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-1"
            >
              <button
                v-for="action in selected.actions"
                :key="action.id"
                class="rpg-map-action-button flex items-center justify-start gap-2 rounded border px-3 py-2 text-left text-[11px] font-bold uppercase tracking-[0.1em] transition hover:bg-white/[0.05]"
                :data-testid="`map-poi-action-${action.id}`"
                :data-action-intent="action.intent"
                type="button"
                @click="selectPoiAction(action)"
              >
                <RpgMapIcon
                  :icon-id="action.iconId"
                  :size="17"
                  :label="action.label"
                />
                <span class="min-w-0 truncate">{{ action.label }}</span>
              </button>
            </div>
            <button
              v-if="resolvedActionLabel"
              class="rpg-btn-primary mt-4 w-full justify-center !py-2 !text-[11px]"
              type="button"
              data-testid="map-confirm"
              @click="confirmSelection"
            >{{ resolvedActionLabel }}</button>
          </template>
          <p v-else class="rpg-text-muted text-sm leading-relaxed">
            Sélectionnez un repère, une sortie, une cible ou une destination pour voir ce que votre clic peut entraîner.
          </p>
        </div>

        <div class="min-h-0 flex-1 overflow-y-auto p-4">
          <div class="mb-2 flex items-center justify-between gap-3">
            <div class="rpg-eyebrow rpg-text-muted">Légende</div>
            <span class="rpg-text-dim text-[10px]">{{ legendEntries.length }} éléments</span>
          </div>
          <div class="space-y-2">
            <button
              v-for="entry in legendEntries"
              :key="entry.id"
              class="rpg-map-legend-row flex w-full items-center gap-2 rounded border px-2.5 py-2 text-left transition hover:bg-white/[0.04]"
              :class="{ 'is-selected': isLegendEntrySelected(entry) }"
              type="button"
              :disabled="!entry.position"
              @click="selectLegend(entry)"
            >
              <span
                class="flex h-7 w-7 shrink-0 items-center justify-center rounded border"
                :style="markerToneStyle(entry.tone)"
              >
                <RpgMapIcon
                  :data-testid="`legend-icon-${entry.id}`"
                  :icon-id="entry.iconId"
                  :size="18"
                  :state="isLegendEntrySelected(entry) ? 'active' : 'normal'"
                  :label="entry.label"
                />
              </span>
              <span class="min-w-0 flex-1">
                <span class="block truncate text-sm font-semibold text-parchment">{{ entry.label }}</span>
                <span class="rpg-text-muted block truncate text-xs">{{ entry.detail }}</span>
              </span>
              <span v-if="entry.position" class="rpg-text-dim font-mono text-[10px]">
                {{ coordinateLabel(entry.position) }}
              </span>
            </button>
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
/* ── Ghost token (destination preview en lean) ─────────────────────────────── */
.move-dest-ghost {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 2px dashed rgba(79, 216, 192, 0.7);
  background: rgba(79, 216, 192, 0.15);
  animation: ghost-pulse 1.2s ease-in-out infinite;
}

@keyframes ghost-pulse {
  0%, 100% { opacity: 0.6; transform: scale(0.95); }
  50%       { opacity: 1;   transform: scale(1.05); }
}

/* ── Wrapper positionné (la Transition anime cet élément) ──────────────────── */
.move-confirm-wrapper {
  position: absolute;
  bottom: 14px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 60;
}

/* ── Panel intérieur ────────────────────────────────────────────────────────── */
.move-confirm-panel {
  background: rgba(14, 13, 20, 0.92);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(79, 216, 192, 0.4);
  border-radius: 10px;
  padding: 8px 12px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(79, 216, 192, 0.08);
  white-space: nowrap;
}

/* ── Info destination ───────────────────────────────────────────────────────── */
.move-confirm-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-right: 12px;
  border-right: 1px solid rgba(247, 236, 208, 0.1);
}

.move-confirm-icon {
  color: var(--color-teal);
  font-size: 14px;
  line-height: 1;
}

.move-confirm-label {
  font-family: var(--font-display);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--color-teal);
  line-height: 1.2;
}

.move-confirm-dest {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--color-parchment);
  line-height: 1.3;
}

.move-confirm-dist {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-left: 4px;
}

/* ── Boutons ────────────────────────────────────────────────────────────────── */
.move-confirm-btn {
  padding: 5px 11px;
  font-size: 11px;
  font-family: var(--font-body);
  font-weight: 700;
  border-radius: 6px;
  border: 1px solid;
  cursor: pointer;
  transition: opacity 120ms ease, background 120ms ease;
}

.move-confirm-btn--ok {
  background: rgba(79, 216, 192, 0.15);
  border-color: rgba(79, 216, 192, 0.5);
  color: var(--color-teal);
}

.move-confirm-btn--ok:hover {
  background: rgba(79, 216, 192, 0.25);
}

.move-confirm-btn--cancel {
  background: transparent;
  border-color: rgba(247, 236, 208, 0.2);
  color: var(--color-text-muted);
}

.move-confirm-btn--cancel:hover {
  background: rgba(247, 236, 208, 0.05);
  color: var(--color-parchment);
}

/* ── Transitions (Transition name="move-confirm") ──────────────────────────── */
/* La Transition anime .move-confirm-wrapper ; son transform de base est translateX(-50%).
   On ajoute translateY(8px) en enter-from/leave-to pour le slide-up. */
.move-confirm-enter-active,
.move-confirm-leave-active {
  transition: opacity 160ms ease, transform 160ms ease;
}

.move-confirm-enter-from,
.move-confirm-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}

/* ── Biome & Fog Custom Decor Styles ────────────────────────────────────────── */
.scene-map-fog {
  position: absolute;
  inset: 0;
  pointer-events: none;
  animation: fog-slow-pulse 8s ease-in-out infinite alternate;
}

@keyframes fog-slow-pulse {
  0% { opacity: 0.82; transform: scale(1.0); }
  50% { opacity: 0.95; transform: scale(1.04); }
  100% { opacity: 0.78; transform: scale(0.98); }
}

.scene-map-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
</style>
