// Picking : un seul Raycaster, hover throttlé à la frame, clic = pointerdown/up
// avec dérive < 6 px (l'orbite à la souris ne déclenche jamais de sélection).
// Les meshes pickables portent userData.pick (PickResult) — on remonte la
// hiérarchie depuis le mesh touché. Le sol renvoie une cellule si cellPicking.

import * as THREE from 'three'
import type { GridDims, PickResult, RuntimeCallbacks } from '../types'
import { worldToCell } from '../utils/gridMath'

export interface PickSources {
  pickables(): THREE.Object3D[]
  ground(): THREE.Object3D | null
  dims(): GridDims
  cellPicking(): boolean
}

const CLICK_MAX_DRIFT_PX = 6

export class PickingController {
  private raycaster = new THREE.Raycaster()
  private pointerNdc = new THREE.Vector2()
  private pendingHover: { x: number; y: number } | null = null
  private downAt: { x: number; y: number } | null = null
  private lastHoverKey: string | null = null
  private disposers: (() => void)[] = []

  constructor(
    private canvas: HTMLCanvasElement,
    private camera: THREE.Camera,
    private sources: PickSources,
    private callbacks: RuntimeCallbacks,
  ) {
    const onMove = (event: PointerEvent) => {
      this.pendingHover = this.localPoint(event)
    }
    const onDown = (event: PointerEvent) => {
      if (event.button === 0) this.downAt = this.localPoint(event)
    }
    const onUp = (event: PointerEvent) => {
      if (event.button !== 0 || !this.downAt) return
      const at = this.localPoint(event)
      const drift = Math.hypot(at.x - this.downAt.x, at.y - this.downAt.y)
      this.downAt = null
      if (drift > CLICK_MAX_DRIFT_PX) return
      const pick = this.raycast(at)
      if (pick) this.callbacks.onClick?.(pick, at)
    }
    const onLeave = () => {
      this.pendingHover = null
      this.emitHover(null, { x: 0, y: 0 })
    }
    canvas.addEventListener('pointermove', onMove)
    canvas.addEventListener('pointerdown', onDown)
    canvas.addEventListener('pointerup', onUp)
    canvas.addEventListener('pointerleave', onLeave)
    this.disposers.push(() => {
      canvas.removeEventListener('pointermove', onMove)
      canvas.removeEventListener('pointerdown', onDown)
      canvas.removeEventListener('pointerup', onUp)
      canvas.removeEventListener('pointerleave', onLeave)
    })
  }

  /** À appeler une fois par frame : traite le dernier pointermove reçu. */
  tick(): void {
    if (!this.pendingHover) return
    const at = this.pendingHover
    this.pendingHover = null
    this.emitHover(this.raycast(at), at)
  }

  dispose(): void {
    for (const dispose of this.disposers) dispose()
    this.disposers = []
  }

  private localPoint(event: PointerEvent): { x: number; y: number } {
    const rect = this.canvas.getBoundingClientRect()
    return { x: event.clientX - rect.left, y: event.clientY - rect.top }
  }

  private emitHover(pick: PickResult | null, screen: { x: number; y: number }): void {
    const key = pick === null
      ? null
      : pick.type === 'cell'
        ? `cell:${pick.col},${pick.row}`
        : `${pick.type}:${pick.id}`
    if (key === this.lastHoverKey && pick?.type !== 'cell') return
    this.lastHoverKey = key
    this.callbacks.onHover?.(pick, screen)
  }

  private raycast(at: { x: number; y: number }): PickResult | null {
    const rect = this.canvas.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return null
    this.pointerNdc.set((at.x / rect.width) * 2 - 1, -(at.y / rect.height) * 2 + 1)
    this.raycaster.setFromCamera(this.pointerNdc, this.camera)

    const hits = this.raycaster.intersectObjects(this.sources.pickables(), true)
    for (const hit of hits) {
      const pick = findPickData(hit.object)
      if (pick) return pick
    }

    if (this.sources.cellPicking()) {
      const ground = this.sources.ground()
      if (ground) {
        const groundHits = this.raycaster.intersectObject(ground, false)
        const point = groundHits[0]?.point
        if (point) {
          const cell = worldToCell(point.x, point.z, this.sources.dims())
          if (cell) return { type: 'cell', col: cell.col, row: cell.row }
        }
      }
    }
    return null
  }
}

function findPickData(object: THREE.Object3D | null): PickResult | null {
  let current = object
  while (current) {
    const pick = current.userData?.pick as PickResult | undefined
    if (pick) return pick
    current = current.parent
  }
  return null
}
