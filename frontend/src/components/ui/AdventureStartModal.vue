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
    <div class="rpg-card w-[500px] shadow-2xl p-6">
      <h2 class="text-lg font-bold text-gold mb-1">Lancer l'aventure</h2>
      <p class="text-parchment/50 text-xs mb-5">Choisissez comment le Maître du Jeu va débuter la session.</p>

      <!-- Mode tabs -->
      <div class="flex gap-2 mb-5">
        <button
          v-for="opt in options"
          :key="opt.id"
          class="flex-1"
          :class="mode === opt.id ? 'rpg-btn-tonal tone-gold' : 'rpg-btn-secondary'"
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
          class="rpg-input w-full resize-none"
        />
      </div>

      <!-- Actions -->
      <div class="flex justify-end gap-3">
        <button
          class="rpg-btn-secondary"
          @click="emit('cancel')"
        >
          Annuler
        </button>
        <button
          :disabled="mode === 'script' && !scriptText.trim()"
          class="rpg-btn-primary"
          @click="confirm"
        >
          Lancer l'aventure !
        </button>
      </div>
    </div>
  </div>
</template>
