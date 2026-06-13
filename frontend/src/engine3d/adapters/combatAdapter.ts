// Adapter PUR pour Battlemap (mode combat ET exploration mobile) :
// combattants/décoration de grille/cellules atteignables → SceneSpec.
// Les entrées sont pré-mâchées par Battlemap (icônes/tones résolus) pour
// garder cet adapter sans dépendance aux stores ni au registre d'icônes.

import type { CombatantState, GridConfig, GridPosition, SceneLayout, SceneTheme } from '../../types'
import type { GridPoint, SceneSpec, TokenSpec } from '../types'
import { modelForClass, modelForMonster, modelForNpc } from '../assets/manifest'
import { buildElementSpecs, buildElevationByCell, buildGroundSpec, TONE_HEX } from './sceneAdapter'
import { resolveTokenOverlaps } from './tokenCollision'

export interface CombatPoiInput {
  id: string
  name: string
  col: number
  row: number
  iconId: string | null
  tone: string
  elementId?: string | null
  /** Rôle sémantique pré-mâché (npc/enemy → personnage 3D au lieu d'un marqueur). */
  role?: string | null
}

export interface CombatExitInput {
  id: string
  label: string
  col: number
  row: number
  iconId: string | null
  active: boolean
  elementId?: string | null
}

export interface CombatPartyMarkerInput {
  id: string
  name: string
  col: number
  row: number
  isMe: boolean
  isAi: boolean
}

export interface CombatZoneInput {
  id: string
  name: string
  cells: GridPosition[]
  icon: string | null
}

export interface CombatAdapterInput {
  scene: SceneLayout | null
  gridConfig: GridConfig | null
  isExploration: boolean
  combatants: CombatantState[]
  /** char_class par id de PC (CombatantState ne porte pas la classe). */
  classById: Record<string, string>
  myCharacterId: string | null
  selectedCombatantId: string | null
  interactionMode: 'inspect' | 'move' | 'attack' | 'spell'
  reachableFree: GridPosition[]
  gridDecoration: { obstacles: GridPosition[]; zones: CombatZoneInput[] }
  partyMarkers: CombatPartyMarkerInput[]
  pois: CombatPoiInput[]
  exits: CombatExitInput[]
  /** Destination de déplacement en attente de confirmation. */
  pendingMove: GridPosition | null
  /** Chemin prévisualisé vers pendingMove (A* backend, départ inclus). */
  pendingPath: GridPosition[]
  /** Gabarit AoE pré-calculé par Battlemap (aoeCells) — null hors visée. */
  pendingAoe: { cells: GridPosition[]; center: GridPosition; valid: boolean } | null
  selectedElementId: string | null
}

export function buildCombatSpec(input: CombatAdapterInput): SceneSpec {
  const scene = input.scene
  const cols = (input.isExploration ? scene?.cols : input.gridConfig?.cols ?? scene?.cols) ?? (input.isExploration ? 8 : 10)
  const rows = (input.isExploration ? scene?.rows : input.gridConfig?.rows ?? scene?.rows) ?? 8
  const dims = { cols, rows }
  const theme = (scene?.scene_theme ?? input.gridConfig?.scene_theme ?? 'forest') as SceneTheme

  const ground = buildGroundSpec(scene, cols, rows, theme)
  if (!input.isExploration && input.gridConfig?.cell_size_m) {
    ground.cellSizeM = input.gridConfig.cell_size_m
  }

  const linkedElementIds = new Set<string>()
  for (const poi of input.pois) {
    if (poi.elementId) linkedElementIds.add(poi.elementId)
  }
  for (const exit of input.exits) {
    if (exit.elementId) linkedElementIds.add(exit.elementId)
  }
  const { elements, blockedCells } = buildElementSpecs(scene?.elements ?? [], {
    dims,
    linkedElementIds,
    selectedElementId: input.selectedElementId,
  })

  const tokens: TokenSpec[] = []
  if (input.isExploration) {
    for (const marker of input.partyMarkers) {
      blockedCells.add(`${marker.col},${marker.row}`)
      tokens.push(baseToken({
        id: marker.id,
        kind: 'hero',
        name: marker.name,
        col: marker.col,
        row: marker.row,
        accent: marker.isMe ? TONE_HEX.gold ?? '#f0c764' : marker.isAi ? TONE_HEX.arcane ?? '#c090ff' : TONE_HEX.teal ?? '#4fd8c0',
        modelKey: modelForClass(input.classById[marker.id]),
        selected: input.selectedCombatantId === marker.id,
      }))
    }
  } else {
    for (const combatant of input.combatants) {
      if (!combatant.position) continue
      blockedCells.add(`${combatant.position.col},${combatant.position.row}`)
      tokens.push(combatantToken(combatant, input))
    }
  }

  for (const poi of input.pois) {
    blockedCells.add(`${poi.col},${poi.row}`)
    // PNJ/ennemis : personnages 3D animés (parité sceneAdapter).
    if (poi.role === 'npc' || poi.role === 'enemy') {
      const isEnemy = poi.role === 'enemy'
      tokens.push(baseToken({
        id: poi.id,
        kind: 'npc',
        name: poi.name,
        col: poi.col,
        row: poi.row,
        accent: isEnemy ? TONE_HEX.blood ?? '#e84545' : TONE_HEX.teal ?? '#4fd8c0',
        modelKey: isEnemy ? modelForMonster(poi.name) : modelForNpc(poi.name),
        initials: poi.name.slice(0, 2).toUpperCase(),
        selected: input.selectedCombatantId === poi.id,
      }))
      continue
    }
    tokens.push(baseToken({
      id: poi.id,
      kind: 'poi',
      name: poi.name,
      col: poi.col,
      row: poi.row,
      accent: TONE_HEX[poi.tone] ?? '#4fd8c0',
      iconId: poi.iconId,
    }))
  }
  for (const exit of input.exits) {
    blockedCells.add(`${exit.col},${exit.row}`)
    tokens.push(baseToken({
      id: exit.id,
      kind: 'exit',
      name: exit.label,
      col: exit.col,
      row: exit.row,
      accent: exit.active ? TONE_HEX.gold ?? '#f0c764' : TONE_HEX.teal ?? '#4fd8c0',
      iconId: exit.iconId,
      exitActive: exit.active,
    }))
  }

  for (const obstacle of input.gridDecoration.obstacles) {
    blockedCells.add(`${obstacle.col},${obstacle.row}`)
  }

  return {
    ground,
    elements,
    tokens: resolveTokenOverlaps(tokens),
    overlay: {
      reachable: toGridPoints(input.reachableFree),
      reachableEmphasis: input.interactionMode === 'move' ? 'move' : 'idle',
      destination: input.pendingMove ? { col: input.pendingMove.col, row: input.pendingMove.row } : null,
      path: toGridPoints(input.pendingPath),
      aoe: input.pendingAoe
        ? {
            cells: toGridPoints(input.pendingAoe.cells),
            center: { col: input.pendingAoe.center.col, row: input.pendingAoe.center.row },
            valid: input.pendingAoe.valid,
          }
        : null,
      zones: input.gridDecoration.zones.map((zone) => ({
        id: zone.id,
        name: zone.name,
        cells: toGridPoints(zone.cells),
        icon: zone.icon,
      })),
      obstacles: toGridPoints(input.gridDecoration.obstacles),
      cellPicking: true,
    },
    scatterBlockedCells: [...blockedCells],
    elevationByCell: buildElevationByCell(elements, dims),
  }
}

function combatantToken(combatant: CombatantState, input: CombatAdapterInput): TokenSpec {
  const isMonster = combatant.kind === 'monster'
  const defeated = combatant.hp_current <= 0
  const targetable =
    isMonster
    && !defeated
    && combatant.id !== input.myCharacterId
    && (input.interactionMode === 'attack' || input.interactionMode === 'spell')
      ? input.interactionMode
      : null

  const accent = isMonster
    ? combatant.color ?? TONE_HEX.blood ?? '#e84545'
    : combatant.is_ai
      ? TONE_HEX.arcane ?? '#c090ff'
      : combatant.id === input.myCharacterId
        ? TONE_HEX.gold ?? '#f0c764'
        : TONE_HEX.teal ?? '#4fd8c0'

  const modelKey = isMonster
    ? modelForMonster(`${combatant.name} ${combatant.species ?? ''}`)
    : modelForClass(input.classById[combatant.id])

  return baseToken({
    id: combatant.id,
    kind: 'combatant',
    name: combatant.name,
    col: combatant.position?.col ?? 0,
    row: combatant.position?.row ?? 0,
    accent,
    modelKey,
    initials: combatant.token ?? combatant.name.slice(0, 2).toUpperCase(),
    hpRatio: combatant.hp_max > 0 ? Math.max(0, combatant.hp_current) / combatant.hp_max : null,
    selected: input.selectedCombatantId === combatant.id,
    active: Boolean(combatant.is_active),
    targetable,
    defeated,
  })
}

function baseToken(partial: Partial<TokenSpec> & Pick<TokenSpec, 'id' | 'kind' | 'name' | 'col' | 'row' | 'accent'>): TokenSpec {
  return {
    modelKey: null,
    initials: '',
    hpRatio: null,
    selected: false,
    highlighted: false,
    active: false,
    targetable: null,
    defeated: false,
    iconId: null,
    exitActive: false,
    ...partial,
  }
}

function toGridPoints(cells: GridPosition[]): GridPoint[] {
  return cells.map((cell) => ({ col: cell.col, row: cell.row }))
}
