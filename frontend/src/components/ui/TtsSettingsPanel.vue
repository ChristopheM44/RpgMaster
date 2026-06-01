<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAudio } from '../../composables/useAudio'
import { adminApi } from '../../services/api'
import { useSettingsStore } from '../../stores/settings'
import type { TtsBackend, TtsVoiceSettings } from '../../types'

const store = useSettingsStore()
const audio = useAudio()

const previewing = ref(false)
const previewError = ref<string | null>(null)
const previewSuccess = ref(false)
const previewText = 'La torche tremble, et les ombres semblent attendre votre prochain pas.'

const kokoroPresets = [
  { id: 'ff_siwis', label: 'ff_siwis', detail: 'Français féminin, défaut' },
  { id: 'am_michael', label: 'am_michael', detail: 'Masculin posé' },
  { id: 'am_adam', label: 'am_adam', detail: 'Masculin neutre' },
  { id: 'af_bella', label: 'af_bella', detail: 'Féminin expressif' },
  { id: 'af_sarah', label: 'af_sarah', detail: 'Féminin naturel' },
  { id: 'af_nicole', label: 'af_nicole', detail: 'Féminin posé' },
  { id: 'af_sky', label: 'af_sky', detail: 'Neutre / jeune' },
]

const langOptions = [
  { value: 'fr-fr', label: 'Français' },
  { value: 'en-us', label: 'Anglais US' },
  { value: 'en-gb', label: 'Anglais UK' },
]

const selectedPreset = computed(() =>
  kokoroPresets.find((preset) => preset.id === store.gmVoice.preset_id),
)

const speedLabel = computed(() => store.gmVoice.speed.toFixed(2))

onMounted(async () => {
  await Promise.all([store.fetchSettings(), store.fetchHealth()])
})

function updateGmVoice(patch: Partial<TtsVoiceSettings>) {
  store.gmVoice = { ...store.gmVoice, ...patch }
}

async function save() {
  await store.updateSettings({
    tts_enabled: store.ttsEnabled,
    tts_backend: store.ttsBackend,
    npc_voice_enabled: store.npcVoiceEnabled,
    gm_voice: store.gmVoice,
  })
  await store.fetchHealth()
}

function setBackend(b: TtsBackend) {
  store.ttsBackend = b
}

function setPreset(id: string) {
  updateGmVoice({ preset_id: id, voice_id_local: id })
}

function setCustomVoice(event: Event) {
  const value = (event.target as HTMLInputElement).value
  const preset = kokoroPresets.find((item) => item.id === value)
  updateGmVoice({
    voice_id_local: value,
    preset_id: preset?.id ?? 'custom',
  })
}

async function toggleVoice() {
  store.ttsEnabled = !store.ttsEnabled
  if (store.ttsEnabled) await audio.unlockAudio()
}

async function previewVoice() {
  previewing.value = true
  previewError.value = null
  previewSuccess.value = false
  try {
    await audio.unlockAudio()
    const result = await adminApi.previewTts({
      text: previewText,
      gm_voice: store.gmVoice,
    })
    await audio.playAudioB64(result.audio_b64)
    previewSuccess.value = true
  } catch (e) {
    previewError.value = e instanceof Error ? e.message : 'Prévisualisation indisponible'
  } finally {
    previewing.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-xl font-bold text-parchment">Voix et TTS</h2>
      <p class="mt-1 text-sm text-parchment/60">
        Paramètres de lecture audio pour le Maître du Jeu et les dialogues PNJ.
      </p>
    </div>

    <div class="grid gap-4 md:grid-cols-2">
      <div class="flex items-center justify-between rounded-lg border border-parchment/10 bg-ink/40 p-4">
        <div>
          <p class="font-medium text-parchment">Activer la voix</p>
          <p class="text-sm text-parchment/60">Les narrations et dialogues configurés seront lus.</p>
        </div>
        <button
          type="button"
          :class="[
            'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
            store.ttsEnabled ? 'bg-gold' : 'bg-parchment/20',
          ]"
          @click="toggleVoice"
        >
          <span
            :class="[
              'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
              store.ttsEnabled ? 'translate-x-6' : 'translate-x-1',
            ]"
          />
        </button>
      </div>

      <div class="flex items-center justify-between rounded-lg border border-parchment/10 bg-ink/40 p-4">
        <div>
          <p class="font-medium text-parchment">Voix des PNJ</p>
          <p class="text-sm text-parchment/60">Utilise les personas quand elles existent.</p>
        </div>
        <button
          type="button"
          :class="[
            'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
            store.npcVoiceEnabled ? 'bg-teal' : 'bg-parchment/20',
          ]"
          @click="store.npcVoiceEnabled = !store.npcVoiceEnabled"
        >
          <span
            :class="[
              'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
              store.npcVoiceEnabled ? 'translate-x-6' : 'translate-x-1',
            ]"
          />
        </button>
      </div>
    </div>

    <div class="space-y-3">
      <p class="font-medium text-parchment">Backend TTS</p>

      <div class="grid gap-3 md:grid-cols-2">
        <label
          class="flex cursor-pointer items-center gap-4 rounded-lg border p-4 transition-colors"
          :class="store.ttsBackend === 'kokoro'
            ? 'border-gold bg-gold/10'
            : 'border-parchment/10 bg-ink/20 hover:border-parchment/30'"
          @click="setBackend('kokoro')"
        >
          <input type="radio" :checked="store.ttsBackend === 'kokoro'" class="sr-only" />
          <div class="flex-1">
            <p class="font-medium text-parchment">Kokoro-ONNX</p>
            <p class="text-sm text-parchment/60">Local, aucun serveur séparé.</p>
          </div>
          <span
            :class="[
              'rounded-full px-2 py-0.5 text-xs font-medium',
              store.health.kokoro
                ? 'bg-green-900/60 text-green-300'
                : 'bg-red-900/60 text-red-300',
            ]"
          >
            {{ store.health.kokoro ? 'Disponible' : 'Indisponible' }}
          </span>
        </label>

        <label
          class="flex cursor-pointer items-center gap-4 rounded-lg border p-4 transition-colors"
          :class="store.ttsBackend === 'vllm'
            ? 'border-gold bg-gold/10'
            : 'border-parchment/10 bg-ink/20 hover:border-parchment/30'"
          @click="setBackend('vllm')"
        >
          <input type="radio" :checked="store.ttsBackend === 'vllm'" class="sr-only" />
          <div class="flex-1">
            <p class="font-medium text-parchment">vLLM-Omni</p>
            <p class="text-sm text-parchment/60">Voxtral local sur <code class="text-arcane">:8091</code>.</p>
          </div>
          <span
            :class="[
              'rounded-full px-2 py-0.5 text-xs font-medium',
              store.health.vllm
                ? 'bg-green-900/60 text-green-300'
                : 'bg-red-900/60 text-red-300',
            ]"
          >
            {{ store.health.vllm ? 'Disponible' : 'Indisponible' }}
          </span>
        </label>
      </div>
    </div>

    <div class="space-y-4 rounded-lg border border-parchment/10 bg-ink/30 p-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p class="font-medium text-parchment">Voix du Maître du Jeu</p>
          <p class="text-sm text-parchment/60">
            Avec Kokoro, le timbre correspond au modèle de voix sélectionné.
          </p>
        </div>
        <span class="rounded-full border border-gold/20 px-2 py-0.5 font-mono text-xs text-gold">
          vitesse {{ speedLabel }}
        </span>
      </div>

      <div class="grid gap-4 md:grid-cols-2">
        <div class="space-y-2">
          <label class="block text-sm font-medium text-parchment/80">Preset Kokoro</label>
          <select
            :value="store.gmVoice.preset_id"
            class="w-full rounded-lg border border-parchment/20 bg-ink/60 px-3 py-2 text-sm text-parchment focus:border-arcane/60 focus:outline-none"
            @change="setPreset(($event.target as HTMLSelectElement).value)"
          >
            <option v-for="preset in kokoroPresets" :key="preset.id" :value="preset.id">
              {{ preset.label }} — {{ preset.detail }}
            </option>
            <option value="custom">Custom</option>
          </select>
          <p class="text-xs text-parchment/40">
            {{ selectedPreset?.detail ?? 'ID personnalisé conservé tel quel.' }}
          </p>
        </div>

        <div class="space-y-2">
          <label class="block text-sm font-medium text-parchment/80">Voice ID avancé</label>
          <input
            :value="store.gmVoice.voice_id_local"
            type="text"
            class="w-full rounded-lg border border-parchment/20 bg-ink/60 px-3 py-2 font-mono text-sm text-parchment focus:border-arcane/60 focus:outline-none"
            placeholder="ff_siwis"
            @input="setCustomVoice"
          />
        </div>
      </div>

      <div class="grid gap-4 md:grid-cols-2">
        <div class="space-y-2">
          <label class="block text-sm font-medium text-parchment/80">Langue</label>
          <select
            :value="store.gmVoice.lang"
            class="w-full rounded-lg border border-parchment/20 bg-ink/60 px-3 py-2 text-sm text-parchment focus:border-arcane/60 focus:outline-none"
            @change="updateGmVoice({ lang: ($event.target as HTMLSelectElement).value })"
          >
            <option v-for="lang in langOptions" :key="lang.value" :value="lang.value">
              {{ lang.label }} — {{ lang.value }}
            </option>
          </select>
        </div>

        <div class="space-y-2">
          <label class="block text-sm font-medium text-parchment/80">Vitesse</label>
          <input
            :value="store.gmVoice.speed"
            type="range"
            min="0.5"
            max="1.5"
            step="0.05"
            class="w-full accent-gold"
            @input="updateGmVoice({ speed: Number(($event.target as HTMLInputElement).value) })"
          />
          <div class="flex justify-between font-mono text-xs text-parchment/40">
            <span>0.50</span>
            <span>0.90</span>
            <span>1.50</span>
          </div>
        </div>
      </div>

      <button
        class="rounded border border-teal/40 bg-teal/10 px-4 py-2 text-teal transition-colors hover:bg-teal/20 disabled:opacity-50"
        type="button"
        :disabled="previewing"
        @click="previewVoice"
      >
        {{ previewing ? 'Lecture…' : 'Tester la voix' }}
      </button>
      <p v-if="previewError" class="text-sm text-blood">{{ previewError }}</p>
      <p v-if="previewSuccess" class="text-sm text-green-400">Extrait généré.</p>
    </div>

    <p v-if="store.error" class="text-sm text-blood">
      {{ store.error }}
    </p>

    <div class="flex flex-wrap gap-3">
      <button
        class="rounded bg-gold px-4 py-2 font-semibold text-ink transition-colors hover:bg-gold/80 disabled:opacity-50"
        type="button"
        :disabled="store.loading"
        @click="save"
      >
        {{ store.loading ? 'Sauvegarde…' : 'Sauvegarder voix' }}
      </button>
      <button
        class="rounded border border-parchment/20 px-4 py-2 text-parchment/70 transition-colors hover:border-parchment/40"
        type="button"
        @click="store.fetchHealth()"
      >
        Rafraîchir le statut
      </button>
    </div>
  </div>
</template>
