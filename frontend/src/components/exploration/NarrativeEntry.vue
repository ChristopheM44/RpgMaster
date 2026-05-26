<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '../../stores/session'
import RefChip from './RefChip.vue'
import RollCard from './RollCard.vue'
import DecisionCard from './DecisionCard.vue'
import type { ExNarrativeEntry } from '../../fixtures/exploration'

const props = defineProps<{
  entry: ExNarrativeEntry
}>()

const emit = defineEmits<{
  decide: [optionId: string]
}>()

const sessionStore = useSessionStore()

const refs = computed<string[]>(() => {
  if ('refs' in props.entry && props.entry.refs) return props.entry.refs
  return []
})

function onRefHover(id: string | null) {
  sessionStore.setHighlighted(id)
}

function onRefClick(id: string) {
  sessionStore.selectEntity(id)
}

function onEntryEnter() {
  if (refs.value.length > 0) {
    sessionStore.setHighlighted(refs.value)
  }
}

function onEntryLeave() {
  sessionStore.setHighlighted(null)
}
</script>

<template>
  <!-- ─ divider ────────────────────────────────────────────── -->
  <div v-if="entry.type === 'divider'" class="ne-divider">
    <span class="ne-divider-rule" />
    <span class="ne-divider-text">✦ {{ entry.text }} ✦</span>
    <span class="ne-divider-rule rev" />
  </div>

  <!-- ─ gm ─────────────────────────────────────────────────── -->
  <div
    v-else-if="entry.type === 'gm'"
    class="ne-gm"
    @mouseenter="onEntryEnter"
    @mouseleave="onEntryLeave"
  >
    <div class="ne-gm-eyebrow rpg-eyebrow">
      <span>✦</span>Maître du jeu
    </div>
    <p class="ne-gm-text">{{ entry.text }}</p>
    <div v-if="refs.length" class="ne-refs">
      <RefChip
        v-for="rid in refs"
        :key="rid"
        :ref-id="rid"
        @hover="onRefHover"
        @click="onRefClick"
      />
    </div>
  </div>

  <!-- ─ player ────────────────────────────────────────────── -->
  <div
    v-else-if="entry.type === 'player'"
    class="ne-player"
    @mouseenter="onEntryEnter"
    @mouseleave="onEntryLeave"
  >
    <div class="ne-player-head">
      <div class="ne-player-who">
        <span class="ne-player-marker">▸</span>
        <span>{{ entry.who }}</span>
      </div>
      <div v-if="refs.length" class="ne-refs">
        <RefChip
          v-for="rid in refs"
          :key="rid"
          :ref-id="rid"
          @hover="onRefHover"
          @click="onRefClick"
        />
      </div>
    </div>
    <div class="ne-player-text">« {{ entry.text }} »</div>
  </div>

  <!-- ─ roll ──────────────────────────────────────────────── -->
  <RollCard v-else-if="entry.type === 'roll'" :entry="entry" />

  <!-- ─ decision ──────────────────────────────────────────── -->
  <DecisionCard
    v-else-if="entry.type === 'decision'"
    :entry="entry"
    @decide="(id: string) => emit('decide', id)"
  />
</template>

<style scoped>
/* ── divider ────────────────────────────────────────────────────────── */
.ne-divider {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 20px 0;
}

.ne-divider-rule {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(240, 199, 100, 0.33));
}

.ne-divider-rule.rev {
  background: linear-gradient(90deg, rgba(240, 199, 100, 0.33), transparent);
}

.ne-divider-text {
  font-family: var(--font-display);
  font-size: 10px;
  color: var(--color-gold);
  letter-spacing: 3px;
  text-transform: uppercase;
  white-space: nowrap;
}

/* ── gm ─────────────────────────────────────────────────────────────── */
.ne-gm { margin: 20px 0; }

.ne-gm-eyebrow {
  color: var(--color-ember);
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 5px;
}

.ne-gm-text {
  font-family: var(--font-serif);
  font-size: 15.5px;
  line-height: 1.65;
  color: var(--color-parchment);
  margin: 0;
  text-wrap: pretty;
}

.ne-refs {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 6px;
}

/* ── player ─────────────────────────────────────────────────────────── */
.ne-player {
  margin: 16px 0;
  padding: 8px 12px;
  background: rgba(192, 144, 255, 0.06);
  border: 1px solid rgba(192, 144, 255, 0.22);
  border-left: 3px solid rgba(192, 144, 255, 0.6);
  border-radius: 6px;
}

.ne-player-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
  justify-content: space-between;
}

.ne-player-who {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  color: var(--color-arcane);
}

.ne-player-marker {
  color: var(--color-arcane);
  font-size: 10px;
}

.ne-player-text {
  font-size: 13.5px;
  color: var(--color-parchment-dark);
  font-family: var(--font-serif);
  font-style: italic;
  line-height: 1.5;
}
</style>
