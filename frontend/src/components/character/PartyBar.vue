<script setup lang="ts">
import { useCharacterStore } from '../../stores/character'
import { useGameStore } from '../../stores/game'
import type { Character } from '../../types'

const emit = defineEmits<{
  (e: 'toggle-ai', characterId: string, nextIsAi: boolean): void
  (e: 'trigger-ai'): void
}>()

const charStore = useCharacterStore()
const gameStore = useGameStore()

function hpPct(c: Character): number {
  return Math.max(0, c.hp_max > 0 ? (c.hp_current / c.hp_max) * 100 : 0)
}

function hpColor(c: Character): string {
  const pct = hpPct(c)
  return pct > 50 ? 'var(--color-green)' : pct > 25 ? 'var(--color-gold)' : 'var(--color-blood)'
}

const isSelected = (c: Character) => c.id === charStore.myCharacter?.id

function onToggleAi(e: Event, c: Character) {
  e.stopPropagation()
  emit('toggle-ai', c.id, !c.is_ai)
}
</script>

<template>
  <div
    v-if="charStore.sessionCharacters.length > 0"
    class="rpg-party-bar flex shrink-0 items-stretch border-t"
  >
    <!-- GROUPE label (rotated) -->
    <div
      class="rpg-party-label-rail flex shrink-0 items-center justify-center border-r px-2"
    >
      <span
        class="rpg-party-label font-mono text-[9px] font-bold uppercase tracking-[0.25em]"
      >Groupe</span>
    </div>

    <!-- Characters list (horizontal scroll) -->
    <div class="flex flex-1 items-center gap-2 overflow-x-auto px-3 py-2">
      <div
        v-for="c in charStore.sessionCharacters"
        :key="c.id"
        class="rpg-party-card group relative flex shrink-0 cursor-pointer items-center gap-2.5 rounded-[10px] border px-3 py-2 transition-all"
        :class="{ 'is-selected': isSelected(c) }"
        @click="charStore.setMyCharacter(c)"
      >
        <!-- Toggle IA/Joueur, shown on hover -->
        <button
          class="rpg-ai-toggle absolute top-1 right-1 z-10 rounded px-1.5 py-0.5 text-[9px] font-bold opacity-0 transition-opacity group-hover:opacity-100"
          :class="{ 'is-ai': c.is_ai }"
          :title="c.is_ai ? 'Reprendre le contrôle (joueur)' : 'Laisser l\'IA jouer ce personnage'"
          @click="onToggleAi($event, c)"
        >{{ c.is_ai ? '👤' : '🤖' }}</button>
        <!-- Avatar -->
        <div
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg font-display text-base font-bold"
          :class="c.is_ai ? 'rpg-avatar-ai' : 'rpg-avatar-player'"
        >{{ c.name.charAt(0).toUpperCase() }}</div>

        <!-- Info -->
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-1.5">
            <span
              class="truncate font-display text-xs font-semibold"
              :class="isSelected(c) ? 'rpg-text-gold' : 'rpg-text-main'"
            >{{ c.name }}</span>
            <span
              v-if="c.is_ai"
              class="rpg-text-arcane shrink-0 text-[8px] font-bold tracking-[0.1em]"
            >IA</span>
            <span
              v-if="gameStore.isCharacterThinking(c.id)"
              class="rpg-text-gold shrink-0 text-[8px] font-bold tracking-[0.08em]"
            >PENSE…</span>
          </div>
          <div class="rpg-text-muted text-[10px]">{{ c.char_class }}</div>

          <!-- HP bar -->
          <div class="mt-1">
            <div
              class="rpg-hp-track hairline relative w-full overflow-hidden rounded-full"
            >
              <div
                class="absolute inset-y-0 left-0 rounded-full transition-all duration-300"
                :style="{ width: `${hpPct(c)}%`, background: hpColor(c) }"
              />
            </div>
            <div class="rpg-text-dim mt-0.5 font-mono text-[9px]">
              {{ c.hp_current }}/{{ c.hp_max }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
