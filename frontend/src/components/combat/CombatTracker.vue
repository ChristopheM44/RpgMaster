<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../../stores/game'

const gameStore = useGameStore()

function hpColor(cur: number, max: number): string {
  const pct = max > 0 ? cur / max : 0
  return pct > 0.5 ? 'var(--color-green)' : pct > 0.25 ? 'var(--color-gold)' : 'var(--color-blood)'
}

function hpPct(cur: number, max: number): number {
  return Math.max(0, max > 0 ? (cur / max) * 100 : 0)
}

const isInCombat = computed(() => gameStore.isInCombat)

function isAiCompanion(combatant: (typeof gameStore.combatants)[0]): boolean {
  return combatant.kind === 'pc' && Boolean(combatant.is_ai_controlled ?? combatant.is_ai)
}
</script>

<template>
  <div class="flex flex-1 min-h-0 flex-col">

    <!-- Section header -->
    <div
      class="rpg-border flex shrink-0 items-center justify-between border-b px-4 py-2.5"
    >
      <span class="rpg-eyebrow rpg-text-blood">⚔ Combat</span>
      <span
        v-if="isInCombat"
        class="rpg-text-blood-soft font-mono text-[11px]"
      >Round {{ gameStore.roundNumber }}</span>
    </div>

    <!-- Combatant list -->
    <div class="flex-1 overflow-y-auto px-3 py-3 space-y-2">
      <p
        v-if="!isInCombat"
        class="rpg-text-muted mt-4 text-center font-serif italic text-sm"
      >
        Hors combat
      </p>

      <div
        v-for="combatant in gameStore.combatants"
        :key="combatant.id"
        class="rpg-combat-card rounded-lg border px-3 py-2.5 transition-all"
        :class="{ 'is-active': combatant.is_active }"
      >
        <div class="flex items-center gap-2.5">
          <!-- Initiative badge -->
          <div
            class="rpg-initiative-badge flex h-7 w-7 shrink-0 items-center justify-center rounded-md font-mono text-xs font-bold"
            :class="combatant.is_active ? 'rpg-text-gold' : 'rpg-text-muted'"
          >{{ combatant.initiative }}</div>

          <!-- Name + AI indicator -->
          <span
            class="flex-1 truncate font-display text-sm font-semibold"
            :class="combatant.is_active ? 'rpg-text-gold' : 'rpg-text-main'"
          >{{ combatant.name }}</span>
          <span
            v-if="isAiCompanion(combatant)"
            class="rpg-text-arcane shrink-0 text-[9px] font-bold tracking-[0.1em]"
          >IA</span>
          <span
            v-if="gameStore.isCharacterThinking(combatant.id)"
            class="rpg-text-gold shrink-0 text-[9px] font-bold tracking-[0.08em]"
          >PENSE…</span>

          <!-- Active turn diamond -->
          <span v-if="combatant.is_active" class="rpg-text-gold shrink-0 text-xs">◆</span>
        </div>

        <!-- HP bar (D3 style) -->
        <div class="mt-2 flex items-center gap-2">
          <div
            class="rpg-hp-track relative flex-1 overflow-hidden rounded-full"
          >
            <div
              class="absolute inset-y-0 left-0 rounded-full transition-all duration-300"
              :style="{
                width: `${hpPct(combatant.hp_current, combatant.hp_max)}%`,
                background: hpColor(combatant.hp_current, combatant.hp_max),
                boxShadow: combatant.is_active
                  ? `0 0 8px ${hpColor(combatant.hp_current, combatant.hp_max)}80`
                  : 'none',
              }"
            />
          </div>
          <span
            class="rpg-text-muted shrink-0 font-mono text-xs"
          >{{ combatant.hp_current }}<span class="rpg-text-dim">/{{ combatant.hp_max }}</span></span>
        </div>

        <!-- Conditions -->
        <div v-if="combatant.conditions.length" class="mt-1.5 flex flex-wrap gap-1">
          <span
            v-for="cond in combatant.conditions"
            :key="cond"
            class="rpg-chip rpg-tone-blood"
          >{{ cond }}</span>
        </div>

        <!-- Death saves -->
        <div
          v-if="combatant.hp_current <= 0 && combatant.death_saves"
          class="mt-2 space-y-1"
        >
          <div v-if="combatant.death_saves.stable" class="rpg-text-green text-xs italic">
            Stable
          </div>
          <template v-else>
            <div class="flex items-center gap-1.5">
              <span class="rpg-text-green w-14 shrink-0 text-xs opacity-70">Succès</span>
              <div class="flex gap-1">
                <span
                  v-for="i in 3"
                  :key="i"
                  class="rpg-death-dot h-3 w-3 rounded-full border transition-colors"
                  :class="{ 'is-success': i <= (combatant.death_saves.successes ?? 0) }"
                />
              </div>
            </div>
            <div class="flex items-center gap-1.5">
              <span class="rpg-text-blood-soft w-14 shrink-0 text-xs">Échecs</span>
              <div class="flex gap-1">
                <span
                  v-for="i in 3"
                  :key="i"
                  class="rpg-death-dot h-3 w-3 rounded-full border transition-colors"
                  :class="{ 'is-failure': i <= (combatant.death_saves.failures ?? 0) }"
                />
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>
