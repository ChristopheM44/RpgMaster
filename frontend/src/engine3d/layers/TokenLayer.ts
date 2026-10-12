// Tokens : héros/combattants (modèle de classe ou pion, anneaux d'état), POI
// (losange flottant relié au sol ; un danger se lit au sol, sans losange),
// sorties (chevrons animés vers le bord). Les NOMS, repères et bannières de
// sortie sont des étiquettes DOM (LabelLayer). Sync par diff d'id — les
// déplacements sont tweenés (anim Walk).

import * as THREE from 'three'
import type { GridPoint, TokenSpec } from '../types'
import type { EngineCtx } from '../core/context'
import { addHazardDecal, buildPawn } from '../assets/ProceduralFactory'
import { disposeObject } from './GroundLayer'
import { FACING_VECTOR } from '../adapters/stairs'
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
  /** Losange de POI (rotation + flottement) ou chevrons de sortie (vague). */
  marker: THREE.Object3D | null
  chevrons: THREE.Mesh[]
  /** Bords de décalque de danger à faire tourner. */
  spinners: THREE.Object3D[]
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
      if (visual.spec.kind === 'poi' && visual.marker) {
        visual.marker.rotation.y = this.time * 1.1 + visual.bobPhase
        visual.marker.position.y = visual.headY + Math.sin(this.time * 2 + visual.bobPhase) * 0.05
      }
      for (const spinner of visual.spinners) spinner.rotation.z = this.time * 0.25
      visual.chevrons.forEach((chevron, index) => {
        ;(chevron.material as THREE.MeshBasicMaterial).opacity =
          0.2 + 0.7 * Math.max(0, Math.sin(this.time * 3 - index * 0.9))
      })
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
      marker: null,
      chevrons: [],
      spinners: [],
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

    container.traverse((node) => {
      if (node.userData.hazardRing) visual.spinners.push(node)
    })
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
    // Voile coloré sous le socle : le rôle se lit même de loin (vocabulaire lot 3).
    const glow = new THREE.Mesh(
      new THREE.CircleGeometry(0.34, 32),
      new THREE.MeshBasicMaterial({ color: spec.accent, transparent: true, opacity: 0.16, depthWrite: false }),
    )
    glow.rotation.x = -Math.PI / 2
    glow.position.y = 0.015
    visual.container.add(glow)

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
    visual.container.rotation.y = 0
    if (spec.poiRole === 'hazard') {
      // Un danger se lit AU SOL. S'il est déjà porté par un élément (décalque),
      // le jeton reste invisible ; sinon on pose un petit décalque ici.
      visual.headY = 0.3
      visual.rings.state = this.addRing(visual.container, 0.46, 0.54, '#ffffff', 0.85, false)
      if (!spec.hasElement) addHazardDecal(visual.container, 0.95, 0.95, spec.id, ctx.tokens)
      return
    }
    // Losange flottant relié au sol : « il y a quelque chose à examiner ici ».
    const height = 1.15
    visual.headY = height
    const color = new THREE.Color(spec.accent)
    const gem = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.15, 0),
      new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.85, roughness: 0.35, metalness: 0.2 }),
    )
    gem.scale.y = 1.45
    gem.position.y = height
    visual.marker = gem
    visual.container.add(gem)
    const beam = new THREE.Mesh(
      new THREE.CylinderGeometry(0.01, 0.01, height - 0.2, 6),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.35, depthWrite: false }),
    )
    beam.position.y = (height - 0.2) / 2
    visual.container.add(beam)
    const spot = new THREE.Mesh(
      new THREE.CircleGeometry(0.22, 24),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.3, depthWrite: false }),
    )
    spot.rotation.x = -Math.PI / 2
    spot.position.y = 0.015
    visual.container.add(spot)
    visual.rings.state = this.addRing(visual.container, 0.3, 0.38, '#ffffff', 0.85, false)
  }

  private buildExit(visual: TokenVisual, spec: TokenSpec, ctx: EngineCtx): void {
    visual.headY = 0.9
    visual.container.rotation.y = 0
    // Chevrons au sol vers le bord de sortie : « par ici on quitte la scène ».
    const facing = spec.exitFacing ? FACING_VECTOR[spec.exitFacing] : { x: 0, z: -1 }
    const shape = new THREE.Shape()
    shape.moveTo(-0.22, -0.1)
    shape.lineTo(0, 0.1)
    shape.lineTo(0.22, -0.1)
    shape.lineTo(0.22, -0.02)
    shape.lineTo(0, 0.18)
    shape.lineTo(-0.22, -0.02)
    shape.closePath()
    const geometry = new THREE.ShapeGeometry(shape)
    const color = exitColor(spec, ctx)
    for (let index = 0; index < 3; index++) {
      const chevron = new THREE.Mesh(
        geometry,
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.6, depthWrite: false, side: THREE.DoubleSide }),
      )
      chevron.rotation.x = -Math.PI / 2
      chevron.rotation.z = Math.atan2(-facing.x, -facing.z)
      chevron.position.set(facing.x * (index - 1) * 0.28, 0.03, facing.z * (index - 1) * 0.28)
      visual.chevrons.push(chevron)
      visual.container.add(chevron)
      // Ombre sombre sous chaque chevron : lisible sur sol clair (sable, dalles).
      const shadow = new THREE.Mesh(
        geometry,
        new THREE.MeshBasicMaterial({ color: '#0e0d14', transparent: true, opacity: 0.45, depthWrite: false }),
      )
      shadow.rotation.copy(chevron.rotation)
      shadow.position.copy(chevron.position).setY(0.025)
      shadow.position.x += 0.02
      shadow.position.z += 0.03
      shadow.scale.setScalar(1.18)
      visual.container.add(shadow)
    }
    // Disque invisible : zone de clic/survol généreuse sur la case.
    const hit = new THREE.Mesh(
      new THREE.CircleGeometry(0.45, 16),
      new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false }),
    )
    hit.rotation.x = -Math.PI / 2
    hit.position.y = 0.02
    visual.container.add(hit)
    visual.rings.state = this.addRing(visual.container, 0.46, 0.54, '#ffffff', 0.85, false)
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
      this.applyDefeated(visual, spec)
    }
    if (spec.kind === 'exit') {
      const color = exitColor(spec, ctx)
      for (const chevron of visual.chevrons) (chevron.material as THREE.MeshBasicMaterial).color.set(color)
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

/** Or = sortie empruntable ; teal = accès d'arrivée ou sortie inactive. */
function exitColor(spec: TokenSpec, ctx: EngineCtx): string {
  return spec.arrival || !spec.exitActive ? ctx.tokens.teal : ctx.tokens.gold
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
