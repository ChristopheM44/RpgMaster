<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  seed?: string | null
}>(), {
  seed: null,
})

const patternId = computed(() => `map-parchment-${hashSeed(props.seed ?? 'default')}`)
const stainA = computed(() => hashSeed(`${props.seed}:a`) % 100)
const stainB = computed(() => hashSeed(`${props.seed}:b`) % 100)

function hashSeed(seed: string): number {
  let hash = 0
  for (let i = 0; i < seed.length; i++) {
    hash = (hash * 31 + seed.charCodeAt(i)) >>> 0
  }
  return hash
}
</script>

<template>
  <svg class="map-background" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
    <defs>
      <pattern :id="patternId" width="12" height="12" patternUnits="userSpaceOnUse">
        <path
          d="M0 2 C4 0 7 4 12 1 M1 10 C5 7 8 12 12 9"
          stroke="var(--color-border)"
          stroke-width="0.15"
          fill="none"
        />
      </pattern>
      <radialGradient id="map-parchment-warm" cx="50%" cy="45%" r="65%">
        <stop offset="0%" stop-color="var(--color-parchment)" stop-opacity="0.18" />
        <stop offset="100%" stop-color="var(--color-gold)" stop-opacity="0.04" />
      </radialGradient>
    </defs>
    <path
      class="map-background__paper"
      d="M3 6 C10 2 18 5 27 3 C39 1 52 4 66 3 C80 2 91 4 97 9 C94 20 98 30 96 42 C94 55 99 66 95 79 C91 93 76 96 62 94 C49 92 37 98 24 95 C12 92 4 86 5 73 C6 60 2 49 4 35 C6 24 1 15 3 6 Z"
    />
    <rect width="100" height="100" :fill="`url(#${patternId})`" class="map-background__grain" />
    <circle :cx="18 + (stainA % 46)" :cy="18 + (stainB % 52)" r="16" class="map-background__stain" />
    <circle :cx="56 + (stainB % 24)" :cy="34 + (stainA % 42)" r="10" class="map-background__stain is-soft" />
  </svg>
</template>

<style scoped>
.map-background {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  color: var(--color-gold);
  pointer-events: none;
}

.map-background__paper {
  fill: url(#map-parchment-warm);
  stroke: var(--color-border-strong);
  stroke-width: 0.6;
}

.map-background__grain {
  stroke: var(--color-border);
  stroke-width: 0.25;
  fill: transparent;
  opacity: 0.55;
}

.map-background__stain {
  fill: var(--color-ember);
  opacity: 0.08;
}

.map-background__stain.is-soft {
  fill: var(--color-teal);
  opacity: 0.06;
}
</style>
