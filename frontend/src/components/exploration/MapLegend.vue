<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '../../stores/session'
import { useExplorationParty } from '../../composables/useExplorationParty'
import { useExplorationPois } from '../../composables/useExplorationPois'

const sessionStore = useSessionStore()
const { party } = useExplorationParty()
const { reperes, sorties } = useExplorationPois()

const heroes = computed(() => party.value)
const pois = computed(() => reperes.value)
const exits = computed(() => sorties.value)

function isHighlighted(id: string) {
  return sessionStore.highlightedIds.includes(id)
}

function onHover(id: string | null) {
  sessionStore.setHighlighted(id)
}

function onClick(id: string) {
  sessionStore.selectEntity(id)
}

function poiSymbol(kind: string) {
  switch (kind) {
    case 'npc': return '◉'
    case 'clue': return '✦'
    case 'hazard': return '⚠'
    case 'cover': return '◆'
    case 'loot': return '▣'
    default: return '✦'
  }
}
</script>

<template>
  <div class="map-legend">
    <span class="map-legend-label">LÉGENDE</span>
    <span class="map-legend-divider" />

    <!-- Heroes pellets -->
    <div class="map-legend-group">
      <div
        v-for="h in heroes"
        :key="h.id"
        class="map-legend-pellet"
        :class="{
          'is-me': h.isMe,
          'is-highlighted': isHighlighted(h.id),
        }"
        :title="h.name"
        :style="{
          background: `radial-gradient(circle at 30% 30%, ${h.color}, ${h.color}99)`,
        }"
        @mouseenter="onHover(h.id)"
        @mouseleave="onHover(null)"
        @click="onClick(h.id)"
      >{{ h.token }}</div>
    </div>

    <span class="map-legend-divider" />

    <!-- POIs -->
    <div v-if="pois.length" class="map-legend-group">
      <div
        v-for="p in pois"
        :key="p.id"
        class="map-legend-chip"
        :class="{ 'is-highlighted': isHighlighted(p.id) }"
        :title="p.title"
        @mouseenter="onHover(p.id)"
        @mouseleave="onHover(null)"
        @click="onClick(p.id)"
      >{{ p.iconSymbol ?? poiSymbol(p.kind) }} {{ p.label }}</div>
    </div>

    <span v-if="pois.length" class="map-legend-divider" />

    <!-- Exits -->
    <div v-if="exits.length" class="map-legend-group">
      <div
        v-for="e in exits"
        :key="e.id"
        class="map-legend-chip"
        :class="{
          'is-highlighted': isHighlighted(e.id),
          'is-active': e.active,
        }"
        :title="e.title"
        @mouseenter="onHover(e.id)"
        @mouseleave="onHover(null)"
        @click="onClick(e.id)"
      >↦ {{ e.label }}</div>
    </div>
  </div>
</template>

<style scoped>
.map-legend {
  position: absolute;
  bottom: 14px;
  left: 14px;
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 6px 10px;
  background: rgba(14, 13, 20, 0.78);
  backdrop-filter: blur(8px);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  z-index: 4;
}

.map-legend-label {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 1.5px;
  color: var(--color-text-dim);
  text-transform: uppercase;
}

.map-legend-divider {
  width: 1px;
  height: 14px;
  background: var(--color-border);
  margin: 0 4px;
}

.map-legend-group {
  display: flex;
  gap: 3px;
}

.map-legend-pellet {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 1.5px solid rgba(247, 236, 208, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-size: 8px;
  font-weight: 700;
  color: var(--color-bg);
  cursor: pointer;
  transition: transform 120ms, border-color 120ms;
}

.map-legend-pellet.is-me {
  border-color: var(--color-gold);
}

.map-legend-pellet.is-highlighted {
  border-color: var(--color-ember);
  transform: scale(1.15);
}

.map-legend-chip {
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-border);
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: border-color 120ms, color 120ms, background 120ms;
}

.map-legend-chip.is-highlighted {
  background: rgba(255, 130, 71, 0.15);
  border-color: var(--color-ember);
  color: var(--color-ember);
}

.map-legend-chip.is-active {
  background: rgba(240, 199, 100, 0.15);
  border-color: var(--color-gold);
  color: var(--color-gold);
}
</style>
