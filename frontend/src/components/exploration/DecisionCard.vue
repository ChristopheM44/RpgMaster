<script setup lang="ts">
import { useSessionStore } from '../../stores/session'
import type { ExNarrativeEntry } from '../../fixtures/exploration'

defineProps<{
  entry: Extract<ExNarrativeEntry, { type: 'decision' }>
}>()

const emit = defineEmits<{ decide: [optionId: string] }>()

const sessionStore = useSessionStore()

function onEnter(id: string) {
  sessionStore.setHighlighted(id)
}

function onLeave() {
  sessionStore.setHighlighted(null)
}

function onClick(id: string) {
  emit('decide', id)
}

function isHighlighted(id: string) {
  return sessionStore.highlightedIds.includes(id)
}
</script>

<template>
  <div class="decision-card">
    <div class="rpg-eyebrow decision-card-eyebrow">◆ Décision · {{ entry.who }}</div>
    <p class="decision-card-text">{{ entry.text }}</p>
    <div class="decision-card-options">
      <button
        v-for="opt in entry.options"
        :key="opt.id"
        class="decision-card-option"
        :class="[`tone-${opt.tone}`, { 'is-highlighted': isHighlighted(opt.id) }]"
        @mouseenter="onEnter(opt.id)"
        @mouseleave="onLeave"
        @click="onClick(opt.id)"
      >
        <span class="decision-card-option-icon">{{ opt.icon }}</span>
        {{ opt.label }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.decision-card {
  margin: 18px 0;
  padding: 10px 12px;
  background: rgba(240, 199, 100, 0.05);
  border: 1px solid rgba(240, 199, 100, 0.30);
  border-left: 3px solid var(--color-gold);
  border-radius: 6px;
}

.decision-card-eyebrow {
  color: var(--color-gold);
  margin-bottom: 6px;
}

.decision-card-text {
  font-family: var(--font-serif);
  font-size: 13px;
  color: var(--color-parchment);
  margin: 0 0 8px;
  font-style: italic;
  text-wrap: pretty;
}

.decision-card-options {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.decision-card-option {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: 5px;
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  cursor: pointer;
  border: 1px solid;
  transition: background 120ms, color 120ms;
}

.decision-card-option.tone-gold   { background: rgba(240, 199, 100, 0.18); color: var(--color-gold); border-color: rgba(240, 199, 100, 0.5); }
.decision-card-option.tone-teal   { background: rgba(79, 216, 192, 0.18); color: var(--color-teal); border-color: rgba(79, 216, 192, 0.5); }
.decision-card-option.tone-blood  { background: rgba(232, 69, 69, 0.18); color: var(--color-blood); border-color: rgba(232, 69, 69, 0.5); }
.decision-card-option.tone-arcane { background: rgba(192, 144, 255, 0.18); color: var(--color-arcane); border-color: rgba(192, 144, 255, 0.5); }

.decision-card-option.is-highlighted.tone-gold   { background: linear-gradient(135deg, var(--color-gold), #f0c764aa);  color: var(--color-bg); }
.decision-card-option.is-highlighted.tone-teal   { background: linear-gradient(135deg, var(--color-teal), #4fd8c0aa);   color: var(--color-bg); }
.decision-card-option.is-highlighted.tone-blood  { background: linear-gradient(135deg, var(--color-blood), #e84545aa);  color: var(--color-bg); }
.decision-card-option.is-highlighted.tone-arcane { background: linear-gradient(135deg, var(--color-arcane), #c090ffaa); color: var(--color-bg); }
</style>
