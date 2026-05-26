import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { sessionApi } from '../services/api'
import type { Session } from '../types'

export type MapScope = 'scene' | 'ville' | 'region'

const LS_MAP_SCOPE = 'rpg.exploration.mapScope'
const LS_CARNET_OPEN = 'rpg.exploration.carnetOpen'

function readScope(): MapScope {
  if (typeof localStorage === 'undefined' || typeof localStorage.getItem !== 'function') return 'scene'
  const stored = localStorage.getItem(LS_MAP_SCOPE)
  return stored === 'ville' || stored === 'region' ? stored : 'scene'
}

function readCarnetOpen(): boolean {
  if (typeof localStorage === 'undefined' || typeof localStorage.getItem !== 'function') return false
  return localStorage.getItem(LS_CARNET_OPEN) === '1'
}

export const useSessionStore = defineStore('session', () => {
  const sessions = ref<Session[]>([])
  const total = ref(0)
  const currentSession = ref<Session | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ── Exploration V2 UI state ─────────────────────────────────────────────
  const selectedId = ref<string | null>(null)
  const highlightedIds = ref<string[]>([])
  const mapScope = ref<MapScope>(readScope())
  const carnetOpen = ref<boolean>(readCarnetOpen())
  /** Récit drawer visible (utilisé par CombatLayout V2 / NarrativeLog drawer). */
  const recitOpen = ref(true)

  watch(mapScope, (v) => {
    if (typeof localStorage !== 'undefined' && typeof localStorage.setItem === 'function') {
      localStorage.setItem(LS_MAP_SCOPE, v)
    }
  })
  watch(carnetOpen, (v) => {
    if (typeof localStorage !== 'undefined' && typeof localStorage.setItem === 'function') {
      localStorage.setItem(LS_CARNET_OPEN, v ? '1' : '0')
    }
  })

  // Changer de scope vide la sélection (un POI de scène n'existe pas en région).
  watch(mapScope, () => {
    selectedId.value = null
    highlightedIds.value = []
  })

  async function fetchSessions() {
    loading.value = true
    error.value = null
    try {
      const data = await sessionApi.list()
      sessions.value = data.sessions
      total.value = data.total
    } catch {
      error.value = 'Impossible de charger les sessions.'
    } finally {
      loading.value = false
    }
  }

  async function createSession(name: string): Promise<Session | null> {
    loading.value = true
    error.value = null
    try {
      const session = await sessionApi.create({ name })
      sessions.value.unshift(session)
      total.value++
      currentSession.value = session
      return session
    } catch {
      error.value = 'Impossible de créer la session.'
      return null
    } finally {
      loading.value = false
    }
  }

  async function deleteSession(id: string) {
    error.value = null
    try {
      await sessionApi.delete(id)
      sessions.value = sessions.value.filter((s) => s.id !== id)
      total.value--
      if (currentSession.value?.id === id) currentSession.value = null
    } catch {
      error.value = 'Impossible de supprimer la session.'
    }
  }

  function setCurrentSession(session: Session) {
    currentSession.value = session
  }

  // ── Actions Exploration V2 ──────────────────────────────────────────────
  function selectEntity(id: string | null) {
    selectedId.value = id && id === selectedId.value ? null : id
  }

  function setHighlighted(ids: string[] | string | null) {
    if (ids === null) {
      highlightedIds.value = []
      return
    }
    highlightedIds.value = Array.isArray(ids) ? ids : [ids]
  }

  function setMapScope(scope: MapScope) {
    mapScope.value = scope
  }

  function toggleCarnet(open?: boolean) {
    carnetOpen.value = open === undefined ? !carnetOpen.value : open
  }

  /** Action de déplacement de groupe — TODO: brancher backend (WS event ou REST). */
  function moveParty(_destId: string) {
    // TODO: brancher backend — émettre un événement "party_move" via WebSocket
    selectedId.value = null
  }

  return {
    sessions,
    total,
    currentSession,
    loading,
    error,
    // V2 UI state
    selectedId,
    highlightedIds,
    mapScope,
    carnetOpen,
    recitOpen,
    // Actions REST
    fetchSessions,
    createSession,
    deleteSession,
    setCurrentSession,
    // Actions UI
    selectEntity,
    setHighlighted,
    setMapScope,
    toggleCarnet,
    moveParty,
  }
})
