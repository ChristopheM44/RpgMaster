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
import { easeInOut, TweenGroup, type Tween } from './tween'
import { ElementsLayer } from '../layers/ElementsLayer'
import { GroundLayer } from '../layers/GroundLayer'
import { LabelLayer } from '../layers/LabelLayer'
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
  private labels: LabelLayer
  private hemi: THREE.HemisphereLight
  private sun: THREE.DirectionalLight
  /** Plancher de lisibilité en ambiance sombre (night/torchlit) — jamais de noir total.
   *  Couleur chaude ET assez claire : un AmbientLight quasi noir ne relève rien,
   *  quelle que soit l'intensité (lumière sombre × sol sombre = sol noir). */
  private ambientFloor = new THREE.AmbientLight('#423626', 0)
  /** Luminosité UI : valeurs de base de l'ambiance courante × multiplicateur joueur. */
  private brightness = 1
  private baseExposure = 1.05
  private baseAmbient = 0
  private clock = new THREE.Clock()
  private rafId: number | null = null
  private running = true
  private disposed = false
  private dims: GridDims = { cols: 12, rows: 12 }
  private cellPickingEnabled = false
  private frameKey = ''
  private lastCtx: EngineCtx | null = null
  private cameraTween: Tween | null = null

  constructor(private canvas: HTMLCanvasElement, callbacks: RuntimeCallbacks = {}) {
    // Bannière de sortie cliquée = même chemin qu'un clic 3D sur la sortie.
    this.labels = new LabelLayer({
      onExitClick: (id, screen) => callbacks.onClick?.({ type: 'token', id, tokenKind: 'exit' }, screen),
    })
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
      onHoverCell: (cell) => {
        // Combat : les overlays de déplacement donnent déjà le retour de case.
        const shown = this.cellPickingEnabled ? null : cell
        this.ground.setHoverCell(shown, shown ? this.lastCtx?.elevationAt(shown.col, shown.row) ?? 0 : 0)
      },
    }, callbacks)

    this.resize()
    this.loop()
  }

  update(spec: SceneSpec): void {
    if (this.disposed) return
    this.dims = { cols: spec.ground.cols, rows: spec.ground.rows }
    this.cellPickingEnabled = spec.overlay.cellPicking

    const biome = biomeFor(spec.ground.theme, spec.ground.enclosed)
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
    // Lieu clos : brume sombre du biome. Extérieur : ciel de l'ambiance teinté par le biome
    // (le terrain prolongé se perd à l'horizon au lieu de s'arrêter net).
    const background = biome.enclosed
      ? new THREE.Color(biome.fog).lerp(new THREE.Color(this.themeTokens.bg), 0.35)
      : new THREE.Color(preset.sky).lerp(new THREE.Color(biome.fog), 0.35)
    this.scene.background = background
    const diag = gridDiagonal(this.dims)
    const density = spec.ground.ambiance.fogDensity
    // Plan proche repoussé au-delà de l'aire jouable (caméra ~1.05×diag) : avant,
    // le brouillard mordait le centre de la salle et le fondait vers le noir.
    this.scene.fog = new THREE.Fog(background, diag * (1.35 - 0.45 * density), diag * (3.2 - 1.2 * density))

    this.hemi.color = new THREE.Color(preset.hemiSky)
    this.hemi.groundColor = new THREE.Color(preset.hemiGround)
    this.hemi.intensity = preset.hemiIntensity
    this.sun.color = new THREE.Color(preset.sunColor)
    this.sun.intensity = preset.sunIntensity
    this.baseExposure = preset.exposure
    // Plancher ambiant : nuit/torches ET tout lieu clos (même « couvert », sans torches,
    // les murs coupent le ciel et la salle tombait dans le noir).
    this.baseAmbient = preset.pointLights || biome.enclosed ? 0.5 : 0
    this.applyBrightness()
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
      // Nouvelle scène : jetons recréés à leurs nouvelles cases (un même héros
      // ne doit pas « finir » sa marche vers la sortie de la scène précédente).
      if (this.frameKey) this.tokens.dispose()
      this.frameKey = frameKey
      this.rig.frameGrid(this.dims)
    }

    this.ground.update(spec.ground, { tokens: this.themeTokens, biome })
    const selectedElementId = spec.elements.find((element) => element.selected)?.id ?? null
    this.elements.update(spec.elements, selectedElementId, ctx)
    this.scatter.update(spec.ground, new Set(spec.scatterBlockedCells), ctx)
    this.tokens.sync(spec.tokens, ctx)
    this.labels.sync(spec.tokens)
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

  attachLabels(root: HTMLElement | null): void {
    this.labels.attach(root)
  }

  setZoomPreset(preset: ZoomPreset): void {
    this.rig.setZoomPreset(preset)
  }

  focusCell(col: number, row: number, durationS = 0.9): Promise<void> {
    const from = this.rig.pose()
    const world = cellCenterToWorld(col, row, this.dims)
    const target = new THREE.Vector3(world.x, 0, world.z)
    const position = target.clone().add(from.position.clone().sub(from.target).multiplyScalar(0.55))
    return this.animatePose(from, { target, position }, durationS)
  }

  arriveAt(col: number, row: number, durationS = 1.0): void {
    const end = this.rig.pose()
    const world = cellCenterToWorld(col, row, this.dims)
    const target = new THREE.Vector3(world.x, 0, world.z)
    const start = {
      target,
      position: target.clone().add(end.position.clone().sub(end.target).multiplyScalar(0.5)),
    }
    this.rig.setPose(start.target, start.position)
    void this.animatePose(start, end, durationS)
  }

  /** Interpole cible + position caméra via la boucle de tweens (résolu à la fin ou à l'annulation). */
  private animatePose(
    from: { target: THREE.Vector3; position: THREE.Vector3 },
    to: { target: THREE.Vector3; position: THREE.Vector3 },
    durationS: number,
  ): Promise<void> {
    if (this.cameraTween) this.tweens.cancel(this.cameraTween)
    return new Promise((resolve) => {
      let elapsed = 0
      let done = false
      const finish = (): void => {
        if (done) return
        done = true
        if (this.cameraTween === tween) this.cameraTween = null
        resolve()
      }
      const tween: Tween = {
        update: (dt) => {
          elapsed += dt
          const k = easeInOut(Math.min(1, elapsed / Math.max(0.01, durationS)))
          this.rig.setPose(
            from.target.clone().lerp(to.target, k),
            from.position.clone().lerp(to.position, k),
          )
          if (k >= 1) finish()
          return k >= 1
        },
        cancel: finish,
      }
      this.cameraTween = tween
      this.tweens.add(tween)
    })
  }

  setBrightness(value: number): void {
    this.brightness = Math.min(2, Math.max(0.5, value))
    this.applyBrightness()
  }

  /** Applique le multiplicateur joueur aux valeurs de base de l'ambiance courante. */
  private applyBrightness(): void {
    this.renderer.toneMappingExposure = this.baseExposure * this.brightness
    this.ambientFloor.intensity = this.baseAmbient * this.brightness
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
    this.labels.dispose()
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
    this.elements.tick(dt, this.rig.camera.position, this.rig.controls.target)
    this.labels.tick(
      this.rig.camera,
      this.canvas.clientWidth,
      this.canvas.clientHeight,
      (id) => this.tokens.anchorWorld(id),
    )
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
