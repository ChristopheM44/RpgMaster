import { defineStore } from 'pinia'
import { ref } from 'vue'
import { sessionApi } from '../services/api'
import type { Session } from '../types'

export const useSessionStore = defineStore('session', () => {
  const sessions = ref<Session[]>([])
  const total = ref(0)
  const currentSession = ref<Session | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

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

  return {
    sessions,
    total,
    currentSession,
    loading,
    error,
    fetchSessions,
    createSession,
    deleteSession,
    setCurrentSession,
  }
})
