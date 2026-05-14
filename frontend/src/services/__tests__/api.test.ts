import { afterEach, describe, expect, it, vi } from 'vitest'

import { campaignApi, sessionApi } from '../api'

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

    const [, options] = fetchMock.mock.calls[0]
    expect(fetchMock.mock.calls[0][0]).toBe('http://localhost:8000/api/sessions?skip=2&limit=5')
    expect((options.headers as Headers).get('Content-Type')).toBe('application/json')
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

describe('campaignApi', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('posts campaign reset requests', async () => {
    const payload = {
      campaign: {
        id: 'campaign-1',
        name: 'Brumes',
        description: '',
        starting_level: 1,
        session_ids: ['session-1'],
        current_session_index: 0,
        character_ids: [],
        xp_pool: {},
        created_at: '2026-05-14T00:00:00Z',
        updated_at: '2026-05-14T00:00:00Z',
        tagline: '',
        generation_status: 'empty',
        active_chapter: {},
        progress: { done: 0, total: 1 },
        counts: {
          sessions: 1,
          characters: 0,
          quests_active: 0,
          quests_done: 0,
          chronicle_entries: 0,
          npcs: 0,
          places: 0,
        },
      },
      session_id: 'session-1',
      characters_reset: 0,
      sessions_removed: 0,
    }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(payload),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(campaignApi.reset('campaign-1')).resolves.toEqual(payload)

    const [, options] = fetchMock.mock.calls[0]
    expect(fetchMock.mock.calls[0][0]).toBe(
      'http://localhost:8000/api/campaigns/campaign-1/reset',
    )
    expect(options.method).toBe('POST')
  })
})
