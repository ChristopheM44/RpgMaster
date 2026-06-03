import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import RollCard from '../RollCard.vue'
import type { ExNarrativeEntry } from '../../../fixtures/exploration'

function mountRoll(overrides: Partial<Extract<ExNarrativeEntry, { type: 'roll' }>> = {}) {
  const entry: Extract<ExNarrativeEntry, { type: 'roll' }> = {
    id: 1,
    type: 'roll',
    who: 'Oaken',
    what: 'DEX Save · DD 14',
    rolls: [{ label: '1d20', value: 18, hit: true }],
    ...overrides,
  }
  return mount(RollCard, { props: { entry } })
}

describe('RollCard — espacement (LOT G.2)', () => {
  it('sépare le personnage de son jet (jamais « OakenDEX Save »)', () => {
    const text = mountRoll().text()

    expect(text).toMatch(/Oaken\s+DEX Save/)
    expect(text).not.toContain('OakenDEX')
  })

  it('sépare le libellé du jet de la notation de dé (jamais « DD 141d20 »)', () => {
    const text = mountRoll().text()

    expect(text).toMatch(/DD 14\s+1d20/)
    expect(text).not.toContain('141d20')
  })

  it('sépare la notation de dé du total (jamais « 1d2018 »)', () => {
    const text = mountRoll().text()

    expect(text).toMatch(/1d20\s+18/)
    expect(text).not.toContain('1d2018')
  })
})
