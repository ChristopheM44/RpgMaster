<script setup lang="ts">
import { computed } from 'vue'
import type { Character } from '../../types'

const props = defineProps<{ character: Character }>()

const XP_THRESHOLDS: Record<number, number> = {
  1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500, 6: 14000, 7: 23000, 8: 34000,
  9: 48000, 10: 64000, 11: 85000, 12: 100000, 13: 120000, 14: 140000,
  15: 165000, 16: 195000, 17: 225000, 18: 265000, 19: 305000, 20: 355000,
}

const progress = computed(() => {
  const level = Math.max(1, Math.min(20, props.character.level))
  if (level >= 20) return 100
  const current = XP_THRESHOLDS[level] ?? 0
  const next = XP_THRESHOLDS[level + 1] ?? current
  return Math.max(0, Math.min(100, ((props.character.xp - current) / (next - current)) * 100))
})
</script>

<template>
  <div class="space-y-1.5">
    <div class="flex items-center justify-between text-[10px] font-semibold uppercase tracking-[0.14em]">
      <span class="rpg-text-dim">XP</span>
      <span class="rpg-text-muted">{{ character.xp }} · {{ character.xp_to_next_level }} avant niv. {{ character.level + 1 }}</span>
    </div>
    <div class="rpg-hp-track thin relative overflow-hidden rounded-full">
      <div
        class="absolute inset-y-0 left-0 rounded-full transition-all duration-300"
        :style="{ width: `${progress}%`, background: 'var(--color-gold)' }"
      />
    </div>
  </div>
</template>
