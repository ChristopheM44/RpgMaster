<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '../../stores/session'
import { useGameStore } from '../../stores/game'
import { useExplorationParty } from '../../composables/useExplorationParty'
import { useExplorationPois } from '../../composables/useExplorationPois'
import HeroToken from './HeroToken.vue'
import PoiToken from './PoiToken.vue'

const props = withDefaults(defineProps<{
  cell?: number
}>(), {
  cell: 44,
})

const sessionStore = useSessionStore()
const gameStore = useGameStore()
const { party } = useExplorationParty()
const { pois } = useExplorationPois()

// Dimensions de la scène : pilotées par le backend, fallback 12×12 si pas chargé.
const cols = computed(() => gameStore.currentScene?.cols ?? 12)
const rows = computed(() => gameStore.currentScene?.rows ?? 12)

const widthPx = computed(() => cols.value * props.cell)
const heightPx = computed(() => rows.value * props.cell)

const canopyCircles: Array<[number, number]> = [
  [1, 1], [3, 5], [8, 1], [10, 4], [2, 9], [8, 9], [10, 10], [6, 6],
]

const grid = computed(() => {
  const v = Array.from({ length: cols.value + 1 }, (_, i) => i * props.cell)
  const h = Array.from({ length: rows.value + 1 }, (_, i) => i * props.cell)
  return { v, h }
})

function pathTrack() {
  const c = props.cell
  const trackRow = Math.max(0, Math.min(rows.value - 1, Math.floor(rows.value / 2)))
  return `M 0 ${(trackRow + 0.5) * c} Q ${3 * c} ${(trackRow - 1) * c} ${5 * c} ${trackRow * c} T ${cols.value * c} ${(trackRow + 0.5) * c}`
}

function isSelected(id: string) {
  return sessionStore.selectedId === id
}

function isHighlighted(id: string) {
  return sessionStore.highlightedIds.includes(id)
}

function onClick(id: string) {
  sessionStore.selectEntity(id)
}
</script>

<template>
  <div
    class="scene-map"
    :style="{ width: `${widthPx}px`, height: `${heightPx}px` }"
  >
    <!-- Brume / texture forêt -->
    <div class="scene-map-fog" />

    <!-- Canopée -->
    <svg
      class="scene-map-layer"
      :width="widthPx"
      :height="heightPx"
      style="opacity: 0.35"
    >
      <circle
        v-for="([cx, cy], i) in canopyCircles"
        :key="i"
        :cx="cx * cell + cell / 2"
        :cy="cy * cell + cell / 2"
        :r="cell * 1.1"
        fill="rgba(58,90,58,0.25)"
      />
    </svg>

    <!-- Piste serpentine -->
    <svg
      class="scene-map-layer"
      :width="widthPx"
      :height="heightPx"
    >
      <path
        :d="pathTrack()"
        fill="none"
        stroke="rgba(247,236,208,0.10)"
        :stroke-width="cell * 0.6"
        stroke-linecap="round"
      />
      <path
        :d="pathTrack()"
        fill="none"
        stroke="rgba(247,236,208,0.18)"
        stroke-width="1"
        stroke-dasharray="4 6"
      />
    </svg>

    <!-- Grille -->
    <svg
      class="scene-map-layer"
      :width="widthPx"
      :height="heightPx"
    >
      <line
        v-for="(x, i) in grid.v"
        :key="`v${i}`"
        :x1="x"
        :y1="0"
        :x2="x"
        :y2="heightPx"
        stroke="rgba(255,235,180,0.04)"
        stroke-width="1"
      />
      <line
        v-for="(y, i) in grid.h"
        :key="`h${i}`"
        :x1="0"
        :y1="y"
        :x2="widthPx"
        :y2="y"
        stroke="rgba(255,235,180,0.04)"
        stroke-width="1"
      />
    </svg>

    <!-- Coords -->
    <div class="scene-map-coord top-left">A1</div>
    <div class="scene-map-coord bottom-right">{{ String.fromCharCode(64 + cols) }}{{ rows }} · {{ cols }}×{{ rows }} m</div>

    <!-- POI tokens -->
    <PoiToken
      v-for="poi in pois"
      :key="poi.id"
      :poi="poi"
      :cell="cell"
      :selected="isSelected(poi.id)"
      :highlighted="isHighlighted(poi.id)"
      @click="onClick"
    />

    <!-- Hero tokens -->
    <HeroToken
      v-for="hero in party"
      :key="hero.id"
      :hero="hero"
      :cell="cell"
      :selected="isSelected(hero.id)"
      :highlighted="isHighlighted(hero.id)"
      @click="onClick"
    />
  </div>
</template>

<style scoped>
.scene-map {
  position: relative;
  border-radius: 10px;
  border: 1px solid var(--color-border-strong);
  background: linear-gradient(135deg, #16201a 0%, #0e120e 100%);
  overflow: hidden;
  box-shadow: inset 0 0 80px rgba(0, 0, 0, 0.7), 0 6px 28px rgba(0, 0, 0, 0.5);
  flex-shrink: 0;
}

.scene-map-fog {
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(ellipse 240px 120px at 25% 30%, rgba(58, 90, 58, 0.30), transparent 70%),
    radial-gradient(ellipse 200px 100px at 75% 25%, rgba(192, 144, 255, 0.10), transparent 70%),
    radial-gradient(ellipse 180px 90px at 80% 80%, rgba(255, 130, 71, 0.06), transparent 70%),
    radial-gradient(ellipse 220px 110px at 30% 80%, rgba(79, 216, 192, 0.08), transparent 70%);
  pointer-events: none;
}

.scene-map-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.scene-map-coord {
  position: absolute;
  font-size: 9px;
  color: var(--color-text-dim);
  font-family: var(--font-mono);
  pointer-events: none;
}

.scene-map-coord.top-left { top: 4px; left: 4px; }
.scene-map-coord.bottom-right { bottom: 4px; right: 4px; }
</style>
