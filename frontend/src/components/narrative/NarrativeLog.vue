<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useGameStore } from '../../stores/game'
import DiceRollResult from './DiceRollResult.vue'

const gameStore = useGameStore()
const logEl = ref<HTMLElement | null>(null)

watch(
  () => gameStore.narrativeLog.length,
  async () => {
    await nextTick()
    if (logEl.value) {
      logEl.value.scrollTop = logEl.value.scrollHeight
    }
  },
)
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="border-b border-gold/20 px-4 py-2">
      <h2 class="text-sm font-semibold uppercase tracking-widest text-gold/60">Récit</h2>
    </div>

    <div ref="logEl" class="flex-1 overflow-y-auto px-4 py-3 space-y-3 scrollbar-thin scrollbar-track-ink scrollbar-thumb-gold/20">
      <p v-if="gameStore.narrativeLog.length === 0" class="text-center text-parchment/30 italic mt-8">
        En attente du début de la session...
      </p>

      <template v-for="entry in gameStore.narrativeLog" :key="entry.id">
        <!-- Narration du MJ -->
        <div v-if="entry.type === 'narration'" class="space-y-1">
          <span v-if="entry.speaker" class="text-xs font-semibold text-gold/70 uppercase tracking-wide">
            {{ entry.speaker }}
          </span>
          <p class="text-parchment leading-relaxed italic">{{ entry.text }}</p>
        </div>

        <!-- Action joueur -->
        <div v-else-if="entry.type === 'player'" class="flex gap-2">
          <span class="text-arcane font-semibold shrink-0">▶</span>
          <div>
            <span v-if="entry.speaker" class="text-arcane font-semibold text-sm">{{ entry.speaker }} : </span>
            <span class="text-parchment/90">{{ entry.text }}</span>
          </div>
        </div>

        <!-- Jet de dé -->
        <div v-else-if="entry.type === 'roll' && entry.roll">
          <DiceRollResult :roll="entry.roll" />
        </div>

        <!-- Message système -->
        <div v-else-if="entry.type === 'system'">
          <p class="text-center text-xs text-parchment/40 py-1">─── {{ entry.text }} ───</p>
        </div>
      </template>
    </div>
  </div>
</template>
