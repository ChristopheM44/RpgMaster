import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import CampaignTransferModal from '../CampaignTransferModal.vue'

describe('CampaignTransferModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('blocks invalid JSON files before previewing the import', async () => {
    const wrapper = mount(CampaignTransferModal, {
      props: { mode: 'import', campaign: null },
      global: { stubs: { Teleport: true } },
    })
    const input = wrapper.find('input[type="file"]')
    const file = new File(['not-json'], 'broken.json', { type: 'application/json' })
    Object.defineProperty(input.element, 'files', {
      value: [file],
      configurable: true,
    })

    await input.trigger('change')
    await flushPromises()

    expect(wrapper.text()).toContain('Le fichier JSON est invalide.')
  })
})
