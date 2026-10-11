// Relief du terrain prolongé autour du plateau — fonctions PURES (testables sans
// WebGL). Le plateau jouable reste plat (hauteur 0) ; le relief monte
// progressivement au-delà de son bord pour que la scène ne flotte plus dans le vide.

import { hashSeed } from './seededRandom'

/** Distance (unités monde) entre un point et le rectangle du plateau (0 dedans). */
export function distanceOutsideBoard(x: number, z: number, halfW: number, halfH: number): number {
  const dx = Math.max(0, Math.abs(x) - halfW)
  const dz = Math.max(0, Math.abs(z) - halfH)
  return Math.hypot(dx, dz)
}

/** Bruit de valeur 2D lissé, déterministe (graine entière), dans [-1, 1]. */
export function valueNoise(x: number, z: number, seed: number): number {
  const x0 = Math.floor(x)
  const z0 = Math.floor(z)
  const fx = x - x0
  const fz = z - z0
  const sx = fx * fx * (3 - 2 * fx)
  const sz = fz * fz * (3 - 2 * fz)
  const a = lattice(x0, z0, seed)
  const b = lattice(x0 + 1, z0, seed)
  const c = lattice(x0, z0 + 1, seed)
  const d = lattice(x0 + 1, z0 + 1, seed)
  return (a + (b - a) * sx) + ((c + (d - c) * sx) - (a + (b - a) * sx)) * sz
}

function lattice(x: number, z: number, seed: number): number {
  let h = (x * 374761393 + z * 668265263 + seed * 2147483647) | 0
  h = Math.imul(h ^ (h >>> 13), 1274126177)
  h ^= h >>> 16
  return ((h >>> 0) / 4294967295) * 2 - 1
}

export interface TerrainOptions {
  halfW: number
  halfH: number
  /** Amplitude du relief lointain (unités monde) ; 0 = plaine. */
  relief: number
  seed: number
  /** Distance au plateau sur laquelle le relief s'installe. */
  rampWidth?: number
}

/** Hauteur (unités monde) du terrain au point monde (x, z). */
export function terrainHeight(x: number, z: number, options: TerrainOptions): number {
  const outside = distanceOutsideBoard(x, z, options.halfW, options.halfH)
  if (outside <= 0 || options.relief <= 0) return 0
  const ramp = options.rampWidth ?? 5
  const t = Math.min(1, outside / ramp)
  const k = t * t * (3 - 2 * t)
  const broad = valueNoise(x * 0.11, z * 0.11, options.seed)
  const detail = valueNoise(x * 0.37, z * 0.37, options.seed + 17) * 0.35
  // Toujours au-dessus du plateau en moyenne : on regarde le plateau depuis un creux.
  const height = (0.55 + 0.45 * broad + detail) * options.relief + outside * 0.03 * options.relief
  return Math.max(0, height) * k
}

export function terrainSeed(sceneId: string): number {
  return hashSeed(`terrain|${sceneId}`)
}
