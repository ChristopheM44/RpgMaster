<script setup lang="ts">
import { ref } from 'vue'

type Mode = 'libre' | 'script' | 'auto'

const emit = defineEmits<{
  confirm: [
    mode: Mode,
    script?: string,
    options?: {
      adventure_preset?: string
      biome?: string
      weather?: string
      tone?: string
    }
  ]
  cancel: []
}>()

const mode = ref<Mode>('libre')
const scriptText = ref('')

const selectedPreset = ref('')
const selectedBiome = ref('')
const selectedWeather = ref('')
const selectedTone = ref('')

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
  emit(
    'confirm',
    mode.value,
    mode.value === 'script' ? scriptText.value : undefined,
    mode.value !== 'script'
      ? {
          adventure_preset: selectedPreset.value || undefined,
          biome: selectedBiome.value || undefined,
          weather: selectedWeather.value || undefined,
          tone: selectedTone.value || undefined,
        }
      : undefined
  )
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

        <!-- Custom seed options for Libre and Auto modes -->
        <div v-else class="border-t border-parchment/10 pt-4 mt-3">
          <h3 class="text-xs font-bold text-gold uppercase tracking-wider mb-3">Options de départ (Optionnel)</h3>
          
          <div class="grid grid-cols-2 gap-3">
            <!-- Preset d'Univers -->
            <div>
              <label class="block text-[10px] text-parchment/50 uppercase mb-1">Ambiance / Univers</label>
              <select v-model="selectedPreset" class="rpg-input w-full text-xs py-1">
                <option value="">Aléatoire / Classique</option>
                <option value="pangee_romain">Pangée & Empire Romain</option>
                <option value="jungle_dinos">Jungle & Ruines (Dinos)</option>
                <option value="toundra_gelee">Toundra des Glaces</option>
                <option value="brume_gothique">Horreur Gothique</option>
              </select>
            </div>

            <!-- Biome -->
            <div>
              <label class="block text-[10px] text-parchment/50 uppercase mb-1">Biome</label>
              <select v-model="selectedBiome" class="rpg-input w-full text-xs py-1">
                <option value="">Aléatoire</option>
                <option value="taverne">Taverne animée</option>
                <option value="dungeon">Donjon / Crypte</option>
                <option value="forest">Forêt mystérieuse</option>
                <option value="swamp">Marécage fétide</option>
                <option value="desert">Désert aride</option>
                <option value="mountain">Montagne escarpée</option>
                <option value="coastal">Littoral sauvage</option>
                <option value="cave">Grotte naturelle</option>
                <option value="plains">Plaines herbeuses</option>
              </select>
            </div>

            <!-- Weather -->
            <div>
              <label class="block text-[10px] text-parchment/50 uppercase mb-1">Climat</label>
              <select v-model="selectedWeather" class="rpg-input w-full text-xs py-1">
                <option value="">Aléatoire</option>
                <option value="Calme">Calme</option>
                <option value="Tempétueux">Tempétueux</option>
                <option value="Brumeux">Brumeux</option>
                <option value="Nuit noire">Nuit noire</option>
                <option value="Éclipse lunaire">Éclipse lunaire</option>
              </select>
            </div>

            <!-- Tone -->
            <div>
              <label class="block text-[10px] text-parchment/50 uppercase mb-1">Ton</label>
              <select v-model="selectedTone" class="rpg-input w-full text-xs py-1">
                <option value="">Aléatoire</option>
                <option value="exploration calme">Exploration calme</option>
                <option value="mystérieuse et tendue">Mystérieuse et tendue</option>
                <option value="héroïque et active">Héroïque et active</option>
                <option value="survie immédiate">Survie immédiate</option>
              </select>
            </div>
          </div>
        </div>
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
