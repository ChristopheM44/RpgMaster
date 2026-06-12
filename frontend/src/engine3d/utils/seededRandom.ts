// PRNG déterministe — même implémentation que useMapDecor (mulberry32) pour
// que le décor procédural d'une scène soit stable d'un rendu à l'autre.

export function hashSeed(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = (Math.imul(31, h) + s.charCodeAt(i)) | 0
  }
  return h >>> 0
}

export type Prng = () => number

export function makePrng(seed: string): Prng {
  let state = hashSeed(seed || 'default')
  return function rand(): number {
    state += 0x6d2b79f5
    let t = Math.imul(state ^ (state >>> 15), 1 | state)
    t ^= t + Math.imul(t ^ (t >>> 7), 61 | t)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function pick<T>(rand: Prng, items: readonly T[]): T {
  const index = Math.min(items.length - 1, Math.floor(rand() * items.length))
  return items[index] as T
}

export function range(rand: Prng, min: number, max: number): number {
  return min + rand() * (max - min)
}
