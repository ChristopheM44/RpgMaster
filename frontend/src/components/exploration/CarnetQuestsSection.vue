<script setup lang="ts">
import { useQuestStore } from '../../stores/quest'
import CollapsibleSection from './CollapsibleSection.vue'
import type { ExQuest } from '../../fixtures/exploration'

// TODO: brancher backend — questStore est encore mocké sur EX_QUESTS

const questStore = useQuestStore()

function kindMeta(kind: ExQuest['kind']) {
  if (kind === 'principale') return { c: 'var(--color-gold)', label: 'Principale' }
  if (kind === 'secondaire') return { c: 'var(--color-teal)', label: 'Secondaire' }
  return { c: 'var(--color-arcane)', label: 'Rumeur' }
}
</script>

<template>
  <CollapsibleSection id="quests" eyebrow="◈ Quêtes en cours" :count="questStore.quests.length">
    <div class="carnet-quests">
      <div
        v-for="q in questStore.quests"
        :key="q.id"
        class="carnet-quest-card"
        :style="{ borderLeftColor: kindMeta(q.kind).c }"
      >
        <div class="carnet-quest-head">
          <span class="carnet-quest-kind" :style="{ color: kindMeta(q.kind).c }">
            {{ kindMeta(q.kind).label }}
          </span>
          <span v-if="q.due" class="carnet-quest-due">⏳ {{ q.due }}</span>
        </div>
        <div class="carnet-quest-title">{{ q.title }}</div>
        <div class="carnet-quest-desc">{{ q.desc }}</div>
        <div v-if="q.steps !== null" class="carnet-quest-progress">
          <div class="carnet-quest-bar">
            <div
              class="carnet-quest-bar-fill"
              :style="{
                width: `${(q.progress / Math.max(1, q.steps)) * 100}%`,
                background: kindMeta(q.kind).c,
              }"
            />
          </div>
          <span class="carnet-quest-progress-text">{{ q.progress }}/{{ q.steps }}</span>
        </div>
      </div>
    </div>
  </CollapsibleSection>
</template>

<style scoped>
.carnet-quests {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 6px 14px 10px;
}

.carnet-quest-card {
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--color-border);
  border-left-width: 2px;
  border-left-style: solid;
}

.carnet-quest-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 3px;
}

.carnet-quest-kind {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.carnet-quest-due {
  font-size: 8px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}

.carnet-quest-title {
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 700;
  color: var(--color-parchment);
  margin-bottom: 3px;
  line-height: 1.2;
}

.carnet-quest-desc {
  font-family: var(--font-serif);
  font-size: 11px;
  color: var(--color-text-muted);
  font-style: italic;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

.carnet-quest-progress {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.carnet-quest-bar {
  flex: 1;
  height: 3px;
  border-radius: 2px;
  background: rgba(0, 0, 0, 0.5);
  overflow: hidden;
}

.carnet-quest-bar-fill {
  height: 100%;
  transition: width 200ms ease;
}

.carnet-quest-progress-text {
  font-size: 8px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}
</style>
