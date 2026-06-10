// Caméra perspective + OrbitControls contraints : vue isométrique-ish par
// défaut (sud-est, ~35° d'élévation), pan clampé à la grille, presets de zoom.

import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import type { GridDims, ZoomPreset } from '../types'
import { gridDiagonal } from '../utils/gridMath'

const POLAR_MIN = 0.35
const POLAR_MAX = 1.25
const DEFAULT_POLAR = 0.95
const DEFAULT_AZIMUTH = Math.PI / 4

const ZOOM_FACTORS: Record<ZoomPreset, number> = {
  wide: 1.55,
  normal: 1.05,
  close: 0.62,
}

export class CameraRig {
  readonly camera: THREE.PerspectiveCamera
  readonly controls: OrbitControls
  private dims: GridDims = { cols: 12, rows: 12 }

  constructor(canvas: HTMLCanvasElement) {
    this.camera = new THREE.PerspectiveCamera(45, 1, 0.05, 600)
    this.controls = new OrbitControls(this.camera, canvas)
    this.controls.enableDamping = true
    this.controls.dampingFactor = 0.08
    this.controls.minPolarAngle = POLAR_MIN
    this.controls.maxPolarAngle = POLAR_MAX
    this.controls.screenSpacePanning = false
    this.controls.addEventListener('change', () => this.clampTarget())
  }

  /** Cadre la grille : cible au centre, caméra au sud-est, distances bornées. */
  frameGrid(dims: GridDims, preset: ZoomPreset = 'normal'): void {
    this.dims = dims
    const diag = gridDiagonal(dims)
    this.controls.minDistance = diag * 0.4
    this.controls.maxDistance = diag * 2.2
    this.controls.target.set(0, 0, 0)
    this.placeAt(diag * ZOOM_FACTORS[preset], DEFAULT_POLAR, DEFAULT_AZIMUTH)
  }

  setZoomPreset(preset: ZoomPreset): void {
    const spherical = new THREE.Spherical().setFromVector3(
      this.camera.position.clone().sub(this.controls.target),
    )
    this.placeAt(gridDiagonal(this.dims) * ZOOM_FACTORS[preset], spherical.phi, spherical.theta)
  }

  setAspect(width: number, height: number): void {
    this.camera.aspect = height === 0 ? 1 : width / height
    this.camera.updateProjectionMatrix()
  }

  update(): void {
    this.controls.update()
  }

  dispose(): void {
    this.controls.dispose()
  }

  private placeAt(distance: number, polar: number, azimuth: number): void {
    const clamped = Math.min(this.controls.maxDistance, Math.max(this.controls.minDistance, distance))
    const offset = new THREE.Vector3().setFromSphericalCoords(
      clamped,
      Math.min(POLAR_MAX, Math.max(POLAR_MIN, polar)),
      azimuth,
    )
    this.camera.position.copy(this.controls.target).add(offset)
    this.camera.lookAt(this.controls.target)
    this.controls.update()
  }

  private clampTarget(): void {
    const halfC = this.dims.cols / 2
    const halfR = this.dims.rows / 2
    const target = this.controls.target
    target.x = Math.max(-halfC, Math.min(halfC, target.x))
    target.z = Math.max(-halfR, Math.min(halfR, target.z))
    target.y = Math.max(0, Math.min(3, target.y))
  }
}
