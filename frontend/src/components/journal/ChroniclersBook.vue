<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../../stores/game'

const gameStore = useGameStore()
const chronicle = computed(() => gameStore.chronicle)

const KIND_LABEL: Record<string, string> = {
  npc: 'PNJ',
  location: 'Lieu',
}

const KIND_CLASS: Record<string, string> = {
  npc: 'rpg-tone-arcane',
  location: 'rpg-tone-teal',
}
</script>

<template>
  <div class="px-5 py-4">
    <div
      v-if="!chronicle.length"
      class="rpg-text-muted py-4 text-center text-[12px] italic"
    >
      Aucun PNJ ni lieu enregistré
    </div>

    <div v-else class="space-y-1.5">
      <div
        v-for="entry in chronicle"
        :key="entry.id"
        class="flex items-start gap-2 text-[12px]"
      >
        <span
          class="rpg-kind-badge mt-0.5 shrink-0 rounded px-1 py-0.5 text-[9px] font-bold uppercase tracking-[0.1em]"
          :class="KIND_CLASS[entry.kind] ?? 'rpg-tone-muted'"
        >
          {{ KIND_LABEL[entry.kind] ?? entry.kind }}
        </span>
        <div class="min-w-0">
          <span class="rpg-text-main font-display font-semibold">{{ entry.name }}</span>
          <span
            v-if="entry.note"
            class="rpg-text-muted font-serif italic"
          >
            — {{ entry.note }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
