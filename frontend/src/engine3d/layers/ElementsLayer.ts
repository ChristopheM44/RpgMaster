// Éléments de scène (murs, portes, mobilier, terrain…) : procédural immédiat,
// remplacé par le modèle glTF correspondant quand il existe et se charge.
// Anneau de sélection doré sous l'élément sélectionné (pas de rebuild au clic).

import * as THREE from 'three'
import type { ElementSpec } from '../types'
import type { EngineCtx } from '../core/context'
import { buildProceduralElement } from '../assets/ProceduralFactory'
import { modelForElement } from '../assets/manifest'
import { disposeGroup, disposeObject } from './GroundLayer'
import { gridPointToWorld, metersToWorld } from '../utils/gridMath'

const MAX_POINT_LIGHTS = 6

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
          4.5,
          metersToWorld(7, ctx.cellSizeM),
          1.8,
        )
        const center = elementCenterWorld(spec, ctx)
        light.position.set(center.x, metersToWorld(spec.heightM, ctx.cellSizeM) + 0.15, center.z)
        this.group.add(light)
        pointLights += 1
      }

      this.tryModelSwap(spec, container, procedural, generation, ctx)
    }
  }

  /** Tente le remplacement procédural → modèle (rect/ellipse uniquement). */
  private tryModelSwap(
    spec: ElementSpec,
    container: THREE.Group,
    procedural: THREE.Object3D,
    generation: number,
    ctx: EngineCtx,
  ): void {
    if (spec.geometry.type === 'line') return
    const footprint = elementFootprintWorld(spec)
    const modelKey = modelForElement(spec.kind, spec.name, footprint)
    if (!modelKey) return

    void ctx.registry.load(modelKey).then((model) => {
      if (!model || generation !== this.generation || !this.entries.has(spec.id)) return
      const instance = ctx.registry.instantiate(model, {
        footprint,
        maxHeight: metersToWorld(Math.max(spec.heightM, 0.4) * 1.6, ctx.cellSizeM),
      })
      const center = elementCenterWorld(spec, ctx)
      instance.position.set(center.x, metersToWorld(spec.elevationM, ctx.cellSizeM), center.z)
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
