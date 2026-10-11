// Pont design-system → moteur 3D : lit les tokens CSS (--color-*) au montage
// avec fallbacks hex (main.css), et transpose les 12 biomes SVG de feu
// LocalMapCanvas en palettes 3D (sol, grille, fog, lumières, scatter).

import type { SceneTheme } from '../../types'
import type { AmbianceLight } from '../types'

export interface ThemeTokens {
  bg: string
  bgElev: string
  surface: string
  parchment: string
  parchmentDark: string
  textMuted: string
  border: string
  borderStrong: string
  ember: string
  gold: string
  goldDeep: string
  blood: string
  arcane: string
  teal: string
  green: string
  dim: string
}

const TOKEN_FALLBACKS: ThemeTokens = {
  bg: '#0e0d14',
  bgElev: '#181623',
  surface: '#1f1c2e',
  parchment: '#f7ecd0',
  parchmentDark: '#c9c0a8',
  textMuted: '#8d8775',
  border: '#3a3526',
  borderStrong: '#55502f',
  ember: '#ff8247',
  gold: '#f0c764',
  goldDeep: '#b88a2a',
  blood: '#e84545',
  arcane: '#c090ff',
  teal: '#4fd8c0',
  green: '#6fd96f',
  dim: '#6b6580',
}

const TOKEN_VARS: Record<keyof ThemeTokens, string> = {
  bg: '--color-bg',
  bgElev: '--color-bg-elev',
  surface: '--color-surface',
  parchment: '--color-parchment',
  parchmentDark: '--color-parchment-dark',
  textMuted: '--color-text-muted',
  border: '--color-border',
  borderStrong: '--color-border-strong',
  ember: '--color-ember',
  gold: '--color-gold',
  goldDeep: '--color-gold-deep',
  blood: '--color-blood',
  arcane: '--color-arcane',
  teal: '--color-teal',
  green: '--color-green',
  dim: '--color-dim',
}

/**
 * Lit un token CSS ; ne garde que les valeurs hex/rgb pleinement opaques —
 * les tokens rgba() translucides (parchment-dark…) retombent sur le fallback,
 * un matériau 3D ayant besoin d'une couleur pleine.
 */
function readToken(style: CSSStyleDeclaration, varName: string, fallback: string): string {
  const raw = style.getPropertyValue(varName).trim()
  if (/^#[0-9a-f]{3,8}$/i.test(raw)) return raw
  const rgb = raw.match(/^rgb\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)\s*\)$/i)
  if (rgb) {
    const [r, g, b] = [Number(rgb[1]), Number(rgb[2]), Number(rgb[3])]
    return `#${[r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('')}`
  }
  return fallback
}

export function resolveThemeTokens(): ThemeTokens {
  if (typeof window === 'undefined' || typeof document === 'undefined') return { ...TOKEN_FALLBACKS }
  const style = getComputedStyle(document.documentElement)
  const tokens = { ...TOKEN_FALLBACKS }
  for (const key of Object.keys(TOKEN_VARS) as (keyof ThemeTokens)[]) {
    tokens[key] = readToken(style, TOKEN_VARS[key], TOKEN_FALLBACKS[key])
  }
  return tokens
}

// ─── Biomes ──────────────────────────────────────────────────────────────────

export type ScatterKind =
  | 'tree_pine'
  | 'tree_palm'
  | 'tree_dark'
  | 'bush'
  | 'grass'
  | 'flower'
  | 'mushroom'
  | 'rock'
  | 'stone'
  | 'stump'
  | 'log'
  | 'cactus'
  | 'lily'
  | 'crate'
  | 'torch'

/** Rendu du sol : dalles alignées sur la grille (intérieur), pavés, ou matière naturelle. */
export type GroundStyle = 'flagstone' | 'planks' | 'cobble' | 'cave' | 'grass' | 'forest' | 'sand' | 'rock' | 'mud'

export interface Biome3D {
  /**
   * Albédo NATUREL du sol (sable clair, herbe, dalles). Avant 2026-10 ces valeurs
   * reprenaient la palette sombre de l'interface (#1e1810 pour le sable !) : le sol
   * restait noir même en plein jour. L'atmosphère sombre passe par la lumière et
   * la brume, pas par l'albédo.
   */
  ground: string
  /** Seconde teinte (variations, joints, taches). */
  groundAccent: string
  groundStyle: GroundStyle
  /** Lieu clos (donjon, caverne) : roche sombre autour, brume sombre ; sinon terrain prolongé. */
  enclosed: boolean
  /** Amplitude du relief au-delà du plateau (unités monde). */
  relief: number
  grid: string
  gridOpacity: number
  /** Teinte de brume propre au biome (mêlée à celle de l'ambiance en extérieur). */
  fog: string
  scatter: ScatterKind[]
  /** Torches d'angle façon battlemap SVG (dungeon/cave). */
  cornerTorches: boolean
}

export const BIOME_3D: Record<SceneTheme, Biome3D> = {
  forest: {
    ground: '#5a6a3c', groundAccent: '#4a4630', groundStyle: 'forest', enclosed: false, relief: 1.2,
    grid: '#ffebb4', gridOpacity: 0.22, fog: '#7d8a6a',
    scatter: ['tree_pine', 'bush', 'mushroom', 'log', 'grass'], cornerTorches: false,
  },
  beach: {
    ground: '#d9c493', groundAccent: '#c2a774', groundStyle: 'sand', enclosed: false, relief: 0.6,
    grid: '#5a4a30', gridOpacity: 0.18, fog: '#b8c8cc',
    scatter: ['tree_palm', 'rock', 'grass'], cornerTorches: false,
  },
  coastal: {
    ground: '#9a9483', groundAccent: '#7f7a6b', groundStyle: 'rock', enclosed: false, relief: 1.2,
    grid: '#ffebb4', gridOpacity: 0.2, fog: '#a3b2b8',
    scatter: ['rock', 'grass', 'tree_palm'], cornerTorches: false,
  },
  rocky: {
    ground: '#8f8371', groundAccent: '#74695a', groundStyle: 'rock', enclosed: false, relief: 2.2,
    grid: '#ffebb4', gridOpacity: 0.2, fog: '#a69a88',
    scatter: ['rock', 'stone', 'stump'], cornerTorches: false,
  },
  mountain: {
    ground: '#85837f', groundAccent: '#6c6b69', groundStyle: 'rock', enclosed: false, relief: 3,
    grid: '#ffebb4', gridOpacity: 0.2, fog: '#9ea3ad',
    scatter: ['rock', 'stone', 'tree_pine'], cornerTorches: false,
  },
  dungeon: {
    ground: '#8a8278', groundAccent: '#2a2520', groundStyle: 'flagstone', enclosed: true, relief: 0,
    grid: '#ffebb4', gridOpacity: 0.16, fog: '#120f16',
    scatter: [], cornerTorches: true,
  },
  cave: {
    ground: '#6f6862', groundAccent: '#4a443f', groundStyle: 'cave', enclosed: true, relief: 0,
    grid: '#ffebb4', gridOpacity: 0.16, fog: '#0e0d12',
    scatter: ['rock', 'mushroom'], cornerTorches: true,
  },
  city: {
    ground: '#8d8576', groundAccent: '#5e574c', groundStyle: 'cobble', enclosed: false, relief: 0,
    grid: '#ffebb4', gridOpacity: 0.18, fog: '#8f8a84',
    scatter: ['crate'], cornerTorches: false,
  },
  plains: {
    ground: '#7a8a48', groundAccent: '#93864f', groundStyle: 'grass', enclosed: false, relief: 0.8,
    grid: '#ffebb4', gridOpacity: 0.2, fog: '#a9b394',
    scatter: ['grass', 'bush', 'flower', 'tree_pine'], cornerTorches: false,
  },
  swamp: {
    ground: '#55593a', groundAccent: '#3e4230', groundStyle: 'mud', enclosed: false, relief: 0.5,
    grid: '#ffebb4', gridOpacity: 0.2, fog: '#5d6656',
    scatter: ['tree_dark', 'lily', 'mushroom', 'grass'], cornerTorches: false,
  },
  desert: {
    ground: '#dcc396', groundAccent: '#c4a57a', groundStyle: 'sand', enclosed: false, relief: 1.8,
    grid: '#5a4024', gridOpacity: 0.18, fog: '#e2cfa8',
    scatter: ['cactus', 'rock', 'stone'], cornerTorches: false,
  },
}

export function biomeFor(theme: string | null | undefined, enclosed = false): Biome3D {
  const base = BIOME_3D[(theme ?? 'forest') as SceneTheme] ?? BIOME_3D.forest
  if (!enclosed || base.enclosed) return base
  // Intérieur d'un thème d'extérieur (taverne, temple, échoppe en « city ») : plancher,
  // pas de terrain ni de végétation, brume sombre, torches allumées.
  return {
    ...base,
    ground: '#9a7650',
    groundAccent: '#3a2a1c',
    groundStyle: 'planks',
    enclosed: true,
    relief: 0,
    fog: '#141016',
    scatter: [],
    cornerTorches: true,
  }
}

// ─── Ambiances lumineuses ────────────────────────────────────────────────────

export interface AmbiancePreset {
  hemiSky: string
  hemiGround: string
  hemiIntensity: number
  sunColor: string
  sunIntensity: number
  /** Élévation du soleil (rad) — basse au crépuscule. */
  sunElevation: number
  /** PointLights sur les éléments `light` actives uniquement en torchlit. */
  pointLights: boolean
  /** Tone mapping exposure. */
  exposure: number
  /** Ciel/brume en extérieur (les lieux clos gardent la brume sombre du biome). */
  sky: string
}

// Calibré pour des albédos naturels (BIOME_3D) : plus besoin de surexposer.
export const AMBIANCE_PRESETS: Record<AmbianceLight, AmbiancePreset> = {
  day: {
    hemiSky: '#eef3f8', hemiGround: '#a08a68', hemiIntensity: 1.35,
    sunColor: '#fff4e0', sunIntensity: 2.5, sunElevation: 0.95, pointLights: false,
    exposure: 1.0, sky: '#d6d0c2',
  },
  dusk: {
    hemiSky: '#c49a82', hemiGround: '#3a2a2c', hemiIntensity: 0.85,
    sunColor: '#ff9a5a', sunIntensity: 1.8, sunElevation: 0.35, pointLights: false,
    exposure: 1.0, sky: '#8c6a66',
  },
  night: {
    hemiSky: '#5a6a92', hemiGround: '#121420', hemiIntensity: 0.7,
    sunColor: '#9fb2e0', sunIntensity: 0.75, sunElevation: 0.8, pointLights: true,
    exposure: 1.05, sky: '#1b2234',
  },
  torchlit: {
    hemiSky: '#9a8270', hemiGround: '#2a201a', hemiIntensity: 1.3,
    sunColor: '#ffd2a8', sunIntensity: 1.05, sunElevation: 0.9, pointLights: true,
    exposure: 1.15, sky: '#16121a',
  },
  overcast: {
    hemiSky: '#c4c8ce', hemiGround: '#5a5650', hemiIntensity: 1.25,
    sunColor: '#dfe3e8', sunIntensity: 1.1, sunElevation: 0.85, pointLights: false,
    exposure: 1.0, sky: '#a7a9ad',
  },
}

export function ambiancePreset(light: string | null | undefined): AmbiancePreset {
  return AMBIANCE_PRESETS[(light ?? 'day') as AmbianceLight] ?? AMBIANCE_PRESETS.day
}
