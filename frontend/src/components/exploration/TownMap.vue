<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '../../stores/session'
import { EX_TOWN, type ExTownBuilding } from '../../fixtures/exploration'

const props = withDefaults(defineProps<{
  width?: number
  height?: number
}>(), {
  width: 640,
  height: 580,
})

const sessionStore = useSessionStore()

const forestCircles: Array<[number, number]> = [
  [80, 8], [88, 12], [92, 22], [82, 18], [8, 8], [16, 12], [6, 20],
  [14, 86], [8, 92], [22, 90],
]

function toneColor(tag: ExTownBuilding['tag']): string {
  switch (tag) {
    case 'sûr':      return 'var(--color-green)'
    case 'objectif': return 'var(--color-gold)'
    case 'danger':   return 'var(--color-blood)'
    default:          return 'var(--color-parchment-dark)'
  }
}

function toneHex(tag: ExTownBuilding['tag']): string {
  switch (tag) {
    case 'sûr':      return '#6fd96f'
    case 'objectif': return '#f0c764'
    case 'danger':   return '#e84545'
    default:          return '#f7ecd0'
  }
}

function isSelected(id: string) { return sessionStore.selectedId === id }
function isHighlighted(id: string) { return sessionStore.highlightedIds.includes(id) }

function onClick(id: string) {
  sessionStore.selectEntity(id)
}

function rectFill(b: ExTownBuilding) {
  if (isSelected(b.id)) return `${toneHex(b.tag)}40`
  if (isHighlighted(b.id)) return `${toneHex(b.tag)}25`
  return 'rgba(40,32,24,0.7)'
}

function rectStroke(b: ExTownBuilding) {
  if (isSelected(b.id)) return 'var(--color-gold)'
  if (isHighlighted(b.id)) return 'var(--color-ember)'
  return toneHex(b.tag)
}

const labels = computed(() =>
  EX_TOWN.buildings.map((b) => ({
    id: b.id,
    label: b.label,
    color: isSelected(b.id) ? 'var(--color-gold)' : toneColor(b.tag),
    leftPct: (b.x + b.w / 2),
    topPct: (b.y + b.h) + (4 / props.height) * 100,
  })),
)
</script>

<template>
  <div
    class="town-map"
    :style="{ width: `${width}px`, height: `${height}px` }"
  >
    <svg
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

      <!-- Rivière -->
      <path d="M 0 76 Q 30 80 60 78 T 100 80" stroke="rgba(79,216,192,0.25)" stroke-width="1.5" fill="none" />

      <!-- Routes -->
      <path
        v-for="(d, i) in EX_TOWN.roads"
        :key="`r${i}`"
        :d="d"
        stroke="rgba(247,236,208,0.18)"
        stroke-width="2.5"
        stroke-linecap="round"
        fill="none"
        stroke-dasharray="0.5 1.5"
      />

      <!-- Forêts -->
      <circle
        v-for="([x, y], i) in forestCircles"
        :key="`f${i}`"
        :cx="x"
        :cy="y"
        r="3"
        fill="rgba(58,90,58,0.4)"
      />

      <!-- Bâtiments -->
      <g
        v-for="b in EX_TOWN.buildings"
        :key="b.id"
        style="cursor: pointer"
        @click="onClick(b.id)"
      >
        <rect
          :x="b.x"
          :y="b.y"
          :width="b.w"
          :height="b.h"
          rx="0.6"
          :fill="rectFill(b)"
          :stroke="rectStroke(b)"
          :stroke-width="isSelected(b.id) ? 0.5 : 0.25"
        />
        <text
          :x="b.x + b.w / 2"
          :y="b.y + b.h / 2 + 0.4"
          text-anchor="middle"
          :fill="toneHex(b.tag)"
          font-size="2.2"
          font-family="Cinzel, serif"
          font-weight="700"
        >{{ b.pin }}</text>
      </g>
    </svg>

    <!-- Labels HTML overlay -->
    <div
      v-for="l in labels"
      :key="l.id"
      class="town-map-label"
      :style="{
        left: `${l.leftPct}%`,
        top: `${l.topPct}%`,
        color: l.color,
      }"
    >{{ l.label }}</div>

    <!-- Position du groupe -->
    <div class="town-map-here">
      <span class="town-map-here-icon">👥</span>
      <span class="town-map-here-label">Vous</span>
    </div>

    <!-- Coords overlay -->
    <div class="town-map-coord">Phandalin · plan</div>
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
