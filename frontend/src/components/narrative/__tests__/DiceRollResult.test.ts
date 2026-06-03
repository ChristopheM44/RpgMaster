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

  it('keeps tokens separated so copy/screen-reader never concatenates them (LOT G.2)', () => {
    const wrapper = mount(DiceRollResult, {
      props: {
        roll: {
          dice_notation: '1d20',
          rolls: [18],
          total: 18,
          modifier: 0,
          label: 'DEX Save',
          success: true,
          character_name: 'Oaken',
        },
      },
    })

    expect(wrapper.text()).toMatch(/Oaken\s+DEX Save/)
    expect(wrapper.text()).not.toContain('OakenDEX')
  })
})
