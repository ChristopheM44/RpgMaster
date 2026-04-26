<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../../stores/game'
import type { QuestCategory } from '../../types'

const gameStore = useGameStore()

const CATEGORY_ORDER: QuestCategory[] = ['principale', 'secondaire', 'rumeur']

const CATEGORY_COLOR: Record<QuestCategory, string> = {
  principale: 'var(--color-ember, #c0392b)',
  secondaire: 'var(--color-arcane, #8b5cf6)',
  rumeur: 'var(--color-text-muted)',
}

const activeQuests = computed(() => gameStore.quests.filter((q) => q.status === 'active'))

const grouped = computed(() =>
  CATEGORY_ORDER.map((cat) => ({
    cat,
    quests: activeQuests.value.filter((q) => q.category === cat),
  })).filter((g) => g.quests.length > 0),
)
</script>

<template>
  <div class="px-5 py-4">
    <div
      v-if="!activeQuests.length"
      class="py-4 text-center text-[12px] italic"
      style="color: var(--color-text-muted)"
    >
      Aucune quête en cours
    </div>

    <div v-else class="space-y-5">
      <div v-for="group in grouped" :key="group.cat">
        <div
          class="mb-2 text-[9px] font-bold uppercase tracking-[0.2em]"
          :style="{ color: CATEGORY_COLOR[group.cat] }"
        >
          {{ group.cat }}
        </div>

        <div v-for="quest in group.quests" :key="quest.id" class="mb-3">
          <div
            v-if="quest.urgency"
            class="mb-0.5 text-[10px]"
            style="color: var(--color-gold)"
          >
            ⏳ {{ quest.urgency }}
          </div>
          <div
            class="font-display text-[13px] font-semibold leading-snug"
            style="color: var(--color-parchment)"
          >
            {{ quest.title }}
          </div>
          <div
            v-if="quest.summary"
            class="mt-0.5 font-serif text-[11px] italic leading-relaxed"
            style="color: var(--color-text-muted)"
          >
            « {{ quest.summary }} »
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
