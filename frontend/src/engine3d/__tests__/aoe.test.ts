// Parité STRICTE avec backend/app/engine/aoe.py — les cas « fixtures » sont
// repris de backend/tests/test_engine/test_aoe.py ; toute divergence ici
// signifie que la preview frontend ment sur ce que le moteur résoudrait.
import { describe, expect, it } from 'vitest'
import { aoeCells, circleCells, cubeCells, coneCells, lineCells } from '../adapters/aoe'

const CELL = 1.5
const dims = { cols: 5, rows: 5 }

describe('aoe (miroir backend)', () => {
  it('fixture backend : cercle rayon 1.5 m → 9 cellules autour de (2,2)', () => {
    const cells = circleCells({ col: 2, row: 2 }, 1.5, CELL, dims)
    expect(cells).toHaveLength(9)
    expect(cells).toContainEqual({ col: 2, row: 2 })
    expect(cells).toContainEqual({ col: 1, row: 1 })
    expect(cells).not.toContainEqual({ col: 4, row: 4 })
  })

  it('fixture backend : ligne Bresenham (0,0)→(3,0)', () => {
    expect(lineCells({ col: 0, row: 0 }, { col: 3, row: 0 })).toEqual([
      { col: 0, row: 0 },
      { col: 1, row: 0 },
      { col: 2, row: 0 },
      { col: 3, row: 0 },
    ])
  })

  it('cube : ancré coin haut-gauche, trunc(size/cell), clamp grille', () => {
    // 4.5 m / 1.5 → 3 cellules de côté.
    const cells = cubeCells({ col: 3, row: 3 }, 4.5, CELL, dims)
    expect(cells).toHaveLength(4) // clamp à la grille 5×5 : cols 3-4 × rows 3-4
    expect(cells).toContainEqual({ col: 3, row: 3 })
    expect(cells).toContainEqual({ col: 4, row: 4 })
    // Taille sous une cellule → max(1, …) = 1 cellule.
    expect(cubeCells({ col: 0, row: 0 }, 1.0, CELL, dims)).toEqual([{ col: 0, row: 0 }])
  })

  it('cône : s\'élargit d\'une cellule par pas vers le quadrant de la cible', () => {
    const cells = coneCells({ col: 0, row: 0 }, { col: 3, row: 3 }, 3.0, CELL, dims)
    // 2 pas : pas 1 → centre (1,1) ±1 ; pas 2 → centre (2,2) ±2 (borné grille).
    expect(cells).toContainEqual({ col: 1, row: 1 })
    expect(cells).toContainEqual({ col: 0, row: 1 })
    expect(cells).toContainEqual({ col: 2, row: 1 })
    expect(cells).toContainEqual({ col: 4, row: 2 })
    expect(cells).not.toContainEqual({ col: 0, row: 0 }) // l'origine n'est pas dedans
  })

  it('aoeCells : sphere/cylinder centrés cible, emanation centrée lanceur', () => {
    const base = { sizeM: 1.5, cellSizeM: CELL, origin: { col: 0, row: 0 }, target: { col: 3, row: 3 }, dims }
    const sphere = aoeCells({ ...base, shape: 'sphere' })
    expect(sphere).toContainEqual({ col: 3, row: 3 })
    expect(sphere).not.toContainEqual({ col: 0, row: 0 })

    const emanation = aoeCells({ ...base, shape: 'emanation' })
    expect(emanation).toContainEqual({ col: 0, row: 0 })
    expect(emanation).not.toContainEqual({ col: 3, row: 3 })

    expect(aoeCells({ ...base, shape: 'line' })).toEqual(lineCells({ col: 0, row: 0 }, { col: 3, row: 3 }))
    expect(aoeCells({ ...base, shape: 'forme_inconnue' })).toEqual([])
  })

  it('arrondis : trunc, jamais round (6 m / 1.5 = 4 cellules ; 5.9 m → 3)', () => {
    expect(circleCells({ col: 2, row: 2 }, 6.0, CELL, { cols: 12, rows: 12 }).length).toBe(
      circleCells({ col: 2, row: 2 }, 6.5, CELL, { cols: 12, rows: 12 }).length,
    )
    const r3 = circleCells({ col: 5, row: 5 }, 5.9, CELL, { cols: 12, rows: 12 })
    expect(r3).toContainEqual({ col: 2, row: 2 }) // distance 3 incluse
    expect(r3).not.toContainEqual({ col: 1, row: 1 }) // distance 4 exclue
  })
})
