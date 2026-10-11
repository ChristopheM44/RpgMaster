// Décor procédural seedé par scene_id : végétation/rochers selon le biome,
// densité pilotée par vegetation_density, biais vers les bords (centre jouable
// dégagé), jamais sur une cellule occupée. Torches d'angle en dungeon/cave.

import * as THREE from 'three'
import type { GroundSpec } from '../types'
import type { EngineCtx } from '../core/context'
import type { ScatterKind } from '../core/ThemeProvider'
import { buildScatterObject } from '../assets/ProceduralFactory'
import { SCATTER_MODELS, SCATTER_TARGET_HEIGHT_M } from '../assets/manifest'
import { disposeGroup, disposeObject } from './GroundLayer'
import { cellCenterToWorld, metersToWorld } from '../utils/gridMath'
import { makePrng, pick, range } from '../utils/seededRandom'
import { distanceOutsideBoard, terrainHeight, terrainSeed } from '../utils/terrain'

const MAX_SCATTER = 56
const MAX_TORCH_LIGHTS = 4
/** Décor du terrain prolongé (hors plateau) : le monde continue au-delà de la grille. */
const MAX_OUTER_SCATTER = 110

export class ScatterLayer {
  readonly group = new THREE.Group()
  private buildKey = ''
  private generation = 0

  update(ground: GroundSpec, blocked: Set<string>, ctx: EngineCtx): void {
    const key = [
      ground.sceneId,
      ground.theme,
      ctx.biome.enclosed ? 'enclosed' : 'open',
      ground.vegetationDensity.toFixed(2),
      `${ground.cols}x${ground.rows}`,
      ctx.ambiance.pointLights || ctx.biome.enclosed ? 'pl' : 'no-pl',
      [...blocked].sort().join(';'),
    ].join('|')
    if (key === this.buildKey) return
    this.buildKey = key
    this.rebuild(ground, blocked, ctx)
  }

  dispose(): void {
    this.generation += 1
    disposeGroup(this.group)
    this.buildKey = ''
  }

  private rebuild(ground: GroundSpec, blocked: Set<string>, ctx: EngineCtx): void {
    this.generation += 1
    const generation = this.generation
    disposeGroup(this.group)

    const { cols, rows } = ground
    const rand = makePrng(`${ground.sceneId}|${ground.theme}`)
    const biome = ctx.biome

    if (biome.scatter.length > 0 && ground.vegetationDensity > 0.01) {
      const freeCells: { col: number; row: number; edge: number }[] = []
      for (let row = 0; row < rows; row++) {
        for (let col = 0; col < cols; col++) {
          if (blocked.has(`${col},${row}`)) continue
          const edgeDistance = Math.min(col, row, cols - 1 - col, rows - 1 - row)
          const edgeFactor = 1 - Math.min(1, edgeDistance / Math.max(2, Math.min(cols, rows) / 3))
          freeCells.push({ col, row, edge: edgeFactor })
        }
      }

      const target = Math.min(MAX_SCATTER, Math.round(freeCells.length * ground.vegetationDensity * 0.16))
      const used = new Set<string>()
      let placed = 0
      let attempts = 0
      while (placed < target && attempts < target * 10 && freeCells.length > 0) {
        attempts += 1
        const cell = pick(rand, freeCells)
        const cellId = `${cell.col},${cell.row}`
        if (used.has(cellId)) continue
        // Biais bords : probabilité d'acceptation plus forte près du périmètre.
        if (rand() > 0.3 + 0.7 * cell.edge) continue
        used.add(cellId)
        placed += 1
        const center = cellCenterToWorld(cell.col, cell.row, ctx.dims)
        this.placeScatter(
          pick(rand, biome.scatter),
          { x: center.x + range(rand, -0.32, 0.32), y: 0, z: center.z + range(rand, -0.32, 0.32) },
          range(rand, 0.75, 1.3),
          ground,
          rand,
          generation,
          ctx,
        )
      }
    }

    // Ville : pas de caisses semées dans la campagne (décor urbain hors plateau = lot 4).
    if (!biome.enclosed && biome.groundStyle !== 'cobble' && biome.scatter.length > 0) {
      this.placeOuterScatter(ground, generation, ctx)
    }

    if (biome.cornerTorches) this.placeCornerTorches(ground, blocked, ctx)
  }

  /** Végétation/rochers sur le relief autour du plateau, plus denses vers l'horizon. */
  private placeOuterScatter(ground: GroundSpec, generation: number, ctx: EngineCtx): void {
    const rand = makePrng(`${ground.sceneId}|outer`)
    const halfW = ground.cols / 2
    const halfH = ground.rows / 2
    const margin = Math.max(ground.cols, ground.rows) * 1.6
    const terrain = { halfW, halfH, relief: ctx.biome.relief, seed: terrainSeed(ground.sceneId) }
    const count = Math.round(MAX_OUTER_SCATTER * Math.max(0.3, Math.min(1, ground.vegetationDensity + 0.25)))
    let placed = 0
    for (let attempt = 0; attempt < count * 6 && placed < count; attempt++) {
      const x = range(rand, -halfW - margin, halfW + margin)
      const z = range(rand, -halfH - margin, halfH + margin)
      const outside = distanceOutsideBoard(x, z, halfW, halfH)
      // Bord du plateau dégagé (lisibilité), densité croissante avec la distance.
      if (outside < 0.8 || rand() > Math.min(1, outside / 6)) continue
      placed += 1
      this.placeScatter(
        pick(rand, ctx.biome.scatter),
        { x, y: terrainHeight(x, z, terrain) - 0.03, z },
        range(rand, 0.8, 1.7),
        ground,
        rand,
        generation,
        ctx,
      )
    }
  }

  private placeScatter(
    kind: ScatterKind,
    at: { x: number; y: number; z: number },
    scaleJitter: number,
    ground: GroundSpec,
    rand: ReturnType<typeof makePrng>,
    generation: number,
    ctx: EngineCtx,
  ): void {
    const container = new THREE.Group()
    container.position.set(at.x, at.y, at.z)
    container.rotation.y = range(rand, 0, Math.PI * 2)

    const procedural = buildScatterObject(kind, rand, ctx.tokens)
    procedural.scale.setScalar(scaleJitter)
    container.add(procedural)
    this.group.add(container)

    const variants = SCATTER_MODELS[kind]
    if (!variants?.length) return
    const variant = pick(rand, variants)
    const targetHeight = metersToWorld(SCATTER_TARGET_HEIGHT_M[kind], ground.cellSizeM) * scaleJitter

    void ctx.registry.load(variant).then((model) => {
      if (!model || generation !== this.generation || !container.parent) return
      const instance = ctx.registry.instantiate(model, { targetHeight })
      container.remove(procedural)
      disposeObject(procedural)
      container.add(instance)
    })
  }

  private placeCornerTorches(ground: GroundSpec, blocked: Set<string>, ctx: EngineCtx): void {
    const generation = this.generation
    const { cols, rows } = ground
    const corners = [
      { col: 1, row: 1 },
      { col: cols - 2, row: 1 },
      { col: 1, row: rows - 2 },
      { col: cols - 2, row: rows - 2 },
    ]
    let lights = 0
    const rand = makePrng(`${ground.sceneId}|torches`)
    for (const corner of corners) {
      if (corner.col < 0 || corner.row < 0) continue
      if (blocked.has(`${corner.col},${corner.row}`)) continue
      const container = new THREE.Group()
      const center = cellCenterToWorld(corner.col, corner.row, ctx.dims)
      container.position.set(center.x, 0, center.z)
      const procedural = buildScatterObject('torch', rand, ctx.tokens)
      container.add(procedural)
      this.group.add(container)

      if ((ctx.ambiance.pointLights || ctx.biome.enclosed) && lights < MAX_TORCH_LIGHTS) {
        // Portée allongée (~16 m ≈ 11 cellules) pour traverser une salle entière :
        // à 8 m les torches d'angle mouraient avant le centre. Chute plus douce.
        const light = new THREE.PointLight(
          new THREE.Color(ctx.tokens.ember),
          8,
          metersToWorld(16, ground.cellSizeM),
          1.5,
        )
        light.position.set(center.x, 1.6, center.z)
        this.group.add(light)
        lights += 1
      }

      void ctx.registry.load('prop/torch_lit').then((model) => {
        if (!model || generation !== this.generation || !container.parent) return
        const instance = ctx.registry.instantiate(model, {
          targetHeight: metersToWorld(SCATTER_TARGET_HEIGHT_M.torch, ground.cellSizeM),
        })
        container.remove(procedural)
        disposeObject(procedural)
        container.add(instance)
      })
    }
  }
}
