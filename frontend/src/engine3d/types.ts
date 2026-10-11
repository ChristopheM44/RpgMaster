// Types du moteur 3D — spec sérialisable produite par les adapters (purs) et
// consommée par SceneRuntime. Aucune dépendance à Vue/Pinia ni à three ici :
// les adapters restent testables sans WebGL.

import type {
  SceneElementFacing,
  SceneElementGeometry,
  SceneElementVerticalDirection,
  SceneTheme,
} from '../types'

export interface GridDims {
  cols: number
  rows: number
}

export interface GridPoint {
  col: number
  row: number
}

export type AmbianceLight = 'day' | 'dusk' | 'night' | 'torchlit' | 'overcast'

export interface AmbianceSpec {
  light: AmbianceLight
  fogDensity: number
}

export interface GroundSpec {
  cols: number
  rows: number
  cellSizeM: number
  theme: SceneTheme
  sceneId: string
  visualAssetUrl: string | null
  ambiance: AmbianceSpec
  vegetationDensity: number
  /** Cellules "col,row" retirées du sol (trémies d'escaliers descendants). */
  holes?: string[]
  /** Grille tactique visible (combat). En exploration : seule la case survolée est marquée. */
  showGrid?: boolean
  /** Lieu clos pour CETTE scène (taverne en thème city…) — s'ajoute au `enclosed` du biome. */
  enclosed?: boolean
}

export interface ElementSpec {
  id: string
  name: string
  kind: string
  geometry: SceneElementGeometry
  terrainType: string | null
  /** Hauteur en mètres (défaut par kind, écrasé par le hint LLM `height_m`). */
  heightM: number
  elevationM: number
  subtle: boolean
  interactive: boolean
  inspectable: boolean
  selected: boolean
  /** Hint public validé côté manifest ; null → heuristique/fallback procédural. */
  modelKey: string | null
  /** Direction cardinale vers laquelle l'accès ou élément mural s'ouvre. */
  facing: SceneElementFacing | null
  /** Sens vertical d'un escalier quand il est emprunté vers `facing`. */
  verticalDirection: SceneElementVerticalDirection | null
}

export type TokenKind = 'hero' | 'poi' | 'exit' | 'combatant' | 'npc'

export interface TokenSpec {
  id: string
  kind: TokenKind
  name: string
  col: number
  row: number
  /** Couleur d'accent hex (anneau, teinte du pion procédural). */
  accent: string
  /** Clé manifest d'un modèle 3D (ex. 'char/knight'), null → pion procédural. */
  modelKey: string | null
  initials: string
  hpRatio: number | null
  selected: boolean
  highlighted: boolean
  /** Tour actif (combat) — anneau gold + glow. */
  active: boolean
  /** Ciblable dans le mode courant (combat attack/spell). */
  targetable: 'attack' | 'spell' | null
  defeated: boolean
  /** POI uniquement : id d'icône rpgMapIcons rendue en billboard. */
  iconId: string | null
  /** Exit uniquement. */
  exitActive: boolean
  /** Offsets monde sub-cellule (anti-chevauchement) — voir tokenCollision.ts. */
  offsetX?: number
  offsetZ?: number
}

export interface ZoneSpec {
  id: string
  name: string
  cells: GridPoint[]
  icon: string | null
}

export interface OverlaySpec {
  /** Cellules atteignables (combat) — teinte green en mode move, gold sinon. */
  reachable: GridPoint[]
  reachableEmphasis: 'move' | 'idle'
  /** Destination de déplacement sélectionnée (ghost teal pulsant). */
  destination: GridPoint | null
  /** Chemin de déplacement prévisualisé (départ → destination, départ inclus). */
  path: GridPoint[]
  /** Gabarit de zone d'effet (sort à aire) — invalid = hors portée (teinte muted). */
  aoe: { cells: GridPoint[]; center: GridPoint; valid: boolean } | null
  zones: ZoneSpec[]
  obstacles: GridPoint[]
  /** Active le picking des cellules de sol (mode move). */
  cellPicking: boolean
}

export interface SceneSpec {
  ground: GroundSpec
  elements: ElementSpec[]
  tokens: TokenSpec[]
  overlay: OverlaySpec
  /** Cellules "col,row" interdites au scatter (occupées par éléments/tokens). */
  scatterBlockedCells: string[]
  /** Hauteur de surface en MÈTRES par cellule "col,row" (stairs/terrain ; négative dans une trémie). */
  elevationByCell: Record<string, number>
  /** Accès par lequel le groupe vient d'arriver (transition de scène), sinon null. */
  arrival?: ArrivalSpec | null
}

export interface ArrivalSpec {
  exitId: string
  col: number
  row: number
  facing: SceneElementFacing | null
  verticalDirection: SceneElementVerticalDirection
  fromSceneId: string
  /** Sortie empruntée dans la scène précédente (pour le travelling de départ). */
  viaExitId: string | null
  /** Libellé de l'accès d'arrivée (bandeau « Vous arrivez… »). */
  label: string
}

export type PickResult =
  | { type: 'token'; id: string; tokenKind: TokenKind }
  | { type: 'element'; id: string }
  | { type: 'cell'; col: number; row: number }

export interface RuntimeCallbacks {
  onHover?: (pick: PickResult | null, screen: { x: number; y: number }) => void
  onClick?: (pick: PickResult, screen: { x: number; y: number }) => void
}

export type ZoomPreset = 'wide' | 'normal' | 'close'

/** Surface publique du runtime, mockée dans les tests de composants. */
export interface SceneRuntimeHandle {
  update(spec: SceneSpec): void
  moveToken(id: string, path: GridPoint[]): void
  projectCell(col: number, row: number): { x: number; y: number } | null
  projectToken(id: string): { x: number; y: number } | null
  setZoomPreset(preset: ZoomPreset): void
  /** Travelling vers une cellule (départ par une sortie) ; résolu en fin d'animation. */
  focusCell(col: number, row: number, durationS?: number): Promise<void>
  /** Après un changement de scène : part de l'accès d'arrivée et recule jusqu'au cadrage normal. */
  arriveAt(col: number, row: number, durationS?: number): void
  setRunning(running: boolean): void
  /** Multiplicateur de luminosité piloté par l'UI (exposition + plancher ambiant). */
  setBrightness(value: number): void
  resize(): void
  dispose(): void
}
