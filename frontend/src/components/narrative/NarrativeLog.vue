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
  <div class="flex flex-1 min-h-0 flex-col overflow-hidden">

    <!-- Big section heading -->
    <div
      class="flex shrink-0 items-baseline gap-4 px-10 pt-8 pb-4"
    >
      <h2
        class="font-display text-[32px] font-bold tracking-[0.05em] leading-none"
        :style="{ color: 'var(--color-parchment)' }"
      >
        <span :style="{ color: 'var(--color-ember)' }">✦</span>
        Récit
      </h2>
      <div
        class="flex-1 h-px"
        :style="{ background: 'linear-gradient(90deg, var(--color-border-strong), transparent)' }"
      />
    </div>

    <!-- Log -->
    <div
      ref="logEl"
      class="flex-1 overflow-y-auto px-10 pb-6 space-y-6"
    >
      <p
        v-if="gameStore.narrativeLog.length === 0"
        class="mt-16 text-center font-serif italic text-lg"
        :style="{ color: 'var(--color-text-muted)' }"
      >
        En attente du début de la session…
      </p>

      <template v-for="entry in gameStore.narrativeLog" :key="entry.id">

        <!-- Narration GM -->
        <div v-if="entry.type === 'narration'" class="space-y-3">
          <div class="rpg-eyebrow" :style="{ color: 'var(--color-ember)' }">
            ✦ {{ entry.speaker ?? 'Maître du Jeu' }}
          </div>
          <p
            class="font-serif leading-[1.8] text-pretty"
            style="font-size: 17px;"
            :style="{ color: 'var(--color-parchment-dark)' }"
          >{{ entry.text }}</p>
        </div>

        <!-- Action joueur -->
        <div
          v-else-if="entry.type === 'player'"
          class="flex gap-3 rounded-lg border-l-2 py-2.5 pl-4 pr-3"
          :style="{
            borderColor: 'rgba(192,144,255,0.5)',
            background: 'rgba(192,144,255,0.05)',
          }"
        >
          <div class="min-w-0 flex-1">
            <span
              v-if="entry.speaker"
              class="mr-2 text-sm font-display font-semibold"
              :style="{ color: 'var(--color-arcane)' }"
            >{{ entry.speaker }}</span>
            <span class="text-sm" :style="{ color: 'var(--color-parchment)' }">{{ entry.text }}</span>
          </div>
        </div>

        <!-- Jet de dé -->
        <div v-else-if="entry.type === 'roll' && entry.roll">
          <DiceRollResult :roll="entry.roll" />
        </div>

        <!-- Action de combat -->
        <div
          v-else-if="entry.type === 'combat_action' && entry.combatAction"
          class="rounded-lg border px-4 py-3 text-sm space-y-2"
          :style="{
            background: 'rgba(232,69,69,0.06)',
            borderColor: 'rgba(232,69,69,0.2)',
          }"
        >
          <div class="flex items-center gap-2 font-semibold" :style="{ color: 'var(--color-blood)' }">
            <span>⚔</span>
            <span class="font-display">{{ entry.combatAction.attacker_name }}</span>
            <span class="text-xs font-normal" :style="{ color: 'var(--color-text-muted)' }">attaque</span>
            <span class="font-display">{{ entry.combatAction.target_name }}</span>
            <span
              v-if="entry.combatAction.critical"
              class="rpg-chip ml-auto"
              :style="{ color: 'var(--color-gold)', borderColor: 'rgba(240,199,100,0.4)', background: 'rgba(240,199,100,0.1)' }"
            >Critique !</span>
          </div>
          <div class="flex flex-wrap gap-3 text-xs" :style="{ color: 'var(--color-text-muted)' }">
            <span>d20 : <span class="font-mono font-bold" :style="{ color: 'var(--color-parchment)' }">{{ entry.combatAction.d20 }}</span></span>
            <span>Total : <span class="font-mono font-bold" :style="{ color: 'var(--color-parchment)' }">{{ entry.combatAction.attack_roll }}</span> vs CA {{ entry.combatAction.target_ac }}</span>
            <span v-if="entry.combatAction.hit" class="font-semibold" :style="{ color: 'var(--color-green)' }">Touché</span>
            <span v-else :style="{ color: 'var(--color-text-dim)' }">Raté</span>
            <span v-if="entry.combatAction.hit && entry.combatAction.damage !== null" class="font-semibold" :style="{ color: 'var(--color-blood)' }">{{ entry.combatAction.damage }} dégâts</span>
          </div>
        </div>

        <!-- Système -->
        <div v-else-if="entry.type === 'system'" class="py-1 text-center text-xs" :style="{ color: 'var(--color-text-dim)' }">
          ──── {{ entry.text }} ────
        </div>

      </template>

      <!-- GM pense -->
      <div
        v-if="gameStore.isProcessing"
        class="flex items-center gap-3 rounded-lg border-l-2 py-3 pl-4"
        :style="{ borderColor: 'rgba(240,199,100,0.3)', background: 'rgba(240,199,100,0.04)' }"
      >
        <span class="font-serif italic text-sm" :style="{ color: 'var(--color-gold)', opacity: '0.7' }">
          Le Maître du Jeu réfléchit
        </span>
        <span class="flex gap-1">
          <span v-for="delay in ['0ms', '150ms', '300ms']" :key="delay" class="inline-block h-1.5 w-1.5 rounded-full animate-bounce" :style="{ background: 'var(--color-gold)', opacity: '0.5', animationDelay: delay }" />
        </span>
      </div>
    </div>
  </div>
</template>
