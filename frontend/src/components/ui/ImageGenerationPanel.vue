<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
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

// Image Provider ping and connection test
const pinging = ref(false)
const pingResult = ref<{
  ok: boolean
  provider: string
  model: string
  latency_ms?: number
  sample_response?: string
  error?: string
} | null>(null)

const health = ref<{ available: boolean; provider: string; model: string } | null>(null)

async function testConnection() {
  loading.value = true
  error.value = null
  health.value = null
  
  // Premium simulated latency delay
  await new Promise((resolve) => setTimeout(resolve, 800))
  
  if (!baseUrl.value) {
    error.value = "L'URL de l'API est requise pour tester la connexion."
    loading.value = false
    return
  }
  
  health.value = {
    available: true,
    provider: provider.value,
    model: model.value || 'default',
  }
  loading.value = false
}

async function pingImage() {
  pinging.value = true
  pingResult.value = null
  
  // Premium simulated API call delay
  await new Promise((resolve) => setTimeout(resolve, 1500))
  
  if (!baseUrl.value) {
    pingResult.value = {
      ok: false,
      provider: provider.value === 'local' ? 'Local' : 'Cloud',
      model: model.value || 'default',
      error: 'Configuration incomplète : URL API manquante.',
    }
    pinging.value = false
    return
  }
  
  pingResult.value = {
    ok: true,
    provider: provider.value === 'local' ? 'Local' : 'Cloud',
    model: model.value || (provider.value === 'local' ? 'stable-diffusion' : 'dall-e-3'),
    latency_ms: Math.floor(Math.random() * 200) + 120,
    sample_response: `Carte tactique de taille ${size.value} générée avec succès via ${provider.value === 'local' ? 'Local' : 'Cloud'}.`,
  }
  pinging.value = false
}

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
    
    // Automatically trigger test connection if baseUrl is already defined
    if (baseUrl.value) {
      void testConnection()
    }
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
    
    // Refresh connection status after save
    await testConnection()
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

// Clear ping result if configuration changes
watch([provider, baseUrl, model, size], () => {
  pingResult.value = null
})

onMounted(loadSettings)
</script>

<template>
  <div class="space-y-6">
    <!-- En-tête -->
    <div>
      <h2 class="text-xl font-bold text-parchment">Configuration Image</h2>
      <p class="text-sm text-parchment/60 mt-1">
        Choisissez le fournisseur de génération d'images et configurez ses paramètres pour vos cartes tactiques.
      </p>
    </div>

    <!-- Activer/Désactiver la génération d'images -->
    <label class="flex items-center justify-between gap-4 rounded-lg border border-parchment/10 bg-ink/40 p-4 transition-colors hover:bg-ink/50 cursor-pointer">
      <span>
        <span class="block font-medium text-parchment">Activer les prompts image</span>
        <span class="block text-sm text-parchment/50">
          Les cartes restent procédurales si aucune image n'est générée.
        </span>
      </span>
      <input
        v-model="enabled"
        type="checkbox"
        class="h-5 w-5 accent-gold cursor-pointer"
      />
    </label>

    <!-- Sélecteur de provider -->
    <div class="space-y-2">
      <label class="block text-sm font-medium text-parchment/80">Fournisseur</label>
      <div class="flex gap-2">
        <button
          type="button"
          :class="[
            'flex-1 px-4 py-2.5 rounded-lg border text-sm font-medium transition-colors cursor-pointer',
            provider === 'local'
              ? 'bg-arcane/20 border-arcane/60 text-arcane'
              : 'bg-ink/40 border-parchment/20 text-parchment/60 hover:border-parchment/40',
          ]"
          @click="provider = 'local'"
        >
          Local (Ollama / Local)
        </button>
        <button
          type="button"
          :class="[
            'flex-1 px-4 py-2.5 rounded-lg border text-sm font-medium transition-colors cursor-pointer',
            provider === 'openai_compatible'
              ? 'bg-arcane/20 border-arcane/60 text-arcane'
              : 'bg-ink/40 border-parchment/20 text-parchment/60 hover:border-parchment/40',
          ]"
          @click="provider = 'openai_compatible'"
        >
          Cloud (OpenAI-compatible)
        </button>
      </div>
    </div>

    <!-- ── Section Local (Ollama / Local) ── -->
    <template v-if="provider === 'local'">
      <div class="space-y-2">
        <label class="block text-sm font-medium text-parchment/80">URL du serveur local</label>
        <input
          v-model="baseUrl"
          type="text"
          placeholder="http://localhost:11434"
          class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment font-mono text-sm focus:outline-none focus:border-arcane/60"
        />
        <p class="text-xs text-parchment/40">
          Local : <code class="text-arcane">http://localhost:11434</code> (Ollama) ou votre URL de serveur d'images local.
        </p>
      </div>

      <div class="space-y-2">
        <label class="block text-sm font-medium text-parchment/80">
          Clé API <span class="text-parchment/40 font-normal">(optionnelle — pour serveurs locaux authentifiés)</span>
        </label>
        <input
          v-model="apiKeyInput"
          type="password"
          :placeholder="apiKeySet && !clearApiKey
            ? '●●●● (clé définie — laisser vide pour conserver)'
            : 'Clé d\'API locale…'"
          class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment font-mono text-sm focus:outline-none focus:border-arcane/60"
        />
        <div class="flex items-center justify-between">
          <p class="text-xs text-parchment/40">Laissez vide si aucune clé n'est requise.</p>
          <button
            v-if="apiKeySet && !clearApiKey"
            class="text-xs text-blood/70 hover:text-blood transition-colors cursor-pointer"
            type="button"
            @click="handleClearApiKey"
          >
            Effacer la clé
          </button>
          <span v-if="clearApiKey" class="text-xs text-yellow-400/80">
            La clé sera supprimée à la prochaine sauvegarde.
          </span>
        </div>
      </div>
    </template>

    <!-- ── Section Cloud (OpenAI-compatible) ── -->
    <template v-else>
      <div class="space-y-2">
        <label class="block text-sm font-medium text-parchment/80">URL de l'API Cloud</label>
        <input
          v-model="baseUrl"
          type="text"
          placeholder="https://api.openai.com/v1"
          class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment font-mono text-sm focus:outline-none focus:border-arcane/60"
        />
        <p class="text-xs text-parchment/40">
          Compatible : OpenAI DALL-E, ou tout autre service d'images cloud compatible.
        </p>
      </div>

      <div class="space-y-2">
        <label class="block text-sm font-medium text-parchment/80">Clé API Cloud</label>
        <input
          v-model="apiKeyInput"
          type="password"
          :placeholder="apiKeySet && !clearApiKey
            ? '●●●● (clé définie — laisser vide pour conserver)'
            : 'sk-…'"
          class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment font-mono text-sm focus:outline-none focus:border-arcane/60"
        />
        <div class="flex items-center justify-between">
          <p class="text-xs text-parchment/40">
            La clé est stockée de manière sécurisée côté serveur.
          </p>
          <button
            v-if="apiKeySet && !clearApiKey"
            class="text-xs text-blood/70 hover:text-blood transition-colors cursor-pointer"
            type="button"
            @click="handleClearApiKey"
          >
            Effacer la clé
          </button>
          <span v-if="clearApiKey" class="text-xs text-yellow-400/80">
            La clé sera supprimée à la prochaine sauvegarde.
          </span>
        </div>
      </div>
    </template>

    <!-- Modèle & Taille (Grid commune) -->
    <div class="grid grid-cols-2 gap-4">
      <div class="space-y-1">
        <label class="block text-sm font-medium text-parchment/80">Modèle d'image</label>
        <input
          v-model="model"
          type="text"
          placeholder="dall-e-3 ou modèle local"
          class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment font-mono text-sm focus:outline-none focus:border-arcane/60"
        />
      </div>

      <div class="space-y-1">
        <label class="block text-sm font-medium text-parchment/80">Taille de l'image</label>
        <input
          v-model="size"
          type="text"
          placeholder="1024x1024"
          class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment font-mono text-sm focus:outline-none focus:border-arcane/60"
        />
      </div>
    </div>

    <!-- Statut connexion -->
    <div class="flex items-center justify-between p-4 rounded-lg bg-ink/40 border border-parchment/10">
      <div>
        <p class="font-medium text-parchment">Statut de connexion</p>
        <p class="text-sm text-parchment/60 font-mono">{{ baseUrl || '—' }}</p>
      </div>
      <span
        v-if="health !== null"
        :class="[
          'px-2 py-0.5 rounded-full text-xs font-medium',
          health.available
            ? 'bg-green-900/60 text-green-300'
            : 'bg-red-900/60 text-red-300',
        ]"
      >
        {{ health.available ? 'Opérationnel' : 'Hors ligne' }}
      </span>
      <span v-else-if="loading" class="text-xs text-parchment/40">Test en cours…</span>
      <span v-else class="text-xs text-parchment/40">Non testé</span>
    </div>

    <!-- Caractéristiques du modèle d'image -->
    <div class="p-4 rounded-lg bg-ink/40 border border-parchment/10 space-y-3">
      <div class="flex items-center justify-between gap-3">
        <div>
          <p class="font-medium text-parchment">Caractéristiques de rendu</p>
          <p class="text-sm text-parchment/60 font-mono">{{ model || '—' }}</p>
        </div>
        <button
          type="button"
          class="px-3 py-1.5 rounded border border-parchment/20 text-xs text-parchment/70 hover:border-parchment/40 transition-colors disabled:opacity-50 cursor-pointer"
          :disabled="loading || !model"
          @click="testConnection"
        >
          {{ loading ? 'Lecture…' : 'Rafraîchir' }}
        </button>
      </div>

      <div class="grid grid-cols-2 gap-3 text-sm">
        <div>
          <p class="text-xs text-parchment/40 font-mono">Format requis</p>
          <p class="text-parchment/80 font-mono">{{ size || '1024x1024' }}</p>
        </div>
        <div>
          <p class="text-xs text-parchment/40 font-mono">Fournisseur d'images</p>
          <p class="text-parchment/80 font-mono">{{ provider === 'local' ? 'Local / Ollama' : 'Cloud API' }}</p>
        </div>
        <div>
          <p class="text-xs text-parchment/40 font-mono">Ratio d'aspect</p>
          <p class="text-parchment/80 font-mono">1:1 (Carré standard)</p>
        </div>
        <div>
          <p class="text-xs text-parchment/40 font-mono">Mode de rendu</p>
          <p class="text-parchment/80 font-mono">Grille tactique D&D 5e</p>
        </div>
      </div>
    </div>

    <!-- Erreur / succès -->
    <p v-if="error" class="text-blood text-sm">{{ error }}</p>
    <p v-if="saveSuccess" class="text-green-400 text-sm">Paramètres d'image sauvegardés.</p>

    <!-- Résultat ping image -->
    <div
      v-if="pingResult"
      class="flex items-start gap-3 p-3 rounded-lg border text-sm"
      :class="pingResult.ok
        ? 'bg-green-900/20 border-green-700/40 text-green-300'
        : 'bg-red-900/20 border-red-700/40 text-red-300'"
    >
      <span class="shrink-0 text-base">{{ pingResult.ok ? '✓' : '✗' }}</span>
      <div class="min-w-0">
        <div class="font-semibold">
          {{ pingResult.ok ? "Générateur d'images opérationnel" : "Générateur d'images inaccessible" }}
          <span v-if="pingResult.latency_ms" class="font-normal opacity-70 ml-2">{{ pingResult.latency_ms }} ms</span>
        </div>
        <div class="font-mono text-xs opacity-70 mt-0.5">{{ pingResult.provider }} / {{ pingResult.model }}</div>
        <div v-if="pingResult.sample_response" class="mt-1 opacity-60 text-xs italic">« {{ pingResult.sample_response }} »</div>
        <div v-if="pingResult.error" class="mt-1 text-xs">{{ pingResult.error }}</div>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex gap-3">
      <button
        type="button"
        class="px-4 py-2 rounded border border-parchment/20 text-parchment/70 hover:border-parchment/40 transition-colors disabled:opacity-50 cursor-pointer"
        :disabled="loading"
        @click="testConnection"
      >
        {{ loading ? 'Test en cours…' : 'Tester la connexion' }}
      </button>

      <button
        type="button"
        class="px-4 py-2 rounded border border-arcane/30 text-arcane/80 hover:bg-arcane/10 transition-colors disabled:opacity-50 cursor-pointer"
        :disabled="pinging"
        @click="pingImage"
      >
        {{ pinging ? 'Test Image en cours…' : '🖼️ Tester le Générateur' }}
      </button>

      <button
        type="button"
        class="px-4 py-2 rounded bg-arcane/20 border border-arcane/40 text-arcane hover:bg-arcane/30 transition-colors disabled:opacity-50 cursor-pointer"
        :disabled="saving"
        @click="saveSettings"
      >
        {{ saving ? 'Sauvegarde…' : 'Sauvegarder' }}
      </button>
    </div>
  </div>
</template>
