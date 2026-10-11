// Sol : plan teinté biome (pickable pour les cellules), damier d'accent très
// léger, lignes de grille, cadre périmétrique, et texture optionnelle issue de
// MapVisualAsset (image IA) en surimpression.

import * as THREE from 'three'
import type { GroundSpec } from '../types'
import type { Biome3D, ThemeTokens } from '../core/ThemeProvider'

export interface GroundCtx {
  tokens: ThemeTokens
  biome: Biome3D
}

export class GroundLayer {
  readonly group = new THREE.Group()
  /** Plan de picking plein (invisible) : les cellules de trémie restent cliquables. */
  private plane: THREE.Mesh | null = null
  private buildKey = ''
  private textureUrl: string | null = null
  private assetPlane: THREE.Mesh | null = null

  update(spec: GroundSpec, ctx: GroundCtx): void {
    const key = `${spec.cols}x${spec.rows}|${spec.theme}|${(spec.holes ?? []).join(';')}`
    if (key !== this.buildKey) {
      this.rebuild(spec, ctx)
      this.buildKey = key
      this.textureUrl = null
    }
    this.syncVisualAsset(spec)
  }

  private holes = new Set<string>()

  groundMesh(): THREE.Object3D | null {
    return this.plane
  }

  dispose(): void {
    disposeGroup(this.group)
    this.group.clear()
    this.plane = null
    this.assetPlane = null
    this.buildKey = ''
    this.textureUrl = null
  }

  private rebuild(spec: GroundSpec, ctx: GroundCtx): void {
    this.dispose()
    this.holes = new Set(spec.holes ?? [])
    const { cols, rows } = spec
    const biome = ctx.biome
    const holes = new Set(spec.holes ?? [])

    // Sol visible : une dalle par cellule, sans les trémies (escaliers descendants).
    const floor = new THREE.Mesh(
      buildCellGridGeometry(cols, rows, holes),
      new THREE.MeshStandardMaterial({ color: new THREE.Color(biome.ground), roughness: 0.98 }),
    )
    floor.receiveShadow = true
    this.group.add(floor)

    const plane = new THREE.Mesh(
      new THREE.PlaneGeometry(cols, rows),
      new THREE.MeshBasicMaterial({ visible: false }),
    )
    plane.rotation.x = -Math.PI / 2
    this.plane = plane
    this.group.add(plane)

    // Damier d'accent une cellule sur deux — lisibilité tactique discrète.
    const accentCount = Math.ceil((cols * rows) / 2)
    const accent = new THREE.InstancedMesh(
      new THREE.PlaneGeometry(1, 1),
      new THREE.MeshStandardMaterial({
        color: new THREE.Color(biome.groundAccent),
        roughness: 0.98,
        transparent: true,
        opacity: 0.85,
      }),
      accentCount,
    )
    const matrix = new THREE.Matrix4()
    const rotation = new THREE.Quaternion().setFromEuler(new THREE.Euler(-Math.PI / 2, 0, 0))
    let index = 0
    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        if ((col + row) % 2 !== 0 || holes.has(`${col},${row}`)) continue
        matrix.compose(
          new THREE.Vector3(col + 0.5 - cols / 2, 0.001, row + 0.5 - rows / 2),
          rotation,
          new THREE.Vector3(1, 1, 1),
        )
        accent.setMatrixAt(index++, matrix)
      }
    }
    accent.count = index
    accent.instanceMatrix.needsUpdate = true
    this.group.add(accent)

    // Lignes de grille.
    const positions: number[] = []
    const y = 0.004
    for (let col = 0; col <= cols; col++) {
      positions.push(col - cols / 2, y, -rows / 2, col - cols / 2, y, rows / 2)
    }
    for (let row = 0; row <= rows; row++) {
      positions.push(-cols / 2, y, row - rows / 2, cols / 2, y, row - rows / 2)
    }
    const gridGeometry = new THREE.BufferGeometry()
    gridGeometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
    const grid = new THREE.LineSegments(
      gridGeometry,
      new THREE.LineBasicMaterial({
        color: new THREE.Color(biome.grid),
        transparent: true,
        opacity: biome.gridOpacity,
      }),
    )
    this.group.add(grid)

    // Cadre périmétrique sombre (assise visuelle de la table).
    const frameMaterial = new THREE.MeshStandardMaterial({
      color: new THREE.Color(ctx.tokens.bgElev),
      roughness: 0.9,
    })
    const frameHeight = 0.09
    const thickness = 0.22
    const frames: [number, number, number, number][] = [
      [cols + thickness * 2, thickness, 0, -(rows / 2 + thickness / 2)],
      [cols + thickness * 2, thickness, 0, rows / 2 + thickness / 2],
      [thickness, rows, -(cols / 2 + thickness / 2), 0],
      [thickness, rows, cols / 2 + thickness / 2, 0],
    ]
    for (const [sizeX, sizeZ, x, z] of frames) {
      const bar = new THREE.Mesh(new THREE.BoxGeometry(sizeX, frameHeight, sizeZ), frameMaterial)
      bar.position.set(x, frameHeight / 2 - 0.02, z)
      bar.receiveShadow = true
      this.group.add(bar)
    }

    // Jupe sous le plateau : ce qui est creusé sous le sol (trémies) ne
    // dépasse plus en blocs noirs quand on regarde le plateau de côté.
    const skirtMaterial = new THREE.MeshBasicMaterial({ color: new THREE.Color(ctx.tokens.bg) })
    const skirtDepth = 2.2
    for (const [sizeX, sizeZ, x, z] of frames) {
      const skirt = new THREE.Mesh(new THREE.BoxGeometry(sizeX, skirtDepth, sizeZ), skirtMaterial)
      skirt.position.set(x, -skirtDepth / 2 - 0.02, z)
      this.group.add(skirt)
    }
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
export function buildCellGridGeometry(cols: number, rows: number, holes: Set<string>): THREE.BufferGeometry {
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
        uvs.push((col + dx) / cols, 1 - (row + dz) / rows)
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
