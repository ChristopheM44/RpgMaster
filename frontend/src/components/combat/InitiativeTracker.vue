<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../../stores/game'

const emit = defineEmits<{
  nextTurn: []
}>()

const gameStore = useGameStore()

const orderedCombatants = computed(() =>
  [...gameStore.combatants].sort((a, b) => b.initiative - a.initiative),
)

function hpPct(cur: number, max: number): number {
  return Math.max(0, max > 0 ? (cur / max) * 100 : 0)
}

function hpColor(cur: number, max: number): string {
  const pct = max > 0 ? cur / max : 0
  return pct > 0.5 ? 'var(--color-green)' : pct > 0.25 ? '#e5b93a' : 'var(--color-blood)'
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
    class="flex w-[260px] shrink-0 flex-col border-r"
    :style="{ borderColor: 'var(--color-border)', background: 'linear-gradient(180deg, rgba(36,30,32,0.95), var(--color-bg-elev))' }"
  >
    <div class="border-b px-4 py-3" :style="{ borderColor: 'var(--color-border)' }">
      <div class="flex items-center justify-between">
        <span class="rpg-eyebrow" :style="{ color: 'var(--color-blood)' }">Combat</span>
        <span class="font-mono text-[11px]" :style="{ color: 'var(--color-gold)' }">Round {{ gameStore.roundNumber }}</span>
      </div>
      <p class="mt-1 truncate text-xs" :style="{ color: 'var(--color-text-muted)' }">
        {{ gameStore.activeCombatant?.name ?? 'Initiative' }}
      </p>
    </div>

    <div class="min-h-0 flex-1 space-y-1.5 overflow-y-auto p-3">
      <button
        v-for="combatant in orderedCombatants"
        :key="combatant.id"
        class="group grid h-14 w-full grid-cols-[32px_34px_1fr] items-center gap-2 rounded-md border px-2 text-left transition-all"
        :style="{
          background: combatant.id === gameStore.selectedCombatantId
            ? 'rgba(247,199,107,0.08)'
            : combatant.is_active ? 'rgba(255,130,71,0.08)' : 'rgba(255,255,255,0.025)',
          borderColor: combatant.is_active
            ? 'rgba(247,199,107,0.55)'
            : combatant.id === gameStore.selectedCombatantId ? 'rgba(247,236,208,0.28)' : 'rgba(247,236,208,0.08)',
          boxShadow: combatant.is_active ? '0 0 18px rgba(255,130,71,0.12)' : 'none',
        }"
        @click="gameStore.setSelectedCombatant(combatant.id)"
      >
        <span class="font-mono text-xs font-bold" :style="{ color: combatant.is_active ? 'var(--color-gold)' : 'var(--color-text-muted)' }">
          {{ combatant.initiative }}
        </span>
        <span
          class="flex h-8 w-8 items-center justify-center rounded-full border text-[10px] font-bold"
          :style="{
            background: combatant.kind === 'monster'
              ? `radial-gradient(circle at 35% 25%, rgba(255,255,255,0.22), ${combatant.color ?? 'var(--color-blood)'})`
              : isAiCompanion(combatant)
                ? 'linear-gradient(135deg, var(--color-arcane), #7050b0)'
                : 'linear-gradient(135deg, var(--color-ember), var(--color-gold))',
            borderColor: combatant.is_active ? 'var(--color-gold)' : 'rgba(247,236,208,0.22)',
            color: combatant.kind === 'pc' ? 'var(--color-bg)' : 'white',
          }"
        >{{ labelFor(combatant) }}</span>
          <span class="min-w-0">
            <span class="flex items-center gap-1.5">
              <span class="truncate font-display text-sm font-semibold" :style="{ color: combatant.is_active ? 'var(--color-gold)' : 'var(--color-parchment)' }">
                {{ combatant.name }}
              </span>
              <span v-if="isAiCompanion(combatant)" class="text-[9px] font-bold uppercase tracking-[0.1em]" :style="{ color: 'var(--color-arcane)' }">IA</span>
              <span v-if="gameStore.isCharacterThinking(combatant.id)" class="text-[9px] font-bold uppercase tracking-[0.08em]" :style="{ color: 'var(--color-gold)' }">PENSE…</span>
            </span>
          <span class="mt-1 flex items-center gap-1.5">
            <span class="h-1.5 flex-1 overflow-hidden rounded-full bg-black/40">
              <span
                class="block h-full rounded-full transition-all"
                :style="{ width: `${hpPct(combatant.hp_current, combatant.hp_max)}%`, background: hpColor(combatant.hp_current, combatant.hp_max) }"
              />
            </span>
            <span class="font-mono text-[10px]" :style="{ color: 'var(--color-text-muted)' }">
              {{ combatant.hp_current }}/{{ combatant.hp_max }}
            </span>
          </span>
        </span>
      </button>
    </div>

    <div class="space-y-2 border-t p-3" :style="{ borderColor: 'var(--color-border)' }">
      <button class="rpg-btn-primary w-full justify-center !py-2 !text-[11px]" @click="emit('nextTurn')">
        Tour suivant
      </button>
      <div class="grid grid-cols-3 gap-1.5">
        <button class="rpg-btn-secondary justify-center !px-1 !py-1 !text-[9px] opacity-45" disabled title="Bientôt">+ Allié</button>
        <button class="rpg-btn-secondary justify-center !px-1 !py-1 !text-[9px] opacity-45" disabled title="Bientôt">+ Ennemi</button>
        <button class="rpg-btn-secondary justify-center !px-1 !py-1 !text-[9px] opacity-45" disabled title="Bientôt">Init.</button>
      </div>
    </div>
  </aside>
</template>
