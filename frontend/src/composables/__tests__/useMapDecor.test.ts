import { describe, expect, it } from 'vitest'

import {
  inferRegionBiome,
  generateRegionDecor,
  resolveMapDecor,
} from '../useMapDecor'

describe('useMapDecor', () => {
  it('does not add a random coastline to default regional decor', () => {
    expect(generateRegionDecor('plain-seed').coastline).toBeUndefined()
  })

  it('infers desert decor without coastline for dunes and oasis', () => {
    const decor = resolveMapDecor(null, 'sables', 'region', "La Piste d'Ambre dune oasis")

    expect(inferRegionBiome("La Piste d'Ambre dune oasis")).toBe('desert')
    expect(decor.coastline).toBeUndefined()
  })

  it('keeps coastline only for explicit coastal corpus', () => {
    const decor = resolveMapDecor(null, 'coast', 'region', 'Port des Brumes côte mer rivage')

    expect(inferRegionBiome('Port des Brumes côte mer rivage')).toBe('coastal')
    expect(decor.coastline).toBeDefined()
  })
})
