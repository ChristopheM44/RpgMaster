// Props procéduraux nommés (refonte lot 4) : objets sans GLB dans les packs CC0
// mais fréquents dans les récits — fontaine, puits, autel, sarcophage, enclume,
// lutrin, butte, traces de pas. Choisis par le catalogue sémantique (`proc/*`,
// cf. backend prop_catalog) ; dessinés ici à des proportions réelles (mètres).
// Le groupe renvoyé est centré sur l'empreinte (le caller le positionne).

import * as THREE from 'three'
import type { ElementSpec } from '../types'
import type { ThemeTokens } from '../core/ThemeProvider'
import { metersToWorld } from '../utils/gridMath'
import { makePrng } from '../utils/seededRandom'

export interface PropBuildCtx {
  cellSizeM: number
  tokens: ThemeTokens
  /** Albédo du sol du biome (butte, dune) : la butte EST du terrain. */
  groundColor?: string
}

const STONE = '#958d80'
const STONE_LIGHT = '#aaa294'
const WOOD = '#6b4a2f'
const WOOD_DARK = '#4d3522'
const IRON = '#3d3c42'
const WATER = '#4f8793'
const DRY_BED = '#7f7464'

function mat(hex: string, options: { roughness?: number; metalness?: number; emissive?: string; emissiveIntensity?: number; opacity?: number } = {}): THREE.MeshStandardMaterial {
  const material = new THREE.MeshStandardMaterial({
    color: new THREE.Color(hex),
    roughness: options.roughness ?? 0.9,
    metalness: options.metalness ?? 0.02,
  })
  if (options.emissive) {
    material.emissive = new THREE.Color(options.emissive)
    material.emissiveIntensity = options.emissiveIntensity ?? 0.4
  }
  if (options.opacity != null && options.opacity < 1) {
    material.transparent = true
    material.opacity = options.opacity
    material.depthWrite = false
  }
  return material
}

function add(group: THREE.Group, geometry: THREE.BufferGeometry, material: THREE.Material, x: number, y: number, z: number): THREE.Mesh {
  const mesh = new THREE.Mesh(geometry, material)
  mesh.position.set(x, y, z)
  mesh.castShadow = true
  mesh.receiveShadow = true
  group.add(mesh)
  return mesh
}

/** Prop procédural nommé, ou null si la clé n'est pas connue. */
export function buildProceduralProp(
  key: string,
  spec: Pick<ElementSpec, 'id' | 'name' | 'facing'>,
  worldSize: { x: number; z: number },
  elevation: number,
  ctx: PropBuildCtx,
): THREE.Group | null {
  const m = (meters: number) => metersToWorld(meters, ctx.cellSizeM)
  const group = new THREE.Group()
  // Face avant = +Z local, tournée vers `facing` (rayonnage contre un mur est/ouest).
  const quarterTurn = spec.facing === 'east' || spec.facing === 'west'
  const size = quarterTurn ? { x: worldSize.z, z: worldSize.x } : worldSize
  const minSide = Math.min(size.x, size.z)

  switch (key) {
    case 'proc/fountain': {
      const r = Math.max(0.3, minSide * 0.48)
      const h = m(0.45)
      const dry = /tari|sec\b|s[eè]che|vide|ass[eé]ch|dry/i.test(spec.name)
      add(group, new THREE.CylinderGeometry(r, r * 1.05, h, 10), mat(STONE), 0, h / 2, 0)
      const rim = add(group, new THREE.TorusGeometry(r * 0.93, r * 0.07, 6, 20), mat(STONE_LIGHT), 0, h, 0)
      rim.rotation.x = -Math.PI / 2
      add(
        group,
        new THREE.CircleGeometry(r * 0.86, 24),
        dry ? mat(DRY_BED) : mat(WATER, { roughness: 0.12, metalness: 0.1, emissive: WATER, emissiveIntensity: 0.12 }),
        0,
        h - m(0.06),
        0,
      ).rotation.x = -Math.PI / 2
      add(group, new THREE.CylinderGeometry(r * 0.12, r * 0.16, m(1.0), 8), mat(STONE_LIGHT), 0, m(0.5), 0)
      add(group, new THREE.CylinderGeometry(r * 0.42, r * 0.22, m(0.14), 12), mat(STONE_LIGHT), 0, m(1.02), 0)
      break
    }
    case 'proc/well': {
      const r = Math.max(0.25, minSide * 0.36)
      const h = m(0.75)
      add(group, new THREE.CylinderGeometry(r, r * 1.04, h, 12), mat(STONE), 0, h / 2, 0)
      add(group, new THREE.CircleGeometry(r * 0.8, 20), mat('#0c0b0a', { roughness: 1 }), 0, h + 0.002, 0).rotation.x = -Math.PI / 2
      const postH = m(1.7)
      for (const side of [-1, 1]) {
        add(group, new THREE.BoxGeometry(0.07, postH, 0.07), mat(WOOD), side * r * 0.95, postH / 2, 0)
      }
      add(group, new THREE.CylinderGeometry(0.035, 0.035, r * 2, 8), mat(WOOD_DARK), 0, postH * 0.82, 0).rotation.z = Math.PI / 2
      for (const side of [-1, 1]) {
        const roof = add(group, new THREE.BoxGeometry(r * 2.5, 0.04, r * 0.9), mat(WOOD_DARK), 0, postH + 0.08, side * r * 0.3)
        roof.rotation.x = side * 0.5
      }
      break
    }
    case 'proc/altar': {
      const w = Math.max(0.5, size.x * 0.85)
      const d = Math.max(0.35, size.z * 0.6)
      const h = m(0.95)
      add(group, new THREE.BoxGeometry(w, h, d), mat(STONE), 0, h / 2, 0)
      add(group, new THREE.BoxGeometry(w * 1.08, m(0.08), d * 1.12), mat(STONE_LIGHT), 0, h + m(0.04), 0)
      add(group, new THREE.BoxGeometry(w * 0.3, m(0.012), d * 1.14), mat(ctx.tokens.blood, { roughness: 0.8 }), 0, h + m(0.085), 0)
      for (const side of [-1, 1]) {
        add(group, new THREE.CylinderGeometry(0.03, 0.035, m(0.22), 8), mat(ctx.tokens.parchment), side * w * 0.38, h + m(0.19), 0)
        add(
          group,
          new THREE.SphereGeometry(0.035, 8, 6),
          mat(ctx.tokens.ember, { emissive: ctx.tokens.ember, emissiveIntensity: 1.6 }),
          side * w * 0.38,
          h + m(0.33),
          0,
        )
      }
      break
    }
    case 'proc/sarcophagus': {
      const alongX = size.x >= size.z
      const long = Math.max(0.6, Math.max(size.x, size.z) * 0.9)
      const short = Math.max(0.35, Math.min(size.x, size.z) * 0.78)
      const h = m(0.7)
      const body = new THREE.Group()
      add(body, new THREE.BoxGeometry(long, h, short), mat(STONE), 0, h / 2, 0)
      add(body, new THREE.BoxGeometry(long * 1.05, m(0.12), short * 1.08), mat(STONE_LIGHT), 0, h + m(0.06), 0)
      add(body, new THREE.BoxGeometry(long * 0.78, m(0.06), short * 0.32), mat(STONE_LIGHT), 0, h + m(0.15), 0)
      add(body, new THREE.SphereGeometry(short * 0.2, 10, 8), mat(STONE_LIGHT), long * 0.38, h + m(0.16), 0)
      if (!alongX) body.rotation.y = Math.PI / 2
      group.add(body)
      break
    }
    case 'proc/anvil': {
      const s = Math.max(0.5, minSide)
      add(group, new THREE.CylinderGeometry(s * 0.24, s * 0.28, m(0.5), 10), mat(WOOD_DARK), 0, m(0.25), 0)
      const iron = mat(IRON, { roughness: 0.45, metalness: 0.65 })
      add(group, new THREE.BoxGeometry(s * 0.34, m(0.14), s * 0.2), iron, 0, m(0.57), 0)
      add(group, new THREE.BoxGeometry(s * 0.52, m(0.1), s * 0.24), iron, 0, m(0.69), 0)
      const horn = add(group, new THREE.ConeGeometry(s * 0.1, s * 0.3, 10), iron, s * 0.4, m(0.69), 0)
      horn.rotation.z = -Math.PI / 2
      break
    }
    case 'proc/lectern': {
      const s = Math.max(0.5, minSide)
      add(group, new THREE.BoxGeometry(s * 0.4, m(0.06), s * 0.4), mat(WOOD_DARK), 0, m(0.03), 0)
      add(group, new THREE.CylinderGeometry(0.045, 0.06, m(1.05), 8), mat(WOOD), 0, m(0.55), 0)
      const top = new THREE.Group()
      top.position.set(0, m(1.1), 0)
      top.rotation.x = 0.42
      add(top, new THREE.BoxGeometry(s * 0.56, m(0.04), s * 0.42), mat(WOOD), 0, 0, 0)
      for (const side of [-1, 1]) {
        const page = add(top, new THREE.BoxGeometry(s * 0.25, m(0.02), s * 0.34), mat(ctx.tokens.parchment, { roughness: 1 }), side * s * 0.13, m(0.035), 0)
        page.rotation.z = side * -0.08
      }
      group.add(top)
      break
    }
    case 'proc/bookcase': {
      // Bâti haut, montants, 4 tablettes ; dos de livres colorés (ou portes fermées
      // pour une armoire / un buffet).
      const w = Math.max(0.5, size.x * 0.96)
      const d = Math.max(0.22, Math.min(size.z, 0.55))
      const h = m(2.1)
      const wood = mat(WOOD)
      const back = add(group, new THREE.BoxGeometry(w, h, 0.04), mat(WOOD_DARK), 0, h / 2, -d / 2 + 0.02)
      back.castShadow = true
      for (const side of [-1, 1]) {
        add(group, new THREE.BoxGeometry(0.05, h, d), wood, side * (w / 2 - 0.025), h / 2, 0)
      }
      add(group, new THREE.BoxGeometry(w, 0.05, d), wood, 0, h - 0.025, 0)
      const closed = /armoire|placard|buffet|vaisselier/i.test(spec.name)
      if (closed) {
        for (const side of [-1, 1]) {
          add(group, new THREE.BoxGeometry(w / 2 - 0.04, h - 0.1, 0.03), mat(WOOD, { roughness: 0.75 }), side * (w / 4), h / 2, d / 2 - 0.02)
        }
        break
      }
      const rand = makePrng(`books|${spec.id}`)
      const spines = ['#7a2e2a', '#2f4a6b', '#5c6b2e', '#6b4a2f', '#8a7340', '#4a3a5c', '#a08562']
        .map((hex) => mat(hex, { roughness: 0.85 }))
      const shelves = 4
      const tier = (h - 0.05) / shelves
      for (let i = 0; i < shelves; i++) {
        const y = i * tier
        add(group, new THREE.BoxGeometry(w - 0.1, 0.035, d), wood, 0, y + 0.0175, 0)
        let x = -w / 2 + 0.07
        while (x < w / 2 - 0.1) {
          const bw = 0.035 + rand() * 0.05
          const bh = tier * (0.55 + rand() * 0.3)
          if (rand() > 0.12) {
            const book = add(
              group,
              new THREE.BoxGeometry(bw, bh, d * 0.8),
              spines[Math.floor(rand() * spines.length)] ?? wood,
              x + bw / 2,
              y + 0.035 + bh / 2,
              0.02,
            )
            book.castShadow = false
          }
          x += bw + 0.006
        }
      }
      break
    }
    case 'proc/mound': {
      const h = m(0.6)
      const mound = add(group, new THREE.SphereGeometry(0.5, 20, 10, 0, Math.PI * 2, 0, Math.PI / 2), mat(shade(ctx.groundColor ?? '#a08a62', 0.9), { roughness: 1 }), 0, 0, 0)
      mound.scale.set(size.x * 0.98, h / 0.5, size.z * 0.98)
      break
    }
    case 'proc/footprints': {
      const rand = makePrng(`steps|${spec.id}`)
      const angle = rand() * Math.PI * 2
      const dir = new THREE.Vector2(Math.cos(angle), Math.sin(angle))
      const normal = new THREE.Vector2(-dir.y, dir.x)
      const span = Math.max(size.x, size.z) * 0.85
      const material = mat('#3a3027', { roughness: 1, opacity: 0.6 })
      const steps = 7
      for (let i = 0; i < steps; i++) {
        const t = (i / (steps - 1) - 0.5) * span
        const side = i % 2 === 0 ? 1 : -1
        const print = new THREE.Mesh(new THREE.CircleGeometry(0.5, 12), material)
        print.scale.set(0.07, 0.13, 1)
        print.rotation.x = -Math.PI / 2
        print.rotation.z = -angle + Math.PI / 2
        print.position.set(dir.x * t + normal.x * side * 0.07, 0.013, dir.y * t + normal.y * side * 0.07)
        print.receiveShadow = true
        group.add(print)
      }
      break
    }
    default:
      return null
  }

  group.position.y = elevation
  group.rotation.y = FACING_ROTATION_Y[spec.facing ?? 'south'] ?? 0
  return group
}

/** Face avant +Z (= sud) : même convention que les meubles GLB (ElementsLayer). */
const FACING_ROTATION_Y: Record<string, number> = {
  south: 0,
  north: Math.PI,
  east: Math.PI / 2,
  west: -Math.PI / 2,
}

function shade(hex: string, factor: number): string {
  const color = new THREE.Color(hex).multiplyScalar(factor)
  return `#${color.getHexString()}`
}
