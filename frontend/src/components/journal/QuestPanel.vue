<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../../stores/game'
import type { QuestCategory } from '../../types'

const gameStore = useGameStore()

const CATEGORY_ORDER: QuestCategory[] = ['principale', 'secondaire', 'rumeur']

const CATEGORY_CLASS: Record<QuestCategory, string> = {
  principale: 'rpg-text-ember',
  secondaire: 'rpg-text-arcane',
  rumeur: 'rpg-text-muted',
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
      class="rpg-text-muted py-4 text-center text-[12px] italic"
    >
      Aucune quête en cours
    </div>

    <div v-else class="space-y-5">
      <div v-for="group in grouped" :key="group.cat">
        <div
          class="mb-2 text-[9px] font-bold uppercase tracking-[0.2em]"
          :class="CATEGORY_CLASS[group.cat]"
        >
          {{ group.cat }}
        </div>

        <div v-for="quest in group.quests" :key="quest.id" class="mb-3">
          <div
            v-if="quest.urgency"
            class="rpg-text-gold mb-0.5 text-[10px]"
          >
            ⏳ {{ quest.urgency }}
          </div>
          <div
            class="rpg-text-main font-display text-[13px] font-semibold leading-snug"
          >
            {{ quest.title }}
          </div>
          <div
            v-if="quest.summary"
            class="rpg-text-muted mt-0.5 font-serif text-[11px] italic leading-relaxed"
          >
            « {{ quest.summary }} »
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
