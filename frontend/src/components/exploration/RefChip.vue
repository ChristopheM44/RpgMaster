<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '../../stores/session'
import { useExplorationParty } from '../../composables/useExplorationParty'
import { useExplorationPois } from '../../composables/useExplorationPois'

const props = defineProps<{
  refId: string
}>()

const emit = defineEmits<{
  hover: [id: string | null]
  click: [id: string]
}>()

const sessionStore = useSessionStore()
const { findHero } = useExplorationParty()
const { findPoi } = useExplorationPois()

const hero = computed(() => findHero(props.refId))
const poi = computed(() => findPoi(props.refId))

const isHero = computed(() => !!hero.value)
const isPoi = computed(() => !!poi.value)

const label = computed(() => hero.value?.name ?? poi.value?.title ?? props.refId)
const refLabel = computed(() => hero.value?.pos ?? poi.value?.label ?? '')

const tone = computed(() => {
  if (hero.value) {
    if (hero.value.isMe) return 'gold'
    return hero.value.ai ? 'arcane' : 'teal'
  }
  if (!poi.value) return 'text'
  if (poi.value.kind === 'sortie') return 'gold'
  return poi.value.tone
})

const icon = computed(() => {
  if (hero.value) return '◉'
  if (poi.value?.kind === 'sortie') return '↦'
  if (poi.value?.iconSymbol) return poi.value.iconSymbol
  switch (poi.value?.kind) {
    case 'npc': return '◉'
    case 'enemy': return '⚔'
    case 'clue': return '✦'
    case 'hazard': return '⚠'
    case 'cover': return '◆'
    case 'loot': return '▣'
    default: return '✦'
  }
})

const highlighted = computed(() => sessionStore.highlightedIds.includes(props.refId))

function onEnter() {
  emit('hover', props.refId)
}

function onLeave() {
  emit('hover', null)
}

function onClick(e: MouseEvent) {
  e.stopPropagation()
  emit('click', props.refId)
}
</script>

<template>
  <span
    v-if="isHero || isPoi"
    class="ref-chip"
    :class="[`tone-${tone}`, { 'is-highlighted': highlighted }]"
    @mouseenter="onEnter"
    @mouseleave="onLeave"
    @click="onClick"
  >
    <span class="ref-chip-icon">{{ icon }}</span>
    <span class="ref-chip-label">{{ label }}</span>
    <span class="ref-chip-pos">{{ refLabel }}</span>
  </span>
</template>

<style scoped>
.ref-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0 6px;
  margin: 0 1px;
  border-radius: 3px;
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 11px;
  letter-spacing: 0.3px;
  cursor: pointer;
  transition: background 120ms, border-color 120ms;
  border: 1px solid;
  white-space: nowrap;
  user-select: none;
}

.ref-chip-icon { font-size: 9px; }

.ref-chip-pos {
  font-family: var(--font-mono);
  font-size: 8px;
  opacity: 0.6;
}

/* Tones */
.ref-chip.tone-ember  { color: var(--color-ember);  background: rgba(255, 130, 71, 0.12);  border-color: rgba(255, 130, 71, 0.4); }
.ref-chip.tone-arcane { color: var(--color-arcane); background: rgba(192, 144, 255, 0.12); border-color: rgba(192, 144, 255, 0.4); }
.ref-chip.tone-blood  { color: var(--color-blood);  background: rgba(232, 69, 69, 0.12);   border-color: rgba(232, 69, 69, 0.4); }
.ref-chip.tone-teal   { color: var(--color-teal);   background: rgba(79, 216, 192, 0.12);  border-color: rgba(79, 216, 192, 0.4); }
.ref-chip.tone-gold   { color: var(--color-gold);   background: rgba(240, 199, 100, 0.12); border-color: rgba(240, 199, 100, 0.4); }
.ref-chip.tone-text   { color: var(--color-parchment-dark); background: rgba(247, 236, 208, 0.08); border-color: var(--color-border-strong); }

.ref-chip.is-highlighted.tone-ember  { background: rgba(255, 130, 71, 0.3);   border-color: var(--color-ember); }
.ref-chip.is-highlighted.tone-arcane { background: rgba(192, 144, 255, 0.3); border-color: var(--color-arcane); }
.ref-chip.is-highlighted.tone-blood  { background: rgba(232, 69, 69, 0.3);    border-color: var(--color-blood); }
.ref-chip.is-highlighted.tone-teal   { background: rgba(79, 216, 192, 0.3);   border-color: var(--color-teal); }
.ref-chip.is-highlighted.tone-gold   { background: rgba(240, 199, 100, 0.3); border-color: var(--color-gold); }
.ref-chip.is-highlighted.tone-text   { background: rgba(247, 236, 208, 0.2); border-color: var(--color-parchment); }
</style>
