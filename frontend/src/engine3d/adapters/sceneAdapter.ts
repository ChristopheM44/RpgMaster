// Adapter PUR : SceneLayout + adaptations exploration (ExHero/ExPoi) →
// SceneSpec consommée par le runtime. Aucune dépendance three/Vue/Pinia —
// testable sans WebGL. Les défauts 3D miroir du backend (P5) vivent ici aussi,
// pour que la 3D fonctionne même sur un backend sans hints.

import type { ExHero, ExPoi } from '../../fixtures/exploration'
import type {
  SceneElement,
  SceneElementFacing,
  SceneElementVerticalDirection,
  SceneLayout,
  SceneTheme,
} from '../../types'
import type { AmbianceLight, ElementSpec, GroundSpec, SceneSpec, TokenSpec } from '../types'
import { isModelKey, modelForClass, modelForMonster, modelForNpc } from '../assets/manifest'
import { resolveTokenOverlaps } from './tokenCollision'
import { rectCells } from '../utils/gridMath'

// Mêmes valeurs que local_map_service (backend) — défauts par kind en mètres.
export const DEFAULT_HEIGHT_M: Record<string, number> = {
  wall: 2.5,
  door: 2.2,
  window: 1.0,
  furniture: 0.8,
  cover: 1.0,
  hazard: 0.05,
  light: 1.6,
  stairs: 0.4,
  terrain: 0.02,
  decor: 0.6,
}

const VEGETATION_BY_THEME: Record<SceneTheme, number> = {
  forest: 0.8,
  swamp: 0.6,
  plains: 0.4,
  beach: 0.3,
  coastal: 0.3,
  rocky: 0.25,
  mountain: 0.25,
  desert: 0.15,
  city: 0.05,
  dungeon: 0,
  cave: 0,
}

// MIROIR de _THEME_FOG_DENSITY (backend local_map_service.py) — modifier les deux ensemble.
const FOG_BY_THEME: Partial<Record<SceneTheme, number>> = {
  cave: 0.35,
  swamp: 0.4,
  dungeon: 0.25,
  mountain: 0.25,
  forest: 0.2,
}

const AMBIANCE_LIGHTS: readonly AmbianceLight[] = ['day', 'dusk', 'night', 'torchlit', 'overcast']
const ELEMENT_FACINGS: readonly SceneElementFacing[] = ['north', 'east', 'south', 'west']
const ELEMENT_VERTICAL_DIRECTIONS: readonly SceneElementVerticalDirection[] = ['up', 'down', 'level']

/** Tones V2 → hex (mêmes valeurs que les fallbacks du ThemeProvider). */
export const TONE_HEX: Record<string, string> = {
  gold: '#f0c764',
  teal: '#4fd8c0',
  blood: '#e84545',
  arcane: '#c090ff',
  ember: '#ff8247',
  green: '#6fd96f',
  muted: '#8d8775',
}

export interface SceneAdapterInput {
  scene: SceneLayout | null
  heroes: ExHero[]
  pois: ExPoi[]
  selectedId: string | null
  highlightedIds: string[]
}

export function buildSceneSpec(input: SceneAdapterInput): SceneSpec {
  const scene = input.scene
  const cols = scene?.cols ?? 12
  const rows = scene?.rows ?? 12
  const dims = { cols, rows }
  const theme = (scene?.scene_theme ?? 'forest') as SceneTheme

  const linkedElementIds = new Set<string>()
  for (const poi of input.pois) {
    if (poi.elementId) linkedElementIds.add(poi.elementId)
  }
  const ground = buildGroundSpec(scene, cols, rows, theme)
  const { elements, blockedCells } = buildElementSpecs(scene?.elements ?? [], {
    dims,
    linkedElementIds,
    selectedElementId: resolveSelectedElementId(input, scene?.elements ?? []),
  })
  const tokens = buildTokens(input, blockedCells)

  return {
    ground,
    elements,
    tokens,
    overlay: {
      reachable: [],
      reachableEmphasis: 'idle',
      destination: null,
      path: [],
      aoe: null,
      zones: [],
      obstacles: [],
      cellPicking: false,
    },
    scatterBlockedCells: [...blockedCells],
    elevationByCell: buildElevationByCell(elements, dims),
  }
}

/** Partagé exploration/combat : spec de sol depuis SceneLayout + défauts thème. */
export function buildGroundSpec(scene: SceneLayout | null, cols: number, rows: number, theme: SceneTheme): GroundSpec {
  const rawLight = scene?.ambiance?.light
  const light: AmbianceLight = AMBIANCE_LIGHTS.includes(rawLight as AmbianceLight)
    ? (rawLight as AmbianceLight)
    : theme === 'dungeon' || theme === 'cave'
      ? 'torchlit'
      : 'day'
  const fogDensity = clamp01(scene?.ambiance?.fog_density ?? FOG_BY_THEME[theme] ?? 0.15)
  const vegetationDensity = clamp01(scene?.vegetation_density ?? VEGETATION_BY_THEME[theme] ?? 0.3)
  const visualAsset = scene?.visual_asset

  return {
    cols,
    rows,
    cellSizeM: scene?.cell_size_m ?? 1.5,
    theme,
    sceneId: scene?.scene_id ?? `${cols}x${rows}|${theme}`,
    visualAssetUrl: visualAsset?.status === 'ready' && visualAsset.url ? visualAsset.url : null,
    ambiance: { light, fogDensity },
    vegetationDensity,
  }
}

export interface ElementSpecOptions {
  dims: { cols: number; rows: number }
  /** Éléments liés à un POI/sortie — cliquables même sans `interactive`. */
  linkedElementIds: Set<string>
  selectedElementId: string | null
}

/** Partagé exploration/combat : SceneElement[] → ElementSpec[] + cellules occupées. */
export function buildElementSpecs(
  rawElements: SceneElement[],
  options: ElementSpecOptions,
): { elements: ElementSpec[]; blockedCells: Set<string> } {
  const blockedCells = new Set<string>()
  const raw = rawElements.filter((element) => element.visibility !== 'hidden')

  const elements = raw.map((element) => {
    for (const cell of elementCells(element.geometry, options.dims)) {
      blockedCells.add(`${cell.col},${cell.row}`)
    }
    const interactive = Boolean(element.interactive || options.linkedElementIds.has(element.id))
    return {
      id: element.id,
      name: element.name,
      kind: element.kind,
      geometry: element.geometry,
      terrainType: element.terrain_type ?? null,
      heightM: element.height_m ?? DEFAULT_HEIGHT_M[element.kind] ?? 0.6,
      elevationM: element.elevation_m ?? 0,
      subtle: element.visibility === 'subtle' && !element.discovered,
      interactive,
      inspectable: isElementInspectable(element, interactive),
      selected: element.id === options.selectedElementId,
      modelKey: isModelKey(element.asset_key) ? element.asset_key : null,
      facing: normalizeFacing(element.facing),
      verticalDirection: normalizeVerticalDirection(element.vertical_direction),
    }
  })

  return { elements, blockedCells }
}

/**
 * Hauteur de surface par cellule (MÈTRES) — seuls `stairs` et `terrain`
 * portent un token (on marche sur le DESSUS : elevation_m + height_m).
 * Conflit multi-éléments → max. Carte creuse : le terrain plat par défaut
 * (0.02 m) reste hors carte — seuil à 0.05 m.
 */
export function buildElevationByCell(
  elements: ElementSpec[],
  dims: { cols: number; rows: number },
): Record<string, number> {
  const byCell: Record<string, number> = {}
  for (const element of elements) {
    if (element.kind !== 'stairs' && element.kind !== 'terrain') continue
    const surfaceM = element.elevationM + element.heightM
    if (surfaceM <= 0.05) continue
    for (const cell of elementCells(element.geometry, dims)) {
      const key = `${cell.col},${cell.row}`
      byCell[key] = Math.max(byCell[key] ?? 0, surfaceM)
    }
  }
  return byCell
}

/** Même prédicat que feu LocalMapCanvas : murs/terrain/décor non inspectables. */
function isElementInspectable(element: SceneElement, interactive: boolean): boolean {
  if (interactive) return true
  if (element.kind === 'terrain' || element.kind === 'decor' || element.kind === 'wall') return false
  return Boolean(element.name)
}

/** Parité SceneMap : POI sélectionné → son élément lié ; sinon id d'élément direct. */
function resolveSelectedElementId(input: SceneAdapterInput, elements: SceneElement[]): string | null {
  if (!input.selectedId) return null
  const selectedPoi = input.pois.find((poi) => poi.id === input.selectedId)
  if (selectedPoi?.elementId) return selectedPoi.elementId
  return elements.some((element) => element.id === input.selectedId) ? input.selectedId : null
}

function buildTokens(input: SceneAdapterInput, blockedCells: Set<string>): TokenSpec[] {
  const tokens: TokenSpec[] = []

  for (const hero of input.heroes) {
    blockedCells.add(`${hero.x},${hero.y}`)
    tokens.push({
      id: hero.id,
      kind: 'hero',
      name: hero.name,
      col: hero.x,
      row: hero.y,
      accent: hero.color,
      modelKey: modelForClass(hero.cls),
      initials: hero.token,
      hpRatio: hero.hpMax > 0 ? hero.hp / hero.hpMax : null,
      selected: input.selectedId === hero.id,
      highlighted: input.highlightedIds.includes(hero.id),
      active: false,
      targetable: null,
      defeated: false,
      iconId: null,
      exitActive: false,
    })
  }

  for (const poi of input.pois) {
    blockedCells.add(`${poi.x},${poi.y}`)
    // PNJ/ennemis : personnages 3D animés (pas des marqueurs d'icône).
    if (poi.kind === 'npc' || poi.kind === 'enemy') {
      const isEnemy = poi.kind === 'enemy'
      tokens.push({
        id: poi.id,
        kind: 'npc',
        name: poi.title,
        col: poi.x,
        row: poi.y,
        accent: isEnemy ? TONE_HEX.blood ?? '#e84545' : TONE_HEX.teal ?? '#4fd8c0',
        modelKey: isEnemy
          ? modelForMonster(`${poi.title} ${poi.desc}`)
          : modelForNpc(`${poi.title} ${poi.desc}`),
        initials: poi.title.slice(0, 2).toUpperCase(),
        hpRatio: null,
        selected: input.selectedId === poi.id,
        highlighted: input.highlightedIds.includes(poi.id),
        active: false,
        targetable: null,
        defeated: false,
        iconId: null,
        exitActive: false,
      })
      continue
    }
    const isExit = poi.kind === 'sortie'
    tokens.push({
      id: poi.id,
      kind: isExit ? 'exit' : 'poi',
      name: poi.title,
      col: poi.x,
      row: poi.y,
      accent: TONE_HEX[poi.tone] ?? '#4fd8c0',
      modelKey: null,
      initials: '',
      hpRatio: null,
      selected: input.selectedId === poi.id,
      highlighted: input.highlightedIds.includes(poi.id),
      active: false,
      targetable: null,
      defeated: false,
      iconId: poi.iconId ?? null,
      exitActive: isExit ? poi.active !== false : false,
    })
  }

  return resolveTokenOverlaps(tokens)
}

function elementCells(geometry: SceneElement['geometry'], dims: { cols: number; rows: number }): { col: number; row: number }[] {
  if (geometry.type === 'rect') {
    return rectCells(geometry.col, geometry.row, geometry.width, geometry.height, dims)
  }
  if (geometry.type === 'ellipse') {
    return rectCells(
      geometry.col - geometry.radius_col,
      geometry.row - geometry.radius_row,
      geometry.radius_col * 2,
      geometry.radius_row * 2,
      dims,
    )
  }
  const minCol = Math.min(geometry.from.col, geometry.to.col)
  const minRow = Math.min(geometry.from.row, geometry.to.row)
  const width = Math.max(0.2, Math.abs(geometry.to.col - geometry.from.col))
  const height = Math.max(0.2, Math.abs(geometry.to.row - geometry.from.row))
  return rectCells(minCol, minRow, width, height, dims)
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value))
}

function normalizeFacing(value: string | null | undefined): SceneElementFacing | null {
  return ELEMENT_FACINGS.includes(value as SceneElementFacing) ? (value as SceneElementFacing) : null
}

function normalizeVerticalDirection(
  value: string | null | undefined,
): SceneElementVerticalDirection | null {
  return ELEMENT_VERTICAL_DIRECTIONS.includes(value as SceneElementVerticalDirection)
    ? (value as SceneElementVerticalDirection)
    : null
}
