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

export interface Biome3D {
  /** Couleur de sol de base (transposée du gradient SVG). */
  ground: string
  /** Variation appliquée en damier très léger. */
  groundAccent: string
  grid: string
  gridOpacity: number
  fog: string
  scatter: ScatterKind[]
  /** Torches d'angle façon battlemap SVG (dungeon/cave). */
  cornerTorches: boolean
}

export const BIOME_3D: Record<SceneTheme, Biome3D> = {
  forest: {
    ground: '#16201a', groundAccent: '#1b2820', grid: '#ffebb4', gridOpacity: 0.05,
    fog: '#101a12', scatter: ['tree_pine', 'bush', 'mushroom', 'log', 'grass'], cornerTorches: false,
  },
  beach: {
    ground: '#262017', groundAccent: '#2d2719', grid: '#ffebb4', gridOpacity: 0.06,
    fog: '#15202b', scatter: ['tree_palm', 'rock', 'grass'], cornerTorches: false,
  },
  coastal: {
    ground: '#1d2126', groundAccent: '#23282d', grid: '#ffebb4', gridOpacity: 0.05,
    fog: '#142028', scatter: ['rock', 'grass', 'tree_palm'], cornerTorches: false,
  },
  rocky: {
    ground: '#1c1814', groundAccent: '#231e18', grid: '#ffebb4', gridOpacity: 0.05,
    fog: '#171310', scatter: ['rock', 'stone', 'stump'], cornerTorches: false,
  },
  mountain: {
    ground: '#181820', groundAccent: '#1e1e28', grid: '#ffebb4', gridOpacity: 0.05,
    fog: '#1a1a26', scatter: ['rock', 'stone', 'tree_pine'], cornerTorches: false,
  },
  dungeon: {
    ground: '#3e3e48', groundAccent: '#4a4a55', grid: '#ffebb4', gridOpacity: 0.08,
    fog: '#131017', scatter: [], cornerTorches: true,
  },
  cave: {
    ground: '#383844', groundAccent: '#44444f', grid: '#ffebb4', gridOpacity: 0.07,
    fog: '#0e0e13', scatter: ['rock', 'mushroom'], cornerTorches: true,
  },
  city: {
    ground: '#181623', groundAccent: '#1d1b29', grid: '#ffebb4', gridOpacity: 0.07,
    fog: '#12101a', scatter: ['crate'], cornerTorches: false,
  },
  plains: {
    ground: '#181c14', groundAccent: '#1e2318', grid: '#ffebb4', gridOpacity: 0.05,
    fog: '#141810', scatter: ['grass', 'bush', 'flower', 'tree_pine'], cornerTorches: false,
  },
  swamp: {
    ground: '#172019', groundAccent: '#1d271b', grid: '#ffebb4', gridOpacity: 0.05,
    fog: '#0c140e', scatter: ['tree_dark', 'lily', 'mushroom', 'grass'], cornerTorches: false,
  },
  desert: {
    ground: '#1e1810', groundAccent: '#241d12', grid: '#ffebb4', gridOpacity: 0.06,
    fog: '#1c1408', scatter: ['cactus', 'rock', 'stone'], cornerTorches: false,
  },
}

export function biomeFor(theme: string | null | undefined): Biome3D {
  return BIOME_3D[(theme ?? 'forest') as SceneTheme] ?? BIOME_3D.forest
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
  /** Tone mapping exposure — relevé en ambiance sombre pour rester lisible. */
  exposure: number
}

export const AMBIANCE_PRESETS: Record<AmbianceLight, AmbiancePreset> = {
  day: {
    hemiSky: '#bfd4e8', hemiGround: '#2a2640', hemiIntensity: 0.95,
    sunColor: '#fff1d6', sunIntensity: 1.55, sunElevation: 0.95, pointLights: false,
    exposure: 1.05,
  },
  dusk: {
    hemiSky: '#8a6a5a', hemiGround: '#1a1420', hemiIntensity: 0.7,
    sunColor: '#ff9a5a', sunIntensity: 1.1, sunElevation: 0.4, pointLights: false,
    exposure: 1.05,
  },
  night: {
    hemiSky: '#3a4a6a', hemiGround: '#0a0a12', hemiIntensity: 0.9,
    sunColor: '#7a8fc0', sunIntensity: 0.88, sunElevation: 0.8, pointLights: true,
    exposure: 1.22,
  },
  torchlit: {
    hemiSky: '#5a463a', hemiGround: '#14100c', hemiIntensity: 1.1,
    sunColor: '#ffb070', sunIntensity: 1.0, sunElevation: 0.9, pointLights: true,
    exposure: 1.32,
  },
  overcast: {
    hemiSky: '#9aa0aa', hemiGround: '#20202a', hemiIntensity: 0.8,
    sunColor: '#cfd4da', sunIntensity: 0.85, sunElevation: 0.85, pointLights: false,
    exposure: 1.05,
  },
}

export function ambiancePreset(light: string | null | undefined): AmbiancePreset {
  return AMBIANCE_PRESETS[(light ?? 'day') as AmbianceLight] ?? AMBIANCE_PRESETS.day
}
