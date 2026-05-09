<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../../stores/game'

const gameStore = useGameStore()

const orderedCombatants = computed(() =>
  [...gameStore.combatants].sort((a, b) => b.initiative - a.initiative),
)

function hpPct(cur: number, max: number): number {
  return Math.max(0, max > 0 ? (cur / max) * 100 : 0)
}

function hpColor(cur: number, max: number): string {
  const pct = max > 0 ? cur / max : 0
  return pct > 0.5 ? 'var(--color-green)' : pct > 0.25 ? 'var(--color-gold)' : 'var(--color-blood)'
}

function labelFor(combatant: (typeof gameStore.combatants)[0]): string {
  if (combatant.token) return combatant.token
  return combatant.name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

function isAiCompanion(combatant: (typeof gameStore.combatants)[0]): boolean {
  return combatant.kind === 'pc' && Boolean(combatant.is_ai_controlled ?? combatant.is_ai)
}
</script>

<template>
  <aside
    class="rpg-initiative-sidebar flex w-[260px] shrink-0 flex-col border-r"
  >
    <div class="rpg-border border-b px-4 py-3">
      <div class="flex items-center justify-between">
        <span class="rpg-eyebrow rpg-text-blood">Combat</span>
        <span class="rpg-text-gold font-mono text-[11px]">Round {{ gameStore.roundNumber }}</span>
      </div>
      <p class="rpg-text-muted mt-1 truncate text-xs">
        {{ gameStore.activeCombatant?.name ?? 'Initiative' }}
      </p>
    </div>

    <div class="min-h-0 flex-1 space-y-1.5 overflow-y-auto p-3">
      <button
        v-for="combatant in orderedCombatants"
        :key="combatant.id"
        class="rpg-initiative-row group grid h-14 w-full grid-cols-[32px_34px_1fr] items-center gap-2 rounded-md border px-2 text-left transition-all"
        :class="{
          'is-active': combatant.is_active,
          'is-selected': combatant.id === gameStore.selectedCombatantId && !combatant.is_active,
        }"
        @click="gameStore.setSelectedCombatant(combatant.id)"
      >
        <span class="font-mono text-xs font-bold" :class="combatant.is_active ? 'rpg-text-gold' : 'rpg-text-muted'">
          {{ combatant.initiative }}
        </span>
        <span
          class="rpg-token flex h-8 w-8 items-center justify-center rounded-full border text-[10px] font-bold"
          :class="[
            combatant.is_active ? 'is-active' : '',
            combatant.kind === 'pc' ? 'is-pc' : '',
            combatant.kind === 'pc' && isAiCompanion(combatant) ? 'is-ai' : '',
            combatant.kind === 'pc' && !isAiCompanion(combatant) ? 'is-human' : '',
            combatant.kind === 'monster' ? 'is-monster' : '',
          ]"
          :style="combatant.kind === 'monster' && combatant.color
            ? { '--rpg-token-color': combatant.color }
            : undefined"
        >{{ labelFor(combatant) }}</span>
          <span class="min-w-0">
            <span class="flex items-center gap-1.5">
              <span class="truncate font-display text-sm font-semibold" :class="combatant.is_active ? 'rpg-text-gold' : 'rpg-text-main'">
                {{ combatant.name }}
              </span>
              <span v-if="isAiCompanion(combatant)" class="rpg-text-arcane text-[9px] font-bold uppercase tracking-[0.1em]">IA</span>
              <span v-if="gameStore.isCharacterThinking(combatant.id)" class="rpg-text-gold text-[9px] font-bold uppercase tracking-[0.08em]">PENSE…</span>
            </span>
          <span class="mt-1 flex items-center gap-1.5">
            <span class="h-1.5 flex-1 overflow-hidden rounded-full bg-black/40">
              <span
                class="block h-full rounded-full transition-all"
                :style="{ width: `${hpPct(combatant.hp_current, combatant.hp_max)}%`, background: hpColor(combatant.hp_current, combatant.hp_max) }"
              />
            </span>
            <span class="rpg-text-muted font-mono text-[10px]">
              {{ combatant.hp_current }}/{{ combatant.hp_max }}
            </span>
          </span>
        </span>
      </button>
    </div>

    <div class="rpg-border space-y-2 border-t p-3">
      <div class="grid grid-cols-3 gap-1.5">
        <button class="rpg-btn-secondary justify-center !px-1 !py-1 !text-[9px] opacity-45" disabled title="Bientôt">+ Allié</button>
        <button class="rpg-btn-secondary justify-center !px-1 !py-1 !text-[9px] opacity-45" disabled title="Bientôt">+ Ennemi</button>
        <button class="rpg-btn-secondary justify-center !px-1 !py-1 !text-[9px] opacity-45" disabled title="Bientôt">Init.</button>
      </div>
    </div>
  </aside>
</template>
