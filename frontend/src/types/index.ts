export type SessionStatus =
  | 'lobby'
  | 'character_creation'
  | 'exploration'
  | 'encounter_start'
  | 'combat'
  | 'encounter_end'
  | 'rest'
  | 'level_up'
  | 'session_end'

export interface Session {
  id: string
  name: string
  status: SessionStatus
  created_at: string
  updated_at: string
}

export interface SessionListResponse {
  sessions: Session[]
  total: number
}

export interface SessionCreate {
  name: string
}

export interface SessionUpdate {
  name?: string
  status?: SessionStatus
}
