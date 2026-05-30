import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import MapTooltip from '../MapTooltip.vue'

describe('MapTooltip', () => {
  it('renders readable entity details', () => {
    const wrapper = mount(MapTooltip, {
      props: {
        x: 120,
        y: 120,
        boundsWidth: 480,
        boundsHeight: 480,
        entity: {
          entityType: 'poi',
          id: 'vibration_sol',
          kind: 'clue',
          label: 'Indice',
          title: 'Vibration anormale',
          description: 'Une onde légère fait tinter les verres.',
          coordinate: 'E5',
          tone: 'gold',
          actionLabel: 'Se renseigner',
        },
      },
    })

    expect(wrapper.text()).toContain('Indice')
    expect(wrapper.text()).toContain('E5')
    expect(wrapper.text()).toContain('Vibration anormale')
    expect(wrapper.text()).toContain('Action : Se renseigner')
  })
})
