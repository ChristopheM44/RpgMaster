<script setup lang="ts">
import { ref } from 'vue'

type Mode = 'libre' | 'script' | 'auto'

const emit = defineEmits<{
  confirm: [mode: Mode, script?: string]
  cancel: []
}>()

const mode = ref<Mode>('libre')
const scriptText = ref('')

const options: { id: Mode; label: string; description: string }[] = [
  {
    id: 'libre',
    label: 'Libre',
    description: 'Le Maître du Jeu improvise librement en fonction de vos personnages.',
  },
  {
    id: 'script',
    label: 'Script',
    description: 'Décrivez le scénario de départ (lieu, enjeux, quête, PNJ clés…).',
  },
  {
    id: 'auto',
    label: 'Génération auto',
    description:
      "Le système génère automatiquement une accroche d'aventure adaptée à vos personnages.",
  },
]

function confirm() {
  emit('confirm', mode.value, mode.value === 'script' ? scriptText.value : undefined)
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
    <div class="w-[500px] rounded-lg border border-gold/40 bg-ink shadow-2xl p-6">
      <h2 class="text-lg font-bold text-gold mb-1">Lancer l'aventure</h2>
      <p class="text-parchment/50 text-xs mb-5">Choisissez comment le Maître du Jeu va débuter la session.</p>

      <!-- Mode tabs -->
      <div class="flex gap-2 mb-5">
        <button
          v-for="opt in options"
          :key="opt.id"
          class="flex-1 rounded border py-2 text-sm font-medium transition-colors"
          :class="
            mode === opt.id
              ? 'border-gold bg-gold/20 text-gold'
              : 'border-parchment/20 bg-parchment/5 text-parchment/50 hover:border-parchment/40 hover:text-parchment/80'
          "
          @click="mode = opt.id"
        >
          {{ opt.label }}
        </button>
      </div>

      <!-- Mode content -->
      <div class="mb-5 min-h-[120px]">
        <p class="text-parchment/70 text-sm mb-3">
          {{ options.find((o) => o.id === mode)?.description }}
        </p>

        <textarea
          v-if="mode === 'script'"
          v-model="scriptText"
          rows="5"
          placeholder="Ex : Les aventuriers se retrouvent à Phandalin, embauchés pour escorter un convoi de matériel minier. En chemin, ils découvrent que des gobelins ont attaqué les muletiers..."
          class="w-full rounded border border-parchment/20 bg-parchment/5 p-3 text-sm text-parchment placeholder-parchment/30 resize-none focus:border-gold/40 focus:outline-none transition-colors"
        />
      </div>

      <!-- Actions -->
      <div class="flex justify-end gap-3">
        <button
          class="rounded border border-parchment/20 px-4 py-2 text-sm text-parchment/60 hover:text-parchment transition-colors"
          @click="emit('cancel')"
        >
          Annuler
        </button>
        <button
          :disabled="mode === 'script' && !scriptText.trim()"
          class="rounded border border-gold/60 bg-gold/15 px-5 py-2 text-sm font-semibold text-gold hover:bg-gold/25 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          @click="confirm"
        >
          Lancer l'aventure !
        </button>
      </div>
    </div>
  </div>
</template>
