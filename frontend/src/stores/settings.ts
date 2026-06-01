import { ref } from 'vue'
import { defineStore } from 'pinia'
import { adminApi } from '../services/api'
import type { TtsSettings, TtsHealthResponse, TtsBackend, TtsVoiceSettings } from '../types'

const DEFAULT_GM_VOICE: TtsVoiceSettings = {
  preset_id: 'ff_siwis',
  voice_id_local: 'ff_siwis',
  lang: 'fr-fr',
  speed: 0.9,
}

export const useSettingsStore = defineStore('settings', () => {
  const ttsEnabled = ref(false)
  const ttsBackend = ref<TtsBackend>('kokoro')
  const ttsAsync = ref(true)
  const voxtralBaseUrl = ref('http://localhost:8091')
  const voxtralModel = ref('mistralai/Voxtral-4B-TTS-2603')
  const gmVoice = ref<TtsVoiceSettings>({ ...DEFAULT_GM_VOICE })
  const npcVoiceEnabled = ref(true)

  const health = ref<TtsHealthResponse>({ kokoro: false, vllm: false })
  const loading = ref(false)
  const error = ref<string | null>(null)

  function _applySettings(s: TtsSettings) {
    ttsEnabled.value = s.tts_enabled
    ttsBackend.value = s.tts_backend
    ttsAsync.value = s.tts_async
    voxtralBaseUrl.value = s.voxtral_base_url
    voxtralModel.value = s.voxtral_model
    gmVoice.value = { ...DEFAULT_GM_VOICE, ...s.gm_voice }
    npcVoiceEnabled.value = s.npc_voice_enabled
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
    gmVoice,
    npcVoiceEnabled,
    health,
    loading,
    error,
    fetchSettings,
    updateSettings,
    fetchHealth,
  }
})
