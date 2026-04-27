import { afterEach, describe, expect, it, vi } from 'vitest'

import { sessionApi } from '../api'

describe('sessionApi', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('builds list requests with pagination parameters', async () => {
    const payload = { sessions: [], total: 0 }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(payload),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(sessionApi.list(2, 5)).resolves.toEqual(payload)

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/sessions?skip=2&limit=5',
      expect.objectContaining({
        headers: { 'Content-Type': 'application/json' },
      }),
    )
  })

  it('throws a useful error when the API response is not ok', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        text: vi.fn().mockResolvedValue('boom'),
      }),
    )

    await expect(sessionApi.get('missing')).rejects.toThrow('API 500: boom')
  })
})
