// Orchestrateur : renderer WebGL, boucle rAF, lumières/fog par ambiance,
// composition des couches, picking et projections écran. Consomme une
// SceneSpec sérialisable produite par les adapters — jamais Pinia directement.

import * as THREE from 'three'
import type { GridDims, GridPoint, RuntimeCallbacks, SceneRuntimeHandle, SceneSpec, ZoomPreset } from '../types'
import { AssetRegistry } from '../assets/AssetRegistry'
import { CameraRig } from './CameraRig'
import type { EngineCtx } from './context'
import { PickingController } from './PickingController'
import { ambiancePreset, biomeFor, resolveThemeTokens, type ThemeTokens } from './ThemeProvider'
import { TweenGroup } from './tween'
import { ElementsLayer } from '../layers/ElementsLayer'
import { GroundLayer } from '../layers/GroundLayer'
import { OverlayLayer } from '../layers/OverlayLayer'
import { ScatterLayer } from '../layers/ScatterLayer'
import { TokenLayer } from '../layers/TokenLayer'
import { cellCenterToWorld, gridDiagonal, metersToWorld } from '../utils/gridMath'

export class SceneRuntime implements SceneRuntimeHandle {
  private renderer: THREE.WebGLRenderer
  private scene = new THREE.Scene()
  private rig: CameraRig
  private picking: PickingController
  private themeTokens: ThemeTokens
  private registry = new AssetRegistry()
  private tweens = new TweenGroup()
  private ground = new GroundLayer()
  private elements = new ElementsLayer()
  private scatter = new ScatterLayer()
  private tokens = new TokenLayer()
  private overlay = new OverlayLayer()
  private hemi: THREE.HemisphereLight
  private sun: THREE.DirectionalLight
  /** Plancher de lisibilité en ambiance sombre (night/torchlit) — jamais de noir total. */
  private ambientFloor = new THREE.AmbientLight('#181410', 0)
  private clock = new THREE.Clock()
  private rafId: number | null = null
  private running = true
  private disposed = false
  private dims: GridDims = { cols: 12, rows: 12 }
  private cellPickingEnabled = false
  private frameKey = ''
  private lastCtx: EngineCtx | null = null

  constructor(private canvas: HTMLCanvasElement, callbacks: RuntimeCallbacks = {}) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true })
    this.renderer.outputColorSpace = THREE.SRGBColorSpace
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping
    this.renderer.toneMappingExposure = 1.05
    this.renderer.shadowMap.enabled = true
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap
    this.renderer.setPixelRatio(Math.min(typeof window !== 'undefined' ? window.devicePixelRatio : 1, 2))

    this.themeTokens = resolveThemeTokens()
    this.rig = new CameraRig(canvas)

    this.hemi = new THREE.HemisphereLight('#bfd4e8', '#2a2640', 0.95)
    this.sun = new THREE.DirectionalLight('#fff1d6', 1.55)
    this.sun.castShadow = true
    this.sun.shadow.mapSize.set(1024, 1024)
    this.sun.shadow.bias = -0.0015
    this.scene.add(this.hemi, this.sun, this.sun.target, this.ambientFloor)
    this.scene.add(
      this.ground.group,
      this.elements.group,
      this.scatter.group,
      this.tokens.group,
      this.overlay.group,
    )

    this.picking = new PickingController(canvas, this.rig.camera, {
      pickables: () => [...this.tokens.pickables(), ...this.elements.pickables()],
      ground: () => this.ground.groundMesh(),
      dims: () => this.dims,
      cellPicking: () => this.cellPickingEnabled,
    }, callbacks)

    this.resize()
    this.loop()
  }

  update(spec: SceneSpec): void {
    if (this.disposed) return
    this.dims = { cols: spec.ground.cols, rows: spec.ground.rows }
    this.cellPickingEnabled = spec.overlay.cellPicking

    const biome = biomeFor(spec.ground.theme)
    const preset = ambiancePreset(spec.ground.ambiance.light)
    // `?? {}` : tolère les specs mockées des tests composants sans le champ.
    const elevationByCell = spec.elevationByCell ?? {}
    const cellSizeM = spec.ground.cellSizeM
    const ctx: EngineCtx = {
      dims: this.dims,
      cellSizeM,
      tokens: this.themeTokens,
      biome,
      ambiance: preset,
      registry: this.registry,
      tweens: this.tweens,
      elevationAt: (col, row) => metersToWorld(elevationByCell[`${col},${row}`] ?? 0, cellSizeM),
    }
    this.lastCtx = ctx

    // Fond + fog cohérents : la géométrie se fond dans la couleur de brume.
    const background = new THREE.Color(biome.fog).lerp(new THREE.Color(this.themeTokens.bg), 0.35)
    this.scene.background = background
    const diag = gridDiagonal(this.dims)
    const density = spec.ground.ambiance.fogDensity
    this.scene.fog = new THREE.Fog(background, diag * (1.15 - 0.55 * density), diag * (3.0 - 1.4 * density))

    this.hemi.color = new THREE.Color(preset.hemiSky)
    this.hemi.groundColor = new THREE.Color(preset.hemiGround)
    this.hemi.intensity = preset.hemiIntensity
    this.sun.color = new THREE.Color(preset.sunColor)
    this.sun.intensity = preset.sunIntensity
    this.renderer.toneMappingExposure = preset.exposure
    this.ambientFloor.intensity = preset.pointLights ? 0.22 : 0
    this.sun.position.set(diag * 0.55, Math.sin(preset.sunElevation) * diag * 0.9, diag * 0.3)
    this.sun.target.position.set(0, 0, 0)
    const shadowSpan = Math.max(this.dims.cols, this.dims.rows) / 2 + 2
    const shadowCam = this.sun.shadow.camera
    shadowCam.left = -shadowSpan
    shadowCam.right = shadowSpan
    shadowCam.top = shadowSpan
    shadowCam.bottom = -shadowSpan
    shadowCam.far = diag * 3
    shadowCam.updateProjectionMatrix()

    const frameKey = `${spec.ground.sceneId}|${this.dims.cols}x${this.dims.rows}`
    if (frameKey !== this.frameKey) {
      this.frameKey = frameKey
      this.rig.frameGrid(this.dims)
    }

    this.ground.update(spec.ground, { tokens: this.themeTokens, biome })
    const selectedElementId = spec.elements.find((element) => element.selected)?.id ?? null
    this.elements.update(spec.elements, selectedElementId, ctx)
    this.scatter.update(spec.ground, new Set(spec.scatterBlockedCells), ctx)
    this.tokens.sync(spec.tokens, ctx)
    this.overlay.update(spec.overlay, ctx)
  }

  moveToken(id: string, path: GridPoint[]): void {
    if (this.lastCtx) this.tokens.moveAlong(id, path, this.lastCtx)
  }

  projectCell(col: number, row: number): { x: number; y: number } | null {
    const world = cellCenterToWorld(col, row, this.dims)
    const elevation = this.lastCtx?.elevationAt(col, row) ?? 0
    return this.project(new THREE.Vector3(world.x, elevation + 0.4, world.z))
  }

  projectToken(id: string): { x: number; y: number } | null {
    const anchor = this.tokens.anchorWorld(id)
    return anchor ? this.project(anchor) : null
  }

  setZoomPreset(preset: ZoomPreset): void {
    this.rig.setZoomPreset(preset)
  }

  setRunning(running: boolean): void {
    if (this.running === running) return
    this.running = running
    if (running && this.rafId === null && !this.disposed) {
      this.clock.getDelta()
      this.loop()
    }
  }

  resize(): void {
    const width = this.canvas.clientWidth || 1
    const height = this.canvas.clientHeight || 1
    this.renderer.setSize(width, height, false)
    this.rig.setAspect(width, height)
  }

  dispose(): void {
    this.disposed = true
    if (this.rafId !== null) cancelAnimationFrame(this.rafId)
    this.rafId = null
    this.picking.dispose()
    this.rig.dispose()
    this.tweens.clear()
    this.ground.dispose()
    this.elements.dispose()
    this.scatter.dispose()
    this.tokens.dispose()
    this.overlay.dispose()
    this.scene.clear()
    this.renderer.dispose()
  }

  private project(world: THREE.Vector3): { x: number; y: number } | null {
    const projected = world.clone().project(this.rig.camera)
    if (projected.z > 1) return null
    const width = this.canvas.clientWidth
    const height = this.canvas.clientHeight
    return { x: ((projected.x + 1) / 2) * width, y: ((1 - projected.y) / 2) * height }
  }

  private loop = (): void => {
    if (this.disposed || !this.running) {
      this.rafId = null
      return
    }
    this.rafId = requestAnimationFrame(this.loop)
    const dt = Math.min(0.1, this.clock.getDelta())
    this.tweens.update(dt)
    this.tokens.tick(dt)
    this.overlay.tick(dt)
    this.rig.update()
    this.picking.tick()
    this.renderer.render(this.scene, this.rig.camera)
  }
}

export function createSceneRuntime(
  canvas: HTMLCanvasElement,
  callbacks: RuntimeCallbacks = {},
): SceneRuntimeHandle {
  return new SceneRuntime(canvas, callbacks)
}
