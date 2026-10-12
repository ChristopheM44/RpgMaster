// Sol : plateau texturé (dalles alignées sur la grille en lieu clos, matière
// naturelle répétable en extérieur), terrain PROLONGÉ autour du plateau (relief
// en extérieur, roche sombre autour d'un lieu clos) — la scène ne flotte plus
// dans le vide. Grille tactique visible en combat seulement ; case survolée
// toujours marquée. Texture optionnelle MapVisualAsset (image IA) en surimpression.

import * as THREE from 'three'
import type { GridPoint, GroundSpec } from '../types'
import type { Biome3D, ThemeTokens } from '../core/ThemeProvider'
import { boardTexture, NATURAL_TILE_WORLD, naturalTexture } from '../assets/groundTextures'
import { terrainHeight, terrainSeed, type TerrainOptions } from '../utils/terrain'

export interface GroundCtx {
  tokens: ThemeTokens
  biome: Biome3D
}

const ENCLOSED_SURROUND = '#1d191f'

export class GroundLayer {
  readonly group = new THREE.Group()
  /** Plan de picking plein (invisible) : les cellules de trémie restent cliquables. */
  private plane: THREE.Mesh | null = null
  private grid: THREE.LineSegments | null = null
  private hover: THREE.Group | null = null
  private buildKey = ''
  private textureUrl: string | null = null
  private assetPlane: THREE.Mesh | null = null
  private holes = new Set<string>()
  private dims = { cols: 12, rows: 12 }

  update(spec: GroundSpec, ctx: GroundCtx): void {
    const key = `${spec.sceneId}|${spec.cols}x${spec.rows}|${spec.theme}|${ctx.biome.enclosed}|${(spec.holes ?? []).join(';')}`
    if (key !== this.buildKey) {
      this.rebuild(spec, ctx)
      this.buildKey = key
      this.textureUrl = null
    }
    if (this.grid) this.grid.visible = Boolean(spec.showGrid)
    this.syncVisualAsset(spec)
  }

  groundMesh(): THREE.Object3D | null {
    return this.plane
  }

  /** Case survolée (y = surface de la case, unités monde) ; null pour masquer. */
  setHoverCell(cell: GridPoint | null, y = 0): void {
    if (!this.hover) return
    if (!cell || cell.col < 0 || cell.row < 0 || cell.col >= this.dims.cols || cell.row >= this.dims.rows) {
      this.hover.visible = false
      return
    }
    this.hover.visible = true
    this.hover.position.set(cell.col + 0.5 - this.dims.cols / 2, y + 0.02, cell.row + 0.5 - this.dims.rows / 2)
  }

  dispose(): void {
    disposeGroup(this.group)
    this.group.clear()
    this.plane = null
    this.grid = null
    this.hover = null
    this.assetPlane = null
    this.buildKey = ''
    this.textureUrl = null
  }

  private rebuild(spec: GroundSpec, ctx: GroundCtx): void {
    this.dispose()
    const { cols, rows } = spec
    const biome = ctx.biome
    const holes = new Set(spec.holes ?? [])
    this.holes = holes
    this.dims = { cols, rows }

    if (biome.enclosed) {
      // Plateau : dalles alignées sur la grille (UV 0..1 sur le plateau).
      const texture = boardTexture(biome, cols, rows, spec.sceneId)
      const floor = new THREE.Mesh(
        buildCellGridGeometry(cols, rows, holes),
        new THREE.MeshStandardMaterial({
          color: texture ? '#ffffff' : new THREE.Color(biome.ground),
          map: texture,
          roughness: 0.95,
        }),
      )
      floor.receiveShadow = true
      this.group.add(floor)
      // Roche massive autour : le hors-champ d'un lieu clos est de la pierre, pas le vide.
      const surround = new THREE.Mesh(
        buildTerrainRing(cols, rows, null),
        new THREE.MeshStandardMaterial({ color: ENCLOSED_SURROUND, roughness: 1 }),
      )
      surround.position.y = -0.005
      this.group.add(surround)
    } else {
      // Extérieur : même matériau répétable (UV monde) pour plateau et terrain → aucune couture.
      const tile = NATURAL_TILE_WORLD[biome.groundStyle]
      const texture = naturalTexture(biome, spec.sceneId)
      const material = new THREE.MeshStandardMaterial({
        color: texture ? '#ffffff' : new THREE.Color(biome.ground),
        map: texture,
        roughness: 1,
      })
      const floor = new THREE.Mesh(buildCellGridGeometry(cols, rows, holes, tile), material)
      floor.receiveShadow = true
      this.group.add(floor)
      const terrain = new THREE.Mesh(
        buildTerrainRing(cols, rows, {
          halfW: cols / 2,
          halfH: rows / 2,
          relief: biome.relief,
          seed: terrainSeed(spec.sceneId),
        }, tile),
        material,
      )
      terrain.receiveShadow = true
      this.group.add(terrain)
      // Limite de l'aire de jeu : discrète, le terrain continue au-delà.
      this.group.add(buildBoardOutline(cols, rows, ctx.tokens.gold))
    }

    const plane = new THREE.Mesh(
      new THREE.PlaneGeometry(cols, rows),
      new THREE.MeshBasicMaterial({ visible: false }),
    )
    plane.rotation.x = -Math.PI / 2
    this.plane = plane
    this.group.add(plane)

    // Grille tactique (combat) : affichée/masquée sans reconstruction.
    const positions: number[] = []
    const y = 0.006
    for (let col = 0; col <= cols; col++) positions.push(col - cols / 2, y, -rows / 2, col - cols / 2, y, rows / 2)
    for (let row = 0; row <= rows; row++) positions.push(-cols / 2, y, row - rows / 2, cols / 2, y, row - rows / 2)
    const gridGeometry = new THREE.BufferGeometry()
    gridGeometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
    this.grid = new THREE.LineSegments(
      gridGeometry,
      new THREE.LineBasicMaterial({ color: new THREE.Color(biome.grid), transparent: true, opacity: biome.gridOpacity }),
    )
    this.grid.visible = Boolean(spec.showGrid)
    this.group.add(this.grid)

    // Case survolée : voile + liseré dorés.
    const hover = new THREE.Group()
    const veil = new THREE.Mesh(
      new THREE.PlaneGeometry(0.96, 0.96),
      new THREE.MeshBasicMaterial({ color: ctx.tokens.gold, transparent: true, opacity: 0.14, depthWrite: false }),
    )
    veil.rotation.x = -Math.PI / 2
    const edge = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.PlaneGeometry(0.96, 0.96)),
      new THREE.LineBasicMaterial({ color: ctx.tokens.gold, transparent: true, opacity: 0.8 }),
    )
    edge.rotation.x = -Math.PI / 2
    hover.add(veil, edge)
    hover.visible = false
    this.hover = hover
    this.group.add(hover)
  }

  /** Texture IA (visual_asset ready) en surimpression du sol, chargée lazy. */
  private syncVisualAsset(spec: GroundSpec): void {
    if (spec.visualAssetUrl === this.textureUrl) return
    this.textureUrl = spec.visualAssetUrl
    if (this.assetPlane) {
      this.group.remove(this.assetPlane)
      disposeObject(this.assetPlane)
      this.assetPlane = null
    }
    if (!spec.visualAssetUrl) return

    const url = spec.visualAssetUrl
    new THREE.TextureLoader().load(url, (texture) => {
      if (url !== this.textureUrl) {
        texture.dispose()
        return
      }
      texture.colorSpace = THREE.SRGBColorSpace
      const plane = new THREE.Mesh(
        buildCellGridGeometry(spec.cols, spec.rows, this.holes),
        new THREE.MeshBasicMaterial({ map: texture, transparent: true, opacity: 0.85 }),
      )
      plane.position.y = 0.002
      this.assetPlane = plane
      this.group.add(plane)
    }, undefined, () => {
      // Échec de chargement : la carte structurée reste valide sans image.
    })
  }
}

/**
 * Sol en dalles (une quad par cellule, plan XZ, normales +Y), UV continus sur
 * toute la grille — les cellules de `holes` ("col,row") sont omises.
 */
export function buildCellGridGeometry(
  cols: number,
  rows: number,
  holes: Set<string>,
  /** Si fourni : UV en coordonnées monde (une répétition de texture = `worldTile` cases). */
  worldTile?: number,
): THREE.BufferGeometry {
  const positions: number[] = []
  const normals: number[] = []
  const uvs: number[] = []
  const indices: number[] = []
  let vertex = 0
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      if (holes.has(`${col},${row}`)) continue
      const x0 = col - cols / 2
      const z0 = row - rows / 2
      for (const [dx, dz] of [[0, 0], [1, 0], [1, 1], [0, 1]] as const) {
        positions.push(x0 + dx, 0, z0 + dz)
        normals.push(0, 1, 0)
        if (worldTile) uvs.push((col + dx) / worldTile, (row + dz) / worldTile)
        else uvs.push((col + dx) / cols, 1 - (row + dz) / rows)
      }
      indices.push(vertex, vertex + 3, vertex + 1, vertex + 1, vertex + 3, vertex + 2)
      vertex += 4
    }
  }
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3))
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2))
  geometry.setIndex(indices)
  return geometry
}

/**
 * Terrain autour du plateau : grille de pas 1 alignée sur les bords du plateau
 * (sommets partagés avec lui → aucune fente), sans les quads intérieurs.
 * `terrain` null → anneau plat (roche d'un lieu clos).
 */
export function buildTerrainRing(
  cols: number,
  rows: number,
  terrain: TerrainOptions | null,
  worldTile = 4,
): THREE.BufferGeometry {
  const margin = Math.ceil(Math.max(cols, rows) * 2)
  const x0 = -cols / 2 - margin
  const z0 = -rows / 2 - margin
  const nx = cols + margin * 2
  const nz = rows + margin * 2
  const positions: number[] = []
  const uvs: number[] = []
  for (let iz = 0; iz <= nz; iz++) {
    for (let ix = 0; ix <= nx; ix++) {
      const x = x0 + ix
      const z = z0 + iz
      positions.push(x, terrain ? terrainHeight(x, z, terrain) : 0, z)
      uvs.push((x + cols / 2) / worldTile, (z + rows / 2) / worldTile)
    }
  }
  const indices: number[] = []
  const at = (ix: number, iz: number) => iz * (nx + 1) + ix
  for (let iz = 0; iz < nz; iz++) {
    for (let ix = 0; ix < nx; ix++) {
      const insideBoard = ix >= margin && ix < margin + cols && iz >= margin && iz < margin + rows
      if (insideBoard) continue
      indices.push(at(ix, iz), at(ix, iz + 1), at(ix + 1, iz), at(ix + 1, iz), at(ix, iz + 1), at(ix + 1, iz + 1))
    }
  }
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2))
  geometry.setIndex(indices)
  geometry.computeVertexNormals()
  return geometry
}

function buildBoardOutline(cols: number, rows: number, color: string): THREE.LineSegments {
  const y = 0.012
  const hx = cols / 2
  const hz = rows / 2
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute([
    -hx, y, -hz, hx, y, -hz,
    hx, y, -hz, hx, y, hz,
    hx, y, hz, -hx, y, hz,
    -hx, y, hz, -hx, y, -hz,
  ], 3))
  return new THREE.LineSegments(
    geometry,
    new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.4 }),
  )
}

export function disposeObject(object: THREE.Object3D): void {
  object.traverse((node) => {
    const mesh = node as THREE.Mesh
    if (mesh.geometry) mesh.geometry.dispose()
    const material = mesh.material as THREE.Material | THREE.Material[] | undefined
    if (Array.isArray(material)) material.forEach((m) => disposeMaterial(m))
    else if (material) disposeMaterial(material)
  })
}

function disposeMaterial(material: THREE.Material): void {
  const standard = material as THREE.MeshStandardMaterial
  if (standard.map) standard.map.dispose()
  material.dispose()
}

export function disposeGroup(group: THREE.Group): void {
  for (const child of [...group.children]) {
    disposeObject(child)
    group.remove(child)
  }
}
