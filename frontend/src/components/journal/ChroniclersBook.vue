<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../../stores/game'

const gameStore = useGameStore()
const chronicle = computed(() => gameStore.chronicle)

const KIND_LABEL: Record<string, string> = {
  npc: 'PNJ',
  location: 'Lieu',
}

const KIND_COLOR: Record<string, string> = {
  npc: 'var(--color-arcane, #8b5cf6)',
  location: 'var(--color-teal, #0d9488)',
}
</script>

<template>
  <div class="px-5 py-4">
    <div class="mb-3 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em]" style="color: var(--color-gold)">
      <span>◉ Carnet du chroniqueur</span>
      <span v-if="chronicle.length" class="font-mono text-[11px]">[{{ chronicle.length }}]</span>
    </div>

    <div
      v-if="!chronicle.length"
      class="py-4 text-center text-[12px] italic"
      style="color: var(--color-text-muted)"
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
          class="mt-0.5 shrink-0 rounded px-1 py-0.5 text-[9px] font-bold uppercase tracking-[0.1em]"
          :style="{
            color: KIND_COLOR[entry.kind],
            background: `${KIND_COLOR[entry.kind]}1a`,
            border: `1px solid ${KIND_COLOR[entry.kind]}40`,
          }"
        >
          {{ KIND_LABEL[entry.kind] ?? entry.kind }}
        </span>
        <div class="min-w-0">
          <span class="font-display font-semibold" style="color: var(--color-parchment)">{{ entry.name }}</span>
          <span
            v-if="entry.note"
            class="font-serif italic"
            style="color: var(--color-text-muted)"
          >
            — {{ entry.note }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
