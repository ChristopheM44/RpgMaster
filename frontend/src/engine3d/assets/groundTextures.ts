// Textures de sol procédurales (canvas 2D), seedées par scene_id — aucun asset.
// - Lieux clos : texture ALIGNÉE sur la grille (une dalle ≈ une case), UV 0..1
//   sur le plateau : la grille tactique se lit dans les joints, sans quadrillage.
// - Extérieur : texture RÉPÉTABLE en coordonnées monde (plateau + terrain
//   prolongé partagent le même matériau, donc aucune couture au bord).
// Retourne null sans canvas 2D (jsdom) : le sol retombe sur une couleur unie.

import * as THREE from 'three'
import type { Biome3D, GroundStyle } from '../core/ThemeProvider'
import { makePrng, range, type Prng } from '../utils/seededRandom'

/** Taille (unités monde = cases) couverte par une répétition de texture extérieure. */
export const NATURAL_TILE_WORLD: Record<GroundStyle, number> = {
  flagstone: 2,
  planks: 2,
  cave: 4,
  cobble: 2,
  grass: 5,
  forest: 5,
  sand: 6,
  rock: 6,
  mud: 5,
}

type Rgb = [number, number, number]

function rgb(hex: string): Rgb {
  const color = new THREE.Color(hex)
  return [Math.round(color.r * 255), Math.round(color.g * 255), Math.round(color.b * 255)]
}

function shade([r, g, b]: Rgb, factor: number, alpha = 1): string {
  const f = (v: number) => Math.max(0, Math.min(255, Math.round(v * factor)))
  return `rgba(${f(r)},${f(g)},${f(b)},${alpha})`
}

function mix(a: Rgb, b: Rgb, t: number): Rgb {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]
}

function makeCanvas(width: number, height: number): CanvasRenderingContext2D | null {
  if (typeof document === 'undefined') return null
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  try {
    return canvas.getContext('2d')
  } catch {
    return null // jsdom sans paquet canvas
  }
}

function toTexture(g: CanvasRenderingContext2D, repeat: boolean): THREE.CanvasTexture {
  const texture = new THREE.CanvasTexture(g.canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.anisotropy = 8
  if (repeat) texture.wrapS = texture.wrapT = THREE.RepeatWrapping
  return texture
}

/** Tache douce répétée aux bords pour une texture sans couture. */
function blotch(g: CanvasRenderingContext2D, size: number, x: number, y: number, radius: number, color: string): void {
  for (const dx of [-size, 0, size]) {
    for (const dy of [-size, 0, size]) {
      const cx = x + dx
      const cy = y + dy
      if (cx + radius < 0 || cy + radius < 0 || cx - radius > size || cy - radius > size) continue
      const gradient = g.createRadialGradient(cx, cy, 0, cx, cy, radius)
      gradient.addColorStop(0, color)
      gradient.addColorStop(1, 'rgba(0,0,0,0)')
      g.fillStyle = gradient
      g.fillRect(cx - radius, cy - radius, radius * 2, radius * 2)
    }
  }
}

function speckle(
  g: CanvasRenderingContext2D,
  rand: Prng,
  area: { x?: number; y?: number; w: number; h: number },
  base: Rgb,
  count: number,
): void {
  for (let i = 0; i < count; i++) {
    g.fillStyle = shade(base, range(rand, 0.7, 1.25), range(rand, 0.15, 0.4))
    g.fillRect((area.x ?? 0) + rand() * area.w, (area.y ?? 0) + rand() * area.h, range(rand, 1, 2.5), range(rand, 1, 2.5))
  }
}

function crack(g: CanvasRenderingContext2D, rand: Prng, x: number, y: number, length: number, color: string): void {
  g.strokeStyle = color
  g.lineWidth = 1
  g.beginPath()
  g.moveTo(x, y)
  let angle = rand() * Math.PI * 2
  for (let i = 0; i < 5; i++) {
    angle += range(rand, -0.8, 0.8)
    x += Math.cos(angle) * length / 5
    y += Math.sin(angle) * length / 5
    g.lineTo(x, y)
  }
  g.stroke()
}

// ─── Lieux clos : texture alignée sur la grille ─────────────────────────────

/** Texture du plateau (UV 0..1) pour un lieu clos, ou null si le style est extérieur. */
export function boardTexture(
  biome: Biome3D,
  cols: number,
  rows: number,
  seed: string,
): THREE.CanvasTexture | null {
  if (biome.groundStyle !== 'flagstone' && biome.groundStyle !== 'cave' && biome.groundStyle !== 'planks') return null
  const px = Math.max(24, Math.min(64, Math.floor(2048 / Math.max(cols, rows))))
  const g = makeCanvas(cols * px, rows * px)
  if (!g) return null
  const rand = makePrng(`ground|${seed}`)
  if (biome.groundStyle === 'flagstone') drawFlagstones(g, rand, cols, rows, px, biome)
  else if (biome.groundStyle === 'planks') drawPlanks(g, rand, cols, rows, px, biome)
  else drawCaveFloor(g, rand, cols, rows, px, biome)
  return toTexture(g, false)
}

function drawFlagstones(g: CanvasRenderingContext2D, rand: Prng, cols: number, rows: number, px: number, biome: Biome3D): void {
  const stone = rgb(biome.ground)
  const mortar = rgb(biome.groundAccent)
  g.fillStyle = shade(mortar, 1)
  g.fillRect(0, 0, cols * px, rows * px)
  const gap = Math.max(2, Math.round(px * 0.05))
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      // Une dalle par case, parfois coupée en deux : la case reste lisible.
      const split = rand()
      const slabs: [number, number, number, number][] = split < 0.18
        ? [[0, 0, 1, 0.5], [0, 0.5, 1, 0.5]]
        : split < 0.3
          ? [[0, 0, 0.5, 1], [0.5, 0, 0.5, 1]]
          : [[0, 0, 1, 1]]
      for (const [sx, sy, sw, sh] of slabs) {
        const x = col * px + sx * px + gap / 2
        const y = row * px + sy * px + gap / 2
        const w = sw * px - gap
        const h = sh * px - gap
        const tone = range(rand, 0.84, 1.1)
        const base = mix(stone, [118, 124, 92], rand() < 0.12 ? 0.25 : 0) // rares dalles moussues
        g.fillStyle = shade(base, tone)
        g.fillRect(x, y, w, h)
        // Biseau : arête claire en haut/gauche, sombre en bas/droite.
        g.fillStyle = shade(base, tone * 1.12, 0.6)
        g.fillRect(x, y, w, 2)
        g.fillRect(x, y, 2, h)
        g.fillStyle = shade(base, tone * 0.72, 0.7)
        g.fillRect(x, y + h - 2, w, 2)
        g.fillRect(x + w - 2, y, 2, h)
        speckle(g, rand, { x, y, w, h }, base, Math.round(px * 0.6))
        if (rand() < 0.22) crack(g, rand, x + rand() * w, y + rand() * h, px * 0.45, shade(mortar, 1, 0.55))
      }
    }
  }

}

function drawPlanks(g: CanvasRenderingContext2D, rand: Prng, cols: number, rows: number, px: number, biome: Biome3D): void {
  // Lames de plancher : 3 par case en largeur, joints de bout décalés, rives sur la grille.
  const wood = rgb(biome.ground)
  const seam = rgb(biome.groundAccent)
  const width = cols * px
  g.fillStyle = shade(seam, 1)
  g.fillRect(0, 0, width, rows * px)
  const lane = px / 3
  for (let i = 0; i < rows * 3; i++) {
    const y = i * lane
    let x = -rand() * px * 2
    while (x < width) {
      const length = px * range(rand, 1.5, 3)
      const tone = range(rand, 0.82, 1.12)
      g.fillStyle = shade(wood, tone)
      g.fillRect(x + 1, y + 1, length - 2, lane - 2)
      // Veinage.
      g.strokeStyle = shade(wood, tone * 0.8, 0.35)
      g.lineWidth = 1
      for (let v = 0; v < 2; v++) {
        const vy = y + range(rand, 3, lane - 3)
        g.beginPath()
        g.moveTo(x + 2, vy)
        g.bezierCurveTo(x + length * 0.3, vy + range(rand, -2, 2), x + length * 0.7, vy + range(rand, -2, 2), x + length - 2, vy)
        g.stroke()
      }
      x += length
    }
  }
  // Rives de case marquées discrètement : la grille tactique reste lisible.
  g.fillStyle = shade(seam, 1, 0.5)
  for (let col = 0; col <= cols; col++) g.fillRect(col * px - 1, 0, 2, rows * px)
}

function drawCaveFloor(g: CanvasRenderingContext2D, rand: Prng, cols: number, rows: number, px: number, biome: Biome3D): void {
  const width = cols * px
  const height = rows * px
  const base = rgb(biome.ground)
  const dark = rgb(biome.groundAccent)
  g.fillStyle = shade(base, 1)
  g.fillRect(0, 0, width, height)
  for (let i = 0; i < cols * rows * 1.5; i++) {
    const radius = range(rand, px * 0.3, px * 1.4)
    const gradient = g.createRadialGradient(0, 0, 0, 0, 0, radius)
    const color = rand() < 0.5 ? shade(dark, 1, 0.35) : shade(base, 1.18, 0.3)
    gradient.addColorStop(0, color)
    gradient.addColorStop(1, 'rgba(0,0,0,0)')
    g.save()
    g.translate(rand() * width, rand() * height)
    g.fillStyle = gradient
    g.fillRect(-radius, -radius, radius * 2, radius * 2)
    g.restore()
  }
  for (let i = 0; i < cols * rows * 0.4; i++) crack(g, rand, rand() * width, rand() * height, px * 0.8, shade(dark, 0.8, 0.5))
  speckle(g, rand, { w: width, h: height }, base, cols * rows * 14)
}

// ─── Extérieur : texture répétable ──────────────────────────────────────────

/** Texture répétable (coordonnées monde) pour le plateau et le terrain prolongé. */
export function naturalTexture(biome: Biome3D, seed: string): THREE.CanvasTexture | null {
  const size = 512
  const g = makeCanvas(size, size)
  if (!g) return null
  const rand = makePrng(`natural|${seed}`)
  const base = rgb(biome.ground)
  const accent = rgb(biome.groundAccent)
  g.fillStyle = shade(base, 1)
  g.fillRect(0, 0, size, size)

  switch (biome.groundStyle) {
    case 'cobble':
      drawCobbles(g, rand, size, base, accent)
      break
    case 'sand': {
      // Variations douces (des taches trop contrastées lisent comme de la saleté).
      for (let i = 0; i < 40; i++) blotch(g, size, rand() * size, rand() * size, range(rand, 40, 130), shade(rand() < 0.5 ? accent : base, rand() < 0.5 ? 1 : 1.08, 0.1))
      // Rides de vent.
      g.strokeStyle = shade(accent, 0.95, 0.14)
      g.lineWidth = 2
      for (let y = 0; y < size; y += 16) {
        g.beginPath()
        for (let x = 0; x <= size; x += 8) g.lineTo(x, y + Math.sin((x / size) * Math.PI * 4 + y * 0.3) * 4)
        g.stroke()
      }
      speckle(g, rand, { w: size, h: size }, base, 5000)
      break
    }
    case 'grass':
    case 'forest':
    case 'mud': {
      const blotches = biome.groundStyle === 'forest' ? 70 : 50
      for (let i = 0; i < blotches; i++) {
        const tint = rand() < 0.55 ? accent : mix(base, [210, 200, 140], 0.15)
        blotch(g, size, rand() * size, rand() * size, range(rand, 25, 90), shade(tint, range(rand, 0.85, 1.1), 0.35))
      }
      // Brins / feuilles mortes.
      for (let i = 0; i < 2600; i++) {
        const x = rand() * size
        const y = rand() * size
        g.strokeStyle = shade(rand() < 0.5 ? base : accent, range(rand, 0.7, 1.3), 0.45)
        g.lineWidth = 1
        g.beginPath()
        g.moveTo(x, y)
        g.lineTo(x + range(rand, -2, 2), y - range(rand, 2, 5))
        g.stroke()
      }
      if (biome.groundStyle === 'mud') {
        for (let i = 0; i < 18; i++) blotch(g, size, rand() * size, rand() * size, range(rand, 20, 60), 'rgba(40,52,48,0.35)')
      }
      break
    }
    case 'rock':
    case 'cave':
    case 'flagstone':
    default: {
      for (let i = 0; i < 60; i++) blotch(g, size, rand() * size, rand() * size, range(rand, 20, 90), shade(rand() < 0.5 ? accent : base, range(rand, 0.85, 1.15), 0.35))
      for (let i = 0; i < 40; i++) crack(g, rand, rand() * size, rand() * size, 40, shade(accent, 0.7, 0.45))
      speckle(g, rand, { w: size, h: size }, base, 6000)
    }
  }
  return toTexture(g, true)
}

function drawCobbles(g: CanvasRenderingContext2D, rand: Prng, size: number, base: Rgb, accent: Rgb): void {
  // La tuile couvre 2 cases (NATURAL_TILE_WORLD.cobble) : 3 pavés par case.
  g.fillStyle = shade(accent, 0.8)
  g.fillRect(0, 0, size, size)
  const per = 6
  const cell = size / per
  for (let row = 0; row < per; row++) {
    const offset = row % 2 ? cell / 2 : 0
    for (let col = -1; col < per; col++) {
      const x = col * cell + offset + 2
      const y = row * cell + 2
      g.fillStyle = shade(base, range(rand, 0.82, 1.12))
      g.beginPath()
      g.roundRect(x, y, cell - 4, cell - 4, cell * 0.25)
      g.fill()
      g.fillStyle = shade(base, 1.2, 0.35)
      g.fillRect(x + 4, y + 3, cell - 14, 2)
    }
  }
  speckle(g, rand, { w: size, h: size }, base, 3000)
}
