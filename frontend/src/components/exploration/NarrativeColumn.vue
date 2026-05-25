<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import { useNarrativeStore } from '../../stores/narrative'
import NarrativeEntry from './NarrativeEntry.vue'

const emit = defineEmits<{ decide: [optionId: string] }>()

const narrativeStore = useNarrativeStore()
const scrollEl = ref<HTMLElement | null>(null)

const count = computed(() => narrativeStore.entries.length)

// Auto-scroll vers la dernière entrée à chaque ajout
watch(count, async () => {
  await nextTick()
  if (scrollEl.value) {
    scrollEl.value.scrollTop = scrollEl.value.scrollHeight
  }
})
</script>

<template>
  <section class="narrative-column">
    <header class="narrative-header">
      <span class="narrative-header-icon">✦</span>
      <h2 class="narrative-header-title">Récit</h2>
      <span style="flex: 1" />
      <span class="narrative-header-count">{{ count }} entrées</span>
      <button class="narrative-header-filter" title="Filtrer">⌕ Filtrer</button>
    </header>

    <div ref="scrollEl" class="narrative-scroll">
      <NarrativeEntry
        v-for="entry in narrativeStore.entries"
        :key="entry.id"
        :entry="entry"
        @decide="(id: string) => emit('decide', id)"
      />
    </div>
  </section>
</template>

<style scoped>
.narrative-column {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  background: linear-gradient(180deg, var(--color-bg-elev), rgba(24, 22, 35, 0.6));
}

.narrative-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 24px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
  height: 44px;
}

.narrative-header-icon {
  color: var(--color-ember);
  font-size: 13px;
}

.narrative-header-title {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  color: var(--color-parchment);
  margin: 0;
  letter-spacing: 2px;
  text-transform: uppercase;
}

.narrative-header-count {
  font-size: 9px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}

.narrative-header-filter {
  padding: 4px 8px;
  border-radius: 4px;
  background: transparent;
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  cursor: pointer;
  transition: color 120ms, border-color 120ms;
}

.narrative-header-filter:hover {
  color: var(--color-parchment);
  border-color: var(--color-border-strong);
}

.narrative-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 8px 28px 16px;
  min-height: 0;
}
</style>
