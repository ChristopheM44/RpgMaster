import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import DiceRollResult from '../DiceRollResult.vue'

describe('DiceRollResult', () => {
  it('renders normalized roll payloads from the backend', () => {
    const wrapper = mount(DiceRollResult, {
      props: {
        roll: {
          dice_notation: '1d20',
          rolls: [20],
          total: 25,
          modifier: 5,
          label: 'Attaque',
          success: true,
          character_name: 'Thorvald',
        },
      },
    })

    expect(wrapper.text()).toContain('Thorvald')
    expect(wrapper.text()).toContain('Attaque')
    expect(wrapper.text()).toContain('1d20')
    expect(wrapper.text()).toContain('20')
    expect(wrapper.text()).toContain('= 25')
    expect(wrapper.text()).toContain('Succès')
  })
})
