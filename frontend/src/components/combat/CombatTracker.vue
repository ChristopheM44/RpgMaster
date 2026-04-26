<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../../stores/game'

const gameStore = useGameStore()

function hpColor(cur: number, max: number): string {
  const pct = max > 0 ? cur / max : 0
  return pct > 0.5 ? 'var(--color-green)' : pct > 0.25 ? '#e5b93a' : 'var(--color-blood)'
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
      class="flex shrink-0 items-center justify-between border-b px-4 py-2.5"
      :style="{ borderColor: 'var(--color-border)' }"
    >
      <span
        class="rpg-eyebrow"
        :style="{ color: 'var(--color-blood)' }"
      >⚔ Combat</span>
      <span
        v-if="isInCombat"
        class="font-mono text-[11px]"
        :style="{ color: 'rgba(232,69,69,0.7)' }"
      >Round {{ gameStore.roundNumber }}</span>
    </div>

    <!-- Combatant list -->
    <div class="flex-1 overflow-y-auto px-3 py-3 space-y-2">
      <p
        v-if="!isInCombat"
        class="mt-4 text-center font-serif italic text-sm"
        :style="{ color: 'var(--color-text-muted)' }"
      >
        Hors combat
      </p>

      <div
        v-for="combatant in gameStore.combatants"
        :key="combatant.id"
        class="rounded-lg border px-3 py-2.5 transition-all"
        :style="{
          background: combatant.is_active ? 'rgba(255,130,71,0.05)' : 'var(--color-surface)',
          borderColor: combatant.is_active ? 'rgba(255,130,71,0.5)' : 'var(--color-border)',
          boxShadow: combatant.is_active ? '0 0 16px rgba(255,130,71,0.12)' : 'none',
        }"
      >
        <div class="flex items-center gap-2.5">
          <!-- Initiative badge -->
          <div
            class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md font-mono text-xs font-bold"
            :style="{
              background: 'var(--color-surface-raised)',
              color: combatant.is_active ? 'var(--color-gold)' : 'var(--color-text-muted)',
            }"
          >{{ combatant.initiative }}</div>

          <!-- Name + AI indicator -->
          <span
            class="flex-1 truncate font-display text-sm font-semibold"
            :style="{ color: combatant.is_active ? 'var(--color-gold)' : 'var(--color-parchment)' }"
          >{{ combatant.name }}</span>
          <span
            v-if="isAiCompanion(combatant)"
            class="shrink-0 text-[9px] font-bold tracking-[0.1em]"
            :style="{ color: 'var(--color-arcane)' }"
          >IA</span>
          <span
            v-if="gameStore.isCharacterThinking(combatant.id)"
            class="shrink-0 text-[9px] font-bold tracking-[0.08em]"
            :style="{ color: 'var(--color-gold)' }"
          >PENSE…</span>

          <!-- Active turn diamond -->
          <span v-if="combatant.is_active" class="shrink-0 text-xs" :style="{ color: 'var(--color-gold)' }">◆</span>
        </div>

        <!-- HP bar (D3 style) -->
        <div class="mt-2 flex items-center gap-2">
          <div
            class="relative flex-1 overflow-hidden rounded-full"
            style="height: 8px; background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.04);"
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
            class="shrink-0 font-mono text-xs"
            :style="{ color: 'var(--color-text-muted)' }"
          >{{ combatant.hp_current }}<span :style="{ color: 'var(--color-text-dim)' }">/{{ combatant.hp_max }}</span></span>
        </div>

        <!-- Conditions -->
        <div v-if="combatant.conditions.length" class="mt-1.5 flex flex-wrap gap-1">
          <span
            v-for="cond in combatant.conditions"
            :key="cond"
            class="rpg-chip"
            :style="{ color: 'var(--color-blood)', borderColor: 'rgba(232,69,69,0.4)' }"
          >{{ cond }}</span>
        </div>

        <!-- Death saves -->
        <div
          v-if="combatant.hp_current <= 0 && combatant.death_saves"
          class="mt-2 space-y-1"
        >
          <div v-if="combatant.death_saves.stable" class="text-xs italic" :style="{ color: 'var(--color-green)' }">
            Stable
          </div>
          <template v-else>
            <div class="flex items-center gap-1.5">
              <span class="w-14 shrink-0 text-xs" :style="{ color: 'rgba(111,217,111,0.7)' }">Succès</span>
              <div class="flex gap-1">
                <span
                  v-for="i in 3"
                  :key="i"
                  class="h-3 w-3 rounded-full border transition-colors"
                  :style="i <= (combatant.death_saves.successes ?? 0)
                    ? { background: 'var(--color-green)', borderColor: 'var(--color-green)' }
                    : { background: 'transparent', borderColor: 'rgba(247,236,208,0.2)' }"
                />
              </div>
            </div>
            <div class="flex items-center gap-1.5">
              <span class="w-14 shrink-0 text-xs" :style="{ color: 'rgba(232,69,69,0.7)' }">Échecs</span>
              <div class="flex gap-1">
                <span
                  v-for="i in 3"
                  :key="i"
                  class="h-3 w-3 rounded-full border transition-colors"
                  :style="i <= (combatant.death_saves.failures ?? 0)
                    ? { background: 'var(--color-blood)', borderColor: 'var(--color-blood)' }
                    : { background: 'transparent', borderColor: 'rgba(247,236,208,0.2)' }"
                />
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>
