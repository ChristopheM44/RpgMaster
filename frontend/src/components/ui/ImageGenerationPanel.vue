<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { adminApi } from '../../services/api'
import type { ImageGenerationProvider, ImageGenerationSettingsUpdate } from '../../types'

const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const saveSuccess = ref(false)

const enabled = ref(false)
const provider = ref<ImageGenerationProvider>('openai_compatible')
const baseUrl = ref('')
const model = ref('')
const size = ref('1024x1024')
const apiKeyInput = ref('')
const apiKeySet = ref(false)
const clearApiKey = ref(false)

async function loadSettings() {
  loading.value = true
  error.value = null
  try {
    const settings = await adminApi.getImageGenerationSettings()
    enabled.value = settings.enabled
    provider.value = settings.provider
    baseUrl.value = settings.base_url
    model.value = settings.model
    size.value = settings.size
    apiKeySet.value = settings.api_key_set
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Paramètres image indisponibles'
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  saving.value = true
  saveSuccess.value = false
  error.value = null
  try {
    const payload: ImageGenerationSettingsUpdate = {
      enabled: enabled.value,
      provider: provider.value,
      base_url: baseUrl.value,
      model: model.value,
      size: size.value,
    }
    if (clearApiKey.value) payload.api_key = ''
    else if (apiKeyInput.value) payload.api_key = apiKeyInput.value

    const updated = await adminApi.updateImageGenerationSettings(payload)
    enabled.value = updated.enabled
    provider.value = updated.provider
    baseUrl.value = updated.base_url
    model.value = updated.model
    size.value = updated.size
    apiKeySet.value = updated.api_key_set
    apiKeyInput.value = ''
    clearApiKey.value = false
    saveSuccess.value = true
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Erreur lors de la sauvegarde image'
  } finally {
    saving.value = false
  }
}

function handleClearApiKey() {
  clearApiKey.value = true
  apiKeyInput.value = ''
}

onMounted(loadSettings)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-xl font-bold text-parchment">Génération image</h2>
      <p class="text-sm text-parchment/60 mt-1">
        Configure le modèle qui préparera les fonds vue du dessus des cartes.
      </p>
    </div>

    <label class="flex items-center justify-between gap-4 rounded-lg border border-parchment/10 bg-ink/40 p-4">
      <span>
        <span class="block font-medium text-parchment">Activer les prompts image</span>
        <span class="block text-sm text-parchment/50">
          Les cartes restent procédurales si aucune image n'est générée.
        </span>
      </span>
      <input
        v-model="enabled"
        type="checkbox"
        class="h-5 w-5 accent-gold"
      />
    </label>

    <div class="space-y-2">
      <label class="block text-sm font-medium text-parchment/80">Provider</label>
      <div class="grid grid-cols-2 gap-2">
        <button
          :class="[
            'rounded-lg border px-4 py-2.5 text-sm font-medium transition-colors',
            provider === 'openai_compatible'
              ? 'bg-arcane/20 border-arcane/60 text-arcane'
              : 'bg-ink/40 border-parchment/20 text-parchment/60 hover:border-parchment/40',
          ]"
          type="button"
          @click="provider = 'openai_compatible'"
        >
          OpenAI-compatible
        </button>
        <button
          :class="[
            'rounded-lg border px-4 py-2.5 text-sm font-medium transition-colors',
            provider === 'local'
              ? 'bg-arcane/20 border-arcane/60 text-arcane'
              : 'bg-ink/40 border-parchment/20 text-parchment/60 hover:border-parchment/40',
          ]"
          type="button"
          @click="provider = 'local'"
        >
          Local
        </button>
      </div>
    </div>

    <div class="grid grid-cols-2 gap-4">
      <div class="space-y-2">
        <label class="block text-sm font-medium text-parchment/80">URL API</label>
        <input
          v-model="baseUrl"
          type="text"
          placeholder="https://api.openai.com/v1"
          class="w-full rounded-lg border border-parchment/20 bg-ink/60 px-3 py-2 font-mono text-sm text-parchment focus:border-arcane/60 focus:outline-none"
        />
      </div>
      <div class="space-y-2">
        <label class="block text-sm font-medium text-parchment/80">Taille</label>
        <input
          v-model="size"
          type="text"
          placeholder="1024x1024"
          class="w-full rounded-lg border border-parchment/20 bg-ink/60 px-3 py-2 font-mono text-sm text-parchment focus:border-arcane/60 focus:outline-none"
        />
      </div>
    </div>

    <div class="space-y-2">
      <label class="block text-sm font-medium text-parchment/80">Modèle image</label>
      <input
        v-model="model"
        type="text"
        placeholder="gpt-image-1 ou modèle local"
        class="w-full rounded-lg border border-parchment/20 bg-ink/60 px-3 py-2 font-mono text-sm text-parchment focus:border-arcane/60 focus:outline-none"
      />
    </div>

    <div class="space-y-2">
      <label class="block text-sm font-medium text-parchment/80">Clé API</label>
      <input
        v-model="apiKeyInput"
        type="password"
        :placeholder="apiKeySet && !clearApiKey
          ? '●●●● (clé définie — laisser vide pour conserver)'
          : 'clé optionnelle…'"
        class="w-full rounded-lg border border-parchment/20 bg-ink/60 px-3 py-2 font-mono text-sm text-parchment focus:border-arcane/60 focus:outline-none"
      />
      <div class="flex items-center justify-between">
        <p class="text-xs text-parchment/40">
          La clé reste côté serveur et n'est jamais retournée à l'interface.
        </p>
        <button
          v-if="apiKeySet && !clearApiKey"
          class="text-xs text-blood/70 transition-colors hover:text-blood"
          type="button"
          @click="handleClearApiKey"
        >
          Effacer la clé
        </button>
        <span v-if="clearApiKey" class="text-xs text-yellow-400/80">
          La clé sera supprimée à la sauvegarde.
        </span>
      </div>
    </div>

    <p v-if="loading" class="text-sm text-parchment/50">Chargement…</p>
    <p v-if="error" class="text-sm text-blood">{{ error }}</p>
    <p v-if="saveSuccess" class="text-sm text-green-400">Paramètres image sauvegardés.</p>

    <button
      class="rounded border border-arcane/40 bg-arcane/20 px-4 py-2 text-arcane transition-colors hover:bg-arcane/30 disabled:opacity-50"
      type="button"
      :disabled="saving"
      @click="saveSettings"
    >
      {{ saving ? 'Sauvegarde…' : 'Sauvegarder image' }}
    </button>
  </div>
</template>
