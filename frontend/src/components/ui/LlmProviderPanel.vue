<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adminApi } from '../../services/api'
import type { LlmProvider, OllamaHealthResponse, LlmSettingsUpdate } from '../../types'

const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const saveSuccess = ref(false)

// LLM ping test
const pinging = ref(false)
const pingResult = ref<{ ok: boolean; provider: string; model: string; latency_ms?: number; sample_response?: string; error?: string } | null>(null)

async function pingLlm() {
  pinging.value = true
  pingResult.value = null
  try {
    pingResult.value = await adminApi.pingLlm()
  } catch (e) {
    pingResult.value = { ok: false, provider: provider.value, model: '', error: e instanceof Error ? e.message : 'Erreur réseau' }
  } finally {
    pinging.value = false
  }
}

// Provider actif
const provider = ref<LlmProvider>('ollama')

// Champs Ollama
const ollamaUrl = ref('')
const ollamaApiKeyInput = ref('')
const ollamaApiKeySet = ref(false)
const clearOllamaApiKey = ref(false)
const health = ref<OllamaHealthResponse | null>(null)

// Champs cloud
const openaiBaseUrl = ref('')
const openaiApiKeyInput = ref('')
const apiKeySet = ref(false)
const clearApiKey = ref(false)

// Modèles (communs aux deux modes)
const gmModel = ref('')
const playerModel = ref('')

async function loadSettings() {
  try {
    const s = await adminApi.getLlmSettings()
    provider.value = s.llm_provider
    ollamaUrl.value = s.ollama_base_url
    ollamaApiKeySet.value = s.ollama_api_key_set
    gmModel.value = s.gm_model
    playerModel.value = s.player_model
    openaiBaseUrl.value = s.openai_base_url
    apiKeySet.value = s.api_key_set
  } catch {
    // fallback silencieux
  }
}

async function testConnection() {
  loading.value = true
  error.value = null
  try {
    health.value = await adminApi.getLlmHealth()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  saving.value = true
  error.value = null
  saveSuccess.value = false
  try {
    const payload: LlmSettingsUpdate = {
      llm_provider: provider.value,
      gm_model: gmModel.value || undefined,
      player_model: playerModel.value || undefined,
    }

    if (provider.value === 'ollama') {
      payload.ollama_base_url = ollamaUrl.value || undefined
      if (clearOllamaApiKey.value) {
        payload.ollama_api_key = ''
      } else if (ollamaApiKeyInput.value) {
        payload.ollama_api_key = ollamaApiKeyInput.value
      }
    } else {
      payload.openai_base_url = openaiBaseUrl.value || undefined
      if (clearApiKey.value) {
        payload.openai_api_key = ''
      } else if (openaiApiKeyInput.value) {
        payload.openai_api_key = openaiApiKeyInput.value
      }
      // Si vide et pas de clear : on n'envoie pas openai_api_key → clé conservée
    }

    const updated = await adminApi.updateLlmSettings(payload)
    ollamaUrl.value = updated.ollama_base_url
    gmModel.value = updated.gm_model
    playerModel.value = updated.player_model
    openaiBaseUrl.value = updated.openai_base_url
    apiKeySet.value = updated.api_key_set
    ollamaApiKeySet.value = updated.ollama_api_key_set
    openaiApiKeyInput.value = ''
    ollamaApiKeyInput.value = ''
    clearApiKey.value = false
    clearOllamaApiKey.value = false
    saveSuccess.value = true

    if (provider.value === 'ollama') {
      await testConnection()
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Erreur lors de la sauvegarde'
  } finally {
    saving.value = false
  }
}

function handleClearApiKey() {
  clearApiKey.value = true
  openaiApiKeyInput.value = ''
}

function handleClearOllamaApiKey() {
  clearOllamaApiKey.value = true
  ollamaApiKeyInput.value = ''
}

onMounted(async () => {
  await loadSettings()
  if (provider.value === 'ollama') {
    await testConnection()
  }
})
</script>

<template>
  <div class="space-y-6">
    <!-- En-tête -->
    <div>
      <h2 class="text-xl font-bold text-parchment">Configuration LLM</h2>
      <p class="text-sm text-parchment/60 mt-1">
        Choisissez le fournisseur de modèle de langage et configurez ses paramètres.
      </p>
    </div>

    <!-- Sélecteur de provider -->
    <div class="space-y-2">
      <label class="block text-sm font-medium text-parchment/80">Fournisseur</label>
      <div class="flex gap-2">
        <button
          :class="[
            'flex-1 px-4 py-2.5 rounded-lg border text-sm font-medium transition-colors',
            provider === 'ollama'
              ? 'bg-arcane/20 border-arcane/60 text-arcane'
              : 'bg-ink/40 border-parchment/20 text-parchment/60 hover:border-parchment/40',
          ]"
          @click="provider = 'ollama'"
        >
          Ollama (local)
        </button>
        <button
          :class="[
            'flex-1 px-4 py-2.5 rounded-lg border text-sm font-medium transition-colors',
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

    <!-- ── Section Ollama ── -->
    <template v-if="provider === 'ollama'">
      <div class="space-y-2">
        <label class="block text-sm font-medium text-parchment/80">URL du serveur Ollama</label>
        <input
          v-model="ollamaUrl"
          type="text"
          placeholder="http://localhost:11434"
          class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment font-mono text-sm focus:outline-none focus:border-arcane/60"
        />
        <p class="text-xs text-parchment/40">
          Local : <code class="text-arcane">http://localhost:11434</code> —
          Cloud : <code class="text-arcane">https://ollama.com</code>
        </p>
      </div>

      <!-- Clé API Ollama (optionnelle, pour Ollama cloud) -->
      <div class="space-y-2">
        <label class="block text-sm font-medium text-parchment/80">
          Clé API <span class="text-parchment/40 font-normal">(optionnelle — Ollama cloud uniquement)</span>
        </label>
        <input
          v-model="ollamaApiKeyInput"
          type="password"
          :placeholder="ollamaApiKeySet && !clearOllamaApiKey
            ? '●●●● (clé définie — laisser vide pour conserver)'
            : 'Bearer token Ollama cloud…'"
          class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment font-mono text-sm focus:outline-none focus:border-arcane/60"
        />
        <div class="flex items-center justify-between">
          <p class="text-xs text-parchment/40">Laissez vide pour Ollama local.</p>
          <button
            v-if="ollamaApiKeySet && !clearOllamaApiKey"
            class="text-xs text-blood/70 hover:text-blood transition-colors"
            @click="handleClearOllamaApiKey"
          >
            Effacer la clé
          </button>
          <span v-if="clearOllamaApiKey" class="text-xs text-yellow-400/80">
            La clé sera supprimée à la prochaine sauvegarde.
          </span>
        </div>
      </div>

      <!-- Statut connexion -->
      <div class="flex items-center justify-between p-4 rounded-lg bg-ink/40 border border-parchment/10">
        <div>
          <p class="font-medium text-parchment">Statut de connexion</p>
          <p class="text-sm text-parchment/60 font-mono">{{ ollamaUrl || '—' }}</p>
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
      </div>

      <!-- Modèles Ollama (dropdown si disponibles) -->
      <div class="grid grid-cols-2 gap-4">
        <div class="space-y-1">
          <label class="block text-sm font-medium text-parchment/80">Modèle Maître du Jeu</label>
          <select
            v-if="health && health.models.length > 0"
            v-model="gmModel"
            class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment text-sm focus:outline-none focus:border-arcane/60"
          >
            <option v-for="m in health.models" :key="m" :value="m">{{ m }}</option>
          </select>
          <input
            v-else
            v-model="gmModel"
            type="text"
            placeholder="mistral:7b"
            class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment font-mono text-sm focus:outline-none focus:border-arcane/60"
          />
          <span
            v-if="health"
            :class="[
              'inline-block px-1.5 py-0.5 rounded text-xs',
              health.models.includes(gmModel)
                ? 'bg-green-900/40 text-green-300'
                : 'bg-yellow-900/40 text-yellow-300',
            ]"
          >
            {{ health.models.includes(gmModel) ? 'Installé' : 'Non installé' }}
          </span>
        </div>

        <div class="space-y-1">
          <label class="block text-sm font-medium text-parchment/80">Modèle Joueurs IA</label>
          <select
            v-if="health && health.models.length > 0"
            v-model="playerModel"
            class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment text-sm focus:outline-none focus:border-arcane/60"
          >
            <option v-for="m in health.models" :key="m" :value="m">{{ m }}</option>
          </select>
          <input
            v-else
            v-model="playerModel"
            type="text"
            placeholder="mistral:7b"
            class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment font-mono text-sm focus:outline-none focus:border-arcane/60"
          />
          <span
            v-if="health"
            :class="[
              'inline-block px-1.5 py-0.5 rounded text-xs',
              health.models.includes(playerModel)
                ? 'bg-green-900/40 text-green-300'
                : 'bg-yellow-900/40 text-yellow-300',
            ]"
          >
            {{ health.models.includes(playerModel) ? 'Installé' : 'Non installé' }}
          </span>
        </div>
      </div>

      <!-- Liste des modèles disponibles -->
      <div v-if="health && health.models.length > 0" class="space-y-2">
        <p class="text-sm font-medium text-parchment/70">
          Modèles disponibles ({{ health.models.length }})
        </p>
        <ul class="space-y-1">
          <li
            v-for="model in health.models"
            :key="model"
            class="flex items-center gap-2 px-3 py-1.5 rounded bg-ink/20 border border-parchment/5"
          >
            <span class="h-1.5 w-1.5 rounded-full bg-green-400 flex-shrink-0" />
            <span class="font-mono text-sm text-parchment/80">{{ model }}</span>
          </li>
        </ul>
      </div>
      <div v-else-if="health && health.available" class="text-sm text-parchment/50 italic">
        Aucun modèle installé. Lancez <code class="text-arcane">ollama pull mistral:7b</code>.
      </div>
    </template>

    <!-- ── Section Cloud ── -->
    <template v-else>
      <div class="space-y-2">
        <label class="block text-sm font-medium text-parchment/80">URL de l'API</label>
        <input
          v-model="openaiBaseUrl"
          type="text"
          placeholder="https://api.mistral.ai/v1"
          class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment font-mono text-sm focus:outline-none focus:border-arcane/60"
        />
        <p class="text-xs text-parchment/40">
          Compatible : Mistral AI, Groq, OpenRouter, DeepSeek, Together AI, Ollama remote…
        </p>
      </div>

      <div class="space-y-2">
        <label class="block text-sm font-medium text-parchment/80">Clé API</label>
        <input
          v-model="openaiApiKeyInput"
          type="password"
          :placeholder="apiKeySet && !clearApiKey
            ? '●●●● (clé définie — laisser vide pour conserver)'
            : 'sk-…'"
          class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment font-mono text-sm focus:outline-none focus:border-arcane/60"
        />
        <div class="flex items-center justify-between">
          <p class="text-xs text-parchment/40">
            La clé est stockée côté serveur et n'est jamais retournée par l'API.
          </p>
          <button
            v-if="apiKeySet && !clearApiKey"
            class="text-xs text-blood/70 hover:text-blood transition-colors"
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
          <label class="block text-sm font-medium text-parchment/80">Modèle Maître du Jeu</label>
          <input
            v-model="gmModel"
            type="text"
            placeholder="mistral-large-latest"
            class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment font-mono text-sm focus:outline-none focus:border-arcane/60"
          />
        </div>
        <div class="space-y-1">
          <label class="block text-sm font-medium text-parchment/80">Modèle Joueurs IA</label>
          <input
            v-model="playerModel"
            type="text"
            placeholder="mistral-small-latest"
            class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment font-mono text-sm focus:outline-none focus:border-arcane/60"
          />
        </div>
      </div>

      <div class="p-3 rounded-lg bg-ink/30 border border-parchment/10">
        <p class="text-xs text-parchment/50">
          Les changements de provider prennent effet lors de la prochaine session de jeu.
        </p>
      </div>
    </template>

    <!-- Erreur / succès -->
    <p v-if="error" class="text-blood text-sm">{{ error }}</p>
    <p v-if="saveSuccess" class="text-green-400 text-sm">Paramètres sauvegardés.</p>

    <!-- Résultat ping LLM -->
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
          {{ pingResult.ok ? 'LLM opérationnel' : 'LLM inaccessible' }}
          <span v-if="pingResult.latency_ms" class="font-normal opacity-70 ml-2">{{ pingResult.latency_ms }} ms</span>
        </div>
        <div class="font-mono text-xs opacity-70 mt-0.5">{{ pingResult.provider }} / {{ pingResult.model }}</div>
        <div v-if="pingResult.sample_response" class="mt-1 opacity-60 text-xs italic truncate">« {{ pingResult.sample_response }} »</div>
        <div v-if="pingResult.error" class="mt-1 text-xs">{{ pingResult.error }}</div>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex gap-3">
      <button
        v-if="provider === 'ollama'"
        class="px-4 py-2 rounded border border-parchment/20 text-parchment/70 hover:border-parchment/40 transition-colors disabled:opacity-50"
        :disabled="loading"
        @click="testConnection"
      >
        {{ loading ? 'Test…' : 'Tester la connexion' }}
      </button>

      <button
        class="px-4 py-2 rounded border border-arcane/30 text-arcane/80 hover:bg-arcane/10 transition-colors disabled:opacity-50"
        :disabled="pinging"
        @click="pingLlm"
      >
        {{ pinging ? 'Test LLM…' : '🤖 Tester le LLM' }}
      </button>

      <button
        class="px-4 py-2 rounded bg-arcane/20 border border-arcane/40 text-arcane hover:bg-arcane/30 transition-colors disabled:opacity-50"
        :disabled="saving"
        @click="saveSettings"
      >
        {{ saving ? 'Sauvegarde…' : 'Sauvegarder' }}
      </button>
    </div>
  </div>
</template>
