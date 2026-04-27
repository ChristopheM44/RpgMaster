import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { sessionApi } from '../../services/api'
import { useSessionStore } from '../session'
import type { Session } from '../../types'

vi.mock('../../services/api', () => ({
  sessionApi: {
    list: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
  },
}))

const sampleSession: Session = {
  id: 'session-1',
  name: 'La Crypte',
  status: 'lobby',
  created_at: '2026-04-26T00:00:00Z',
  updated_at: '2026-04-26T00:00:00Z',
  character_count: 0,
}

describe('useSessionStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(sessionApi.list).mockReset()
    vi.mocked(sessionApi.create).mockReset()
    vi.mocked(sessionApi.delete).mockReset()
  })

  it('loads sessions from the API', async () => {
    vi.mocked(sessionApi.list).mockResolvedValue({ sessions: [sampleSession], total: 1 })
    const store = useSessionStore()

    await store.fetchSessions()

    expect(store.sessions).toEqual([sampleSession])
    expect(store.total).toBe(1)
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('adds a newly created session and selects it', async () => {
    vi.mocked(sessionApi.create).mockResolvedValue(sampleSession)
    const store = useSessionStore()

    const created = await store.createSession('La Crypte')

    expect(sessionApi.create).toHaveBeenCalledWith({ name: 'La Crypte' })
    expect(created).toEqual(sampleSession)
    expect(store.sessions[0]).toEqual(sampleSession)
    expect(store.currentSession).toEqual(sampleSession)
    expect(store.total).toBe(1)
  })
})
