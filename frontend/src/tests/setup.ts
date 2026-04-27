import { vi } from 'vitest'

if (!globalThis.crypto?.randomUUID) {
  vi.stubGlobal('crypto', {
    randomUUID: vi.fn(() => 'test-event-id'),
  })
}
