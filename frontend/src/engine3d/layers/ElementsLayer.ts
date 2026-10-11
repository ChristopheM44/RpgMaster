// Éléments de scène (murs, portes, mobilier, terrain…) : procédural immédiat,
// remplacé par le modèle glTF correspondant quand il existe et se charge.
// Anneau de sélection doré sous l'élément sélectionné (pas de rebuild au clic).

import * as THREE from 'three'
import type { ElementSpec } from '../types'
import type { LoadedModel } from '../assets/AssetRegistry'
import type { EngineCtx } from '../core/context'
import { buildProceduralElement } from '../assets/ProceduralFactory'
import { modelForElement, MODEL_MANIFEST, PROP_TARGET_HEIGHT_M } from '../assets/manifest'
import { disposeGroup, disposeObject } from './GroundLayer'
import { gridPointToWorld, metersToWorld } from '../utils/gridMath'

const MAX_POINT_LIGHTS = 6
const WALL_SEGMENT_OVERLAP = 0.025
const ACCESS_THICKNESS_WORLD = 0.3
const WALL_ACCESS_KINDS = new Set(['door', 'window'])

/** Hauteur résiduelle (fraction) d'un mur abaissé en coupe. */
const CUTAWAY_SCALE = 0.14
/** Seuil cos(angle) normale/caméra au-delà duquel un mur de bord est coupé. */
const CUTAWAY_FACING = 0.3
const CUTAWAY_KINDS = new Set(['wall', 'door', 'window'])

interface ElementEntry {
  container: THREE.Group
  spec: ElementSpec
  /** Normale sortante (monde XZ) d'un élément de bord coupable ; null sinon. */
  cutaway: { x: number; z: number; hide: boolean } | null
  /** Facteur de hauteur courant (1 = plein, CUTAWAY_SCALE = coupé). */
  cutK: number
  /** Bords de décalque de danger animés. */
  spinners: THREE.Object3D[]
  generation: number
}

export class ElementsLayer {
  readonly group = new THREE.Group()
  private entries = new Map<string, ElementEntry>()
  private buildKey = ''
  private generation = 0
  private selectionRing: THREE.Mesh | null = null
  private time = 0

  update(specs: ElementSpec[], selectedId: string | null, ctx: EngineCtx): void {
    const key = JSON.stringify(specs.map((spec) => ({ ...spec, selected: undefined })))
    if (key !== this.buildKey) {
      this.rebuild(specs, ctx)
      this.buildKey = key
    }
    this.applySelection(selectedId, ctx)
  }

  /**
   * Murs en coupe : les murs/portes/fenêtres de BORD tournés vers la caméra
   * s'abaissent (les torches murales s'éteignent visuellement) pour qu'on voie
   * toujours l'intérieur ; ils remontent quand la caméra tourne.
   */
  tick(dt: number, camera: THREE.Vector3, target: THREE.Vector3): void {
    let dx = camera.x - target.x
    let dz = camera.z - target.z
    const length = Math.hypot(dx, dz) || 1
    dx /= length
    dz /= length
    const blend = Math.min(1, dt * 7)
    this.time += dt
    for (const entry of this.entries.values()) {
      for (const spinner of entry.spinners) spinner.rotation.z = this.time * 0.25
      const cut = entry.cutaway
      if (!cut) continue
      const goal = cut.x * dx + cut.z * dz > CUTAWAY_FACING ? CUTAWAY_SCALE : 1
      if (Math.abs(entry.cutK - goal) < 0.002) continue
      entry.cutK += (goal - entry.cutK) * blend
      if (cut.hide) entry.container.visible = entry.cutK > 0.6
      else entry.container.scale.y = entry.cutK
    }
  }

  pickables(): THREE.Object3D[] {
    const result: THREE.Object3D[] = []
    for (const entry of this.entries.values()) {
      if (entry.container.userData.pick) result.push(entry.container)
    }
    return result
  }

  dispose(): void {
    this.generation += 1
    disposeGroup(this.group)
    this.entries.clear()
    this.selectionRing = null
    this.buildKey = ''
  }

  private rebuild(specs: ElementSpec[], ctx: EngineCtx): void {
    this.dispose()
    this.buildKey = ''
    this.generation += 1
    const generation = this.generation
    let pointLights = 0

    for (const spec of specs) {
      const container = new THREE.Group()
      const procedural = buildProceduralElement(spec, {
        dims: ctx.dims,
        cellSizeM: ctx.cellSizeM,
        tokens: ctx.tokens,
      })
      container.add(procedural)
      if (spec.inspectable) {
        container.userData.pick = { type: 'element', id: spec.id }
      }
      this.group.add(container)
      const spinners: THREE.Object3D[] = []
      procedural.traverse((node) => {
        if (node.userData.hazardRing) spinners.push(node)
      })
      this.entries.set(spec.id, { container, spec, generation, cutaway: cutawayNormal(spec, ctx.dims), cutK: 1, spinners })

      // Torches/lanternes : vraie lumière en ambiance torchlit/night.
      if (spec.kind === 'light' && (ctx.ambiance.pointLights || ctx.biome.enclosed) && pointLights < MAX_POINT_LIGHTS) {
        const light = new THREE.PointLight(
          new THREE.Color(ctx.tokens.ember),
          5.5,
          metersToWorld(9, ctx.cellSizeM),
          1.6,
        )
        const center = elementCenterWorld(spec, ctx)
        light.position.set(center.x, metersToWorld(spec.heightM, ctx.cellSizeM) + 0.15, center.z)
        this.group.add(light)
        pointLights += 1
      }

      this.tryModelSwap(spec, container, procedural, generation, ctx)
    }
  }

  /** Tente le remplacement procédural → modèle (hint explicite puis heuristique). */
  private tryModelSwap(
    spec: ElementSpec,
    container: THREE.Group,
    procedural: THREE.Object3D,
    generation: number,
    ctx: EngineCtx,
  ): void {
    // Escaliers : toujours procéduraux — le sens (montée vers un mur, trémie
    // creusée dans le sol) dépend de facing/verticalDirection, ce qu'un modèle
    // unique (stairs.glb, toujours montant) ne sait pas rendre.
    if (spec.kind === 'stairs') return
    const placement = elementPlacementWorld(spec, ctx)
    const modelKey = spec.modelKey ?? modelForElement(spec.kind, spec.name, placement.footprint)
    if (!modelKey) return

    void ctx.registry.load(modelKey).then((model) => {
      if (!model || generation !== this.generation || !this.entries.has(spec.id)) return
      const instance = instantiateElementModel(model, modelKey, spec, placement, ctx)
      if (spec.subtle) applySubtle(instance)
      container.remove(procedural)
      disposeObject(procedural)
      container.add(instance)
    })
  }

  private applySelection(selectedId: string | null, ctx: EngineCtx): void {
    if (this.selectionRing) {
      this.group.remove(this.selectionRing)
      disposeObject(this.selectionRing)
      this.selectionRing = null
    }
    if (!selectedId) return
    const entry = this.entries.get(selectedId)
    if (!entry) return

    const footprint = elementFootprintWorld(entry.spec)
    const radius = Math.max(footprint.x, footprint.z) / 2 + 0.18
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(radius, radius + 0.1, 40),
      new THREE.MeshBasicMaterial({
        color: new THREE.Color(ctx.tokens.gold),
        transparent: true,
        opacity: 0.85,
        side: THREE.DoubleSide,
      }),
    )
    ring.rotation.x = -Math.PI / 2
    const center = elementCenterWorld(entry.spec, ctx)
    ring.position.set(center.x, 0.025, center.z)
    this.group.add(ring)
    this.selectionRing = ring
  }
}

/**
 * Normale sortante d'un élément situé sur le pourtour du plateau (≤ 1,2 case du
 * bord) : murs, portes, fenêtres (abaissés) et torches murales (masquées).
 * Les éléments intérieurs ne sont jamais coupés. Pur : testé sans WebGL.
 */
export function cutawayNormal(
  spec: Pick<ElementSpec, 'kind' | 'geometry'>,
  dims: { cols: number; rows: number },
): { x: number; z: number; hide: boolean } | null {
  const hide = spec.kind === 'light'
  if (!CUTAWAY_KINDS.has(spec.kind) && !hide) return null
  const geometry = spec.geometry
  let cx: number
  let cz: number
  if (geometry.type === 'line') {
    cx = (geometry.from.col + geometry.to.col) / 2
    cz = (geometry.from.row + geometry.to.row) / 2
  } else if (geometry.type === 'rect') {
    cx = geometry.col + geometry.width / 2
    cz = geometry.row + geometry.height / 2
  } else {
    return null // enceinte ellipse : déjà rendue creuse (BackSide)
  }
  const reach = hide ? 0.6 : 1.2
  const near = {
    west: cx <= reach,
    east: cx >= dims.cols - reach,
    north: cz <= reach,
    south: cz >= dims.rows - reach,
  }
  // Un mur en ligne longe UN bord : on ignore les bords perpendiculaires à son tracé.
  if (geometry.type === 'line') {
    const alongX = Math.abs(geometry.to.col - geometry.from.col) >= Math.abs(geometry.to.row - geometry.from.row)
    if (alongX) near.west = near.east = false
    else near.north = near.south = false
  }
  const x = (near.east ? 1 : 0) - (near.west ? 1 : 0)
  const z = (near.south ? 1 : 0) - (near.north ? 1 : 0)
  if (x === 0 && z === 0) return null
  const length = Math.hypot(x, z)
  return { x: x / length, z: z / length, hide }
}

function elementFootprintWorld(spec: ElementSpec): { x: number; z: number } {
  const geometry = spec.geometry
  if (geometry.type === 'rect') return { x: Math.max(0.3, geometry.width), z: Math.max(0.3, geometry.height) }
  if (geometry.type === 'ellipse') {
    return { x: Math.max(0.3, geometry.radius_col * 2), z: Math.max(0.3, geometry.radius_row * 2) }
  }
  const length = Math.hypot(geometry.to.col - geometry.from.col, geometry.to.row - geometry.from.row)
  return { x: Math.max(0.3, length), z: 0.2 }
}

export interface ElementPlacement {
  center: { x: number; z: number }
  footprint: { x: number; z: number }
  rotationY: number
}

export function elementPlacementWorld(spec: ElementSpec, ctx: EngineCtx): ElementPlacement {
  const geometry = spec.geometry
  if (geometry.type === 'line') {
    const a = gridPointToWorld(geometry.from.col, geometry.from.row, ctx.dims)
    const b = gridPointToWorld(geometry.to.col, geometry.to.row, ctx.dims)
    return {
      center: { x: (a.x + b.x) / 2, z: (a.z + b.z) / 2 },
      footprint: elementFootprintWorld(spec),
      rotationY: -Math.atan2(b.z - a.z, b.x - a.x),
    }
  }
  const footprint = elementFootprintWorld(spec)
  return {
    center: rectElementCenterWorld(spec, ctx),
    footprint,
    rotationY: rectElementRotationY(spec, footprint),
  }
}

export function instantiateElementModel(
  model: LoadedModel,
  modelKey: string,
  spec: ElementSpec,
  placement: ElementPlacement,
  ctx: EngineCtx,
): THREE.Group {
  const elevation = metersToWorld(spec.elevationM, ctx.cellSizeM)
  if (modelKey === 'prop/wall' && spec.geometry.type === 'line') {
    const group = new THREE.Group()
    const count = Math.max(1, Math.ceil(placement.footprint.x))
    const segmentX = Math.max(0.3, placement.footprint.x / count)
    const targetHeight = metersToWorld(Math.max(spec.heightM, 0.4), ctx.cellSizeM)
    const targetThickness = Math.max(
      0.18,
      Math.min(ACCESS_THICKNESS_WORLD, placement.footprint.z),
    )
    for (let i = 0; i < count; i += 1) {
      const visualLength = segmentX + (count > 1 ? WALL_SEGMENT_OVERLAP : 0)
      const segment = instantiateModelNonUniform(model, {
        x: visualLength / model.size.x,
        y: targetHeight / model.size.y,
        z: targetThickness / model.size.z,
      })
      segment.position.x = -placement.footprint.x / 2 + segmentX * (i + 0.5)
      group.add(segment)
    }
    group.position.set(placement.center.x, elevation, placement.center.z)
    group.rotation.y = placement.rotationY + rotationOffsetFor(modelKey)
    return group
  }
  if (modelKey === 'prop/door') {
    const instance = instantiateWallAccessModel(model, spec, placement, ctx)
    instance.position.set(placement.center.x, elevation, placement.center.z)
    instance.rotation.y = placement.rotationY + rotationOffsetFor(modelKey)
    return instance
  }
  if (modelKey === 'prop/wall_corner') {
    const instance = instantiateWallCornerModel(model, spec, placement, ctx)
    instance.position.set(placement.center.x, elevation, placement.center.z)
    instance.rotation.y = cornerRotationY(spec, ctx)
    return instance
  }

  const intrinsicHeightM = PROP_TARGET_HEIGHT_M[modelKey]
  const instance = ctx.registry.instantiate(
    model,
    intrinsicHeightM != null
      ? { targetHeight: metersToWorld(intrinsicHeightM, ctx.cellSizeM) }
      : {
          footprint: placement.footprint,
          maxHeight: metersToWorld(Math.max(spec.heightM, 0.4) * 1.6, ctx.cellSizeM),
        },
  )
  instance.position.set(placement.center.x, elevation, placement.center.z)
  instance.rotation.y = placement.rotationY + rotationOffsetFor(modelKey)
  return instance
}

/** Offset de rotation déclaré dans le manifeste pour corriger un axe avant de modèle non conforme. */
function rotationOffsetFor(modelKey: string): number {
  return MODEL_MANIFEST[modelKey]?.rotationOffsetY ?? 0
}

function instantiateWallAccessModel(
  model: LoadedModel,
  spec: ElementSpec,
  placement: ElementPlacement,
  ctx: EngineCtx,
): THREE.Group {
  const targetHeight = metersToWorld(Math.max(spec.heightM, 0.4), ctx.cellSizeM)
  const length = Math.max(0.6, Math.max(placement.footprint.x, placement.footprint.z))
  const thickness = Math.max(
    0.18,
    Math.min(ACCESS_THICKNESS_WORLD, Math.min(placement.footprint.x, placement.footprint.z)),
  )
  return instantiateModelNonUniform(model, {
    x: length / model.size.x,
    y: targetHeight / model.size.y,
    z: thickness / model.size.z,
  })
}

function instantiateWallCornerModel(
  model: LoadedModel,
  spec: ElementSpec,
  placement: ElementPlacement,
  ctx: EngineCtx,
): THREE.Group {
  const targetHeight = metersToWorld(Math.max(spec.heightM, 0.4), ctx.cellSizeM)
  return instantiateModelNonUniform(model, {
    x: placement.footprint.x / model.size.x,
    y: targetHeight / model.size.y,
    z: placement.footprint.z / model.size.z,
  })
}

function instantiateModelNonUniform(
  model: LoadedModel,
  scale: { x: number; y: number; z: number },
): THREE.Group {
  const instance = model.prototype.clone(true) as THREE.Group
  instance.scale.set(scale.x, scale.y, scale.z)
  instance.position.set(
    -model.center.x * scale.x,
    -model.minY * scale.y,
    -model.center.z * scale.z,
  )
  instance.traverse((node) => {
    const mesh = node as THREE.Mesh
    if (mesh.isMesh) {
      mesh.castShadow = true
      mesh.receiveShadow = true
    }
  })
  const container = new THREE.Group()
  container.add(instance)
  return container
}

function rectElementRotationY(spec: ElementSpec, footprint: { x: number; z: number }): number {
  if (spec.kind === 'door' || spec.kind === 'window') return wallAxisRotationY(spec.facing, footprint)
  return 0
}

export function wallAxisRotationY(
  facing: ElementSpec['facing'],
  footprint: { x: number; z: number },
): number {
  if (facing === 'east' || facing === 'west') return -Math.PI / 2
  if (facing === 'north' || facing === 'south') return 0
  return footprint.z > footprint.x ? -Math.PI / 2 : 0
}

function cornerRotationY(spec: ElementSpec, ctx: EngineCtx): number {
  const geometry = spec.geometry
  if (geometry.type !== 'rect') return 0
  const nearWest = geometry.col <= 0.1
  const nearEast = geometry.col + geometry.width >= ctx.dims.cols - 0.1
  const nearNorth = geometry.row <= 0.1
  const nearSouth = geometry.row + geometry.height >= ctx.dims.rows - 0.1
  if (nearNorth && nearEast) return -Math.PI / 2
  if (nearSouth && nearEast) return Math.PI
  if (nearSouth && nearWest) return Math.PI / 2
  return 0
}

function elementCenterWorld(spec: ElementSpec, ctx: EngineCtx): { x: number; z: number } {
  const geometry = spec.geometry
  if (geometry.type === 'rect') {
    return gridPointToWorld(geometry.col + geometry.width / 2, geometry.row + geometry.height / 2, ctx.dims)
  }
  if (geometry.type === 'ellipse') return gridPointToWorld(geometry.col, geometry.row, ctx.dims)
  return gridPointToWorld(
    (geometry.from.col + geometry.to.col) / 2,
    (geometry.from.row + geometry.to.row) / 2,
    ctx.dims,
  )
}

function rectElementCenterWorld(spec: ElementSpec, ctx: EngineCtx): { x: number; z: number } {
  const center = elementCenterWorld(spec, ctx)
  const geometry = spec.geometry
  if (geometry.type !== 'rect' || !spec.facing || !WALL_ACCESS_KINDS.has(spec.kind)) {
    return center
  }

  if (spec.facing === 'north' && geometry.row <= 0.05) {
    center.z = gridPointToWorld(0, 0, ctx.dims).z
  } else if (spec.facing === 'south' && geometry.row + geometry.height >= ctx.dims.rows - 0.05) {
    center.z = gridPointToWorld(0, ctx.dims.rows, ctx.dims).z
  } else if (spec.facing === 'west' && geometry.col <= 0.05) {
    center.x = gridPointToWorld(0, 0, ctx.dims).x
  } else if (spec.facing === 'east' && geometry.col + geometry.width >= ctx.dims.cols - 0.05) {
    center.x = gridPointToWorld(ctx.dims.cols, 0, ctx.dims).x
  }

  return center
}

function applySubtle(root: THREE.Object3D): void {
  root.traverse((node) => {
    const mesh = node as THREE.Mesh
    if (!mesh.isMesh) return
    if (Array.isArray(mesh.material)) {
      mesh.material = mesh.material.map(cloneSubtleMaterial)
    } else if (mesh.material) {
      mesh.material = cloneSubtleMaterial(mesh.material)
    }
  })
}

function cloneSubtleMaterial(material: THREE.Material): THREE.Material {
  const cloned = material.clone() as THREE.MeshStandardMaterial
  cloned.transparent = true
  cloned.opacity = 0.42
  if (cloned.color) cloned.color.lerp(new THREE.Color('#55505a'), 0.55)
  return cloned
}
