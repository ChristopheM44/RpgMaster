<script setup lang="ts">
import { useGameStore } from '../../stores/game'

const gameStore = useGameStore()
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="border-b border-gold/20 px-4 py-2">
      <h2 class="text-sm font-semibold uppercase tracking-widest text-gold/60">
        Combat
        <span v-if="gameStore.isInCombat" class="ml-2 text-blood text-xs">Round {{ gameStore.roundNumber }}</span>
      </h2>
    </div>

    <div class="flex-1 overflow-y-auto px-3 py-2 space-y-2">
      <p v-if="!gameStore.isInCombat" class="text-center text-parchment/30 italic text-sm mt-4">
        Hors combat
      </p>

      <div
        v-for="combatant in gameStore.combatants"
        :key="combatant.id"
        class="rounded border px-3 py-2 transition-colors"
        :class="combatant.is_active
          ? 'border-gold bg-gold/10'
          : 'border-gold/20 bg-ink/40'"
      >
        <div class="flex items-center gap-2">
          <!-- Initiative badge -->
          <span class="w-7 text-center text-xs font-bold text-gold/80 shrink-0">
            {{ combatant.initiative }}
          </span>

          <!-- Name + AI indicator -->
          <span class="flex-1 font-semibold truncate" :class="combatant.is_active ? 'text-gold' : 'text-parchment'">
            {{ combatant.name }}
          </span>
          <span v-if="combatant.is_ai" class="text-xs text-parchment/40">IA</span>

          <!-- Active turn indicator -->
          <span v-if="combatant.is_active" class="text-gold text-xs">◆</span>
        </div>

        <!-- HP bar -->
        <div class="mt-1.5 flex items-center gap-2">
          <div class="relative flex-1 h-2 rounded-full bg-ink overflow-hidden">
            <div
              class="absolute inset-y-0 left-0 rounded-full transition-all duration-300"
              :class="(combatant.hp_current / combatant.hp_max) > 0.5
                ? 'bg-green-600'
                : (combatant.hp_current / combatant.hp_max) > 0.25
                  ? 'bg-yellow-500'
                  : 'bg-blood'"
              :style="{ width: `${Math.max(0, (combatant.hp_current / combatant.hp_max) * 100)}%` }"
            />
          </div>
          <span class="text-xs text-parchment/60 shrink-0 font-mono">
            {{ combatant.hp_current }}/{{ combatant.hp_max }}
          </span>
        </div>

        <!-- Conditions -->
        <div v-if="combatant.conditions.length" class="mt-1 flex flex-wrap gap-1">
          <span
            v-for="cond in combatant.conditions"
            :key="cond"
            class="rounded bg-blood/20 px-1.5 py-0.5 text-xs text-blood"
          >{{ cond }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
