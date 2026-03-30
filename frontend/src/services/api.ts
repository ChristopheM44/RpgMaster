import type { Session, SessionCreate, SessionListResponse, SessionUpdate } from '../types'

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
