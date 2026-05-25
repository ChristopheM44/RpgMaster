<script setup lang="ts">
import { useSessionStore } from '../../stores/session'
import { EX_REGION, type ExRegionPin } from '../../fixtures/exploration'

withDefaults(defineProps<{
  width?: number
  height?: number
}>(), {
  width: 640,
  height: 580,
})

const sessionStore = useSessionStore()

const forestCircles: Array<[number, number]> = [
  [24, 18], [32, 22], [40, 16], [36, 26], [58, 20], [66, 12], [72, 22], [80, 16],
  [40, 72], [48, 78], [56, 82], [62, 76], [20, 82], [28, 88],
]

const mountains: Array<[number, number]> = [[78, 28], [84, 32], [88, 26], [92, 34]]

function toneHex(tag: ExRegionPin['tag']): string {
  switch (tag) {
    case 'sûr':    return '#6fd96f'
    case 'active': return '#f0c764'
    case 'danger': return '#e84545'
    case 'rumeur': return '#c090ff'
    default:        return '#f7ecd0'
  }
}

function toneColor(tag: ExRegionPin['tag']): string {
  switch (tag) {
    case 'sûr':    return 'var(--color-green)'
    case 'active': return 'var(--color-gold)'
    case 'danger': return 'var(--color-blood)'
    case 'rumeur': return 'var(--color-arcane)'
    default:        return 'var(--color-parchment-dark)'
  }
}

function isSelected(id: string) { return sessionStore.selectedId === id }
function isHighlighted(id: string) { return sessionStore.highlightedIds.includes(id) }

function onClick(id: string) { sessionStore.selectEntity(id) }

function pinFill(p: ExRegionPin) { return toneHex(p.tag) }
function pinStroke(p: ExRegionPin) { return isSelected(p.id) ? 'var(--color-gold)' : 'rgba(0,0,0,0.6)' }
function pinRadius(p: ExRegionPin) { return isSelected(p.id) || isHighlighted(p.id) ? 2 : 1.5 }
</script>

<template>
  <div
    class="region-map"
    :style="{ width: `${width}px`, height: `${height}px` }"
  >
    <svg
      viewBox="0 0 100 100"
      :width="width"
      :height="height"
      preserveAspectRatio="none"
      class="region-map-svg"
    >
      <!-- Mer -->
      <path d="M 0 0 L 18 0 L 12 30 L 6 60 L 10 90 L 0 100 Z" fill="rgba(40,80,100,0.3)" />
      <path d="M 0 0 L 18 0 L 12 30 L 6 60 L 10 90 L 0 100 Z" stroke="rgba(79,216,192,0.25)" stroke-width="0.3" fill="none" />

      <!-- Forêts -->
      <circle
        v-for="([x, y], i) in forestCircles"
        :key="`f${i}`"
        :cx="x"
        :cy="y"
        r="3.2"
        fill="rgba(58,90,58,0.4)"
      />

      <!-- Montagnes -->
      <polygon
        v-for="([x, y], i) in mountains"
        :key="`m${i}`"
        :points="`${x},${y + 5} ${x - 3},${y + 5} ${x},${y - 2}`"
        fill="rgba(120,108,90,0.5)"
      />

      <!-- Routes -->
      <path
        v-for="(d, i) in EX_REGION.roads"
        :key="`r${i}`"
        :d="d"
        stroke="rgba(247,236,208,0.18)"
        stroke-width="0.5"
        fill="none"
        stroke-dasharray="0.8 1.6"
        stroke-linecap="round"
      />

      <!-- Pins -->
      <g
        v-for="p in EX_REGION.pins"
        :key="p.id"
        style="cursor: pointer"
        @click="onClick(p.id)"
      >
        <circle
          v-if="p.state === 'here'"
          :cx="p.x"
          :cy="p.y"
          r="4"
          fill="none"
          :stroke="toneHex(p.tag)"
          stroke-width="0.4"
          opacity="0.4"
        />
        <circle
          :cx="p.x"
          :cy="p.y"
          :r="pinRadius(p)"
          :fill="pinFill(p)"
          :stroke="pinStroke(p)"
          stroke-width="0.4"
        />
        <circle
          v-if="p.state === 'destination'"
          :cx="p.x"
          :cy="p.y"
          r="3"
          fill="none"
          :stroke="toneHex(p.tag)"
          stroke-width="0.3"
          stroke-dasharray="0.6 0.6"
        />
      </g>
    </svg>

    <!-- Labels -->
    <div
      v-for="p in EX_REGION.pins"
      :key="p.id"
      class="region-map-label"
      :style="{
        left: `${p.x}%`,
        top: `calc(${p.y}% + 8px)`,
        color: isSelected(p.id) ? 'var(--color-gold)' : toneColor(p.tag),
      }"
    >
      {{ p.label }}
      <div v-if="p.state === 'here'" class="region-map-here">▼ vous</div>
    </div>

    <div class="region-map-coord">Côte des Épées</div>
    <div class="region-map-north">N ↑</div>
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
