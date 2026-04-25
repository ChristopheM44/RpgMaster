import type {
  Session,
  SessionCreate,
  SessionListResponse,
  SessionUpdate,
  SrdSpecies,
  SrdClass,
  SrdSpell,
  SrdMonster,
  SrdEquipmentItem,
  Character,
  CharacterCreate,
  CharacterUpdate,
  CharacterListResponse,
  PregenTemplate,
  GameStateResponse,
  SaveSlot,
  SaveSlotListResponse,
  HistoryResponse,
  TtsSettings,
  TtsHealthResponse,
  OllamaHealthResponse,
  LlmSettings,
  LlmSettingsUpdate,
} from '../types'

const BASE_URL = 'http://localhost:8000/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API ${res.status}: ${text}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// ─── Sessions ─────────────────────────────────────────────────────────────────

export const sessionApi = {
  list: (skip = 0, limit = 20) =>
    request<SessionListResponse>(`/sessions?skip=${skip}&limit=${limit}`),

  create: (data: SessionCreate) =>
    request<Session>('/sessions', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  get: (id: string) => request<Session>(`/sessions/${id}`),

  update: (id: string, data: SessionUpdate) =>
    request<Session>(`/sessions/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (id: string) =>
    request<void>(`/sessions/${id}`, { method: 'DELETE' }),
}

// ─── SRD ──────────────────────────────────────────────────────────────────────

export const srdApi = {
  listSpecies: () =>
    request<{ species: SrdSpecies[]; total: number }>('/srd/species'),

  getSpecies: (id: string) => request<SrdSpecies>(`/srd/species/${id}`),

  listClasses: () =>
    request<{ classes: SrdClass[]; total: number }>('/srd/classes'),

  getClass: (id: string) => request<SrdClass>(`/srd/classes/${id}`),

  listSpells: (params?: { level?: number; charClass?: string }) => {
    const qs = new URLSearchParams()
    if (params?.level !== undefined) qs.set('level', String(params.level))
    if (params?.charClass) qs.set('char_class', params.charClass)
    const query = qs.toString() ? `?${qs}` : ''
    return request<{ spells: SrdSpell[]; total: number }>(`/srd/spells${query}`)
  },

  getSpell: (id: string) => request<SrdSpell>(`/srd/spells/${id}`),

  listMonsters: (maxCr?: number) => {
    const query = maxCr !== undefined ? `?max_cr=${maxCr}` : ''
    return request<{ monsters: SrdMonster[]; total: number }>(`/srd/monsters${query}`)
  },

  getMonster: (id: string) => request<SrdMonster>(`/srd/monsters/${id}`),

  listEquipment: (category?: string) => {
    const query = category ? `?category=${encodeURIComponent(category)}` : ''
    return request<{ equipment: SrdEquipmentItem[]; total: number }>(`/srd/equipment${query}`)
  },

  getEquipment: (id: string) => request<SrdEquipmentItem>(`/srd/equipment/${id}`),
}

// ─── Characters ───────────────────────────────────────────────────────────────

export const characterApi = {
  list: (sessionId?: string) =>
    request<CharacterListResponse>(
      `/characters${sessionId ? `?session_id=${sessionId}` : ''}`,
    ),

  create: (data: CharacterCreate) =>
    request<Character>('/characters', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  get: (id: string) => request<Character>(`/characters/${id}`),

  update: (id: string, data: CharacterUpdate) =>
    request<Character>(`/characters/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (id: string) => request<void>(`/characters/${id}`, { method: 'DELETE' }),

  inventoryEquip: (id: string, itemId: string) =>
    request<Character>(`/characters/${id}/inventory/equip`, {
      method: 'POST',
      body: JSON.stringify({ item_id: itemId }),
    }),

  inventoryUse: (id: string, itemId: string) =>
    request<Character>(`/characters/${id}/inventory/use`, {
      method: 'POST',
      body: JSON.stringify({ item_id: itemId }),
    }),

  inventoryDrop: (id: string, itemId: string) =>
    request<Character>(`/characters/${id}/inventory/drop`, {
      method: 'POST',
      body: JSON.stringify({ item_id: itemId }),
    }),
}

// ─── Game ──────────────────────────────────────────────────────────────────────

export const gameApi = {
  getState: (sessionId: string) =>
    request<GameStateResponse>(`/game/${sessionId}/state`),

  start: (
    sessionId: string,
    body?: { adventure_script?: string; auto_generate?: boolean },
  ) =>
    request<{ status: string; phase: string; session_id: string; characters?: number }>(
      `/game/${sessionId}/start`,
      { method: 'POST', body: body ? JSON.stringify(body) : undefined },
    ),

  getHistory: (sessionId: string, limit = 100) =>
    request<HistoryResponse>(`/game/${sessionId}/history?limit=${limit}`),
}

// ─── Save / Load ───────────────────────────────────────────────────────────────

export const saveApi = {
  list: (sessionId: string) =>
    request<SaveSlotListResponse>(`/game/${sessionId}/saves`),

  create: (sessionId: string, name: string) =>
    request<SaveSlot>(`/game/${sessionId}/saves`, {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),

  load: (sessionId: string, saveId: string) =>
    request<{ status: string; save_id: string; phase: string; session_id: string }>(
      `/game/${sessionId}/saves/${saveId}/load`,
      { method: 'POST' },
    ),

  delete: (sessionId: string, saveId: string) =>
    request<void>(`/game/${sessionId}/saves/${saveId}`, { method: 'DELETE' }),
}

// ─── Pregen ───────────────────────────────────────────────────────────────────

export const pregenApi = {
  list: () => request<PregenTemplate[]>('/characters/pregenerated'),

  create: (
    classId: string,
    body: { session_id: string; name?: string; player_name?: string; is_ai?: boolean },
  ) =>
    request<Character>(`/characters/pregenerated/${classId}`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}

// ─── Admin ─────────────────────────────────────────────────────────────────────

export const adminApi = {
  getSettings: () => request<TtsSettings>('/admin/settings'),

  updateSettings: (data: Partial<TtsSettings>) =>
    request<TtsSettings>('/admin/settings', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  getTtsHealth: () => request<TtsHealthResponse>('/admin/tts/health'),

  getLlmHealth: () => request<OllamaHealthResponse>('/admin/llm/health'),

  getLlmSettings: () => request<LlmSettings>('/admin/llm/settings'),

  updateLlmSettings: (data: LlmSettingsUpdate) =>
    request<LlmSettings>('/admin/llm/settings', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  pingLlm: () =>
    request<{ ok: boolean; provider: string; model: string; latency_ms?: number; sample_response?: string; error?: string }>(
      '/admin/llm/ping',
      { method: 'POST' },
    ),
}
