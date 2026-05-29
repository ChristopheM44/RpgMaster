<script setup lang="ts">
import { computed } from 'vue'
import type {
  MapVisualAsset,
  SceneElement,
  SceneElementGeometry,
  SceneLayout,
  SceneTheme,
} from '../../types'

const props = withDefaults(defineProps<{
  scene?: SceneLayout | null
  cell?: number
  mode?: 'exploration' | 'combat'
  colsFallback?: number
  rowsFallback?: number
  themeFallback?: SceneTheme
  selectedElementId?: string | null
}>(), {
  scene: null,
  cell: 44,
  mode: 'exploration',
  colsFallback: 12,
  rowsFallback: 12,
  themeFallback: 'forest',
  selectedElementId: null,
})

const emit = defineEmits<{
  elementClick: [element: SceneElement]
}>()

interface BiomeStyle {
  bg: string
  grid: string
  track: string
  fog: string[]
}

const BIOMES: Record<SceneTheme, BiomeStyle> = {
  forest: {
    bg: 'linear-gradient(135deg, rgba(22,32,26,1), rgba(14,18,14,1))',
    grid: 'rgba(255,235,180,0.045)',
    track: 'rgba(247,236,208,0.10)',
    fog: [
      'radial-gradient(ellipse 240px 120px at 25% 30%, rgba(58,90,58,0.30), transparent 70%)',
      'radial-gradient(ellipse 200px 100px at 75% 25%, rgba(192,144,255,0.10), transparent 70%)',
    ],
  },
  beach: {
    bg: 'linear-gradient(175deg, rgba(26,32,48,1), rgba(26,24,16,1) 60%, rgba(18,17,11,1))',
    grid: 'rgba(255,235,180,0.055)',
    track: 'rgba(79,216,192,0.14)',
    fog: [
      'radial-gradient(ellipse 300px 80px at 50% 100%, rgba(79,216,192,0.22), transparent 70%)',
      'radial-gradient(ellipse 200px 120px at 20% 40%, rgba(247,236,208,0.06), transparent 70%)',
    ],
  },
  coastal: {
    bg: 'linear-gradient(170deg, rgba(22,32,40,1), rgba(24,24,26,1) 60%, rgba(16,16,13,1))',
    grid: 'rgba(255,235,180,0.045)',
    track: 'rgba(79,216,192,0.12)',
    fog: [
      'radial-gradient(ellipse 320px 90px at 50% 100%, rgba(79,216,192,0.18), transparent 70%)',
      'radial-gradient(ellipse 200px 100px at 75% 30%, rgba(192,144,255,0.08), transparent 70%)',
    ],
  },
  rocky: {
    bg: 'linear-gradient(135deg, rgba(28,24,20,1), rgba(20,18,14,1))',
    grid: 'rgba(255,235,180,0.045)',
    track: 'rgba(247,236,208,0.09)',
    fog: [
      'radial-gradient(ellipse 200px 120px at 30% 30%, rgba(120,100,70,0.18), transparent 70%)',
      'radial-gradient(ellipse 180px 90px at 20% 80%, rgba(192,144,255,0.06), transparent 70%)',
    ],
  },
  mountain: {
    bg: 'linear-gradient(160deg, rgba(24,24,32,1), rgba(18,18,26,1))',
    grid: 'rgba(255,235,180,0.045)',
    track: 'rgba(247,236,208,0.08)',
    fog: [
      'radial-gradient(ellipse 300px 80px at 50% 0%, rgba(180,180,220,0.12), transparent 70%)',
      'radial-gradient(ellipse 200px 80px at 80% 60%, rgba(120,100,150,0.10), transparent 70%)',
    ],
  },
  dungeon: {
    bg: 'linear-gradient(135deg, rgba(12,12,16,1), rgba(8,8,8,1))',
    grid: 'rgba(255,235,180,0.065)',
    track: 'rgba(247,236,208,0.08)',
    fog: [
      'radial-gradient(ellipse 180px 100px at 25% 30%, rgba(255,130,71,0.12), transparent 70%)',
      'radial-gradient(ellipse 240px 120px at 50% 80%, rgba(20,10,5,0.50), transparent 70%)',
    ],
  },
  cave: {
    bg: 'linear-gradient(135deg, rgba(10,10,12,1), rgba(6,6,8,1))',
    grid: 'rgba(255,235,180,0.055)',
    track: 'rgba(247,236,208,0.07)',
    fog: [
      'radial-gradient(ellipse 160px 80px at 30% 40%, rgba(79,216,192,0.08), transparent 70%)',
      'radial-gradient(ellipse 240px 120px at 50% 50%, rgba(0,0,0,0.40), transparent 70%)',
    ],
  },
  city: {
    bg: 'linear-gradient(135deg, var(--color-bg-elev), var(--color-bg))',
    grid: 'rgba(255,235,180,0.065)',
    track: 'rgba(247,236,208,0.15)',
    fog: [
      'radial-gradient(ellipse 240px 120px at 30% 40%, rgba(240,199,100,0.08), transparent 70%)',
      'radial-gradient(ellipse 200px 100px at 70% 30%, rgba(255,130,71,0.08), transparent 70%)',
    ],
  },
  plains: {
    bg: 'linear-gradient(135deg, rgba(24,28,20,1), rgba(16,18,12,1))',
    grid: 'rgba(255,235,180,0.045)',
    track: 'rgba(247,236,208,0.13)',
    fog: [
      'radial-gradient(ellipse 300px 60px at 50% 10%, rgba(180,200,100,0.08), transparent 70%)',
      'radial-gradient(ellipse 240px 80px at 20% 50%, rgba(100,140,60,0.10), transparent 70%)',
    ],
  },
  swamp: {
    bg: 'linear-gradient(135deg, rgba(14,20,16,1), rgba(10,16,10,1))',
    grid: 'rgba(255,235,180,0.045)',
    track: 'rgba(79,216,192,0.11)',
    fog: [
      'radial-gradient(ellipse 260px 120px at 30% 60%, rgba(40,80,40,0.30), transparent 70%)',
      'radial-gradient(ellipse 240px 110px at 60% 80%, rgba(79,216,192,0.10), transparent 70%)',
    ],
  },
  desert: {
    bg: 'linear-gradient(135deg, rgba(30,24,16,1), rgba(24,20,10,1))',
    grid: 'rgba(255,235,180,0.055)',
    track: 'rgba(247,236,208,0.13)',
    fog: [
      'radial-gradient(ellipse 300px 60px at 50% 0%, rgba(255,180,60,0.10), transparent 70%)',
      'radial-gradient(ellipse 260px 50px at 50% 100%, rgba(180,120,40,0.14), transparent 70%)',
    ],
  },
}

const cols = computed(() => props.scene?.cols ?? props.colsFallback)
const rows = computed(() => props.scene?.rows ?? props.rowsFallback)
const widthPx = computed(() => cols.value * props.cell)
const heightPx = computed(() => rows.value * props.cell)
const theme = computed(() => props.scene?.scene_theme ?? props.themeFallback)
const biome = computed(() => BIOMES[theme.value] ?? BIOMES.forest)
const elements = computed(() => props.scene?.elements ?? [])
const elementLinks = computed(() => {
  const links = new Set<string>()
  for (const poi of props.scene?.pois ?? []) {
    if (poi.element_id) links.add(poi.element_id)
  }
  for (const exit of props.scene?.exits ?? []) {
    if (exit.element_id) links.add(exit.element_id)
  }
  return links
})
const visualAsset = computed<MapVisualAsset | undefined>(() => props.scene?.visual_asset)
const visualAssetReady = computed(() =>
  visualAsset.value?.status === 'ready' && Boolean(visualAsset.value.url),
)
const patternId = computed(() => `local-map-grid-${hashSeed(props.scene?.scene_id ?? `${cols.value}x${rows.value}`)}`)
const showTrack = computed(() =>
  !elements.value.some((element) => element.kind === 'wall')
  && (props.scene?.exits?.length ?? 0) > 0,
)

function isElementInteractive(element: SceneElement): boolean {
  return Boolean(element.interactive || elementLinks.value.has(element.id))
}

function onElementClick(element: SceneElement) {
  if (!isElementInteractive(element)) return
  emit('elementClick', element)
}

function shapeForGeometry(geometry: SceneElementGeometry) {
  if (geometry.type === 'line') {
    return {
      x1: geometry.from.col * props.cell,
      y1: geometry.from.row * props.cell,
      x2: geometry.to.col * props.cell,
      y2: geometry.to.row * props.cell,
    }
  }
  if (geometry.type === 'rect') {
    return {
      x: geometry.col * props.cell,
      y: geometry.row * props.cell,
      width: geometry.width * props.cell,
      height: geometry.height * props.cell,
    }
  }
  return {
    cx: geometry.col * props.cell,
    cy: geometry.row * props.cell,
    rx: geometry.radius_col * props.cell,
    ry: geometry.radius_row * props.cell,
  }
}

function pathTrack() {
  const exits = (props.scene?.exits ?? []).filter((exit) => exit.position)
  if (exits.length < 2) {
    const trackRow = Math.max(0, Math.min(rows.value - 1, Math.floor(rows.value / 2)))
    return `M 0 ${(trackRow + 0.5) * props.cell} L ${widthPx.value} ${(trackRow + 0.5) * props.cell}`
  }
  const sorted = [...exits].sort((a, b) => a.position.col - b.position.col)
  const start = sorted[0]!.position
  const end = sorted[sorted.length - 1]!.position
  const x1 = (start.col + 0.5) * props.cell
  const y1 = (start.row + 0.5) * props.cell
  const x2 = (end.col + 0.5) * props.cell
  const y2 = (end.row + 0.5) * props.cell
  return `M ${x1} ${y1} C ${x1 + (x2 - x1) * 0.35} ${y1 - props.cell * 1.2} ${x1 + (x2 - x1) * 0.65} ${y2 + props.cell * 1.2} ${x2} ${y2}`
}

function hashSeed(seed: string): number {
  let hash = 0
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) >>> 0
  return hash
}
</script>

<template>
  <div
    class="local-map-canvas"
    :class="[`is-${mode}`, `theme-${theme}`]"
    :style="{
      width: `${widthPx}px`,
      height: `${heightPx}px`,
      background: biome.bg,
    }"
  >
    <img
      v-if="visualAssetReady"
      class="local-map-image"
      :src="visualAsset?.url"
      alt=""
      draggable="false"
    />
    <div
      class="local-map-fog"
      :class="{ 'has-image': visualAssetReady }"
      :style="{ backgroundImage: biome.fog.join(',') }"
    />

    <svg
      v-if="showTrack"
      class="local-map-layer"
      :width="widthPx"
      :height="heightPx"
      aria-hidden="true"
    >
      <path
        :d="pathTrack()"
        fill="none"
        :stroke="biome.track"
        :stroke-width="cell * 0.72"
        stroke-linecap="round"
      />
      <path
        :d="pathTrack()"
        fill="none"
        stroke="rgba(247,236,208,0.22)"
        :stroke-width="cell * 0.15"
        stroke-dasharray="6 7"
        stroke-linecap="round"
      />
    </svg>

    <svg
      class="local-map-layer local-map-elements"
      :width="widthPx"
      :height="heightPx"
    >
      <g
        v-for="element in elements"
        :key="element.id"
        class="local-map-element"
        :class="[
          `kind-${element.kind}`,
          {
            'is-interactive': isElementInteractive(element),
            'is-selected': selectedElementId === element.id,
          },
        ]"
        :role="isElementInteractive(element) ? 'button' : undefined"
        :tabindex="isElementInteractive(element) ? 0 : undefined"
        :data-testid="`local-map-element-${element.id}`"
        @click.stop="onElementClick(element)"
        @keydown.enter.prevent="onElementClick(element)"
      >
        <title>{{ element.name }}</title>
        <line
          v-if="element.geometry.type === 'line'"
          v-bind="shapeForGeometry(element.geometry)"
        />
        <rect
          v-else-if="element.geometry.type === 'rect'"
          v-bind="shapeForGeometry(element.geometry)"
          rx="3"
        />
        <ellipse
          v-else
          v-bind="shapeForGeometry(element.geometry)"
        />
      </g>
    </svg>

    <svg class="local-map-grid" :width="widthPx" :height="heightPx" aria-hidden="true">
      <defs>
        <pattern :id="patternId" :width="cell" :height="cell" patternUnits="userSpaceOnUse">
          <path :d="`M ${cell} 0 L 0 0 0 ${cell}`" :stroke="biome.grid" fill="none" stroke-width="1" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" :fill="`url(#${patternId})`" />
    </svg>

    <slot />

    <div class="local-map-vignette" />
    <div class="local-map-coord top-left">A1</div>
    <div class="local-map-coord bottom-right">
      {{ String.fromCharCode(64 + cols) }}{{ rows }} · {{ cols }}×{{ rows }}
    </div>
  </div>
</template>

<style scoped>
.local-map-canvas {
  position: relative;
  border: 1px solid var(--color-border-strong);
  border-radius: 10px;
  overflow: hidden;
  box-shadow: inset 0 0 80px rgba(0, 0, 0, 0.68), 0 6px 28px rgba(0, 0, 0, 0.45);
  flex-shrink: 0;
}

.local-map-image,
.local-map-fog,
.local-map-layer,
.local-map-grid,
.local-map-vignette {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.local-map-image {
  object-fit: cover;
  z-index: 0;
}

.local-map-fog {
  z-index: 1;
  pointer-events: none;
  opacity: 0.9;
}

.local-map-fog.has-image {
  opacity: 0.34;
  mix-blend-mode: screen;
}

.local-map-layer {
  z-index: 2;
  pointer-events: none;
}

.local-map-elements {
  z-index: 3;
  pointer-events: auto;
}

.local-map-grid {
  z-index: 4;
  pointer-events: none;
}

.local-map-vignette {
  z-index: 5;
  pointer-events: none;
  box-shadow: inset 0 0 52px rgba(0, 0, 0, 0.58);
}

.local-map-element {
  color: var(--color-parchment-dark);
  pointer-events: none;
}

.local-map-element.is-interactive {
  cursor: pointer;
  pointer-events: auto;
}

.local-map-element line,
.local-map-element rect,
.local-map-element ellipse {
  fill: rgba(247, 236, 208, 0.08);
  stroke: currentColor;
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
}

.local-map-element.kind-wall {
  color: var(--color-parchment);
}

.local-map-element.kind-wall line {
  stroke-width: 4;
}

.local-map-element.kind-door {
  color: var(--color-gold);
}

.local-map-element.kind-door rect {
  fill: rgba(240, 199, 100, 0.24);
}

.local-map-element.kind-window {
  color: var(--color-teal);
}

.local-map-element.kind-window rect {
  fill: rgba(79, 216, 192, 0.20);
}

.local-map-element.kind-furniture,
.local-map-element.kind-cover {
  color: var(--color-parchment-dark);
}

.local-map-element.kind-furniture rect,
.local-map-element.kind-cover rect {
  fill: rgba(247, 236, 208, 0.13);
}

.local-map-element.kind-hazard {
  color: var(--color-blood);
}

.local-map-element.kind-hazard ellipse,
.local-map-element.kind-hazard rect {
  fill: rgba(232, 69, 69, 0.16);
}

.local-map-element.kind-light {
  color: var(--color-ember);
}

.local-map-element.kind-light ellipse {
  fill: rgba(255, 130, 71, 0.20);
}

.local-map-element.kind-stairs {
  color: var(--color-arcane);
}

.local-map-element.is-interactive:hover,
.local-map-element.is-selected {
  filter: drop-shadow(0 0 8px currentColor);
}

.local-map-coord {
  position: absolute;
  z-index: 8;
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--color-text-muted);
  background: rgba(14, 13, 20, 0.72);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 2px 5px;
  pointer-events: none;
}

.local-map-coord.top-left {
  top: 6px;
  left: 6px;
}

.local-map-coord.bottom-right {
  right: 6px;
  bottom: 6px;
}
</style>
