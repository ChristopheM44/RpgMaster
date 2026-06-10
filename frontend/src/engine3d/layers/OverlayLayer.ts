// Surcouches tactiques : tuiles atteignables (InstancedMesh), ghost de
// destination pulsant, zones (tuiles + icône), obstacles (rochers procéduraux).
// API réservée pour plus tard : showPath / showAoe.

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
  private zonesGroup = new THREE.Group()
  private zonesKey = ''
  private obstaclesGroup = new THREE.Group()
  private obstaclesKey = ''
  private time = 0

  constructor() {
    this.group.add(this.zonesGroup)
    this.group.add(this.obstaclesGroup)
  }

  update(spec: OverlaySpec, ctx: EngineCtx): void {
    this.syncReachable(spec, ctx)
    this.syncDestination(spec, ctx)
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
  }

  dispose(): void {
    disposeGroup(this.group)
    this.group.clear()
    this.group.add(this.zonesGroup = new THREE.Group())
    this.group.add(this.obstaclesGroup = new THREE.Group())
    this.reachableMesh = null
    this.destinationRing = null
    this.reachableKey = ''
    this.destinationKey = ''
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
      matrix.compose(new THREE.Vector3(world.x, 0.02, world.z), rotation, new THREE.Vector3(1, 1, 1))
      mesh.setMatrixAt(index, matrix)
    })
    mesh.instanceMatrix.needsUpdate = true
    this.group.add(mesh)
    this.reachableMesh = mesh
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
    ring.position.set(world.x, 0.03, world.z)
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
