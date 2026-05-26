<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '../../stores/session'
import { useGameStore } from '../../stores/game'
import type { MapNode, NodeStatus } from '../../types'

withDefaults(defineProps<{
  width?: number
  height?: number
}>(), {
  width: 640,
  height: 580,
})

const sessionStore = useSessionStore()
const gameStore = useGameStore()

const region = computed(() => gameStore.regionMap)
const nodes = computed<MapNode[]>(() => region.value?.nodes ?? [])
const edges = computed(() => region.value?.edges ?? [])
const currentNodeId = computed(() => region.value?.current_node_id)

function toneByStatus(status: NodeStatus): string {
  switch (status) {
    case 'visited':  return '#6fd96f'   // green
    case 'current':  return '#f0c764'   // gold
    case 'rumored':  return '#c090ff'   // arcane
    case 'known':    return 'rgba(247,236,208,0.55)'
    default:          return 'rgba(247,236,208,0.55)'
  }
}

function toneColor(status: NodeStatus): string {
  switch (status) {
    case 'visited':  return 'var(--color-green)'
    case 'current':  return 'var(--color-gold)'
    case 'rumored':  return 'var(--color-arcane)'
    case 'known':    return 'var(--color-parchment-dark)'
    default:          return 'var(--color-parchment-dark)'
  }
}

function nodeById(id: string): MapNode | undefined {
  return nodes.value.find((n) => n.id === id)
}

function edgePath(fromId: string, toId: string): string | null {
  const a = nodeById(fromId)
  const b = nodeById(toId)
  if (!a || !b) return null
  // Courbe quadratique douce entre les deux pins.
  const midX = (a.position.x + b.position.x) / 2
  const midY = (a.position.y + b.position.y) / 2 - 4
  return `M ${a.position.x} ${a.position.y} Q ${midX} ${midY} ${b.position.x} ${b.position.y}`
}

function isSelected(id: string) { return sessionStore.selectedId === id }
function isHighlighted(id: string) { return sessionStore.highlightedIds.includes(id) }

function onClick(id: string) { sessionStore.selectEntity(id) }

function pinRadius(n: MapNode) {
  if (isSelected(n.id) || isHighlighted(n.id)) return 2
  return 1.5
}
</script>

<template>
  <div
    class="region-map"
    :style="{ width: `${width}px`, height: `${height}px` }"
  >
    <svg
      v-if="region"
      viewBox="0 0 100 100"
      :width="width"
      :height="height"
      preserveAspectRatio="none"
      class="region-map-svg"
    >
      <!-- Fond décor (mer ouest stylisée + couvert forestier subtil) -->
      <path d="M 0 0 L 18 0 L 12 30 L 6 60 L 10 90 L 0 100 Z" fill="rgba(40,80,100,0.3)" />
      <path d="M 0 0 L 18 0 L 12 30 L 6 60 L 10 90 L 0 100 Z" stroke="rgba(79,216,192,0.25)" stroke-width="0.3" fill="none" />

      <!-- Edges -->
      <path
        v-for="e in edges"
        :key="e.id"
        :d="edgePath(e.from, e.to) ?? ''"
        stroke="rgba(247,236,208,0.18)"
        stroke-width="0.5"
        fill="none"
        stroke-dasharray="0.8 1.6"
        stroke-linecap="round"
      />

      <!-- Pins -->
      <g
        v-for="n in nodes"
        :key="n.id"
        style="cursor: pointer"
        @click="onClick(n.id)"
      >
        <circle
          v-if="n.id === currentNodeId"
          :cx="n.position.x"
          :cy="n.position.y"
          r="4"
          fill="none"
          :stroke="toneByStatus(n.status)"
          stroke-width="0.4"
          opacity="0.4"
        />
        <circle
          :cx="n.position.x"
          :cy="n.position.y"
          :r="pinRadius(n)"
          :fill="toneByStatus(n.status)"
          :stroke="isSelected(n.id) ? 'var(--color-gold)' : 'rgba(0,0,0,0.6)'"
          stroke-width="0.4"
        />
        <circle
          v-if="n.status === 'rumored'"
          :cx="n.position.x"
          :cy="n.position.y"
          r="3"
          fill="none"
          :stroke="toneByStatus(n.status)"
          stroke-width="0.3"
          stroke-dasharray="0.6 0.6"
        />
      </g>
    </svg>

    <!-- Empty state -->
    <div v-if="!region" class="region-map-empty">
      <span class="rpg-eyebrow">✦ Région</span>
      <p>Aucune région chargée pour cette session.</p>
    </div>

    <!-- Labels HTML overlay -->
    <div
      v-for="n in nodes"
      :key="n.id"
      class="region-map-label"
      :style="{
        left: `${n.position.x}%`,
        top: `calc(${n.position.y}% + 8px)`,
        color: isSelected(n.id) ? 'var(--color-gold)' : toneColor(n.status),
      }"
    >
      {{ n.short_label ?? n.name }}
      <div v-if="n.id === currentNodeId" class="region-map-here">▼ vous</div>
    </div>

    <div v-if="region" class="region-map-coord">{{ region.name }}</div>
    <div v-if="region" class="region-map-north">N ↑</div>
  </div>
</template>

<style scoped>
.region-map {
  position: relative;
  border-radius: 10px;
  border: 1px solid var(--color-border-strong);
  background: linear-gradient(135deg, #18221c 0%, #0c1410 100%);
  overflow: hidden;
  box-shadow: inset 0 0 80px rgba(0, 0, 0, 0.7), 0 6px 28px rgba(0, 0, 0, 0.5);
  flex-shrink: 0;
}

.region-map-svg {
  position: absolute;
  inset: 0;
}

.region-map-empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--color-text-muted);
  font-family: var(--font-serif);
  font-size: 13px;
  font-style: italic;
}

.region-map-label {
  position: absolute;
  transform: translate(-50%, 0);
  font-family: var(--font-display);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.6px;
  text-align: center;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.9);
  pointer-events: none;
  white-space: nowrap;
}

.region-map-here {
  font-size: 7px;
  color: var(--color-gold);
  font-family: var(--font-mono);
  font-weight: 700;
  letter-spacing: 1px;
  margin-top: 1px;
}

.region-map-coord {
  position: absolute;
  top: 8px;
  left: 12px;
  font-size: 9px;
  color: var(--color-text-dim);
  font-family: var(--font-mono);
}

.region-map-north {
  position: absolute;
  bottom: 8px;
  right: 12px;
  font-size: 9px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}
</style>
