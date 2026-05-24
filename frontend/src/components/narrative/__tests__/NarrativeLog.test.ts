import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import { useGameStore } from '../../../stores/game'
import NarrativeLog from '../NarrativeLog.vue'

describe('NarrativeLog thinking state', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows GM thinking by default while processing', () => {
    const store = useGameStore()
    store.setProcessing(true)

    const wrapper = mount(NarrativeLog)

    expect(wrapper.text()).toContain('Le Maître du Jeu réfléchit')
  })

  it('shows player AI thinking when a companion is active', async () => {
    const store = useGameStore()
    const wrapper = mount(NarrativeLog)

    store.applyAiThinking({
      agent_kind: 'player_ai',
      thinking: true,
      character_id: 'shade',
      character_name: 'Shade',
    })
    await nextTick()

    expect(wrapper.text()).toContain('Le joueur IA réfléchit')

    store.applyAiThinking({
      agent_kind: 'player_ai',
      thinking: false,
      character_id: 'shade',
    })
    await nextTick()

    expect(wrapper.text()).not.toContain('Le joueur IA réfléchit')
  })
})
