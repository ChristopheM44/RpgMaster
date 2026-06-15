import { describe, expect, it } from 'vitest'
import * as THREE from 'three'
import {
  elementPlacementWorld,
  instantiateElementModel,
  stairsRotationY,
  wallAxisRotationY,
  type ElementPlacement,
} from '../layers/ElementsLayer'
import type { LoadedModel } from '../assets/AssetRegistry'
import type { ElementSpec } from '../types'

const ctx = {
  dims: { cols: 12, rows: 12 },
  cellSizeM: 1.5,
} as never

function model(size: THREE.Vector3, center = new THREE.Vector3()): LoadedModel {
  return {
    key: 'test',
    prototype: new THREE.Group(),
    animations: [],
    size,
    min: new THREE.Vector3(-size.x / 2, 0, -size.z / 2),
    center,
    minY: 0,
    skinned: false,
  }
}

function spec(overrides: Partial<ElementSpec>): ElementSpec {
  return {
    id: 'element',
    name: 'Element',
    kind: 'wall',
    geometry: { type: 'rect', col: 0, row: 0, width: 1, height: 1 },
    terrainType: null,
    heightM: 2.5,
    elevationM: 0,
    subtle: false,
    interactive: false,
    inspectable: false,
    selected: false,
    modelKey: null,
    facing: null,
    verticalDirection: null,
    ...overrides,
  }
}

describe('ElementsLayer KayKit placement helpers', () => {
  it('oriente les portes selon la face du mur', () => {
    expect(wallAxisRotationY('north', { x: 1, z: 0.3 })).toBe(0)
    expect(wallAxisRotationY('east', { x: 0.3, z: 1 })).toBeCloseTo(-Math.PI / 2)
    expect(wallAxisRotationY(null, { x: 0.3, z: 1 })).toBeCloseTo(-Math.PI / 2)
  })

  it('inverse les escaliers montant/descendant par rapport au facing', () => {
    expect(stairsRotationY('north', 'down', { x: 1, z: 1 })).toBe(0)
    expect(stairsRotationY('north', 'up', { x: 1, z: 1 })).toBeCloseTo(Math.PI)
    expect(stairsRotationY('east', 'down', { x: 1, z: 1 })).toBeCloseTo(-Math.PI / 2)
  })

  it('recale les accès de bord sur la ligne du mur', () => {
    const northDoor = spec({
      kind: 'door',
      geometry: { type: 'rect', col: 5, row: 0, width: 1, height: 0.24 },
      facing: 'north',
    })
    const eastStairs = spec({
      kind: 'stairs',
      geometry: { type: 'rect', col: 11, row: 6, width: 1, height: 1 },
      facing: 'east',
      verticalDirection: 'down',
    })
    const centerStairs = spec({
      kind: 'stairs',
      geometry: { type: 'rect', col: 2.5, row: 6, width: 1.2, height: 1.2 },
      facing: 'south',
      verticalDirection: 'up',
    })

    expect(elementPlacementWorld(northDoor, ctx).center.z).toBeCloseTo(-6)
    expect(elementPlacementWorld(eastStairs, ctx).center.x).toBeCloseTo(6)
    expect(elementPlacementWorld(centerStairs, ctx).center.z).not.toBeCloseTo(6)
  })

  it('scale les murs KayKit sur la longueur, pas sur l’épaisseur', () => {
    const wall = spec({
      kind: 'wall',
      geometry: { type: 'line', from: { col: 0, row: 0 }, to: { col: 3, row: 0 } },
    })
    const placement = elementPlacementWorld(wall, ctx)
    const object = instantiateElementModel(model(new THREE.Vector3(4, 4, 1)), 'prop/wall', wall, placement, ctx)
    const firstSegment = object.children[0]?.children[0] as THREE.Object3D | undefined

    expect(object.children).toHaveLength(3)
    expect(firstSegment).toBeDefined()
    expect(firstSegment!.scale.x).toBeGreaterThan(firstSegment!.scale.z)
    expect(firstSegment!.scale.x).toBeCloseTo((1 + 0.025) / 4)
  })

  it('rend les escaliers sans plafond maxHeight dérivé de height_m=0.4', () => {
    const stairs = spec({
      kind: 'stairs',
      geometry: { type: 'rect', col: 5, row: 0, width: 1, height: 1 },
      heightM: 0.4,
      facing: 'north',
      verticalDirection: 'down',
    })
    const placement: ElementPlacement = elementPlacementWorld(stairs, ctx)
    const object = instantiateElementModel(
      model(new THREE.Vector3(5, 5.1, 4), new THREE.Vector3(0, 2.55, 2)),
      'prop/stairs',
      stairs,
      placement,
      ctx,
    )
    const instance = object.children[0] as THREE.Object3D | undefined

    expect(instance).toBeDefined()
    expect(instance!.scale.y).toBeCloseTo(0.2)
    // stairs.glb monte vers -Z (rotationOffsetY=π) : facing=north + down → visualFacing=south
    // (rotation géométrique 0) + offset π.
    expect(object.rotation.y).toBeCloseTo(Math.PI)
  })
})
