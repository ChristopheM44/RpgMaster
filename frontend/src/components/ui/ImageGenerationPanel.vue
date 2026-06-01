<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
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

// Connection test result
const health = ref<{ available: boolean; provider: string; model: string; latency_ms?: number; error?: string } | null>(null)
const availableModels = ref<string[]>([])

// Image generation ping
const pinging = ref(false)
const pingResult = ref<{
  ok: boolean
  provider: string
  model: string
  latency_ms?: number
  image_url?: string
  error?: string
} | null>(null)

const sortedModels = computed(() =>
  [...availableModels.value].sort((a, b) =>
    a.localeCompare(b, 'fr', { numeric: true, sensitivity: 'base' }),
  ),
)

async function testConnection() {
  loading.value = true
  error.value = null
  health.value = null

  try {
    const result = await adminApi.testImageGeneration()
    health.value = {
      available: result.available,
      provider: result.provider,
      model: result.model,
      latency_ms: result.latency_ms,
      error: result.error,
    }
    availableModels.value = result.models ?? []
  } catch (e) {
    health.value = {
      available: false,
      provider: provider.value,
      model: model.value || 'default',
      error: e instanceof Error ? e.message : 'Test de connexion échoué',
    }
    error.value = e instanceof Error ? e.message : 'Test de connexion échoué'
  } finally {
    loading.value = false
  }
}

async function pingImage() {
  pinging.value = true
  pingResult.value = null

  try {
    pingResult.value = await adminApi.pingImageGeneration()
  } catch (e) {
    pingResult.value = {
      ok: false,
      provider: provider.value,
      model: model.value || 'default',
      error: e instanceof Error ? e.message : 'Test de génération échoué',
    }
  } finally {
    pinging.value = false
  }
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

// Clear connection status and ping result when config changes
watch([provider, baseUrl], () => {
  availableModels.value = []
  health.value = null
  pingResult.value = null
})

onMounted(async () => {
  await loadSettings()
  if (baseUrl.value) {
    await testConnection()
  }
})
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
          Ollama / Serveur local
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
          Cloud (DALL-E / API compatible)
        </button>
      </div>
    </div>

    <!-- ── Section Ollama / Serveur local ── -->
    <template v-if="provider === 'local'">
      <div class="space-y-2">
        <label class="block text-sm font-medium text-parchment/80">URL du serveur d'images</label>
        <input
          v-model="baseUrl"
          type="text"
          placeholder="http://localhost:7860"
          class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment font-mono text-sm focus:outline-none focus:border-arcane/60"
        />
        <p class="text-xs text-parchment/40">
          API compatible OpenAI images <code class="text-arcane">/v1/images/generations</code>.
          Stable Diffusion WebUI, ComfyUI, etc.
        </p>
      </div>

      <!-- Clé API (optionnelle) -->
      <div class="space-y-2">
        <label class="block text-sm font-medium text-parchment/80">
          Clé API <span class="text-parchment/40 font-normal">(optionnelle)</span>
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
          {{ health.available ? 'Connecté' : 'Indisponible' }}
        </span>
        <span v-else-if="loading" class="text-xs text-parchment/40">Test…</span>
        <span v-else class="text-xs text-parchment/40">Non testé</span>
      </div>

      <!-- Modèles Ollama (dropdown si disponibles) -->
      <div class="grid grid-cols-2 gap-4">
        <div class="space-y-1">
          <label class="block text-sm font-medium text-parchment/80">Modèle d'image</label>
          <select
            v-if="sortedModels.length > 0"
            v-model="model"
            class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment text-sm focus:outline-none focus:border-arcane/60"
          >
            <option v-for="m in sortedModels" :key="m" :value="m">{{ m }}</option>
          </select>
          <input
            v-else
            v-model="model"
            type="text"
            placeholder="sd3-medium ou modèle local"
            class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment font-mono text-sm focus:outline-none focus:border-arcane/60"
          />
          <span
            v-if="health && sortedModels.length > 0"
            :class="[
              'inline-block px-1.5 py-0.5 rounded text-xs',
              sortedModels.includes(model)
                ? 'bg-green-900/40 text-green-300'
                : 'bg-yellow-900/40 text-yellow-300',
            ]"
          >
            {{ sortedModels.includes(model) ? 'Installé' : 'Non installé' }}
          </span>
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

      <!-- Liste des modèles disponibles -->
      <div v-if="health && sortedModels.length > 0" class="space-y-2">
        <p class="text-sm font-medium text-parchment/70">
          Modèles disponibles ({{ sortedModels.length }})
        </p>
        <ul class="max-h-[11.75rem] space-y-1 overflow-y-auto pr-1">
          <li
            v-for="m in sortedModels"
            :key="m"
            class="flex items-center gap-2 px-3 py-1.5 rounded bg-ink/20 border border-parchment/5"
          >
            <span class="h-1.5 w-1.5 rounded-full bg-green-400 flex-shrink-0" />
            <span class="font-mono text-sm text-parchment/80">{{ m }}</span>
          </li>
        </ul>
      </div>
      <div v-else-if="health && health.available && sortedModels.length === 0" class="text-sm text-parchment/50 italic">
        Aucun modèle d'image détecté. Installez un modèle de génération d'images sur votre serveur.
      </div>
    </template>

    <!-- ── Section Cloud (DALL-E / API compatible) ── -->
    <template v-else>
      <div class="space-y-2">
        <label class="block text-sm font-medium text-parchment/80">URL de l'API</label>
        <input
          v-model="baseUrl"
          type="text"
          placeholder="https://api.openai.com/v1"
          class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment font-mono text-sm focus:outline-none focus:border-arcane/60"
        />
        <p class="text-xs text-parchment/40">
          Compatible : OpenAI DALL-E, Mistral, ou tout service d'images cloud compatible.
        </p>
      </div>

      <div class="space-y-2">
        <label class="block text-sm font-medium text-parchment/80">Clé API</label>
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

      <!-- Modèles Cloud (toujours texte libre) -->
      <div class="grid grid-cols-2 gap-4">
        <div class="space-y-1">
          <label class="block text-sm font-medium text-parchment/80">Modèle d'image</label>
          <input
            v-model="model"
            type="text"
            placeholder="dall-e-3"
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
          {{ health.available ? 'Connecté' : 'Indisponible' }}
        </span>
        <span v-else-if="loading" class="text-xs text-parchment/40">Test…</span>
        <span v-else class="text-xs text-parchment/40">Non testé</span>
      </div>

      <div class="p-3 rounded-lg bg-ink/30 border border-parchment/10">
        <p class="text-xs text-parchment/50">
          Les changements de fournisseur prennent effet lors de la prochaine session de jeu.
        </p>
      </div>
    </template>

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
        <div class="font-mono text-xs opacity-70 mt-0.5">{{ pingResult.provider === 'local' ? 'Ollama' : 'Cloud' }} / {{ pingResult.model }}</div>
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
        {{ loading ? 'Test…' : 'Tester la connexion' }}
      </button>

      <button
        type="button"
        class="px-4 py-2 rounded border border-arcane/30 text-arcane/80 hover:bg-arcane/10 transition-colors disabled:opacity-50 cursor-pointer"
        :disabled="pinging"
        @click="pingImage"
      >
        {{ pinging ? 'Génération…' : '🖼️ Tester le Générateur' }}
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