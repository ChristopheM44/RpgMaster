import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import NarrativeColumn from '../NarrativeColumn.vue'
import { useGameStore } from '../../../stores/game'

const NarrativeEntryStub = {
  props: ['entry'],
  template: '<article data-testid="narrative-entry">{{ entry.type }}</article>',
}

describe('NarrativeColumn', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('opens the filter menu and filters visible entries by type', async () => {
    const gameStore = useGameStore()
    gameStore.addNarration({ text: 'Le vent se lève.', entry_kind: 'narration' })
    gameStore.addPlayerEntry('Je tends la torche.', 'Thorvald')
    gameStore.addRollResult({
      dice_notation: '1d20+2',
      rolls: [14],
      total: 16,
      modifier: 2,
      dc: 12,
      label: 'Investigation',
      success: true,
      character_name: 'Thorvald',
    })

    const wrapper = mount(NarrativeColumn, {
      global: {
        stubs: {
          NarrativeEntry: NarrativeEntryStub,
        },
      },
    })

    expect(wrapper.findAll('[data-testid="narrative-entry"]')).toHaveLength(3)

    await wrapper.find('[data-testid="narrative-filter-toggle"]').trigger('click')
    expect(wrapper.find('[data-testid="narrative-filter-menu"]').exists()).toBe(true)

    const rollFilter = wrapper.findAll('.narrative-filter-option')
      .find((button) => button.text().includes('Jets'))
    expect(rollFilter).toBeTruthy()
    await rollFilter!.trigger('click')

    const entries = wrapper.findAll('[data-testid="narrative-entry"]')
    expect(entries).toHaveLength(1)
    expect(entries[0]?.text()).toBe('roll')
    expect(wrapper.text()).toContain('1/3 entrées')
    expect(wrapper.find('[data-testid="narrative-filter-toggle"]').text()).toContain('Jets')
  })
})
