import { ref } from 'vue'
import { defineStore } from 'pinia'
import { adminApi } from '../services/api'
import type { TtsSettings, TtsHealthResponse, TtsBackend } from '../types'

export const useSettingsStore = defineStore('settings', () => {
  const ttsEnabled = ref(false)
  const ttsBackend = ref<TtsBackend>('kokoro')
  const ttsAsync = ref(true)
  const voxtralBaseUrl = ref('http://localhost:8091')
  const voxtralModel = ref('mistralai/Voxtral-4B-TTS-2603')

  const health = ref<TtsHealthResponse>({ kokoro: false, vllm: false })
  const loading = ref(false)
  const error = ref<string | null>(null)

  function _applySettings(s: TtsSettings) {
    ttsEnabled.value = s.tts_enabled
    ttsBackend.value = s.tts_backend
    ttsAsync.value = s.tts_async
    voxtralBaseUrl.value = s.voxtral_base_url
    voxtralModel.value = s.voxtral_model
  }

  async function fetchSettings() {
    loading.value = true
    error.value = null
    try {
      const s = await adminApi.getSettings()
      _applySettings(s)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
    } finally {
      loading.value = false
    }
  }

  async function updateSettings(patch: Partial<TtsSettings>) {
    loading.value = true
    error.value = null
    try {
      const s = await adminApi.updateSettings(patch)
      _applySettings(s)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchHealth() {
    try {
      health.value = await adminApi.getTtsHealth()
    } catch {
      health.value = { kokoro: false, vllm: false }
    }
  }

  return {
    ttsEnabled,
    ttsBackend,
    ttsAsync,
    voxtralBaseUrl,
    voxtralModel,
    health,
    loading,
    error,
    fetchSettings,
    updateSettings,
    fetchHealth,
  }
})
