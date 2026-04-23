<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useGameStore } from '../../stores/game'
import DiceRollResult from './DiceRollResult.vue'

const gameStore = useGameStore()
const logEl = ref<HTMLElement | null>(null)

watch(
  () => gameStore.narrativeLog.length + (gameStore.isProcessing ? 1 : 0),
  async () => {
    await nextTick()
    if (logEl.value) {
      logEl.value.scrollTop = logEl.value.scrollHeight
    }
  },
)
</script>

<template>
  <div class="flex flex-1 min-h-0 flex-col">
    <div class="border-b border-gold/20 px-4 py-2">
      <h2 class="rpg-eyebrow">Récit</h2>
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
          <p class="prose-narrative italic">{{ entry.text }}</p>
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

        <!-- Action IA structurée (combat) -->
        <div v-else-if="entry.type === 'combat_action' && entry.combatAction" class="rpg-card border-blood/30 bg-blood/5 px-3 py-2 text-sm space-y-1">
          <div class="flex items-center gap-2 text-blood font-semibold">
            <span>⚔</span>
            <span>{{ entry.combatAction.attacker_name }}</span>
            <span class="text-parchment/50 font-normal">attaque</span>
            <span>{{ entry.combatAction.target_name }}</span>
            <span v-if="entry.combatAction.critical" class="rpg-chip text-gold border-gold/50 bg-gold/10 ml-1">Critique !</span>
          </div>
          <div class="flex flex-wrap gap-3 text-xs text-parchment/70">
            <span>d20 : <span class="font-mono text-parchment">{{ entry.combatAction.d20 }}</span></span>
            <span>Total : <span class="font-mono text-parchment">{{ entry.combatAction.attack_roll }}</span> vs CA {{ entry.combatAction.target_ac }}</span>
            <span v-if="entry.combatAction.hit" class="text-green-400 font-semibold">Touché</span>
            <span v-else class="text-parchment/40">Raté</span>
            <span v-if="entry.combatAction.hit && entry.combatAction.damage !== null" class="text-blood font-semibold">
              {{ entry.combatAction.damage }} dégâts
            </span>
          </div>
        </div>

        <!-- Message système -->
        <div v-else-if="entry.type === 'system'">
          <p class="text-center text-xs text-parchment/40 py-1">─── {{ entry.text }} ───</p>
        </div>
      </template>

      <!-- Indicateur "MJ réfléchit..." -->
      <div v-if="gameStore.isProcessing" class="flex items-center gap-2 py-1">
        <span class="text-gold/50 italic text-sm">Le Maître du Jeu réfléchit</span>
        <span class="flex gap-1">
          <span class="inline-block h-1.5 w-1.5 rounded-full bg-gold/50 animate-bounce" style="animation-delay: 0ms" />
          <span class="inline-block h-1.5 w-1.5 rounded-full bg-gold/50 animate-bounce" style="animation-delay: 150ms" />
          <span class="inline-block h-1.5 w-1.5 rounded-full bg-gold/50 animate-bounce" style="animation-delay: 300ms" />
        </span>
      </div>
    </div>
  </div>
</template>
