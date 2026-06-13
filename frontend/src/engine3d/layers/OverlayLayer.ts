// Surcouches tactiques : tuiles atteignables (InstancedMesh), ghost de
// destination pulsant, chemin de déplacement prévisualisé (opacité dégressive),
// zones (tuiles + icône), obstacles (rochers procéduraux).

import * as THREE from 'three'
import type { OverlaySpec } from '../types'
import type { EngineCtx } from '../core/context'
import { buildScatterObject } from '../assets/ProceduralFactory'
import { disposeGroup, disposeObject } from './GroundLayer'
import { loadIconTexture } from '../utils/iconTexture'
import { cellCenterToWorld } from '../utils/gridMath'
import { makePrng } from '../utils/seededRandom'

export class OverlayLayer {
  readonly group = new THREE.Group()
  private reachableMesh: THREE.InstancedMesh | null = null
  private reachableKey = ''
  private destinationRing: THREE.Mesh | null = null
  private destinationKey = ''
  private pathGroup = new THREE.Group()
  private pathKey = ''
  private aoeGroup = new THREE.Group()
  private aoeKey = ''
  private aoeRing: THREE.Mesh | null = null
  private zonesGroup = new THREE.Group()
  private zonesKey = ''
  private obstaclesGroup = new THREE.Group()
  private obstaclesKey = ''
  private time = 0

  constructor() {
    this.group.add(this.zonesGroup)
    this.group.add(this.obstaclesGroup)
    this.group.add(this.pathGroup)
    this.group.add(this.aoeGroup)
  }

  update(spec: OverlaySpec, ctx: EngineCtx): void {
    this.syncReachable(spec, ctx)
    this.syncDestination(spec, ctx)
    this.syncPath(spec, ctx)
    this.syncAoe(spec, ctx)
    this.syncZones(spec, ctx)
    this.syncObstacles(spec, ctx)
  }

  tick(dt: number): void {
    this.time += dt
    if (this.destinationRing) {
      const pulse = 1 + Math.sin(this.time * 4) * 0.08
      this.destinationRing.scale.setScalar(pulse)
      ;(this.destinationRing.material as THREE.MeshBasicMaterial).opacity =
        0.55 + Math.sin(this.time * 4) * 0.2
    }
    if (this.aoeRing) {
      const pulse = 1 + Math.sin(this.time * 4) * 0.05
      this.aoeRing.scale.setScalar(pulse)
    }
  }

  dispose(): void {
    disposeGroup(this.group)
    this.group.clear()
    this.group.add(this.zonesGroup = new THREE.Group())
    this.group.add(this.obstaclesGroup = new THREE.Group())
    this.group.add(this.pathGroup = new THREE.Group())
    this.group.add(this.aoeGroup = new THREE.Group())
    this.reachableMesh = null
    this.destinationRing = null
    this.aoeRing = null
    this.reachableKey = ''
    this.destinationKey = ''
    this.pathKey = ''
    this.aoeKey = ''
    this.zonesKey = ''
    this.obstaclesKey = ''
  }

  private syncReachable(spec: OverlaySpec, ctx: EngineCtx): void {
    const key = `${spec.reachableEmphasis}|${spec.reachable.map((c) => `${c.col},${c.row}`).join(';')}`
    if (key === this.reachableKey) return
    this.reachableKey = key

    if (this.reachableMesh) {
      this.group.remove(this.reachableMesh)
      disposeObject(this.reachableMesh)
      this.reachableMesh = null
    }
    if (spec.reachable.length === 0) return

    const isMove = spec.reachableEmphasis === 'move'
    const mesh = new THREE.InstancedMesh(
      new THREE.PlaneGeometry(0.86, 0.86),
      new THREE.MeshBasicMaterial({
        color: new THREE.Color(isMove ? ctx.tokens.green : ctx.tokens.gold),
        transparent: true,
        opacity: isMove ? 0.24 : 0.12,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
      spec.reachable.length,
    )
    const matrix = new THREE.Matrix4()
    const rotation = new THREE.Quaternion().setFromEuler(new THREE.Euler(-Math.PI / 2, 0, 0))
    spec.reachable.forEach((cell, index) => {
      const world = cellCenterToWorld(cell.col, cell.row, ctx.dims)
      const y = ctx.elevationAt(cell.col, cell.row) + 0.02
      matrix.compose(new THREE.Vector3(world.x, y, world.z), rotation, new THREE.Vector3(1, 1, 1))
      mesh.setMatrixAt(index, matrix)
    })
    mesh.instanceMatrix.needsUpdate = true
    this.group.add(mesh)
    this.reachableMesh = mesh
  }

  /** Chemin prévisualisé : tuiles teal, opacité dégressive départ→arrivée.
   *  La dernière cellule est exclue — le ring destination la marque déjà. */
  private syncPath(spec: OverlaySpec, ctx: EngineCtx): void {
    const key = spec.path.map((c) => `${c.col},${c.row}`).join(';')
    if (key === this.pathKey) return
    this.pathKey = key
    disposeGroup(this.pathGroup)

    const cells = spec.path.slice(0, -1)
    if (cells.length === 0) return

    const rotation = new THREE.Quaternion().setFromEuler(new THREE.Euler(-Math.PI / 2, 0, 0))
    cells.forEach((cell, index) => {
      const tile = new THREE.Mesh(
        new THREE.PlaneGeometry(0.5, 0.5),
        new THREE.MeshBasicMaterial({
          color: new THREE.Color(ctx.tokens.teal),
          transparent: true,
          opacity: 0.18 + (0.22 * index) / Math.max(1, cells.length - 1),
          depthWrite: false,
          side: THREE.DoubleSide,
        }),
      )
      tile.quaternion.copy(rotation)
      const world = cellCenterToWorld(cell.col, cell.row, ctx.dims)
      tile.position.set(world.x, ctx.elevationAt(cell.col, cell.row) + 0.025, world.z)
      this.pathGroup.add(tile)
    })
  }

  /** Gabarit AoE : tuiles arcane (muted si hors portée) + anneau central pulsant. */
  private syncAoe(spec: OverlaySpec, ctx: EngineCtx): void {
    const aoe = spec.aoe
    const key = aoe
      ? `${aoe.valid}|${aoe.center.col},${aoe.center.row}|${aoe.cells.map((c) => `${c.col},${c.row}`).join(';')}`
      : ''
    if (key === this.aoeKey) return
    this.aoeKey = key
    disposeGroup(this.aoeGroup)
    this.aoeRing = null
    if (!aoe || aoe.cells.length === 0) return

    const color = new THREE.Color(aoe.valid ? ctx.tokens.arcane : ctx.tokens.dim)
    const rotation = new THREE.Quaternion().setFromEuler(new THREE.Euler(-Math.PI / 2, 0, 0))
    const tiles = new THREE.InstancedMesh(
      new THREE.PlaneGeometry(0.86, 0.86),
      new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: aoe.valid ? 0.2 : 0.1,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
      aoe.cells.length,
    )
    const matrix = new THREE.Matrix4()
    aoe.cells.forEach((cell, index) => {
      const world = cellCenterToWorld(cell.col, cell.row, ctx.dims)
      const y = ctx.elevationAt(cell.col, cell.row) + 0.028
      matrix.compose(new THREE.Vector3(world.x, y, world.z), rotation, new THREE.Vector3(1, 1, 1))
      tiles.setMatrixAt(index, matrix)
    })
    tiles.instanceMatrix.needsUpdate = true
    this.aoeGroup.add(tiles)

    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.32, 0.42, 32),
      new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: aoe.valid ? 0.85 : 0.4,
        side: THREE.DoubleSide,
        depthWrite: false,
      }),
    )
    ring.rotation.x = -Math.PI / 2
    const world = cellCenterToWorld(aoe.center.col, aoe.center.row, ctx.dims)
    ring.position.set(world.x, ctx.elevationAt(aoe.center.col, aoe.center.row) + 0.032, world.z)
    this.aoeGroup.add(ring)
    this.aoeRing = ring
  }

  private syncDestination(spec: OverlaySpec, ctx: EngineCtx): void {
    const key = spec.destination ? `${spec.destination.col},${spec.destination.row}` : ''
    if (key === this.destinationKey) return
    this.destinationKey = key

    if (this.destinationRing) {
      this.group.remove(this.destinationRing)
      disposeObject(this.destinationRing)
      this.destinationRing = null
    }
    if (!spec.destination) return

    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.3, 0.4, 32),
      new THREE.MeshBasicMaterial({
        color: new THREE.Color(ctx.tokens.teal),
        transparent: true,
        opacity: 0.7,
        side: THREE.DoubleSide,
        depthWrite: false,
      }),
    )
    ring.rotation.x = -Math.PI / 2
    const world = cellCenterToWorld(spec.destination.col, spec.destination.row, ctx.dims)
    ring.position.set(world.x, ctx.elevationAt(spec.destination.col, spec.destination.row) + 0.03, world.z)
    this.group.add(ring)
    this.destinationRing = ring
  }

  private syncZones(spec: OverlaySpec, ctx: EngineCtx): void {
    const key = JSON.stringify(spec.zones)
    if (key === this.zonesKey) return
    this.zonesKey = key
    disposeGroup(this.zonesGroup)

    for (const zone of spec.zones) {
      if (zone.cells.length === 0) continue
      const tiles = new THREE.InstancedMesh(
        new THREE.PlaneGeometry(0.92, 0.92),
        new THREE.MeshBasicMaterial({
          color: new THREE.Color(ctx.tokens.gold),
          transparent: true,
          opacity: 0.11,
          depthWrite: false,
          side: THREE.DoubleSide,
        }),
        zone.cells.length,
      )
      const matrix = new THREE.Matrix4()
      const rotation = new THREE.Quaternion().setFromEuler(new THREE.Euler(-Math.PI / 2, 0, 0))
      let centroidX = 0
      let centroidZ = 0
      zone.cells.forEach((cell, index) => {
        const world = cellCenterToWorld(cell.col, cell.row, ctx.dims)
        centroidX += world.x
        centroidZ += world.z
        matrix.compose(new THREE.Vector3(world.x, 0.015, world.z), rotation, new THREE.Vector3(1, 1, 1))
        tiles.setMatrixAt(index, matrix)
      })
      tiles.instanceMatrix.needsUpdate = true
      this.zonesGroup.add(tiles)

      const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ transparent: true, depthWrite: false }))
      sprite.scale.set(0.5, 0.5, 1)
      sprite.position.set(centroidX / zone.cells.length, 0.55, centroidZ / zone.cells.length)
      this.zonesGroup.add(sprite)
      void loadIconTexture(zone.icon ?? 'c-aoe').then((texture) => {
        if (!texture || !sprite.parent) return
        const material = sprite.material as THREE.SpriteMaterial
        material.map = texture
        material.needsUpdate = true
      })
    }
  }

  private syncObstacles(spec: OverlaySpec, ctx: EngineCtx): void {
    const key = spec.obstacles.map((c) => `${c.col},${c.row}`).join(';')
    if (key === this.obstaclesKey) return
    this.obstaclesKey = key
    disposeGroup(this.obstaclesGroup)

    for (const cell of spec.obstacles) {
      const rand = makePrng(`obstacle|${cell.col},${cell.row}`)
      const cluster = new THREE.Group()
      const world = cellCenterToWorld(cell.col, cell.row, ctx.dims)
      cluster.position.set(world.x, 0, world.z)
      cluster.add(buildScatterObject('rock', rand, ctx.tokens))
      const second = buildScatterObject('stone', rand, ctx.tokens)
      second.position.set(0.2, 0, -0.18)
      cluster.add(second)
      cluster.userData.pick = { type: 'cell', col: cell.col, row: cell.row }
      this.obstaclesGroup.add(cluster)
    }
  }
}
