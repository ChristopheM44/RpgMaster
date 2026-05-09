<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useGameStore } from '../../stores/game'
import DiceRollResult from './DiceRollResult.vue'

const gameStore = useGameStore()
const logEl = ref<HTMLElement | null>(null)

watch(
  () => gameStore.narrativeLog.length + ((gameStore.isProcessing || gameStore.isGmThinking) ? 1 : 0),
  async () => {
    await nextTick()
    if (logEl.value) {
      logEl.value.scrollTop = logEl.value.scrollHeight
    }
  },
)
</script>

<template>
  <div class="flex flex-1 min-h-0 flex-col overflow-hidden">

    <!-- Big section heading -->
    <div
      class="flex shrink-0 items-baseline gap-4 px-10 pt-8 pb-4"
    >
      <h2
        class="rpg-text-main font-display text-[32px] font-bold tracking-[0.05em] leading-none"
      >
        <span class="rpg-text-ember">✦</span>
        Récit
      </h2>
      <div class="rpg-divider flex-1 h-px" />
    </div>

    <!-- Log -->
    <div
      ref="logEl"
      class="flex-1 overflow-y-auto px-10 pb-6 space-y-6"
    >
      <p
        v-if="gameStore.narrativeLog.length === 0"
        class="rpg-text-muted mt-16 text-center font-serif italic text-lg"
      >
        En attente du début de la session…
      </p>

      <template v-for="entry in gameStore.narrativeLog" :key="entry.id">

        <!-- Narration GM -->
        <div v-if="entry.type === 'narration'" class="space-y-3">
          <div class="rpg-eyebrow">
            ✦ {{ entry.speaker ?? 'Maître du Jeu' }}
          </div>
          <p
            class="rpg-text-secondary font-serif leading-[1.8] text-[17px] text-pretty"
          >{{ entry.text }}</p>
        </div>

        <!-- Dialogue compagnon / PNJ -->
        <div
          v-else-if="entry.type === 'dialogue'"
          class="rpg-dialogue-entry flex gap-3 rounded-lg border-l-2 py-2.5 pl-4 pr-3"
          :class="{ 'is-companion': entry.speaker_kind === 'companion' }"
        >
          <div class="min-w-0 flex-1">
            <span
              v-if="entry.speaker"
              class="mr-2 text-sm font-display font-semibold"
              :class="entry.speaker_kind === 'companion' ? 'rpg-text-arcane' : 'rpg-text-gold'"
            >{{ entry.speaker }}</span>
            <span class="rpg-text-main text-sm leading-relaxed">{{ entry.text }}</span>
          </div>
        </div>

        <!-- Action joueur -->
        <div
          v-else-if="entry.type === 'player'"
          class="rpg-player-entry flex gap-3 rounded-lg border-l-2 py-2.5 pl-4 pr-3"
        >
          <div class="min-w-0 flex-1">
            <span
              v-if="entry.speaker"
              class="rpg-text-arcane mr-2 text-sm font-display font-semibold"
            >{{ entry.speaker }}</span>
            <span class="rpg-text-main text-sm">{{ entry.text }}</span>
          </div>
        </div>

        <!-- Jet de dé -->
        <div v-else-if="entry.type === 'roll' && entry.roll">
          <DiceRollResult :roll="entry.roll" />
        </div>

        <!-- Action de combat -->
        <div
          v-else-if="entry.type === 'combat_action' && entry.combatAction"
          class="rpg-combat-log-entry rounded-lg border px-4 py-3 text-sm space-y-2"
        >
          <div class="rpg-text-blood flex items-center gap-2 font-semibold">
            <span>⚔</span>
            <span class="font-display">{{ entry.combatAction.attacker_name }}</span>
            <span class="rpg-text-muted text-xs font-normal">attaque</span>
            <span class="font-display">{{ entry.combatAction.target_name }}</span>
            <span
              v-if="entry.combatAction.critical"
              class="rpg-chip rpg-tone-gold ml-auto"
            >Critique !</span>
          </div>
          <div class="rpg-text-muted flex flex-wrap gap-3 text-xs">
            <span>d20 : <span class="rpg-text-main font-mono font-bold">{{ entry.combatAction.d20 }}</span></span>
            <span>Total : <span class="rpg-text-main font-mono font-bold">{{ entry.combatAction.attack_roll }}</span> vs CA {{ entry.combatAction.target_ac }}</span>
            <span v-if="entry.combatAction.hit" class="rpg-text-green font-semibold">Touché</span>
            <span v-else class="rpg-text-dim">Raté</span>
            <span v-if="entry.combatAction.hit && entry.combatAction.damage !== null" class="rpg-text-blood font-semibold">{{ entry.combatAction.damage }} dégâts</span>
          </div>
        </div>

        <!-- Système -->
        <div v-else-if="entry.type === 'system'" class="rpg-text-dim py-1 text-center text-xs">
          ──── {{ entry.text }} ────
        </div>

      </template>

      <!-- GM pense -->
      <div
        v-if="gameStore.isProcessing || gameStore.isGmThinking"
        class="rpg-thinking-entry flex items-center gap-3 rounded-lg border-l-2 py-3 pl-4"
      >
        <span class="rpg-text-gold font-serif italic text-sm opacity-70">
          Le Maître du Jeu réfléchit
        </span>
        <span class="flex gap-1">
          <span v-for="delay in ['0ms', '150ms', '300ms']" :key="delay" class="rpg-thinking-dot inline-block h-1.5 w-1.5 rounded-full animate-bounce" :style="{ animationDelay: delay }" />
        </span>
      </div>
    </div>
  </div>
</template>
