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
  GameStateResponse,
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
}

// ─── Game ──────────────────────────────────────────────────────────────────────

export const gameApi = {
  getState: (sessionId: string) =>
    request<GameStateResponse>(`/game/${sessionId}/state`),

  start: (sessionId: string) =>
    request<{ status: string; phase: string; session_id: string; characters?: number }>(
      `/game/${sessionId}/start`,
      { method: 'POST' },
    ),
}
