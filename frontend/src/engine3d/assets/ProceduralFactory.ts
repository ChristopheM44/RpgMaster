// Fabrique procédurale — garantit un mesh pour CHAQUE kind d'élément (y compris
// les kinds inventés par le LLM), un pion pour tout personnage sans modèle, et
// les végétaux/rochers de scatter. Tout est teinté via les tokens du design
// system ; aucun asset externe requis.

import * as THREE from 'three'
import type { ElementSpec, GridDims } from '../types'
import type { ScatterKind, ThemeTokens } from '../core/ThemeProvider'
import { gridPointToWorld, metersToWorld } from '../utils/gridMath'
import { pick, range, type Prng } from '../utils/seededRandom'
import {
  cellBounds,
  FACING_VECTOR,
  inferStairsFacing,
  isStairwell,
  RISING_STAIRS_MIN_RISE_M,
  RISING_STAIRS_STEPS,
  stairwellDepthM,
  STAIRWELL_STEPS,
} from '../adapters/stairs'
import type { SceneElementFacing } from '../../types'
import { hazardTextures } from './groundTextures'
import { isProceduralPropKey, matchProp } from './manifest'
import { buildProceduralProp } from './proceduralProps'

export interface ElementBuildCtx {
  dims: GridDims
  cellSizeM: number
  tokens: ThemeTokens
  /** Albédo du sol du biome (butte, dune). */
  groundColor?: string
}

const PROP_KINDS = new Set(['furniture', 'cover', 'decor'])

/** Clé `proc/*` d'un élément : hint explicite, sinon nom reconnu par le catalogue. */
export function proceduralPropKeyFor(spec: Pick<ElementSpec, 'kind' | 'name' | 'modelKey'>): string | null {
  if (isProceduralPropKey(spec.modelKey)) return spec.modelKey
  if (spec.modelKey || !PROP_KINDS.has(spec.kind)) return null
  const matched = matchProp(spec.name)
  return isProceduralPropKey(matched) ? matched : null
}

// ─── Helpers matériaux ───────────────────────────────────────────────────────

function color(hex: string): THREE.Color {
  return new THREE.Color(hex)
}

function desaturated(base: THREE.Color, amount = 0.6): THREE.Color {
  const gray = new THREE.Color('#55505a')
  return base.clone().lerp(gray, amount)
}

interface MatOptions {
  emissive?: string
  emissiveIntensity?: number
  opacity?: number
  roughness?: number
  metalness?: number
}

function makeMaterial(hex: string, subtle: boolean, options: MatOptions = {}): THREE.MeshStandardMaterial {
  const base = subtle ? desaturated(color(hex)) : color(hex)
  const material = new THREE.MeshStandardMaterial({
    color: base,
    roughness: options.roughness ?? 0.92,
    metalness: options.metalness ?? 0.02,
  })
  if (options.emissive) {
    material.emissive = subtle ? desaturated(color(options.emissive)) : color(options.emissive)
    material.emissiveIntensity = options.emissiveIntensity ?? 0.3
  }
  const opacity = (options.opacity ?? 1) * (subtle ? 0.42 : 1)
  if (opacity < 1) {
    material.transparent = true
    material.opacity = opacity
  }
  return material
}

// ─── Placement depuis la géométrie de grille ─────────────────────────────────

interface Footprint {
  /** Centre monde XZ. */
  x: number
  z: number
  /** Empreinte monde (X = largeur le long de l'axe local). */
  sizeX: number
  sizeZ: number
  rotationY: number
}

function footprintFor(spec: ElementSpec, dims: GridDims): Footprint {
  const geometry = spec.geometry
  if (geometry.type === 'line') {
    const a = gridPointToWorld(geometry.from.col, geometry.from.row, dims)
    const b = gridPointToWorld(geometry.to.col, geometry.to.row, dims)
    const length = Math.max(0.25, Math.hypot(b.x - a.x, b.z - a.z))
    return {
      x: (a.x + b.x) / 2,
      z: (a.z + b.z) / 2,
      sizeX: length,
      sizeZ: 0.18,
      rotationY: -Math.atan2(b.z - a.z, b.x - a.x),
    }
  }
  if (geometry.type === 'rect') {
    const center = gridPointToWorld(geometry.col + geometry.width / 2, geometry.row + geometry.height / 2, dims)
    return {
      x: center.x,
      z: center.z,
      sizeX: Math.max(0.2, geometry.width * 0.94),
      sizeZ: Math.max(0.2, geometry.height * 0.94),
      rotationY: 0,
    }
  }
  const center = gridPointToWorld(geometry.col, geometry.row, dims)
  return {
    x: center.x,
    z: center.z,
    sizeX: Math.max(0.2, geometry.radius_col * 2),
    sizeZ: Math.max(0.2, geometry.radius_row * 2),
    rotationY: 0,
  }
}

function isEllipse(spec: ElementSpec): boolean {
  return spec.geometry.type === 'ellipse'
}

// ─── Éléments ────────────────────────────────────────────────────────────────

/**
 * Mesh procédural pour un élément de scène. Ne retourne jamais null : tout
 * kind inconnu retombe sur le rendu `decor`.
 */
export function buildProceduralElement(spec: ElementSpec, ctx: ElementBuildCtx): THREE.Object3D {
  const foot = footprintFor(spec, ctx.dims)
  const height = Math.max(0.04, metersToWorld(spec.heightM, ctx.cellSizeM))
  const elevation = metersToWorld(spec.elevationM, ctx.cellSizeM)
  const group = new THREE.Group()
  const subtle = spec.subtle
  const tokens = ctx.tokens

  // Objet nommé sans GLB (fontaine, autel, sarcophage…) : dessiné à l'échelle réelle.
  const propKey = proceduralPropKeyFor(spec)
  const prop = propKey
    ? buildProceduralProp(propKey, spec, { x: foot.sizeX, z: foot.sizeZ }, elevation, {
        cellSizeM: ctx.cellSizeM,
        tokens,
        groundColor: ctx.groundColor,
      })
    : null
  if (prop) {
    group.add(prop)
    group.position.set(foot.x, 0, foot.z)
    return group
  }

  const addVolume = (material: THREE.MeshStandardMaterial, volumeHeight = height, inset = 1): THREE.Mesh => {
    const mesh = isEllipse(spec)
      ? new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, volumeHeight, 20), material)
      : new THREE.Mesh(new THREE.BoxGeometry(1, volumeHeight, 1), material)
    mesh.scale.set(foot.sizeX * inset, 1, foot.sizeZ * inset)
    mesh.position.y = elevation + volumeHeight / 2
    mesh.castShadow = true
    mesh.receiveShadow = true
    group.add(mesh)
    return mesh
  }

  const addFlat = (material: THREE.MeshStandardMaterial, y = 0.012): THREE.Mesh => {
    const mesh = isEllipse(spec)
      ? new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, 0.015, 24), material)
      : new THREE.Mesh(new THREE.BoxGeometry(1, 0.015, 1), material)
    mesh.scale.set(foot.sizeX, 1, foot.sizeZ)
    mesh.position.y = y + elevation
    mesh.receiveShadow = true
    group.add(mesh)
    return mesh
  }

  // Enceinte circulaire (mur ellipse) : coque OUVERTE rendue côté intérieur
  // (BackSide). La paroi face caméra est culled → on voit DANS la caverne ; la
  // paroi opposée sert de fond. Pas de chapeau plein qui enterrerait l'intérieur,
  // pas d'ombre projetée vers le centre — sinon le mur redevient un dôme opaque.
  const addEnclosureShell = (material: THREE.MeshStandardMaterial): void => {
    const shellMat = material.clone()
    shellMat.side = THREE.BackSide
    const shell = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, height, 48, 1, true), shellMat)
    shell.scale.set(foot.sizeX, 1, foot.sizeZ)
    shell.position.y = elevation + height / 2
    group.add(shell)
  }

  // Grand rectangle = pièce close : 4 segments de mur en périmètre, centre dégagé.
  const addRectFrame = (material: THREE.MeshStandardMaterial): void => {
    const t = Math.min(0.3, foot.sizeX / 2, foot.sizeZ / 2)
    const segments = [
      { sx: foot.sizeX, sz: t, px: 0, pz: -foot.sizeZ / 2 + t / 2 },
      { sx: foot.sizeX, sz: t, px: 0, pz: foot.sizeZ / 2 - t / 2 },
      { sx: t, sz: foot.sizeZ, px: -foot.sizeX / 2 + t / 2, pz: 0 },
      { sx: t, sz: foot.sizeZ, px: foot.sizeX / 2 - t / 2, pz: 0 },
    ]
    for (const seg of segments) {
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(seg.sx, height, seg.sz), material)
      mesh.position.set(seg.px, elevation + height / 2, seg.pz)
      mesh.receiveShadow = true
      group.add(mesh)
    }
  }

  switch (spec.kind) {
    case 'wall': {
      const stone = desaturated(color(tokens.dim), 0.25).multiplyScalar(0.82)
      const material = makeMaterial(`#${stone.getHexString()}`, subtle, { roughness: 0.96 })
      const geom = spec.geometry
      if (geom.type === 'ellipse') addEnclosureShell(material)
      else if (geom.type === 'rect' && geom.width > 1 && geom.height > 1) addRectFrame(material)
      else addVolume(material) // mur 1 cellule (pilier) ou segment droit : plein
      break
    }
    case 'door': {
      const material = makeMaterial(tokens.goldDeep, subtle, {
        emissive: tokens.gold,
        emissiveIntensity: 0.12,
        roughness: 0.7,
      })
      addVolume(material, height, 0.96)
      break
    }
    case 'window': {
      const material = makeMaterial(tokens.teal, subtle, {
        emissive: tokens.teal,
        emissiveIntensity: 0.5,
        opacity: 0.5,
        roughness: 0.3,
      })
      const mesh = addVolume(material, height * 0.55)
      mesh.position.y = elevation + metersToWorld(1.0, ctx.cellSizeM)
      break
    }
    case 'furniture': {
      addVolume(makeMaterial('#7a5c3a', subtle, { roughness: 0.85 }))
      break
    }
    case 'cover': {
      addVolume(makeMaterial('#5c4a34', subtle, { roughness: 0.95 }))
      break
    }
    case 'hazard': {
      // Décalque au sol (fissures + bord sang en pointillés animé) : se lit comme
      // « terrain dangereux » sans légende ; le nom apparaît au survol.
      const decal = new THREE.Group()
      addHazardDecal(decal, Math.max(0.6, foot.sizeX), Math.max(0.6, foot.sizeZ), spec.id, tokens)
      decal.position.y = elevation
      group.add(decal)
      break
    }
    case 'light': {
      const poleHeight = height
      const pole = new THREE.Mesh(
        new THREE.CylinderGeometry(0.045, 0.06, poleHeight, 8),
        makeMaterial('#3a3226', subtle),
      )
      pole.position.y = elevation + poleHeight / 2
      pole.castShadow = true
      group.add(pole)
      const flame = new THREE.Mesh(
        new THREE.SphereGeometry(0.13, 12, 10),
        makeMaterial(tokens.ember, subtle, { emissive: tokens.ember, emissiveIntensity: 1.6 }),
      )
      flame.position.y = elevation + poleHeight + 0.08
      group.add(flame)
      break
    }
    case 'stairs': {
      const facing = spec.facing ?? inferStairsFacing(spec.geometry, ctx.dims)
      if (isStairwell(spec)) buildStairwell(group, spec, ctx, foot, facing)
      else buildRisingStairs(group, spec, ctx, foot, facing, elevation)
      break
    }
    case 'terrain': {
      const kindColor = terrainColor(spec.terrainType, tokens)
      addFlat(makeMaterial(kindColor.hex, subtle, { opacity: kindColor.opacity, roughness: 0.98 }), kindColor.y)
      break
    }
    case 'decor':
    default: {
      // Décor non reconnu : dalle basse neutre (une caisse d'0,8 m pour « Roseaux »
      // ou « Traces » serait un contresens ; le nom s'affiche au survol).
      addVolume(makeMaterial('#6a6254', subtle, { roughness: 0.9 }), Math.min(height, metersToWorld(0.25, ctx.cellSizeM)), 0.8)
      break
    }
  }

  group.position.set(foot.x, 0, foot.z)
  group.rotation.y = foot.rotationY
  return group
}

// ─── Danger ──────────────────────────────────────────────────────────────────

/** Décalque de danger au sol (fissures + bord en pointillés) ; sans canvas → voile sang. */
export function addHazardDecal(
  parent: THREE.Object3D,
  sizeX: number,
  sizeZ: number,
  seed: string,
  tokens: Pick<ThemeTokens, 'blood'>,
): void {
  const textures = hazardTextures(seed)
  const base = new THREE.Mesh(
    new THREE.PlaneGeometry(sizeX, sizeZ),
    new THREE.MeshStandardMaterial({
      color: textures ? '#ffffff' : tokens.blood,
      map: textures?.cracks ?? null,
      transparent: true,
      opacity: textures ? 0.95 : 0.35,
      depthWrite: false,
      roughness: 1,
    }),
  )
  base.rotation.x = -Math.PI / 2
  base.position.y = 0.014
  base.receiveShadow = true
  parent.add(base)
  if (!textures) return
  const ring = new THREE.Mesh(
    new THREE.PlaneGeometry(sizeX * 1.04, sizeZ * 1.04),
    new THREE.MeshBasicMaterial({ map: textures.ring, transparent: true, opacity: 0.85, depthWrite: false }),
  )
  ring.rotation.x = -Math.PI / 2
  ring.position.y = 0.017
  ring.userData.hazardRing = true
  parent.add(ring)
}

// ─── Escaliers ───────────────────────────────────────────────────────────────
// Positions exprimées relativement au centre `foot` (le groupe y est placé).

const STAIR_STONE = '#8b8379'

/** Volée qui MONTE vers `facing` ; palier au-delà du bord. */
function buildRisingStairs(
  group: THREE.Group,
  spec: ElementSpec,
  ctx: ElementBuildCtx,
  foot: Footprint,
  facing: SceneElementFacing,
  elevation: number,
): void {
  const dir = FACING_VECTOR[facing]
  const alongZ = dir.z !== 0
  const along = alongZ ? foot.sizeZ / 0.94 : foot.sizeX / 0.94
  const across = (alongZ ? foot.sizeX : foot.sizeZ)
  const rise = metersToWorld(Math.max(spec.heightM, RISING_STAIRS_MIN_RISE_M), ctx.cellSizeM)
  const steps = RISING_STAIRS_STEPS
  const depth = along / steps
  const material = makeMaterial(STAIR_STONE, spec.subtle, { roughness: 0.9 })
  const box = (w: number, h: number, d: number): THREE.BoxGeometry =>
    new THREE.BoxGeometry(alongZ ? w : d, h, alongZ ? d : w)

  for (let i = 0; i < steps; i++) {
    const h = (rise / steps) * (i + 1)
    const offset = -along / 2 + depth * (i + 0.5)
    const step = new THREE.Mesh(box(across, h, depth), material)
    step.position.set(dir.x * offset, elevation + h / 2, dir.z * offset)
    step.castShadow = true
    step.receiveShadow = true
    group.add(step)
  }
  // Palier qui traverse l'ouverture du mur : l'escalier continue hors de la carte.
  const landing = new THREE.Mesh(box(across, rise, 0.5), material)
  landing.position.set(dir.x * (along / 2 + 0.25), elevation + rise / 2, dir.z * (along / 2 + 0.25))
  landing.receiveShadow = true
  group.add(landing)
}

/**
 * Trémie : les cellules sont retirées du sol (GroundLayer), les marches
 * s'enfoncent vers `facing`, parois et margelle bordent l'ouverture, le fond
 * se perd dans le noir.
 */
function buildStairwell(
  group: THREE.Group,
  spec: ElementSpec,
  ctx: ElementBuildCtx,
  foot: Footprint,
  facing: SceneElementFacing,
): void {
  const dir = FACING_VECTOR[facing]
  const alongZ = dir.z !== 0
  const { c0, r0, c1, r1 } = cellBounds(spec.geometry, ctx.dims)
  const center = gridPointToWorld((c0 + c1) / 2, (r0 + r1) / 2, ctx.dims)
  const cx = center.x - foot.x
  const cz = center.z - foot.z
  const along = alongZ ? r1 - r0 : c1 - c0
  const across = alongZ ? c1 - c0 : r1 - r0
  const depthTotal = metersToWorld(stairwellDepthM({ geometry: spec.geometry, facing }, ctx.dims), ctx.cellSizeM)
  const steps = STAIRWELL_STEPS
  const depth = along / steps
  const drop = depthTotal / steps
  const box = (w: number, h: number, d: number): THREE.BoxGeometry =>
    new THREE.BoxGeometry(alongZ ? w : d, h, alongZ ? d : w)
  const at = (offset: number, y: number, lateral = 0): [number, number, number] => [
    cx + dir.x * offset + (alongZ ? lateral : 0),
    y,
    cz + dir.z * offset + (alongZ ? 0 : lateral),
  ]
  const stone = new THREE.Color(STAIR_STONE)
  const night = new THREE.Color('#07060a')

  for (let i = 0; i < steps; i++) {
    const top = -drop * (i + 1)
    // Assombrissement progressif modéré : la profondeur se lit sans noyer les marches.
    const tone = stone.clone().lerp(night, 0.12 * (i + 1))
    const step = new THREE.Mesh(
      box(across - 0.04, drop * 2, depth),
      makeMaterial(`#${tone.getHexString()}`, spec.subtle, { roughness: 0.95 }),
    )
    step.position.set(...at(-along / 2 + depth * (i + 0.5), top - drop))
    step.receiveShadow = true
    group.add(step)
  }

  const wallHeight = depthTotal + drop * 2
  const wallMaterial = makeMaterial('#2b2630', spec.subtle, { roughness: 1 })
  for (const side of [-1, 1]) {
    const wall = new THREE.Mesh(box(0.06, wallHeight, along), wallMaterial)
    wall.position.set(...at(0, -wallHeight / 2, side * (across / 2 - 0.03)))
    group.add(wall)
  }
  const back = new THREE.Mesh(box(across, wallHeight, 0.06), wallMaterial)
  back.position.set(...at(-along / 2 + 0.03, -wallHeight / 2))
  group.add(back)
  // Au-delà de la dernière marche : pierre sombre (le passage file sous le bord).
  const beyond = new THREE.Mesh(box(across, wallHeight, 0.04), makeMaterial('#1c1822', spec.subtle, { roughness: 1 }))
  beyond.position.set(...at(along / 2 - 0.02, -wallHeight / 2))
  group.add(beyond)

  const rimMaterial = makeMaterial('#a39a8c', spec.subtle, { roughness: 0.85 })
  for (const side of [-1, 1]) {
    const rim = new THREE.Mesh(box(0.08, 0.05, along), rimMaterial)
    rim.position.set(...at(0, 0.02, side * (across / 2)))
    rim.castShadow = true
    group.add(rim)
  }
  const backRim = new THREE.Mesh(box(across + 0.08, 0.05, 0.08), rimMaterial)
  backRim.position.set(...at(-along / 2, 0.02))
  backRim.castShadow = true
  group.add(backRim)
}

function terrainColor(terrainType: string | null, tokens: ThemeTokens): { hex: string; opacity: number; y: number } {
  switch (terrainType) {
    case 'water':
      return { hex: tokens.teal, opacity: 0.3, y: 0.02 }
    case 'mud':
      return { hex: '#3a3226', opacity: 0.6, y: 0.012 }
    case 'street':
      return { hex: tokens.goldDeep, opacity: 0.35, y: 0.012 }
    case 'plaza_paving':
      return { hex: tokens.parchment, opacity: 0.07, y: 0.008 }
    case 'road':
    case 'path':
    default:
      return { hex: '#8a7c60', opacity: 0.35, y: 0.012 }
  }
}

// ─── Pions (personnages sans modèle) ─────────────────────────────────────────

/** Pion façon figurine : socle accentué + corps capsule + tête. */
export function buildPawn(accent: string, heightWorld: number): THREE.Group {
  const group = new THREE.Group()
  const accentColor = color(accent)
  const bodyColor = accentColor.clone().multiplyScalar(0.5)

  const base = new THREE.Mesh(
    new THREE.CylinderGeometry(0.3, 0.34, 0.07, 20),
    new THREE.MeshStandardMaterial({
      color: bodyColor,
      emissive: accentColor,
      emissiveIntensity: 0.35,
      roughness: 0.6,
    }),
  )
  base.position.y = 0.035
  group.add(base)

  const bodyHeight = Math.max(0.4, heightWorld * 0.62)
  const radius = Math.max(0.12, heightWorld * 0.16)
  const body = new THREE.Mesh(
    new THREE.CapsuleGeometry(radius, bodyHeight - radius * 2, 6, 12),
    new THREE.MeshStandardMaterial({ color: bodyColor, roughness: 0.8 }),
  )
  body.position.y = 0.07 + bodyHeight / 2
  body.castShadow = true
  group.add(body)

  const head = new THREE.Mesh(
    new THREE.SphereGeometry(radius * 0.78, 14, 12),
    new THREE.MeshStandardMaterial({ color: accentColor.clone().lerp(new THREE.Color('#f7ecd0'), 0.3), roughness: 0.7 }),
  )
  head.position.y = 0.07 + bodyHeight + radius * 0.5
  head.castShadow = true
  group.add(head)

  return group
}

// ─── Scatter procédural ──────────────────────────────────────────────────────

export function buildScatterObject(kind: ScatterKind, rand: Prng, tokens: ThemeTokens): THREE.Object3D {
  const group = new THREE.Group()
  const wood = new THREE.MeshStandardMaterial({ color: color('#4a3826'), roughness: 0.95 })

  const addCastShadow = (mesh: THREE.Mesh) => {
    mesh.castShadow = true
    group.add(mesh)
    return mesh
  }

  switch (kind) {
    case 'tree_pine': {
      const height = range(rand, 1.1, 1.9)
      const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.09, height * 0.3, 7), wood)
      trunk.position.y = height * 0.15
      group.add(trunk)
      const green = pick(rand, ['#2e4a32', '#27412c', '#35543a'])
      for (let i = 0; i < 2; i++) {
        const cone = new THREE.Mesh(
          new THREE.ConeGeometry(0.42 - i * 0.13, height * 0.55, 8),
          new THREE.MeshStandardMaterial({ color: color(green), roughness: 0.95 }),
        )
        cone.position.y = height * (0.42 + i * 0.3)
        addCastShadow(cone)
      }
      break
    }
    case 'tree_dark': {
      const height = range(rand, 1.6, 2.3)
      const cone = new THREE.Mesh(
        new THREE.ConeGeometry(0.3, height, 7),
        new THREE.MeshStandardMaterial({ color: color('#243024'), roughness: 0.98 }),
      )
      cone.position.y = height / 2
      addCastShadow(cone)
      break
    }
    case 'tree_palm': {
      const height = range(rand, 1.2, 1.8)
      const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.09, height, 7), wood)
      trunk.position.y = height / 2
      trunk.rotation.z = range(rand, -0.12, 0.12)
      group.add(trunk)
      const crown = new THREE.Mesh(
        new THREE.SphereGeometry(0.36, 8, 6),
        new THREE.MeshStandardMaterial({ color: color('#3a5a3a'), roughness: 0.95 }),
      )
      crown.scale.y = 0.45
      crown.position.y = height + 0.05
      addCastShadow(crown)
      break
    }
    case 'bush': {
      const bush = new THREE.Mesh(
        new THREE.SphereGeometry(range(rand, 0.22, 0.4), 9, 7),
        new THREE.MeshStandardMaterial({ color: color(pick(rand, ['#2c422e', '#324a30'])), roughness: 0.98 }),
      )
      bush.scale.y = 0.72
      bush.position.y = 0.16
      addCastShadow(bush)
      break
    }
    case 'grass': {
      const green = new THREE.MeshStandardMaterial({ color: color('#3e4e2c'), roughness: 1 })
      for (let i = 0; i < 3; i++) {
        const blade = new THREE.Mesh(new THREE.ConeGeometry(0.035, range(rand, 0.18, 0.34), 5), green)
        blade.position.set(range(rand, -0.12, 0.12), 0.12, range(rand, -0.12, 0.12))
        group.add(blade)
      }
      break
    }
    case 'flower': {
      const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.22, 5),
        new THREE.MeshStandardMaterial({ color: color('#3e4e2c') }))
      stem.position.y = 0.11
      group.add(stem)
      const bloom = new THREE.Mesh(
        new THREE.SphereGeometry(0.05, 8, 6),
        new THREE.MeshStandardMaterial({
          color: color(pick(rand, [tokens.arcane, tokens.gold, tokens.blood])),
          emissiveIntensity: 0.2,
          roughness: 0.7,
        }),
      )
      bloom.position.y = 0.24
      group.add(bloom)
      break
    }
    case 'mushroom': {
      const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.05, 0.12, 7),
        new THREE.MeshStandardMaterial({ color: color('#d8cdb4'), roughness: 0.9 }))
      stem.position.y = 0.06
      group.add(stem)
      const cap = new THREE.Mesh(
        new THREE.SphereGeometry(0.1, 9, 7, 0, Math.PI * 2, 0, Math.PI / 2),
        new THREE.MeshStandardMaterial({ color: color(pick(rand, ['#a04030', '#b08a52'])), roughness: 0.85 }),
      )
      cap.position.y = 0.12
      addCastShadow(cap)
      break
    }
    case 'rock':
    case 'stone': {
      const rock = new THREE.Mesh(
        new THREE.IcosahedronGeometry(range(rand, 0.16, 0.34), 0),
        new THREE.MeshStandardMaterial({ color: color(pick(rand, ['#4e4a52', '#5a544e', '#46424a'])), roughness: 1, flatShading: true }),
      )
      rock.scale.set(1, range(rand, 0.55, 0.85), 1)
      rock.position.y = 0.12
      addCastShadow(rock)
      break
    }
    case 'stump': {
      const stump = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.2, 0.22, 9), wood)
      stump.position.y = 0.11
      addCastShadow(stump)
      break
    }
    case 'log': {
      const log = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.11, range(rand, 0.6, 0.9), 8), wood)
      log.rotation.z = Math.PI / 2
      log.rotation.y = range(rand, 0, Math.PI)
      log.position.y = 0.1
      addCastShadow(log)
      break
    }
    case 'cactus': {
      const green = new THREE.MeshStandardMaterial({ color: color('#3c5a36'), roughness: 0.9 })
      const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.11, range(rand, 0.5, 0.9), 8), green)
      trunk.position.y = 0.35
      addCastShadow(trunk)
      const arm = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.06, 0.25, 7), green)
      arm.position.set(0.14, 0.42, 0)
      arm.rotation.z = -0.5
      group.add(arm)
      break
    }
    case 'lily': {
      const pad = new THREE.Mesh(
        new THREE.CylinderGeometry(0.16, 0.16, 0.015, 10),
        new THREE.MeshStandardMaterial({ color: color('#2f5440'), roughness: 0.9 }),
      )
      pad.position.y = 0.02
      group.add(pad)
      break
    }
    case 'crate': {
      const crate = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.34, 0.34), wood)
      crate.rotation.y = range(rand, 0, Math.PI / 2)
      crate.position.y = 0.17
      addCastShadow(crate)
      break
    }
    case 'torch': {
      const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.05, 0.9, 7), wood)
      pole.position.y = 0.45
      group.add(pole)
      const flame = new THREE.Mesh(
        new THREE.SphereGeometry(0.09, 10, 8),
        new THREE.MeshStandardMaterial({ color: color(tokens.ember), emissive: color(tokens.ember), emissiveIntensity: 1.8 }),
      )
      flame.position.y = 0.96
      group.add(flame)
      break
    }
  }
  return group
}
