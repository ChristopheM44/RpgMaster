<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '../../stores/session'
import { useGameStore } from '../../stores/game'
import { resolveMapDecor } from '../../composables/useMapDecor'
import type { MapNode, NodeStatus, CityNodeKind, MapDecor } from '../../types'

const props = withDefaults(defineProps<{
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
const visualAsset = computed(() => city.value?.visual_asset)
const visualAssetReady = computed(() =>
  visualAsset.value?.status === 'ready' && Boolean(visualAsset.value.url),
)
const visualAssetGenerating = computed(() =>
  visualAsset.value?.status === 'prompt_ready' || visualAsset.value?.status === 'generating',
)

// Décor : backend ou fallback procédural
const decor = computed<MapDecor>(() =>
  resolveMapDecor(
    city.value?.decor,
    city.value?.background_seed ?? city.value?.id ?? 'city',
    'city',
  )
)

// ── Dimensions bâtiment selon le kind ────────────────────────────────────────
// Coordonnées exprimées en unités viewBox 0..100.
// w×h sont des demi-dimensions : le rect est centré sur position.
function buildingSize(kind: string): { w: number; h: number } {
  switch (kind as CityNodeKind) {
    case 'palace':   return { w: 8, h: 5 }
    case 'district': return { w: 10, h: 7 }
    case 'tavern':   return { w: 7, h: 4 }
    case 'temple':   return { w: 5, h: 3 }
    case 'shop':     return { w: 4, h: 2.5 }
    case 'docks':    return { w: 9, h: 3.5 }
    case 'gate':     return { w: 3, h: 5 }
    case 'square':   return { w: 6, h: 6 }
    case 'building': return { w: 6, h: 3.5 }
    default:          return { w: 5, h: 3 }
  }
}

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

function isSelected(id: string) { return sessionStore.selectedId === id }
function isHighlighted(id: string) { return sessionStore.highlightedIds.includes(id) }

function onClick(id: string) { sessionStore.selectEntity(id) }

function nodeFill(n: MapNode) {
  const tone = toneByStatus(n.status)
  if (isSelected(n.id)) return `${tone}40`
  if (isHighlighted(n.id)) return `${tone}25`
  return 'rgba(40,32,24,0.7)'
}

function nodeStroke(n: MapNode) {
  if (isSelected(n.id)) return 'var(--color-gold)'
  if (isHighlighted(n.id)) return 'var(--color-ember)'
  return toneByStatus(n.status)
}

function pinByKind(kind: string): string {
  switch (kind as CityNodeKind) {
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

// Position HTML du marqueur "Vous" = node courante
const youPosition = computed(() => {
  if (!currentNodeId.value) return null
  const n = nodeById(currentNodeId.value)
  if (!n) return null
  return {
    left: `${n.position.x / 100 * props.width}px`,
    top: `${n.position.y / 100 * props.height - 28}px`,
  }
})
</script>

<template>
  <div
    class="town-map"
    :style="{ width: `${width}px`, height: `${height}px` }"
  >
    <img
      v-if="visualAssetReady"
      class="town-map-image"
      :src="visualAsset?.url"
      alt=""
      draggable="false"
    />
    <div v-if="visualAssetGenerating" class="map-gen-badge" :class="`gen-${visualAsset?.status}`">
      <span class="gen-spinner" />{{ visualAsset?.status === 'generating' ? 'Génération…' : 'En attente…' }}
    </div>
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

      <!-- ── Décor de fond ── -->

      <!-- Forêts périphériques -->
      <circle
        v-for="(f, i) in (decor.forests ?? [])"
        :key="`f${i}`"
        :cx="f.x"
        :cy="f.y"
        :r="f.radius ?? 3"
        :fill="`rgba(58,90,58,${f.opacity ?? 0.4})`"
      />

      <!-- Rivière -->
      <path
        v-if="decor.river"
        :d="decor.river.path"
        :stroke-width="decor.river.width ?? 1.5"
        stroke="rgba(79,216,192,0.25)"
        fill="none"
        stroke-linecap="round"
      />

      <!-- Routes décoratives (arrière-plan, sous les edges réels) -->
      <path
        v-for="(d, i) in (decor.decorative_roads ?? [])"
        :key="`dr${i}`"
        :d="d"
        stroke="rgba(247,236,208,0.12)"
        stroke-width="1.8"
        stroke-linecap="round"
        fill="none"
        stroke-dasharray="0.5 1.5"
      />

      <!-- ── Edges (rues/chemins réels) ── -->
      <path
        v-for="e in edges"
        :key="e.id"
        :d="edgePath(e.from, e.to) ?? ''"
        stroke="rgba(247,236,208,0.22)"
        stroke-width="1.2"
        fill="none"
        stroke-dasharray="0.5 1.5"
        stroke-linecap="round"
      />

      <!-- ── Bâtiments ── -->
      <g
        v-for="n in nodes"
        :key="n.id"
        style="cursor: pointer"
        @click="onClick(n.id)"
      >
        <rect
          :x="n.position.x - buildingSize(n.kind).w / 2"
          :y="n.position.y - buildingSize(n.kind).h / 2"
          :width="buildingSize(n.kind).w"
          :height="buildingSize(n.kind).h"
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
        >{{ n.icon ?? pinByKind(n.kind) }}</text>
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
        left: `${n.position.x / 100 * width}px`,
        top: `${(n.position.y + buildingSize(n.kind).h / 2) / 100 * height + 4}px`,
        color: isSelected(n.id) ? 'var(--color-gold)' : toneColor(n.status),
      }"
    >{{ n.short_label ?? n.name }}</div>

    <!-- Position du groupe (sur la node courante) -->
    <div v-if="youPosition" class="town-map-here" :style="youPosition">
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

.town-map-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.7;
}

.town-map-svg {
  position: absolute;
  inset: 0;
  z-index: 1;
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
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  transform: translate(-50%, 0);
  pointer-events: none;
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

.map-gen-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 6;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 6px;
  background: var(--color-bg-elev);
  border: 1px solid var(--color-border-strong);
  color: var(--color-text-muted);
  font: 500 10px/1 var(--font-display);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  pointer-events: none;
}

.map-gen-badge.gen-generating {
  color: var(--color-ember);
  border-color: var(--color-ember);
}

.gen-spinner {
  display: inline-block;
  width: 10px;
  height: 10px;
  border: 2px solid var(--color-border);
  border-top-color: currentColor;
  border-radius: 50%;
  animation: gen-spin 0.8s linear infinite;
}

@keyframes gen-spin {
  to { transform: rotate(360deg); }
}
</style>
