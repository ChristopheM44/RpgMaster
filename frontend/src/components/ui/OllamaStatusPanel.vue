<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adminApi } from '../../services/api'
import type { OllamaHealthResponse } from '../../types'

const data = ref<OllamaHealthResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function refresh() {
  loading.value = true
  error.value = null
  try {
    data.value = await adminApi.getLlmHealth()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <div class="space-y-6">
    <!-- En-tête -->
    <div>
      <h2 class="text-xl font-bold text-parchment">État du LLM (Ollama)</h2>
      <p class="text-sm text-parchment/60 mt-1">
        Connexion au serveur Ollama et modèles disponibles.
      </p>
    </div>

    <!-- Statut connexion -->
    <div class="flex items-center justify-between p-4 rounded-lg bg-ink/40 border border-parchment/10">
      <div>
        <p class="font-medium text-parchment">Serveur Ollama</p>
        <p class="text-sm text-parchment/60">
          <code class="text-arcane">localhost:11434</code>
        </p>
      </div>
      <span
        v-if="data !== null"
        :class="[
          'px-2 py-0.5 rounded-full text-xs font-medium',
          data.available
            ? 'bg-green-900/60 text-green-300'
            : 'bg-red-900/60 text-red-300',
        ]"
      >
        {{ data.available ? 'Connecté' : 'Indisponible' }}
      </span>
      <span v-else-if="loading" class="text-xs text-parchment/40">Chargement…</span>
    </div>

    <!-- Modèles configurés -->
    <div v-if="data" class="space-y-2">
      <p class="font-medium text-parchment">Modèles configurés</p>

      <div class="grid grid-cols-2 gap-3">
        <div class="p-3 rounded-lg bg-ink/40 border border-parchment/10">
          <p class="text-xs text-parchment/50 mb-1">Maître du Jeu</p>
          <p class="font-mono text-sm text-arcane">{{ data.gm_model }}</p>
          <span
            :class="[
              'mt-1 inline-block px-1.5 py-0.5 rounded text-xs',
              data.models.includes(data.gm_model)
                ? 'bg-green-900/40 text-green-300'
                : 'bg-yellow-900/40 text-yellow-300',
            ]"
          >
            {{ data.models.includes(data.gm_model) ? 'Installé' : 'Non installé' }}
          </span>
        </div>

        <div class="p-3 rounded-lg bg-ink/40 border border-parchment/10">
          <p class="text-xs text-parchment/50 mb-1">Joueurs IA</p>
          <p class="font-mono text-sm text-arcane">{{ data.player_model }}</p>
          <span
            :class="[
              'mt-1 inline-block px-1.5 py-0.5 rounded text-xs',
              data.models.includes(data.player_model)
                ? 'bg-green-900/40 text-green-300'
                : 'bg-yellow-900/40 text-yellow-300',
            ]"
          >
            {{ data.models.includes(data.player_model) ? 'Installé' : 'Non installé' }}
          </span>
        </div>
      </div>
    </div>

    <!-- Liste des modèles disponibles -->
    <div v-if="data && data.models.length > 0" class="space-y-2">
      <p class="font-medium text-parchment">Modèles disponibles ({{ data.models.length }})</p>
      <ul class="space-y-1">
        <li
          v-for="model in data.models"
          :key="model"
          class="flex items-center gap-2 px-3 py-1.5 rounded bg-ink/20 border border-parchment/5"
        >
          <span class="h-1.5 w-1.5 rounded-full bg-green-400 flex-shrink-0" />
          <span class="font-mono text-sm text-parchment/80">{{ model }}</span>
        </li>
      </ul>
    </div>

    <div v-else-if="data && data.available" class="text-sm text-parchment/50 italic">
      Aucun modèle installé. Lancez <code class="text-arcane">ollama pull mistral:7b</code>.
    </div>

    <!-- Erreur -->
    <p v-if="error" class="text-blood text-sm">{{ error }}</p>

    <!-- Rafraîchir -->
    <button
      class="px-4 py-2 rounded border border-parchment/20 text-parchment/70 hover:border-parchment/40 transition-colors disabled:opacity-50"
      :disabled="loading"
      @click="refresh"
    >
      {{ loading ? 'Chargement…' : 'Rafraîchir' }}
    </button>
  </div>
</template>
