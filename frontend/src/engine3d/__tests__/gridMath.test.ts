import { describe, expect, it } from 'vitest'
import {
  cellCenterToWorld,
  clampCell,
  gridDiagonal,
  gridPointToWorld,
  metersToWorld,
  rectCells,
  worldToCell,
} from '../utils/gridMath'

const dims = { cols: 12, rows: 8 }

describe('gridMath', () => {
  it('centre la grille sur l’origine (aller-retour cellule ↔ monde)', () => {
    const world = cellCenterToWorld(0, 0, dims)
    expect(world).toEqual({ x: -5.5, z: -3.5 })
    expect(worldToCell(world.x, world.z, dims)).toEqual({ col: 0, row: 0 })

    const last = cellCenterToWorld(11, 7, dims)
    expect(worldToCell(last.x, last.z, dims)).toEqual({ col: 11, row: 7 })
  })

  it('worldToCell retourne null hors grille', () => {
    expect(worldToCell(-6.2, 0, dims)).toBeNull()
    expect(worldToCell(0, 4.2, dims)).toBeNull()
  })

  it('gridPointToWorld traite les coordonnées continues (coins)', () => {
    expect(gridPointToWorld(6, 4, dims)).toEqual({ x: 0, z: 0 })
  })

  it('convertit les mètres en unités monde via cell_size_m', () => {
    expect(metersToWorld(3, 1.5)).toBe(2)
    expect(metersToWorld(2.5, 1.5)).toBeCloseTo(1.6667, 3)
  })

  it('clampCell borne dans la grille', () => {
    expect(clampCell({ col: -3, row: 99 }, dims)).toEqual({ col: 0, row: 7 })
  })

  it('rectCells énumère les cellules couvertes, bornées à la grille', () => {
    const cells = rectCells(10.5, 6.5, 3, 3, dims)
    expect(cells).toContainEqual({ col: 11, row: 7 })
    expect(cells.every((cell) => cell.col < dims.cols && cell.row < dims.rows)).toBe(true)
  })

  it('gridDiagonal', () => {
    expect(gridDiagonal({ cols: 3, rows: 4 })).toBe(5)
  })
})
