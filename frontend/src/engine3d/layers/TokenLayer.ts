// Tokens : héros/combattants (modèle de classe ou pion, nameplate + barre HP,
// anneaux d'état), POI (billboard d'icône + anneau tone), sorties (anneau
// lumineux). Sync par diff d'id — les déplacements sont tweenés (anim Walk).

import * as THREE from 'three'
import type { GridPoint, TokenSpec } from '../types'
import type { EngineCtx } from '../core/context'
import { buildPawn } from '../assets/ProceduralFactory'
import { disposeObject } from './GroundLayer'
import { loadIconTexture } from '../utils/iconTexture'
import { cellCenterToWorld, metersToWorld } from '../utils/gridMath'
import { tweenPath, type Tween } from '../core/tween'

const MOVE_SPEED_CELLS_PER_S = 2.6
const CHARACTER_HEIGHT_M = 1.7

interface TokenVisual {
  spec: TokenSpec
  container: THREE.Group
  body: THREE.Object3D
  bodyIsModel: boolean
  mixer: THREE.AnimationMixer | null
  idle: THREE.AnimationAction | null
  walk: THREE.AnimationAction | null
  plate: THREE.Sprite | null
  plateKey: string
  iconSprite: THREE.Sprite | null
  rings: Partial<Record<'base' | 'state' | 'active' | 'target', THREE.Mesh>>
  headY: number
  bobPhase: number
  moveTween: Tween | null
  generation: number
}

export class TokenLayer {
  readonly group = new THREE.Group()
  private visuals = new Map<string, TokenVisual>()
  private generation = 0
  private time = 0

  sync(specs: TokenSpec[], ctx: EngineCtx): void {
    const seen = new Set<string>()
    for (const spec of specs) {
      seen.add(spec.id)
      const existing = this.visuals.get(spec.id)
      if (!existing || existing.spec.kind !== spec.kind || existing.spec.modelKey !== spec.modelKey) {
        if (existing) this.removeVisual(spec.id)
        this.createVisual(spec, ctx)
      } else {
        this.updateVisual(existing, spec, ctx)
      }
    }
    for (const id of [...this.visuals.keys()]) {
      if (!seen.has(id)) this.removeVisual(id)
    }
  }

  /** Déplacement tweené le long d'un chemin de cellules (anim Walk si rig). */
  moveAlong(id: string, path: GridPoint[], ctx: EngineCtx): void {
    const visual = this.visuals.get(id)
    if (!visual || path.length === 0) return
    ctx.tweens.cancel(visual.moveTween)

    // L'offset anti-chevauchement ne s'applique qu'au point d'arrivée — le
    // déplacement passe par les centres de cellules. Le y suit l'élévation
    // de chaque cellule (le token monte les escaliers le long du chemin).
    const points = path.map((cell, index) => {
      const world = cellCenterToWorld(cell.col, cell.row, ctx.dims)
      const isLast = index === path.length - 1
      return {
        x: world.x + (isLast ? visual.spec.offsetX ?? 0 : 0),
        y: ctx.elevationAt(cell.col, cell.row),
        z: world.z + (isLast ? visual.spec.offsetZ ?? 0 : 0),
      }
    })
    this.setWalking(visual, true)
    visual.moveTween = tweenPath(
      visual.container.position,
      points,
      MOVE_SPEED_CELLS_PER_S,
      (_segment, direction) => {
        visual.container.rotation.y = Math.atan2(direction.x, direction.z)
      },
      () => {
        visual.moveTween = null
        this.setWalking(visual, false)
      },
    )
    ctx.tweens.add(visual.moveTween)
    const last = path[path.length - 1]
    if (last) visual.spec = { ...visual.spec, col: last.col, row: last.row }
  }

  pickables(): THREE.Object3D[] {
    return [...this.visuals.values()].map((visual) => visual.container)
  }

  anchorWorld(id: string): THREE.Vector3 | null {
    const visual = this.visuals.get(id)
    if (!visual) return null
    return new THREE.Vector3(
      visual.container.position.x,
      visual.container.position.y + visual.headY,
      visual.container.position.z,
    )
  }

  tick(dt: number): void {
    this.time += dt
    for (const visual of this.visuals.values()) {
      visual.mixer?.update(dt)
      if (visual.spec.kind === 'poi' && visual.iconSprite) {
        visual.iconSprite.position.y = visual.headY + Math.sin(this.time * 2 + visual.bobPhase) * 0.05
      }
      const target = visual.rings.target
      if (target?.visible) {
        const pulse = 1 + Math.sin(this.time * 5) * 0.06
        target.scale.setScalar(pulse)
        ;(target.material as THREE.MeshBasicMaterial).opacity = 0.6 + Math.sin(this.time * 5) * 0.25
      }
      const active = visual.rings.active
      if (active?.visible) {
        active.scale.setScalar(1 + Math.sin(this.time * 3) * 0.04)
      }
    }
  }

  dispose(): void {
    this.generation += 1
    for (const id of [...this.visuals.keys()]) this.removeVisual(id)
  }

  // ─── Construction ──────────────────────────────────────────────────────────

  private createVisual(spec: TokenSpec, ctx: EngineCtx): void {
    this.generation += 1
    const generation = this.generation
    const container = new THREE.Group()
    const world = cellCenterToWorld(spec.col, spec.row, ctx.dims)
    container.position.set(
      world.x + (spec.offsetX ?? 0),
      ctx.elevationAt(spec.col, spec.row),
      world.z + (spec.offsetZ ?? 0),
    )
    container.rotation.y = Math.PI / 4
    container.userData.pick = { type: 'token', id: spec.id, tokenKind: spec.kind }

    const visual: TokenVisual = {
      spec,
      container,
      body: new THREE.Group(),
      bodyIsModel: false,
      mixer: null,
      idle: null,
      walk: null,
      plate: null,
      plateKey: '',
      iconSprite: null,
      rings: {},
      headY: 1,
      bobPhase: Math.random() * Math.PI * 2,
      moveTween: null,
      generation,
    }

    if (spec.kind === 'hero' || spec.kind === 'combatant' || spec.kind === 'npc') {
      this.buildCharacter(visual, spec, generation, ctx)
    } else if (spec.kind === 'poi') {
      this.buildPoi(visual, spec, ctx)
    } else {
      this.buildExit(visual, spec, ctx)
    }

    this.group.add(container)
    this.visuals.set(spec.id, visual)
    this.applyState(visual, spec, ctx)
  }

  private buildCharacter(visual: TokenVisual, spec: TokenSpec, generation: number, ctx: EngineCtx): void {
    const heightWorld = metersToWorld(CHARACTER_HEIGHT_M, ctx.cellSizeM)
    visual.headY = heightWorld + 0.12
    const pawn = buildPawn(spec.accent, heightWorld)
    visual.body = pawn
    visual.container.add(pawn)
    visual.rings.base = this.addRing(visual.container, 0.34, 0.42, spec.accent, 0.9)
    visual.rings.state = this.addRing(visual.container, 0.46, 0.55, '#ffffff', 0.85, false)
    visual.rings.active = this.addRing(visual.container, 0.58, 0.66, '#f0c764', 0.9, false)
    visual.rings.target = this.addRing(visual.container, 0.7, 0.79, '#e84545', 0.7, false)
    this.refreshPlate(visual, spec, ctx)

    if (spec.modelKey) {
      void ctx.registry.load(spec.modelKey).then((model) => {
        if (!model || visual.generation !== generation || !this.visuals.has(spec.id)) return
        const instance = ctx.registry.instantiate(model, { targetHeight: heightWorld })
        visual.container.remove(visual.body)
        disposeObject(visual.body)
        visual.body = instance
        visual.bodyIsModel = true
        visual.container.add(instance)
        if (model.animations.length > 0) {
          visual.mixer = new THREE.AnimationMixer(instance)
          const idleClip = findClip(model.animations, /^idle$/i) ?? findClip(model.animations, /idle/i)
          const walkClip = findClip(model.animations, /^walking_a$/i) ?? findClip(model.animations, /walk|run/i)
          if (idleClip) {
            visual.idle = visual.mixer.clipAction(idleClip)
            visual.idle.play()
          }
          if (walkClip) visual.walk = visual.mixer.clipAction(walkClip)
        }
        this.applyState(visual, visual.spec, ctx)
      })
    }
  }

  private buildPoi(visual: TokenVisual, spec: TokenSpec, ctx: EngineCtx): void {
    visual.headY = 1.05
    visual.rings.base = this.addRing(visual.container, 0.2, 0.27, spec.accent, 0.8)
    visual.rings.state = this.addRing(visual.container, 0.32, 0.4, '#ffffff', 0.85, false)

    const sprite = makeSprite(makeGlyphTexture('✦', spec.accent))
    sprite.scale.set(0.62, 0.62, 1)
    sprite.position.y = visual.headY
    visual.iconSprite = sprite
    visual.container.add(sprite)
    if (spec.iconId) {
      void loadIconTexture(spec.iconId).then((texture) => {
        if (!texture || !this.visuals.has(spec.id) || !visual.iconSprite) return
        const material = visual.iconSprite.material as THREE.SpriteMaterial
        material.map?.dispose()
        material.map = texture
        material.needsUpdate = true
      })
    }
  }

  private buildExit(visual: TokenVisual, spec: TokenSpec, ctx: EngineCtx): void {
    visual.headY = 0.6
    const color = spec.exitActive ? '#f0c764' : '#4fd8c0'
    const ring = this.addRing(visual.container, 0.3, 0.42, color, 0.9)
    ;(ring.material as THREE.MeshBasicMaterial).side = THREE.DoubleSide
    visual.rings.base = ring
    visual.rings.state = this.addRing(visual.container, 0.48, 0.56, '#ffffff', 0.85, false)

    const sprite = makeSprite(makeGlyphTexture('⬈', color))
    sprite.scale.set(0.5, 0.5, 1)
    sprite.position.y = 0.55
    visual.iconSprite = sprite
    visual.container.add(sprite)
    if (spec.iconId) {
      void loadIconTexture(spec.iconId).then((texture) => {
        if (!texture || !this.visuals.has(spec.id) || !visual.iconSprite) return
        const material = visual.iconSprite.material as THREE.SpriteMaterial
        material.map?.dispose()
        material.map = texture
        material.needsUpdate = true
      })
    }
  }

  // ─── Mise à jour ───────────────────────────────────────────────────────────

  private updateVisual(visual: TokenVisual, spec: TokenSpec, ctx: EngineCtx): void {
    const moved = spec.col !== visual.spec.col || spec.row !== visual.spec.row
    const offsetChanged =
      (spec.offsetX ?? 0) !== (visual.spec.offsetX ?? 0)
      || (spec.offsetZ ?? 0) !== (visual.spec.offsetZ ?? 0)
    // Spec d'abord (moveAlong lit les offsets du spec courant), col/row préservés
    // tant que le tween n'a pas rattrapé la cellule cible.
    visual.spec = { ...spec, col: visual.spec.col, row: visual.spec.row }
    if ((moved || offsetChanged) && !visual.moveTween) {
      this.moveAlong(spec.id, [{ col: spec.col, row: spec.row }], ctx)
    }
    this.applyState(visual, spec, ctx)
  }

  private applyState(visual: TokenVisual, spec: TokenSpec, ctx: EngineCtx): void {
    const rings = visual.rings
    if (rings.state) {
      const stateColor = spec.selected ? ctx.tokens.gold : spec.highlighted ? ctx.tokens.ember : null
      rings.state.visible = stateColor !== null
      if (stateColor) (rings.state.material as THREE.MeshBasicMaterial).color = new THREE.Color(stateColor)
    }
    if (rings.active) rings.active.visible = spec.active
    if (rings.target) {
      rings.target.visible = spec.targetable !== null
      if (spec.targetable) {
        (rings.target.material as THREE.MeshBasicMaterial).color = new THREE.Color(
          spec.targetable === 'spell' ? ctx.tokens.arcane : ctx.tokens.blood,
        )
      }
    }
    if (spec.kind === 'hero' || spec.kind === 'combatant' || spec.kind === 'npc') {
      this.refreshPlate(visual, spec, ctx)
      this.applyDefeated(visual, spec)
    }
    if (spec.kind === 'exit' && rings.base) {
      (rings.base.material as THREE.MeshBasicMaterial).color = new THREE.Color(
        spec.exitActive ? ctx.tokens.gold : ctx.tokens.teal,
      )
    }
  }

  private applyDefeated(visual: TokenVisual, spec: TokenSpec): void {
    const fallen = spec.defeated
    const tipped = visual.body.rotation.z !== 0
    if (fallen && !tipped) {
      visual.body.rotation.z = Math.PI / 2.2
      visual.body.position.y = 0.08
      visual.mixer?.stopAllAction()
      setOpacity(visual.body, 0.55)
    } else if (!fallen && tipped) {
      visual.body.rotation.z = 0
      visual.body.position.y = 0
      visual.idle?.play()
      setOpacity(visual.body, 1)
    }
  }

  private refreshPlate(visual: TokenVisual, spec: TokenSpec, ctx: EngineCtx): void {
    const key = `${spec.name}|${spec.hpRatio?.toFixed(2) ?? 'x'}|${spec.accent}`
    if (key === visual.plateKey) return
    visual.plateKey = key

    const texture = makePlateTexture(spec.name, spec.hpRatio, spec.accent, ctx)
    if (!texture) return
    if (!visual.plate) {
      visual.plate = makeSprite(texture)
      visual.plate.scale.set(1.5, 0.42, 1)
      visual.plate.position.y = visual.headY + 0.3
      visual.container.add(visual.plate)
    } else {
      const material = visual.plate.material as THREE.SpriteMaterial
      material.map?.dispose()
      material.map = texture
      material.needsUpdate = true
    }
  }

  private addRing(
    parent: THREE.Group,
    inner: number,
    outer: number,
    colorHex: string,
    opacity: number,
    visible = true,
  ): THREE.Mesh {
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(inner, outer, 36),
      new THREE.MeshBasicMaterial({
        color: new THREE.Color(colorHex),
        transparent: true,
        opacity,
        side: THREE.DoubleSide,
        depthWrite: false,
      }),
    )
    ring.rotation.x = -Math.PI / 2
    ring.position.y = 0.02
    ring.visible = visible
    parent.add(ring)
    return ring
  }

  private setWalking(visual: TokenVisual, walking: boolean): void {
    if (!visual.mixer || !visual.walk) return
    if (walking) {
      visual.idle?.fadeOut(0.15)
      visual.walk.reset().fadeIn(0.15).play()
    } else {
      visual.walk.fadeOut(0.2)
      visual.idle?.reset().fadeIn(0.2).play()
    }
  }

  private removeVisual(id: string): void {
    const visual = this.visuals.get(id)
    if (!visual) return
    visual.generation = -1
    this.group.remove(visual.container)
    disposeObject(visual.container)
    this.visuals.delete(id)
  }
}

// ─── Sprites & textures canvas ───────────────────────────────────────────────

function makeSprite(texture: THREE.Texture | null): THREE.Sprite {
  const material = new THREE.SpriteMaterial({
    map: texture ?? undefined,
    transparent: true,
    depthWrite: false,
  })
  return new THREE.Sprite(material)
}

function canvas2d(width: number, height: number): CanvasRenderingContext2D | null {
  if (typeof document === 'undefined') return null
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  return canvas.getContext('2d')
}

function makeGlyphTexture(glyph: string, colorHex: string): THREE.Texture | null {
  const ctx = canvas2d(96, 96)
  if (!ctx) return null
  ctx.font = '64px serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillStyle = colorHex
  ctx.fillText(glyph, 48, 52)
  const texture = new THREE.CanvasTexture(ctx.canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  return texture
}

/** Nameplate : nom (Cinzel) + barre de HP, façon HeroToken SVG. */
function makePlateTexture(
  name: string,
  hpRatio: number | null,
  accent: string,
  ctx: EngineCtx,
): THREE.Texture | null {
  const context = canvas2d(320, 90)
  if (!context) return null

  context.font = '700 34px Cinzel, Georgia, serif'
  context.textAlign = 'center'
  const label = name.length > 16 ? `${name.slice(0, 15)}…` : name
  const textWidth = Math.min(300, context.measureText(label).width + 36)
  const x0 = (320 - textWidth) / 2

  context.fillStyle = 'rgba(14, 13, 20, 0.78)'
  roundRect(context, x0, 6, textWidth, 50, 10)
  context.fill()
  context.strokeStyle = 'rgba(255, 235, 180, 0.22)'
  context.lineWidth = 2
  roundRect(context, x0, 6, textWidth, 50, 10)
  context.stroke()

  context.fillStyle = ctx.tokens.parchment
  context.fillText(label, 160, 44)

  if (hpRatio !== null) {
    const barWidth = 150
    const barX = (320 - barWidth) / 2
    context.fillStyle = 'rgba(0, 0, 0, 0.72)'
    roundRect(context, barX, 64, barWidth, 14, 7)
    context.fill()
    const ratio = Math.max(0, Math.min(1, hpRatio))
    context.fillStyle = ratio > 0.5 ? ctx.tokens.green : ratio > 0.25 ? ctx.tokens.gold : ctx.tokens.blood
    if (ratio > 0) {
      roundRect(context, barX + 2, 66, Math.max(6, (barWidth - 4) * ratio), 10, 5)
      context.fill()
    }
  } else {
    context.fillStyle = accent
    context.beginPath()
    context.arc(160, 70, 5, 0, Math.PI * 2)
    context.fill()
  }

  const texture = new THREE.CanvasTexture(context.canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  return texture
}

function roundRect(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
): void {
  context.beginPath()
  context.moveTo(x + radius, y)
  context.arcTo(x + width, y, x + width, y + height, radius)
  context.arcTo(x + width, y + height, x, y + height, radius)
  context.arcTo(x, y + height, x, y, radius)
  context.arcTo(x, y, x + width, y, radius)
  context.closePath()
}

function findClip(clips: THREE.AnimationClip[], pattern: RegExp): THREE.AnimationClip | null {
  return clips.find((clip) => pattern.test(clip.name)) ?? null
}

function setOpacity(root: THREE.Object3D, opacity: number): void {
  root.traverse((node) => {
    const mesh = node as THREE.Mesh
    if (!mesh.isMesh) return
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
    for (const material of materials) {
      material.transparent = opacity < 1
      material.opacity = opacity
    }
  })
}
