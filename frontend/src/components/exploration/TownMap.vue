<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '../../stores/session'
import { useGameStore } from '../../stores/game'
import type { MapNode, NodeStatus, CityNodeKind } from '../../types'

withDefaults(defineProps<{
  width?: number
  height?: number
}>(), {
  width: 640,
  height: 580,
})

const sessionStore = useSessionStore()
const gameStore = useGameStore()

const city = computed(() => {
  const id = gameStore.activeCityId
  return id ? gameStore.cityMaps[id] : undefined
})

const nodes = computed<MapNode[]>(() => city.value?.nodes ?? [])
const edges = computed(() => city.value?.edges ?? [])
const currentNodeId = computed(() => city.value?.current_node_id)

function toneByStatus(status: NodeStatus): string {
  switch (status) {
    case 'visited':  return '#6fd96f'
    case 'current':  return '#f0c764'
    case 'rumored':  return '#c090ff'
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
  return `M ${a.position.x} ${a.position.y} L ${b.position.x} ${b.position.y}`
}

function pinByKind(kind: CityNodeKind): string {
  switch (kind) {
    case 'tavern':   return '★'
    case 'shop':     return '✦'
    case 'temple':   return '✺'
    case 'palace':   return '◇'
    case 'docks':    return '◈'
    case 'gate':     return '◊'
    case 'square':   return '◉'
    case 'building': return '◇'
    default:          return '◆'
  }
}

function isSelected(id: string) { return sessionStore.selectedId === id }
function isHighlighted(id: string) { return sessionStore.highlightedIds.includes(id) }

function onClick(id: string) { sessionStore.selectEntity(id) }

function nodeFill(n: MapNode) {
  if (isSelected(n.id)) return `${toneByStatus(n.status)}40`
  if (isHighlighted(n.id)) return `${toneByStatus(n.status)}25`
  return 'rgba(40,32,24,0.7)'
}

function nodeStroke(n: MapNode) {
  if (isSelected(n.id)) return 'var(--color-gold)'
  if (isHighlighted(n.id)) return 'var(--color-ember)'
  return toneByStatus(n.status)
}
</script>

<template>
  <div
    class="town-map"
    :style="{ width: `${width}px`, height: `${height}px` }"
  >
    <svg
      v-if="city"
      viewBox="0 0 100 100"
      :width="width"
      :height="height"
      preserveAspectRatio="none"
      class="town-map-svg"
    >
      <defs>
        <linearGradient id="townBg" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%"  stop-color="#2a2218" />
          <stop offset="100%" stop-color="#14110c" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="100" height="100" fill="url(#townBg)" />

      <!-- Edges (routes / chemins) -->
      <path
        v-for="e in edges"
        :key="e.id"
        :d="edgePath(e.from, e.to) ?? ''"
        stroke="rgba(247,236,208,0.18)"
        stroke-width="0.5"
        fill="none"
        stroke-dasharray="0.5 1.5"
        stroke-linecap="round"
      />

      <!-- Nodes (bâtiments / places) -->
      <g
        v-for="n in nodes"
        :key="n.id"
        style="cursor: pointer"
        @click="onClick(n.id)"
      >
        <rect
          :x="n.position.x - 5"
          :y="n.position.y - 3"
          width="10"
          height="6"
          rx="0.6"
          :fill="nodeFill(n)"
          :stroke="nodeStroke(n)"
          :stroke-width="isSelected(n.id) ? 0.5 : 0.25"
        />
        <text
          :x="n.position.x"
          :y="n.position.y + 0.4"
          text-anchor="middle"
          :fill="toneByStatus(n.status)"
          font-size="2.2"
          font-family="Cinzel, serif"
          font-weight="700"
        >{{ n.icon ?? pinByKind(n.kind as CityNodeKind) }}</text>
      </g>
    </svg>

    <!-- Empty state -->
    <div v-if="!city" class="town-map-empty">
      <span class="rpg-eyebrow">✦ Ville</span>
      <p>Aucune carte de ville chargée pour cette session.</p>
    </div>

    <!-- Labels HTML overlay -->
    <div
      v-for="n in nodes"
      :key="n.id"
      class="town-map-label"
      :style="{
        left: `${n.position.x}%`,
        top: `calc(${n.position.y + 3}% + 4px)`,
        color: isSelected(n.id) ? 'var(--color-gold)' : toneColor(n.status),
      }"
    >{{ n.short_label ?? n.name }}</div>

    <!-- Position du groupe -->
    <div v-if="currentNodeId" class="town-map-here">
      <span class="town-map-here-icon">👥</span>
      <span class="town-map-here-label">Vous</span>
    </div>

    <!-- Coords overlay -->
    <div v-if="city" class="town-map-coord">{{ city.name }} · plan</div>
  </div>
</template>

<style scoped>
.town-map {
  position: relative;
  border-radius: 10px;
  border: 1px solid var(--color-border-strong);
  background: linear-gradient(135deg, #2a2218 0%, #14110c 100%);
  overflow: hidden;
  box-shadow: inset 0 0 80px rgba(0, 0, 0, 0.7), 0 6px 28px rgba(0, 0, 0, 0.5);
  flex-shrink: 0;
}

.town-map-svg {
  position: absolute;
  inset: 0;
}

.town-map-empty {
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

.town-map-label {
  position: absolute;
  transform: translate(-50%, 0);
  font-family: var(--font-display);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.6px;
  text-align: center;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.9);
  pointer-events: none;
  white-space: nowrap;
}

.town-map-here {
  position: absolute;
  left: 8%;
  top: 60%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.town-map-here-icon {
  font-size: 18px;
  filter: drop-shadow(0 0 8px rgba(255, 130, 71, 0.7));
}

.town-map-here-label {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--color-ember);
  text-transform: uppercase;
  background: rgba(14, 13, 20, 0.85);
  padding: 1px 6px;
  border-radius: 3px;
}

.town-map-coord {
  position: absolute;
  top: 8px;
  left: 12px;
  font-size: 9px;
  color: var(--color-text-dim);
  font-family: var(--font-mono);
}
</style>
