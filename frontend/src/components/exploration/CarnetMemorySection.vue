<script setup lang="ts">
import { useMemoryStore } from '../../stores/memory'
import CollapsibleSection from './CollapsibleSection.vue'

// TODO: brancher backend — memoryStore est encore mocké sur EX_MEMORY

const memoryStore = useMemoryStore()

function tagColor(tag: string): string {
  if (tag === 'allié')      return 'var(--color-green)'
  if (tag === 'danger')     return 'var(--color-blood)'
  if (tag === 'à explorer') return 'var(--color-teal)'
  if (tag === 'sûr')        return 'var(--color-parchment-dark)'
  return 'var(--color-text-muted)'
}
</script>

<template>
  <CollapsibleSection id="memory" eyebrow="◉ Carnet du chroniqueur" :count="memoryStore.memory.length">
    <div class="carnet-memory">
      <div
        v-for="(m, i) in memoryStore.memory"
        :key="i"
        class="carnet-memory-row"
      >
        <span class="carnet-memory-icon">{{ m.kind === 'PNJ' ? '👤' : '📍' }}</span>
        <div class="carnet-memory-meta">
          <div class="carnet-memory-name">{{ m.name }}</div>
          <div class="carnet-memory-detail">{{ m.detail }}</div>
        </div>
        <span
          class="carnet-memory-tag"
          :style="{
            color: tagColor(m.tag),
            background: `${tagColor(m.tag)}20`,
            borderColor: `${tagColor(m.tag)}40`,
          }"
        >{{ m.tag }}</span>
      </div>
    </div>
  </CollapsibleSection>
</template>

<style scoped>
.carnet-memory {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px 14px 10px;
}

.carnet-memory-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 6px;
  border-radius: 4px;
  border-bottom: 1px dashed var(--color-border);
}

.carnet-memory-icon {
  font-size: 11px;
  flex-shrink: 0;
}

.carnet-memory-meta {
  flex: 1;
  min-width: 0;
}

.carnet-memory-name {
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 600;
  color: var(--color-parchment);
}

.carnet-memory-detail {
  font-family: var(--font-serif);
  font-size: 10px;
  color: var(--color-text-muted);
  font-style: italic;
}

.carnet-memory-tag {
  font-size: 8px;
  padding: 1px 5px;
  border-radius: 3px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  border: 1px solid;
  white-space: nowrap;
}
</style>
