import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useCounterStore } from '../counter'

describe('useCounterStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('increments the count and updates the derived double count', () => {
    const store = useCounterStore()

    store.increment()

    expect(store.count).toBe(1)
    expect(store.doubleCount).toBe(2)
  })
})
