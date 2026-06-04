import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { campaignApi } from '../../services/api'
import { useCampaignStore } from '../campaign'
import type { Campaign } from '../../types'

vi.mock('../../services/api', () => ({
  campaignApi: {
    list: vi.fn(),
    create: vi.fn(),
    get: vi.fn(),
    getScenario: vi.fn(),
    getGmDossier: vi.fn(),
    exportChronicle: vi.fn(),
    previewChronicleImport: vi.fn(),
    importChronicle: vi.fn(),
    importSource: vi.fn(),
    forgeDraft: vi.fn(),
    startForgeDraftJob: vi.fn(),
    getForgeDraftJob: vi.fn(),
    validateContract: vi.fn(),
    attachSession: vi.fn(),
    advance: vi.fn(),
    reset: vi.fn(),
    delete: vi.fn(),
  },
}))

function campaign(overrides: Partial<Campaign> = {}): Campaign {
  return {
    id: 'campaign-1',
    name: 'Brumes',
    description: '',
    starting_level: 1,
    session_ids: ['old-session', 'current-session'],
    current_session_index: 1,
    character_ids: ['char-1'],
    xp_pool: { 'char-1': 300 },
    created_at: '2026-05-14T00:00:00Z',
    updated_at: '2026-05-14T00:00:00Z',
    tagline: '',
    generation_status: 'validated',
    active_chapter: {},
    progress: { done: 1, total: 2 },
    counts: {
      sessions: 2,
      characters: 1,
      quests_active: 1,
      quests_done: 0,
      chronicle_entries: 2,
      npcs: 1,
      places: 1,
    },
    ...overrides,
  }
}

describe('useCampaignStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('replaces a reset campaign and invalidates cached dossier data', async () => {
    const store = useCampaignStore()
    const before = campaign()
    const after = campaign({
      session_ids: ['current-session'],
      current_session_index: 0,
      xp_pool: {},
      counts: { ...before.counts, sessions: 1, quests_active: 0, chronicle_entries: 0 },
    })
    store.campaigns = [before]
    store.currentCampaign = before
    store.scenarios = { 'campaign-1': { played_summary: 'ancien joué' } as never }
    store.gmDossiers = { 'campaign-1': { active_chapter_id: 'chapter_2' } as never }
    vi.mocked(campaignApi.reset).mockResolvedValue({
      campaign: after,
      session_id: 'current-session',
      characters_reset: 1,
      sessions_removed: 1,
    })

    const result = await store.resetCampaign('campaign-1')

    expect(result?.campaign).toEqual(after)
    expect(store.campaigns[0]).toEqual(after)
    expect(store.currentCampaign).toEqual(after)
    expect(store.scenarios['campaign-1']).toBeUndefined()
    expect(store.gmDossiers['campaign-1']).toBeUndefined()
  })

  it('adds an imported chronicle and invalidates cached dossier data', async () => {
    const store = useCampaignStore()
    const imported = campaign({ id: 'campaign-imported', name: 'Archive' })
    store.campaigns = [campaign()]
    store.scenarios = { 'campaign-imported': { played_summary: 'ancien' } as never }
    store.gmDossiers = { 'campaign-imported': { active_chapter_id: 'chapter_1' } as never }
    vi.mocked(campaignApi.importChronicle).mockResolvedValue({
      campaign: imported,
      active_session_id: 'current-session',
      imported: { sessions: 1, characters: 1, messages: 2, save_slots: 1 },
      warnings: [],
    })

    const result = await store.importChronicle({
      format: 'rpgmaster.chronicle',
      format_version: 1,
    })

    expect(result?.campaign).toEqual(imported)
    expect(store.campaigns[0]).toEqual(imported)
    expect(store.currentCampaign).toEqual(imported)
    expect(store.scenarios['campaign-imported']).toBeUndefined()
    expect(store.gmDossiers['campaign-imported']).toBeUndefined()
  })
})
