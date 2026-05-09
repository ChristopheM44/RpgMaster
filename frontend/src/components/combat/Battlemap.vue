<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useCharacterStore } from '../../stores/character'
import { useGameStore } from '../../stores/game'
import RpgMapIcon from '../common/RpgMapIcon.vue'
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
  type RpgMapIconState,
} from '../../icons/rpgMapIcons'
import type {
  CombatantState,
  GridPosition,
  PointOfInterest,
  ScenePoiInteraction,
  SceneExit,
  SceneLayout,
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
  sceneLayout?: SceneLayout | null
  myCharacterId?: string
  isMyTurn?: boolean
  speedM?: number
  interactionMode?: MapInteractionMode
  panelHeight?: string
}>(), {
  mode: 'combat',
  sceneLayout: null,
  interactionMode: 'inspect',
  panelHeight: undefined,
})

const emit = defineEmits<{
  move: [col: number, row: number]
  sceneExit: [exitId: string, label: string]
  scenePoi: [poiId: string, name: string, interaction?: ScenePoiInteraction]
  target: [targetId: string, mode: MapInteractionMode]
  modeChange: [mode: MapInteractionMode]
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
const cellPx = computed(() => {
  if (isFullscreen.value) return zoom.value === 'large' ? 64 : 54
  return zoom.value === 'large' ? 56 : 44
})
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
  if (isExploration.value || !props.isMyTurn || !myPos.value) return new Set()
  const maxCells = Math.floor((props.speedM ?? 9) / cellSizeM.value)
  const result = new Set<string>()
  for (let row = 0; row < rows.value; row++) {
    for (let col = 0; col < cols.value; col++) {
      const position = { col, row }
      const key = positionKey(position)
      if (cellMap.value[key] || obstacleSet.value.has(key)) continue
      const dist = distanceCells(myPos.value, position)
      if (dist > 0 && dist <= maxCells) result.add(key)
    }
  }
  return result
})

const gridCells = computed(() =>
  Array.from({ length: rows.value * cols.value }, (_, index) => ({
    col: index % cols.value,
    row: Math.floor(index / cols.value),
  })),
)

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

const mapBackground = computed(() => {
  if (isExploration.value) {
    return `
      radial-gradient(circle at 52% 48%, rgba(247,199,107,0.18), transparent 16%),
      radial-gradient(circle at 78% 35%, rgba(79,216,192,0.16), transparent 24%),
      linear-gradient(180deg, rgba(63,55,44,0.72), rgba(20,22,21,0.98))
    `
  }
  return `
    radial-gradient(circle at 78% 42%, rgba(247,199,107,0.16), transparent 13%),
    radial-gradient(circle at 35% 35%, rgba(232,69,69,0.12), transparent 30%),
    linear-gradient(180deg, rgba(78,49,36,0.45), rgba(21,19,25,0.98))
  `
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

function hpPct(cur: number, max: number): number {
  return Math.max(0, max > 0 ? (cur / max) * 100 : 0)
}

function tokenLabel(combatant: CombatantState): string {
  if (combatant.token) return combatant.token
  return tokenForName(combatant.name)
}

function tokenForName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  const letters = parts.length > 1 ? parts.map((p) => p[0]).join('') : name.slice(0, 2)
  return letters.toUpperCase()
}

function tokenBackground(combatant: CombatantState): string {
  if (combatant.kind === 'monster') {
    return `radial-gradient(circle at 35% 25%, rgba(255,255,255,0.28), ${combatant.color ?? 'var(--color-blood)'} 62%, rgba(0,0,0,0.8))`
  }
  if (combatant.kind === 'pc' && (combatant.is_ai_controlled ?? combatant.is_ai)) {
    return 'radial-gradient(circle at 35% 25%, rgba(255,255,255,0.25), var(--color-arcane) 58%, #7050b0)'
  }
  return 'radial-gradient(circle at 35% 25%, rgba(255,255,255,0.28), var(--color-arcane) 58%, var(--color-ember))'
}

function clampPosition(position: GridPosition): GridPosition {
  return {
    col: Math.max(0, Math.min(position.col, cols.value - 1)),
    row: Math.max(0, Math.min(position.row, rows.value - 1)),
  }
}

function markerStyle(position: GridPosition) {
  const clamped = clampPosition(position)
  return {
    left: `${clamped.col * cellPx.value + cellPx.value / 2}px`,
    top: `${clamped.row * cellPx.value + cellPx.value / 2}px`,
    transform: 'translate(-50%, -50%)',
  }
}

function cellBoxStyle(position: GridPosition) {
  const clamped = clampPosition(position)
  return {
    left: `${clamped.col * cellPx.value}px`,
    top: `${clamped.row * cellPx.value}px`,
    width: `${cellPx.value}px`,
    height: `${cellPx.value}px`,
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

function targetIconForMode(): RpgMapIconId {
  return props.interactionMode === 'spell' ? 'c-spell-target' : 'c-atk-target'
}

function targetLabelForMode(): string {
  return props.interactionMode === 'spell' ? 'Cible de sort' : "Cible d'attaque"
}

function selectedIconState(kind: SelectionKind, id: string): RpgMapIconState {
  return selected.value?.kind === kind && selected.value.id === id ? 'active' : 'normal'
}

function isSelectedPosition(kind: SelectionKind, position: GridPosition): boolean {
  return selected.value?.kind === kind && positionKey(selected.value.position) === positionKey(position)
}

function reachableIconState(position: GridPosition): RpgMapIconState {
  return isSelectedPosition('move', position) ? 'active' : 'normal'
}

function isLegendEntrySelected(entry: LegendEntry): boolean {
  if (!selected.value) return false
  if (entry.kind !== selected.value.kind) return false
  if (entry.id.endsWith(selected.value.id)) return true
  return Boolean(entry.position && positionKey(entry.position) === positionKey(selected.value.position))
}

function isInteractiveCell(col: number, row: number): boolean {
  const key = `${col},${row}`
  if (isExploration.value) return Boolean(exitMap.value[key] || poiMap.value[key] || partyMap.value[key])
  return reachableCells.value.has(key) || Boolean(cellMap.value[key] || obstacleSet.value.has(key) || zoneByCell.value[key])
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
  if (reachableCells.value.has(key)) selectMove(position)
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

function confirmSelection() {
  const current = selected.value
  if (!current) return
  if (current.kind === 'exit') {
    const exit = (activeScene.value?.exits ?? []).find((e) => e.id === current.id)
    emit('sceneExit', current.id, exit?.label ?? current.name)
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
      <div class="flex min-h-0 flex-1 items-center justify-center overflow-auto p-4">
        <div
          class="rpg-map-grid-frame relative overflow-hidden rounded border"
          data-testid="battlemap-grid"
          :style="{
            width: `${cols * cellPx}px`,
            height: `${rows * cellPx}px`,
            background: mapBackground,
          }"
        >
          <svg class="pointer-events-none absolute inset-0 h-full w-full" aria-hidden="true">
            <defs>
              <pattern id="combat-grid" :width="cellPx" :height="cellPx" patternUnits="userSpaceOnUse">
                <path class="rpg-map-grid-stroke" :d="`M ${cellPx} 0 L 0 0 0 ${cellPx}`" fill="none" stroke-width="1" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#combat-grid)" />
          </svg>

          <div class="pointer-events-none absolute inset-x-0 top-0 h-7 bg-black/25" />
          <div class="pointer-events-none absolute inset-x-0 bottom-0 h-8 bg-black/30" />

          <template v-if="!isExploration">
            <div
              v-for="zone in zones"
              :key="zone.id"
            >
              <button
                v-for="cell in zone.cells"
                :key="`${zone.id}-${cell.col},${cell.row}`"
                class="rpg-map-zone-cell absolute z-10 flex items-center justify-center border bg-gold/10"
                :style="cellBoxStyle(cell)"
                type="button"
                :aria-label="zone.name"
                @click.stop="selectZone(cell, zone)"
              >
                <RpgMapIcon
                  :data-testid="`map-icon-zone-${zone.id}`"
                  :icon-id="iconForCombatZone(zone)"
                  :size="Math.max(18, Math.min(28, cellPx * 0.52))"
                  :state="isSelectedPosition('zone', cell) ? 'active' : 'normal'"
                  :label="zone.name"
                />
              </button>
            </div>
            <button
              v-for="obstacle in obstacles"
              :key="`obstacle-${obstacle.col},${obstacle.row}`"
              class="absolute z-20 flex items-center justify-center bg-black/45"
              :style="{ ...cellBoxStyle(obstacle), color: 'var(--color-text-muted)' }"
              type="button"
              aria-label="Obstacle"
              @click.stop="selectObstacle(obstacle)"
            >
              <RpgMapIcon
                :data-testid="`map-icon-obstacle-${obstacle.col}-${obstacle.row}`"
                icon-id="c-obstacle"
                variant="mono"
                :size="Math.max(18, Math.min(28, cellPx * 0.54))"
                :state="isSelectedPosition('obstacle', obstacle) ? 'active' : 'normal'"
                label="Obstacle"
              />
            </button>
          </template>

          <template v-if="isExploration">
            <button
              v-for="poi in displayPois"
              :key="`poi-${poi.id}`"
              class="rpg-map-poi-marker absolute z-40 flex h-9 w-9 items-center justify-center rounded-lg border transition hover:scale-105"
              :style="{ ...markerStyle(poi.position), ...markerToneStyle(toneForPoi(poi)) }"
              type="button"
              :aria-label="poi.name"
              :title="poi.name"
              @click.stop="selectPoi(poi)"
            >
              <RpgMapIcon
                :data-testid="`map-icon-poi-${poi.id}`"
                :icon-id="iconForPoi(poi)"
                :size="24"
                :state="selectedIconState('poi', poi.id)"
                :label="poi.name"
              />
            </button>

            <button
              v-for="exit in activeScene?.exits ?? []"
              :key="`exit-${exit.id}`"
              class="rpg-map-exit-marker absolute z-40 flex h-10 w-10 items-center justify-center rounded-full border transition hover:scale-105"
              :style="markerStyle(exit.position)"
              type="button"
              :aria-label="exit.label"
              :title="exit.label"
              @click.stop="selectExit(exit)"
            >
              <RpgMapIcon
                :data-testid="`map-icon-exit-${exit.id}`"
                :icon-id="iconForExit(exit)"
                :size="25"
                :state="selectedIconState('exit', exit.id)"
                :label="exit.label"
              />
            </button>

            <button
              v-for="marker in partyMarkers"
              :key="`party-${marker.id}`"
              class="rpg-map-party-marker absolute z-50 flex h-10 w-10 items-center justify-center rounded-full border text-[10px] font-bold text-white transition hover:scale-105"
              :class="{ 'is-mine': marker.id === myCharacterId }"
              :style="markerStyle(marker.position)"
              type="button"
              :aria-label="marker.name"
              :title="marker.name"
              @click.stop="selectParty(marker)"
            >
              <RpgMapIcon
                :data-testid="`map-icon-party-${marker.id}`"
                :icon-id="marker.iconId"
                :size="25"
                :state="selectedIconState('party', marker.id)"
                :label="marker.name"
              />
            </button>
          </template>

          <button
            v-for="cell in gridCells"
            :key="`${cell.col},${cell.row}`"
            class="absolute z-30 flex items-center justify-center"
            :class="{ 'cursor-pointer': isInteractiveCell(cell.col, cell.row) }"
            :style="{ left: `${cell.col * cellPx}px`, top: `${cell.row * cellPx}px`, width: `${cellPx}px`, height: `${cellPx}px` }"
            type="button"
            :aria-label="coordinateLabel(cell)"
            @click="handleCellClick(cell.col, cell.row)"
          >
            <span
              v-if="reachableCells.has(`${cell.col},${cell.row}`)"
              class="flex h-7 w-7 items-center justify-center rounded-full border transition"
              :class="interactionMode === 'move' ? 'bg-green/20 border-green/50' : 'bg-gold/10 border-gold/35'"
            >
              <RpgMapIcon
                :data-testid="`map-icon-reachable-${cell.col}-${cell.row}`"
                :icon-id="reachableIconState(cell) === 'active' ? 'c-move-dest' : 'c-move-tile'"
                :size="18"
                :state="reachableIconState(cell)"
                label="Case accessible"
              />
            </span>

            <div
              v-if="cellMap[`${cell.col},${cell.row}`]"
              class="relative flex h-10 w-10 items-center justify-center rounded-full border text-[11px] font-bold text-white transition-transform hover:scale-105"
              :class="{
                'ring-2 ring-blood/70': interactionMode === 'attack' && canTargetCombatant(cellMap[`${cell.col},${cell.row}`]!),
                'ring-2 ring-arcane/70': interactionMode === 'spell' && canTargetCombatant(cellMap[`${cell.col},${cell.row}`]!),
              }"
              :style="{
                background: tokenBackground(cellMap[`${cell.col},${cell.row}`]!),
                borderColor: cellMap[`${cell.col},${cell.row}`]!.is_active
                  ? 'var(--color-gold)'
                  : cellMap[`${cell.col},${cell.row}`]!.id === gameStore.selectedCombatantId ? 'var(--color-parchment)' : 'rgba(247,236,208,0.28)',
                boxShadow: cellMap[`${cell.col},${cell.row}`]!.is_active
                  ? '0 0 0 2px rgba(247,199,107,0.28), 0 0 18px rgba(247,199,107,0.45)'
                  : cellMap[`${cell.col},${cell.row}`]!.id === gameStore.selectedCombatantId ? '0 0 0 2px rgba(247,236,208,0.22)' : '0 5px 14px rgba(0,0,0,0.35)',
              }"
              :title="cellMap[`${cell.col},${cell.row}`]!.name"
            >
              {{ tokenLabel(cellMap[`${cell.col},${cell.row}`]!) }}
              <RpgMapIcon
                class="absolute -left-2 -top-2 rounded-full bg-bg-elev/95"
                :data-testid="`map-icon-combatant-${cellMap[`${cell.col},${cell.row}`]!.id}`"
                :icon-id="iconForCombatant(cellMap[`${cell.col},${cell.row}`]!)"
                :size="18"
                :state="cellMap[`${cell.col},${cell.row}`]!.hp_current <= 0 ? 'disabled' : 'normal'"
                :label="cellMap[`${cell.col},${cell.row}`]!.name"
              />
              <RpgMapIcon
                v-if="cellMap[`${cell.col},${cell.row}`]!.is_active"
                class="absolute -right-2 -top-2 rounded-full bg-bg-elev/95"
                :data-testid="`map-icon-active-${cellMap[`${cell.col},${cell.row}`]!.id}`"
                icon-id="c-active-turn"
                :size="18"
                state="active"
                label="Tour actif"
              />
              <RpgMapIcon
                v-else-if="cellMap[`${cell.col},${cell.row}`]!.id === gameStore.selectedCombatantId"
                class="absolute -right-2 -top-2 rounded-full bg-bg-elev/95"
                :data-testid="`map-icon-selection-${cellMap[`${cell.col},${cell.row}`]!.id}`"
                icon-id="c-selection"
                :size="18"
                state="active"
                label="Sélection courante"
              />
              <RpgMapIcon
                v-if="canTargetCombatant(cellMap[`${cell.col},${cell.row}`]!) && (interactionMode === 'attack' || interactionMode === 'spell')"
                class="absolute -right-2 -bottom-2 rounded-full bg-bg-elev/95"
                :data-testid="`map-icon-target-${cellMap[`${cell.col},${cell.row}`]!.id}`"
                :icon-id="targetIconForMode()"
                :size="19"
                :state="isSelectedPosition('combatant', cellMap[`${cell.col},${cell.row}`]!.position ?? cell) ? 'active' : 'normal'"
                :label="targetLabelForMode()"
              />
              <span class="absolute -bottom-1.5 h-1 w-8 overflow-hidden rounded-full bg-black/70">
                <span
                  class="block h-full rounded-full"
                  :style="{
                    width: `${hpPct(cellMap[`${cell.col},${cell.row}`]!.hp_current, cellMap[`${cell.col},${cell.row}`]!.hp_max)}%`,
                    background: 'var(--color-green)',
                  }"
                />
              </span>
            </div>
          </button>
        </div>
      </div>

      <aside
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
              v-if="selected.actionLabel"
              class="rpg-btn-primary mt-4 w-full justify-center !py-2 !text-[11px]"
              type="button"
              data-testid="map-confirm"
              @click="confirmSelection"
            >{{ selected.actionLabel }}</button>
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
