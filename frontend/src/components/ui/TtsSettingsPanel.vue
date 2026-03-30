<script setup lang="ts">
import { onMounted } from 'vue'
import { useSettingsStore } from '../../stores/settings'
import type { TtsBackend } from '../../types'

const store = useSettingsStore()

onMounted(async () => {
  await Promise.all([store.fetchSettings(), store.fetchHealth()])
})

async function save() {
  await store.updateSettings({
    tts_enabled: store.ttsEnabled,
    tts_backend: store.ttsBackend,
  })
  await store.fetchHealth()
}

function setBackend(b: TtsBackend) {
  store.ttsBackend = b
}
</script>

<template>
  <div class="space-y-6">
    <!-- En-tête -->
    <div>
      <h2 class="text-xl font-bold text-parchment">Paramètres TTS</h2>
      <p class="text-sm text-parchment/60 mt-1">
        Configuration du moteur de synthèse vocale (Text-to-Speech).
      </p>
    </div>

    <!-- Toggle activation -->
    <div class="flex items-center justify-between p-4 rounded-lg bg-ink/40 border border-parchment/10">
      <div>
        <p class="font-medium text-parchment">Activer la voix</p>
        <p class="text-sm text-parchment/60">Les narrations du MJ seront lues à voix haute.</p>
      </div>
      <button
        :class="[
          'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
          store.ttsEnabled ? 'bg-gold' : 'bg-parchment/20',
        ]"
        @click="store.ttsEnabled = !store.ttsEnabled"
      >
        <span
          :class="[
            'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
            store.ttsEnabled ? 'translate-x-6' : 'translate-x-1',
          ]"
        />
      </button>
    </div>

    <!-- Sélection du backend -->
    <div class="space-y-3">
      <p class="font-medium text-parchment">Backend TTS</p>

      <!-- Kokoro -->
      <label
        class="flex items-center gap-4 p-4 rounded-lg border cursor-pointer transition-colors"
        :class="store.ttsBackend === 'kokoro'
          ? 'border-gold bg-gold/10'
          : 'border-parchment/10 bg-ink/20 hover:border-parchment/30'"
        @click="setBackend('kokoro')"
      >
        <input type="radio" :checked="store.ttsBackend === 'kokoro'" class="sr-only" />
        <div class="flex-1">
          <p class="font-medium text-parchment">Kokoro-ONNX (local)</p>
          <p class="text-sm text-parchment/60">
            Modèle ONNX 82M — voix française <code class="text-arcane">ff_siwis</code>.
            Tourne localement, aucun serveur requis.
          </p>
        </div>
        <!-- Badge health -->
        <span
          :class="[
            'px-2 py-0.5 rounded-full text-xs font-medium',
            store.health.kokoro
              ? 'bg-green-900/60 text-green-300'
              : 'bg-red-900/60 text-red-300',
          ]"
        >
          {{ store.health.kokoro ? 'Disponible' : 'Indisponible' }}
        </span>
      </label>

      <!-- vLLM-Omni -->
      <label
        class="flex items-center gap-4 p-4 rounded-lg border cursor-pointer transition-colors"
        :class="store.ttsBackend === 'vllm'
          ? 'border-gold bg-gold/10'
          : 'border-parchment/10 bg-ink/20 hover:border-parchment/30'"
        @click="setBackend('vllm')"
      >
        <input type="radio" :checked="store.ttsBackend === 'vllm'" class="sr-only" />
        <div class="flex-1">
          <p class="font-medium text-parchment">vLLM-Omni (Voxtral)</p>
          <p class="text-sm text-parchment/60">
            Voxtral-4B via serveur vLLM-Omni sur
            <code class="text-arcane">:8091</code>. Requiert un GPU.
          </p>
        </div>
        <!-- Badge health -->
        <span
          :class="[
            'px-2 py-0.5 rounded-full text-xs font-medium',
            store.health.vllm
              ? 'bg-green-900/60 text-green-300'
              : 'bg-red-900/60 text-red-300',
          ]"
        >
          {{ store.health.vllm ? 'Disponible' : 'Indisponible' }}
        </span>
      </label>
    </div>

    <!-- Erreur -->
    <p v-if="store.error" class="text-blood text-sm">
      {{ store.error }}
    </p>

    <!-- Boutons -->
    <div class="flex gap-3">
      <button
        class="px-4 py-2 rounded bg-gold text-ink font-semibold hover:bg-gold/80 transition-colors disabled:opacity-50"
        :disabled="store.loading"
        @click="save"
      >
        {{ store.loading ? 'Sauvegarde...' : 'Sauvegarder' }}
      </button>
      <button
        class="px-4 py-2 rounded border border-parchment/20 text-parchment/70 hover:border-parchment/40 transition-colors"
        @click="store.fetchHealth()"
      >
        Rafraîchir le statut
      </button>
    </div>
  </div>
</template>
