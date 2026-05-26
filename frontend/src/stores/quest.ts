import { defineStore } from 'pinia'
import { computed } from 'vue'
import { useGameStore } from './game'
import type { Quest as BackendQuest } from '../types'
import type { ExQuest } from '../fixtures/exploration'

// Adapter backend → V2 quêtes.
// Backend Quest n'a pas `progress` / `steps` (granularité plus fine) — on les
// laisse à 0 / null jusqu'à enrichissement backend.

function adapt(q: BackendQuest): ExQuest {
  return {
    id: q.id,
    kind: q.category,
    title: q.title,
    desc: q.summary,
    progress: 0,
    steps: null,
    due: q.urgency ?? undefined,
  }
}

export const useQuestStore = defineStore('quest', () => {
  const gameStore = useGameStore()

  const quests = computed<ExQuest[]>(() =>
    gameStore.quests.filter((q) => q.status === 'active').map(adapt),
  )

  return { quests }
})
