// Éléments de scène (murs, portes, mobilier, terrain…) : procédural immédiat,
// remplacé par le modèle glTF correspondant quand il existe et se charge.
// Anneau de sélection doré sous l'élément sélectionné (pas de rebuild au clic).

import * as THREE from 'three'
import type { ElementSpec } from '../types'
import type { LoadedModel } from '../assets/AssetRegistry'
import type { EngineCtx } from '../core/context'
import { buildProceduralElement } from '../assets/ProceduralFactory'
import { modelForElement, PROP_TARGET_HEIGHT_M } from '../assets/manifest'
import { disposeGroup, disposeObject } from './GroundLayer'
import { gridPointToWorld, metersToWorld } from '../utils/gridMath'

const MAX_POINT_LIGHTS = 6
const WALL_SEGMENT_OVERLAP = 0.025
const ACCESS_THICKNESS_WORLD = 0.3
const WALL_ACCESS_KINDS = new Set(['door', 'window', 'stairs'])

interface ElementEntry {
  container: THREE.Group
  spec: ElementSpec
  generation: number
}

export class ElementsLayer {
  readonly group = new THREE.Group()
  private entries = new Map<string, ElementEntry>()
  private buildKey = ''
  private generation = 0
  private selectionRing: THREE.Mesh | null = null

  update(specs: ElementSpec[], selectedId: string | null, ctx: EngineCtx): void {
    const key = JSON.stringify(specs.map((spec) => ({ ...spec, selected: undefined })))
    if (key !== this.buildKey) {
      this.rebuild(specs, ctx)
      this.buildKey = key
    }
    this.applySelection(selectedId, ctx)
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
      this.entries.set(spec.id, { container, spec, generation })

      // Torches/lanternes : vraie lumière en ambiance torchlit/night.
      if (spec.kind === 'light' && ctx.ambiance.pointLights && pointLights < MAX_POINT_LIGHTS) {
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
    group.rotation.y = placement.rotationY
    return group
  }
  if (modelKey === 'prop/door') {
    const instance = instantiateWallAccessModel(model, spec, placement, ctx)
    instance.position.set(placement.center.x, elevation, placement.center.z)
    instance.rotation.y = placement.rotationY
    return instance
  }
  if (modelKey === 'prop/stairs') {
    const instance = instantiateStairsModel(model, placement)
    instance.position.set(placement.center.x, elevation, placement.center.z)
    instance.rotation.y = placement.rotationY
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
  instance.rotation.y = placement.rotationY
  return instance
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

function instantiateStairsModel(model: LoadedModel, placement: ElementPlacement): THREE.Group {
  const scaleX = placement.footprint.x / model.size.x
  const scaleZ = placement.footprint.z / model.size.z
  const scaleY = Math.min(scaleX, scaleZ)
  return instantiateModelNonUniform(model, {
    x: scaleX,
    y: scaleY,
    z: scaleZ,
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
  if (spec.kind === 'stairs') return stairsRotationY(spec.facing, spec.verticalDirection, footprint)
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

export function stairsRotationY(
  facing: ElementSpec['facing'],
  verticalDirection: ElementSpec['verticalDirection'],
  footprint: { x: number; z: number },
): number {
  if (!facing) return footprint.z > footprint.x ? -Math.PI / 2 : 0
  const visualFacing = verticalDirection === 'down' ? oppositeFacing(facing) : facing
  return plusZRotationToFacing(visualFacing)
}

function plusZRotationToFacing(facing: NonNullable<ElementSpec['facing']>): number {
  switch (facing) {
    case 'north':
      return Math.PI
    case 'east':
      return Math.PI / 2
    case 'west':
      return -Math.PI / 2
    case 'south':
    default:
      return 0
  }
}

function oppositeFacing(
  facing: NonNullable<ElementSpec['facing']>,
): NonNullable<ElementSpec['facing']> {
  switch (facing) {
    case 'north':
      return 'south'
    case 'south':
      return 'north'
    case 'east':
      return 'west'
    case 'west':
      return 'east'
  }
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
