<script setup lang="ts">
import { computed } from 'vue'
import { useCharacterStore } from '../../stores/character'
import type { Character } from '../../types'

const charStore = useCharacterStore()

function hpPct(c: Character): number {
  return Math.max(0, c.hp_max > 0 ? (c.hp_current / c.hp_max) * 100 : 0)
}

function hpColor(c: Character): string {
  const pct = hpPct(c)
  return pct > 50 ? 'var(--color-green)' : pct > 25 ? '#e5b93a' : 'var(--color-blood)'
}

const isSelected = (c: Character) => c.id === charStore.myCharacter?.id
</script>

<template>
  <div
    v-if="charStore.sessionCharacters.length > 0"
    class="flex shrink-0 items-stretch border-t"
    :style="{
      borderColor: 'var(--color-border)',
      background: 'var(--color-bg-elev)',
      height: '88px',
    }"
  >
    <!-- GROUPE label (rotated) -->
    <div
      class="flex shrink-0 items-center justify-center border-r px-2"
      :style="{ borderColor: 'var(--color-border)', width: '32px' }"
    >
      <span
        class="font-mono text-[9px] font-bold uppercase tracking-[0.25em]"
        :style="{
          color: 'var(--color-text-dim)',
          writingMode: 'vertical-rl',
          transform: 'rotate(180deg)',
        }"
      >Groupe</span>
    </div>

    <!-- Characters list (horizontal scroll) -->
    <div class="flex flex-1 items-center gap-2 overflow-x-auto px-3 py-2">
      <div
        v-for="c in charStore.sessionCharacters"
        :key="c.id"
        class="flex shrink-0 cursor-pointer items-center gap-2.5 rounded-[10px] border px-3 py-2 transition-all"
        style="min-width: 160px;"
        :style="{
          borderColor: isSelected(c) ? 'var(--color-ember)' : 'var(--color-border)',
          background: isSelected(c)
            ? 'linear-gradient(135deg, rgba(255,130,71,0.12), rgba(240,199,100,0.06))'
            : 'var(--color-surface)',
          boxShadow: isSelected(c) ? '0 0 16px rgba(255,130,71,0.15)' : 'none',
        }"
        @click="charStore.setMyCharacter(c)"
      >
        <!-- Avatar -->
        <div
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg font-display text-base font-bold"
          :style="{
            background: c.is_ai
              ? 'linear-gradient(135deg, var(--color-arcane), #7050b0)'
              : 'linear-gradient(135deg, var(--color-ember), var(--color-gold))',
            color: 'var(--color-bg)',
          }"
        >{{ c.name.charAt(0).toUpperCase() }}</div>

        <!-- Info -->
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-1.5">
            <span
              class="truncate font-display text-xs font-semibold"
              :style="{ color: isSelected(c) ? 'var(--color-gold)' : 'var(--color-parchment)' }"
            >{{ c.name }}</span>
            <span
              v-if="c.is_ai"
              class="shrink-0 text-[8px] font-bold tracking-[0.1em]"
              :style="{ color: 'var(--color-arcane)' }"
            >IA</span>
          </div>
          <div class="text-[10px]" :style="{ color: 'var(--color-text-muted)' }">{{ c.char_class }}</div>

          <!-- HP bar -->
          <div class="mt-1">
            <div
              class="relative w-full overflow-hidden rounded-full"
              style="height: 3px; background: rgba(0,0,0,0.5);"
            >
              <div
                class="absolute inset-y-0 left-0 rounded-full transition-all duration-300"
                :style="{ width: `${hpPct(c)}%`, background: hpColor(c) }"
              />
            </div>
            <div class="mt-0.5 font-mono text-[9px]" :style="{ color: 'var(--color-text-dim)' }">
              {{ c.hp_current }}/{{ c.hp_max }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
