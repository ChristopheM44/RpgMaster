import { defineStore } from 'pinia'
import { computed } from 'vue'
import { useGameStore } from './game'
import type { ChronicleEntry } from '../types'
import type { ExMemoryEntry } from '../fixtures/exploration'

// Adapter backend → V2 carnet du chroniqueur.
// Backend ChronicleEntry n'a pas de `tag` — on en dérive un depuis `kind`.

function adapt(c: ChronicleEntry): ExMemoryEntry {
  return {
    kind: c.kind === 'npc' ? 'PNJ' : 'Lieu',
    name: c.name,
    detail: c.note,
    tag: c.kind === 'npc' ? 'rencontré' : 'connu',
  }
}

export const useMemoryStore = defineStore('memory', () => {
  const gameStore = useGameStore()

  const memory = computed<ExMemoryEntry[]>(() => gameStore.chronicle.map(adapt))

  return { memory }
})
