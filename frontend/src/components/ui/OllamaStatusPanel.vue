<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adminApi } from '../../services/api'
import type { OllamaHealthResponse, LlmSettings } from '../../types'

const health = ref<OllamaHealthResponse | null>(null)
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const saveSuccess = ref(false)

// Champs éditables
const ollamaUrl = ref('')
const gmModel = ref('')
const playerModel = ref('')

async function loadSettings() {
  try {
    const s = await adminApi.getLlmSettings()
    ollamaUrl.value = s.ollama_base_url
    gmModel.value = s.gm_model
    playerModel.value = s.player_model
  } catch {
    // fallback silencieux, les champs restent vides
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
    const updated = await adminApi.updateLlmSettings({
      ollama_base_url: ollamaUrl.value || undefined,
      gm_model: gmModel.value || undefined,
      player_model: playerModel.value || undefined,
    } as Partial<LlmSettings>)
    ollamaUrl.value = updated.ollama_base_url
    gmModel.value = updated.gm_model
    playerModel.value = updated.player_model
    saveSuccess.value = true
    // Rafraîchir le statut après sauvegarde
    await testConnection()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Erreur lors de la sauvegarde'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadSettings()
  await testConnection()
})
</script>

<template>
  <div class="space-y-6">
    <!-- En-tête -->
    <div>
      <h2 class="text-xl font-bold text-parchment">Configuration Ollama (LLM)</h2>
      <p class="text-sm text-parchment/60 mt-1">
        Paramètres de connexion au serveur Ollama et sélection des modèles.
      </p>
    </div>

    <!-- Champ URL -->
    <div class="space-y-2">
      <label class="block text-sm font-medium text-parchment/80">URL du serveur Ollama</label>
      <input
        v-model="ollamaUrl"
        type="text"
        placeholder="http://localhost:11434"
        class="w-full px-3 py-2 rounded-lg bg-ink/60 border border-parchment/20 text-parchment font-mono text-sm focus:outline-none focus:border-arcane/60"
      />
      <p class="text-xs text-parchment/40">
        Pour un Mac distant : <code class="text-arcane">http://&lt;IP&gt;:11434</code>
        (Ollama doit être lancé avec <code class="text-arcane">OLLAMA_HOST=0.0.0.0</code>)
      </p>
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

    <!-- Modèles -->
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
      <p class="text-sm font-medium text-parchment/70">Modèles disponibles sur ce serveur ({{ health.models.length }})</p>
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

    <!-- Erreur / succès -->
    <p v-if="error" class="text-blood text-sm">{{ error }}</p>
    <p v-if="saveSuccess" class="text-green-400 text-sm">Paramètres sauvegardés.</p>

    <!-- Actions -->
    <div class="flex gap-3">
      <button
        class="px-4 py-2 rounded border border-parchment/20 text-parchment/70 hover:border-parchment/40 transition-colors disabled:opacity-50"
        :disabled="loading"
        @click="testConnection"
      >
        {{ loading ? 'Test…' : 'Tester la connexion' }}
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
