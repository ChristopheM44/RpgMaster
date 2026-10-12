import { describe, expect, it } from 'vitest'
import * as THREE from 'three'
import { buildPawn, buildProceduralElement, buildScatterObject, proceduralPropKeyFor } from '../assets/ProceduralFactory'
import { PROCEDURAL_PROP_KEYS } from '../assets/propCatalog.generated'
import { applyTint } from '../layers/ElementsLayer'
import { resolveThemeTokens, BIOME_3D, type ScatterKind } from '../core/ThemeProvider'
import { makePrng } from '../utils/seededRandom'
import type { ElementSpec } from '../types'

const tokens = resolveThemeTokens()
const ctx = { dims: { cols: 12, rows: 12 }, cellSizeM: 1.5, tokens }

function spec(kind: string, geometry: ElementSpec['geometry']): ElementSpec {
  return {
    id: `el_${kind}`,
    name: `Élément ${kind}`,
    kind,
    geometry,
    terrainType: kind === 'terrain' ? 'water' : null,
    heightM: 1.2,
    elevationM: 0,
    subtle: false,
    interactive: false,
    inspectable: true,
    selected: false,
    modelKey: null,
    tint: null,
    facing: null,
    verticalDirection: null,
  }
}

const KNOWN_KINDS = ['wall', 'door', 'window', 'furniture', 'cover', 'hazard', 'light', 'stairs', 'terrain', 'decor']

describe('ProceduralFactory', () => {
  it('rend un mesh pour CHAQUE kind connu, en line/rect/ellipse', () => {
    const geometries: ElementSpec['geometry'][] = [
      { type: 'line', from: { col: 1, row: 1 }, to: { col: 5, row: 1 } },
      { type: 'rect', col: 2, row: 2, width: 2, height: 1 },
      { type: 'ellipse', col: 6, row: 6, radius_col: 1, radius_row: 0.5 },
    ]
    for (const kind of KNOWN_KINDS) {
      for (const geometry of geometries) {
        const object = buildProceduralElement(spec(kind, geometry), ctx)
        expect(object, `${kind}/${geometry.type}`).toBeInstanceOf(THREE.Object3D)
        expect(object.children.length, `${kind}/${geometry.type} sans mesh`).toBeGreaterThan(0)
      }
    }
  })

  it('un kind INCONNU (inventé par le LLM) retombe sur le rendu décor — jamais null', () => {
    const object = buildProceduralElement(
      spec('cristal_chantant_geant', { type: 'rect', col: 1, row: 1, width: 1, height: 1 }),
      ctx,
    )
    expect(object).toBeInstanceOf(THREE.Object3D)
    expect(object.children.length).toBeGreaterThan(0)
  })

  it('le pion procédural a socle + corps + tête, teinté accent', () => {
    const pawn = buildPawn('#c090ff', 1.13)
    expect(pawn.children.length).toBeGreaterThanOrEqual(3)
  })

  it('chaque ScatterKind référencé par un biome produit un objet', () => {
    const rand = makePrng('test')
    const kinds = new Set<ScatterKind>(Object.values(BIOME_3D).flatMap((biome) => biome.scatter))
    kinds.add('torch')
    for (const kind of kinds) {
      const object = buildScatterObject(kind, rand, tokens)
      expect(object.children.length, kind).toBeGreaterThan(0)
    }
  })

  it('lot 4 : chaque prop procédural nommé (fontaine, autel…) est dessiné', () => {
    for (const key of PROCEDURAL_PROP_KEYS) {
      const object = buildProceduralElement(
        { ...spec('decor', { type: 'rect', col: 2, row: 2, width: 1, height: 2 }), modelKey: key },
        ctx,
      )
      let meshes = 0
      object.traverse((node) => { if ((node as THREE.Mesh).isMesh) meshes += 1 })
      expect(meshes, key).toBeGreaterThan(0)
    }
  })

  it('lot 4 : le nom suffit à choisir le prop procédural, un hint GLB explicite prime', () => {
    const fountain = { ...spec('decor', { type: 'rect', col: 2, row: 2, width: 1, height: 1 }), name: 'Fontaine tarie' }
    expect(proceduralPropKeyFor(fountain)).toBe('proc/fountain')
    expect(proceduralPropKeyFor({ ...fountain, modelKey: 'prop/pot' })).toBeNull()
    expect(proceduralPropKeyFor({ ...fountain, kind: 'wall' })).toBeNull()
  })

  it('lot 4 : la teinte clone les matériaux (ne grise pas les autres instances)', () => {
    const shared = new THREE.MeshStandardMaterial({ color: '#336633' })
    const a = new THREE.Mesh(new THREE.BoxGeometry(), shared)
    const b = new THREE.Mesh(new THREE.BoxGeometry(), shared)
    applyTint(a, 'petrified')
    expect(a.material).not.toBe(shared)
    expect(b.material).toBe(shared)
    expect(shared.color.getHexString()).toBe('336633')
    const cache = new Map<string, THREE.Material>()
    const c = new THREE.Mesh(new THREE.BoxGeometry(), shared)
    const d = new THREE.Mesh(new THREE.BoxGeometry(), shared)
    applyTint(c, 'sand', cache)
    applyTint(d, 'sand', cache)
    expect(c.material).toBe(d.material)
  })
})
