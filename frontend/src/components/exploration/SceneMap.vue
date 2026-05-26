<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '../../stores/session'
import { useGameStore } from '../../stores/game'
import { useExplorationParty } from '../../composables/useExplorationParty'
import { useExplorationPois } from '../../composables/useExplorationPois'
import HeroToken from './HeroToken.vue'
import PoiToken from './PoiToken.vue'
import type { SceneTheme } from '../../types'

const props = withDefaults(defineProps<{
  cell?: number
}>(), {
  cell: 44,
})

const sessionStore = useSessionStore()
const gameStore = useGameStore()
const { party } = useExplorationParty()
const { pois } = useExplorationPois()

// Dimensions pilotées par le backend, fallback 12×12
const cols = computed(() => gameStore.currentScene?.cols ?? 12)
const rows = computed(() => gameStore.currentScene?.rows ?? 12)
const theme = computed<SceneTheme>(() => gameStore.currentScene?.scene_theme ?? 'forest')

const widthPx = computed(() => cols.value * props.cell)
const heightPx = computed(() => rows.value * props.cell)

// ── Biomes ──────────────────────────────────────────────────────────────────

interface BiomeStyle {
  /** Gradient CSS pour le fond */
  bgGradient: string
  /** Couleur de la grille */
  gridColor: string
  /** Couleur de la piste/chemin */
  trackColor: string
  /** Couleur d'ambiance fog principal */
  fogColors: string[]
}

const BIOMES: Record<SceneTheme, BiomeStyle> = {
  forest: {
    bgGradient: 'linear-gradient(135deg, #16201a 0%, #0e120e 100%)',
    gridColor: 'rgba(255,235,180,0.04)',
    trackColor: 'rgba(247,236,208,0.10)',
    fogColors: [
      'radial-gradient(ellipse 240px 120px at 25% 30%, rgba(58,90,58,0.30), transparent 70%)',
      'radial-gradient(ellipse 200px 100px at 75% 25%, rgba(192,144,255,0.10), transparent 70%)',
      'radial-gradient(ellipse 180px 90px at 80% 80%, rgba(255,130,71,0.06), transparent 70%)',
      'radial-gradient(ellipse 220px 110px at 30% 80%, rgba(79,216,192,0.08), transparent 70%)',
    ],
  },
  beach: {
    bgGradient: 'linear-gradient(175deg, #1a2030 0%, #1a1810 60%, #12110b 100%)',
    gridColor: 'rgba(255,235,180,0.05)',
    trackColor: 'rgba(79,216,192,0.12)',
    fogColors: [
      'radial-gradient(ellipse 300px 80px at 50% 100%, rgba(79,216,192,0.22), transparent 70%)',
      'radial-gradient(ellipse 260px 70px at 50% 90%, rgba(30,80,110,0.25), transparent 70%)',
      'radial-gradient(ellipse 200px 120px at 20% 40%, rgba(247,236,208,0.06), transparent 70%)',
      'radial-gradient(ellipse 180px 100px at 80% 50%, rgba(79,216,192,0.08), transparent 70%)',
    ],
  },
  coastal: {
    bgGradient: 'linear-gradient(170deg, #162028 0%, #18181a 60%, #10100d 100%)',
    gridColor: 'rgba(255,235,180,0.04)',
    trackColor: 'rgba(79,216,192,0.10)',
    fogColors: [
      'radial-gradient(ellipse 320px 90px at 50% 100%, rgba(79,216,192,0.18), transparent 70%)',
      'radial-gradient(ellipse 240px 80px at 30% 85%, rgba(30,80,120,0.22), transparent 70%)',
      'radial-gradient(ellipse 200px 100px at 75% 30%, rgba(192,144,255,0.08), transparent 70%)',
      'radial-gradient(ellipse 150px 80px at 15% 50%, rgba(79,216,192,0.10), transparent 70%)',
    ],
  },
  rocky: {
    bgGradient: 'linear-gradient(135deg, #1c1814 0%, #14120e 100%)',
    gridColor: 'rgba(255,235,180,0.04)',
    trackColor: 'rgba(247,236,208,0.08)',
    fogColors: [
      'radial-gradient(ellipse 200px 120px at 30% 30%, rgba(120,100,70,0.18), transparent 70%)',
      'radial-gradient(ellipse 240px 100px at 70% 65%, rgba(90,80,60,0.14), transparent 70%)',
      'radial-gradient(ellipse 180px 90px at 20% 80%, rgba(192,144,255,0.06), transparent 70%)',
      'radial-gradient(ellipse 160px 80px at 80% 20%, rgba(255,130,71,0.04), transparent 70%)',
    ],
  },
  mountain: {
    bgGradient: 'linear-gradient(160deg, #181820 0%, #12121a 100%)',
    gridColor: 'rgba(255,235,180,0.04)',
    trackColor: 'rgba(247,236,208,0.07)',
    fogColors: [
      'radial-gradient(ellipse 300px 80px at 50% 0%, rgba(180,180,220,0.12), transparent 70%)',
      'radial-gradient(ellipse 240px 100px at 20% 30%, rgba(100,90,130,0.14), transparent 70%)',
      'radial-gradient(ellipse 200px 80px at 80% 60%, rgba(120,100,150,0.10), transparent 70%)',
      'radial-gradient(ellipse 180px 70px at 60% 80%, rgba(192,144,255,0.06), transparent 70%)',
    ],
  },
  dungeon: {
    bgGradient: 'linear-gradient(135deg, #0c0c10 0%, #080808 100%)',
    gridColor: 'rgba(255,235,180,0.06)',
    trackColor: 'rgba(247,236,208,0.08)',
    fogColors: [
      'radial-gradient(ellipse 180px 100px at 25% 30%, rgba(255,130,71,0.12), transparent 70%)',
      'radial-gradient(ellipse 200px 80px at 75% 60%, rgba(192,144,255,0.08), transparent 70%)',
      'radial-gradient(ellipse 240px 120px at 50% 80%, rgba(20,10,5,0.50), transparent 70%)',
      'radial-gradient(ellipse 160px 80px at 20% 70%, rgba(232,69,69,0.06), transparent 70%)',
    ],
  },
  cave: {
    bgGradient: 'linear-gradient(135deg, #0a0a0c 0%, #060608 100%)',
    gridColor: 'rgba(255,235,180,0.05)',
    trackColor: 'rgba(247,236,208,0.06)',
    fogColors: [
      'radial-gradient(ellipse 160px 80px at 30% 40%, rgba(79,216,192,0.08), transparent 70%)',
      'radial-gradient(ellipse 200px 100px at 70% 60%, rgba(192,144,255,0.07), transparent 70%)',
      'radial-gradient(ellipse 240px 120px at 50% 50%, rgba(0,0,0,0.40), transparent 70%)',
      'radial-gradient(ellipse 180px 90px at 20% 80%, rgba(255,130,71,0.05), transparent 70%)',
    ],
  },
  city: {
    bgGradient: 'linear-gradient(135deg, #16141e 0%, #0e0d14 100%)',
    gridColor: 'rgba(255,235,180,0.06)',
    trackColor: 'rgba(247,236,208,0.14)',
    fogColors: [
      'radial-gradient(ellipse 240px 120px at 30% 40%, rgba(240,199,100,0.08), transparent 70%)',
      'radial-gradient(ellipse 200px 100px at 70% 30%, rgba(255,130,71,0.08), transparent 70%)',
      'radial-gradient(ellipse 180px 90px at 80% 75%, rgba(192,144,255,0.08), transparent 70%)',
      'radial-gradient(ellipse 220px 110px at 20% 80%, rgba(240,199,100,0.06), transparent 70%)',
    ],
  },
  plains: {
    bgGradient: 'linear-gradient(135deg, #181c14 0%, #10120c 100%)',
    gridColor: 'rgba(255,235,180,0.04)',
    trackColor: 'rgba(247,236,208,0.12)',
    fogColors: [
      'radial-gradient(ellipse 300px 60px at 50% 10%, rgba(180,200,100,0.08), transparent 70%)',
      'radial-gradient(ellipse 240px 80px at 20% 50%, rgba(100,140,60,0.10), transparent 70%)',
      'radial-gradient(ellipse 200px 70px at 80% 60%, rgba(180,200,100,0.08), transparent 70%)',
      'radial-gradient(ellipse 260px 50px at 50% 90%, rgba(120,100,70,0.10), transparent 70%)',
    ],
  },
  swamp: {
    bgGradient: 'linear-gradient(135deg, #0e1410 0%, #0a100a 100%)',
    gridColor: 'rgba(255,235,180,0.04)',
    trackColor: 'rgba(79,216,192,0.10)',
    fogColors: [
      'radial-gradient(ellipse 260px 120px at 30% 60%, rgba(40,80,40,0.30), transparent 70%)',
      'radial-gradient(ellipse 200px 100px at 70% 40%, rgba(192,144,255,0.10), transparent 70%)',
      'radial-gradient(ellipse 240px 110px at 60% 80%, rgba(79,216,192,0.10), transparent 70%)',
      'radial-gradient(ellipse 180px 80px at 10% 30%, rgba(40,90,40,0.20), transparent 70%)',
    ],
  },
  desert: {
    bgGradient: 'linear-gradient(135deg, #1e1810 0%, #18140a 100%)',
    gridColor: 'rgba(255,235,180,0.05)',
    trackColor: 'rgba(247,236,208,0.12)',
    fogColors: [
      'radial-gradient(ellipse 300px 60px at 50% 0%, rgba(255,180,60,0.10), transparent 70%)',
      'radial-gradient(ellipse 240px 80px at 20% 50%, rgba(220,160,60,0.10), transparent 70%)',
      'radial-gradient(ellipse 200px 70px at 80% 60%, rgba(255,130,71,0.08), transparent 70%)',
      'radial-gradient(ellipse 260px 50px at 50% 100%, rgba(180,120,40,0.14), transparent 70%)',
    ],
  },
}

const biome = computed<BiomeStyle>(() => BIOMES[theme.value] ?? BIOMES.forest)

// ── Décor de canopée (seulement pour les biomes végétaux) ──────────────────

const canopyCircles: Array<[number, number]> = [
  [1, 1], [3, 5], [8, 1], [10, 4], [2, 9], [8, 9], [10, 10], [6, 6],
]

const showCanopy = computed(() =>
  ['forest', 'swamp', 'plains'].includes(theme.value)
)

// Pour swamp : canopée plus sombre et dense
const canopyColor = computed(() => {
  if (theme.value === 'swamp') return 'rgba(30,60,30,0.30)'
  if (theme.value === 'plains') return 'rgba(80,110,40,0.18)'
  return 'rgba(58,90,58,0.25)'
})

// ── Décor eau (beach/coastal) ──────────────────────────────────────────────

const showWater = computed(() => ['beach', 'coastal'].includes(theme.value))

// La ligne d'eau couvre le bas de la carte (1/4 inférieur)
const waterRect = computed(() => ({
  y: heightPx.value * 0.72,
  height: heightPx.value * 0.28,
}))

// Ligne de vague SVG
function wavePath(yBase: number, amplitude: number, period: number): string {
  const w = widthPx.value
  const pts: string[] = [`M 0 ${yBase}`]
  const steps = Math.ceil(w / period) + 1
  for (let i = 0; i <= steps; i++) {
    const x = i * period
    const y = yBase + (i % 2 === 0 ? -amplitude : amplitude)
    const cx = x - period / 2
    pts.push(`Q ${cx} ${y} ${x} ${yBase}`)
  }
  return pts.join(' ')
}

const wave1 = computed(() => wavePath(waterRect.value.y + 6, 4, 40))
const wave2 = computed(() => wavePath(waterRect.value.y + 14, 3, 50))

// ── Décor rochers (rocky/mountain) ────────────────────────────────────────

const showRocks = computed(() => ['rocky', 'mountain'].includes(theme.value))

// Points déterministes (coordonnées fixes, pas de PRNG)
const rockClusters: Array<{ x: number; y: number; r: number }> = [
  { x: 0.12, y: 0.15, r: 0.06 },
  { x: 0.82, y: 0.10, r: 0.05 },
  { x: 0.05, y: 0.65, r: 0.07 },
  { x: 0.88, y: 0.72, r: 0.055 },
  { x: 0.50, y: 0.08, r: 0.05 },
  { x: 0.35, y: 0.85, r: 0.06 },
  { x: 0.72, y: 0.42, r: 0.045 },
]

// ── Décor lampe/brasero (donjon/grotte) ────────────────────────────────────

const showTorches = computed(() => ['dungeon', 'cave'].includes(theme.value))

const torchPositions: Array<{ cx: number; cy: number }> = [
  { cx: 0.08, cy: 0.12 },
  { cx: 0.92, cy: 0.12 },
  { cx: 0.08, cy: 0.88 },
  { cx: 0.92, cy: 0.88 },
]

// ── Piste ──────────────────────────────────────────────────────────────────

interface TrackVisual {
  outerColor: string
  outerWidthPct: number // width as percentage of cell size (e.g. 0.6)
  innerColor: string
  innerDash: string
  innerWidthPct: number
  strokeLinecap?: 'round' | 'butt' | 'square'
}

const TRACK_VISUALS: Record<SceneTheme, TrackVisual> = {
  forest: {
    outerColor: 'rgba(247,236,208,0.08)',
    outerWidthPct: 0.75,
    innerColor: 'rgba(139,90,43,0.3)',
    innerDash: '4 6',
    innerWidthPct: 0.15,
  },
  plains: {
    outerColor: 'rgba(247,236,208,0.10)',
    outerWidthPct: 0.7,
    innerColor: 'rgba(111,217,111,0.2)',
    innerDash: '5 5',
    innerWidthPct: 0.15,
  },
  desert: {
    outerColor: 'rgba(240,199,100,0.12)',
    outerWidthPct: 0.8,
    innerColor: 'rgba(240,199,100,0.4)',
    innerDash: '10 8',
    innerWidthPct: 0.18,
  },
  dungeon: {
    outerColor: 'rgba(90,90,95,0.22)',
    outerWidthPct: 0.85,
    innerColor: 'rgba(160,160,170,0.35)',
    innerDash: '14 3', // simulates flagstone blocks
    innerWidthPct: 0.75, // wide flagstones
    strokeLinecap: 'butt',
  },
  cave: {
    outerColor: 'rgba(70,65,60,0.25)',
    outerWidthPct: 0.8,
    innerColor: 'rgba(140,130,120,0.3)',
    innerDash: '8 6',
    innerWidthPct: 0.65,
    strokeLinecap: 'round',
  },
  beach: {
    outerColor: 'rgba(79,216,192,0.10)',
    outerWidthPct: 0.75,
    innerColor: 'rgba(79,216,192,0.35)',
    innerDash: '18 4', // wooden planks
    innerWidthPct: 0.5,
    strokeLinecap: 'butt',
  },
  coastal: {
    outerColor: 'rgba(79,216,192,0.08)',
    outerWidthPct: 0.7,
    innerColor: 'rgba(247,236,208,0.25)',
    innerDash: '20 5', // wooden dock boards
    innerWidthPct: 0.45,
    strokeLinecap: 'butt',
  },
  swamp: {
    outerColor: 'rgba(40,30,20,0.35)',
    outerWidthPct: 0.8,
    innerColor: 'rgba(100,80,60,0.4)',
    innerDash: '12 8', // uneven wooden footbridge planks
    innerWidthPct: 0.55,
    strokeLinecap: 'butt',
  },
  mountain: {
    outerColor: 'rgba(100,100,105,0.18)',
    outerWidthPct: 0.7,
    innerColor: 'rgba(200,200,205,0.25)',
    innerDash: '3 9', // gravel stones
    innerWidthPct: 0.25,
    strokeLinecap: 'round',
  },
  rocky: {
    outerColor: 'rgba(110,100,90,0.18)',
    outerWidthPct: 0.75,
    innerColor: 'rgba(180,170,160,0.3)',
    innerDash: '4 8',
    innerWidthPct: 0.2,
    strokeLinecap: 'round',
  },
  city: {
    outerColor: 'rgba(120,110,100,0.2)',
    outerWidthPct: 0.9,
    innerColor: 'rgba(240,199,100,0.25)',
    innerDash: '16 4', // paved cobblestone street
    innerWidthPct: 0.8,
    strokeLinecap: 'butt',
  },
}

function pathTrack() {
  const c = props.cell
  const sceneExits = (gameStore.currentScene?.exits ?? []).filter(e => e.position)
  
  if (sceneExits.length < 2) {
    // Fallback to middle horizontal serpentine if less than 2 exits
    const trackRow = Math.max(0, Math.min(rows.value - 1, Math.floor(rows.value / 2)))
    return `M 0 ${(trackRow + 0.5) * c} Q ${3 * c} ${(trackRow - 1) * c} ${5 * c} ${trackRow * c} T ${cols.value * c} ${(trackRow + 0.5) * c}`
  }
  
  // Sort exits by column to go left-to-right (or by row if it's more vertical than horizontal)
  const sorted = [...sceneExits].sort((a, b) => (a.position?.col ?? 0) - (b.position?.col ?? 0))
  const start = sorted[0]?.position
  const end = sorted[sorted.length - 1]?.position
  
  if (!start || !end) {
    const trackRow = Math.max(0, Math.min(rows.value - 1, Math.floor(rows.value / 2)))
    return `M 0 ${(trackRow + 0.5) * c} Q ${3 * c} ${(trackRow - 1) * c} ${5 * c} ${trackRow * c} T ${cols.value * c} ${(trackRow + 0.5) * c}`
  }
  
  const x1 = (start.col + 0.5) * c
  const y1 = (start.row + 0.5) * c
  const x2 = (end.col + 0.5) * c
  const y2 = (end.row + 0.5) * c
  
  const dx = x2 - x1
  const dy = y2 - y1
  
  if (Math.abs(dx) >= Math.abs(dy)) {
    // Horizontal serpentine: S-curve via cubic bezier
    const cx1 = x1 + dx * 0.35
    const cy1 = y1 - c * 1.5
    const cx2 = x1 + dx * 0.65
    const cy2 = y2 + c * 1.5
    return `M ${x1} ${y1} C ${cx1} ${cy1} ${cx2} ${cy2} ${x2} ${y2}`
  } else {
    // Vertical serpentine
    const cy1 = y1 + dy * 0.35
    const cx1 = x1 - c * 1.5
    const cy2 = y1 + dy * 0.65
    const cx2 = x2 + c * 1.5
    return `M ${x1} ${y1} C ${cx1} ${cy1} ${cx2} ${cy2} ${x2} ${y2}`
  }
}

const showTrack = computed(() => true)
const trackVisual = computed(() => TRACK_VISUALS[theme.value] ?? TRACK_VISUALS.forest)

// ── Grille ─────────────────────────────────────────────────────────────────

const grid = computed(() => {
  const v = Array.from({ length: cols.value + 1 }, (_, i) => i * props.cell)
  const h = Array.from({ length: rows.value + 1 }, (_, i) => i * props.cell)
  return { v, h }
})

// ── Sélection ──────────────────────────────────────────────────────────────

function isSelected(id: string) { return sessionStore.selectedId === id }
function isHighlighted(id: string) { return sessionStore.highlightedIds.includes(id) }
function onClick(id: string) { sessionStore.selectEntity(id) }
</script>

<template>
  <div
    class="scene-map"
    :style="{
      width: `${widthPx}px`,
      height: `${heightPx}px`,
      background: biome.bgGradient,
    }"
  >
    <!-- ── Fond ambiance (fog) ── -->
    <div
      class="scene-map-fog"
      :style="{ backgroundImage: biome.fogColors.join(',') }"
    />

    <!-- ── Eau (beach / coastal) ── -->
    <svg
      v-if="showWater"
      class="scene-map-layer"
      :width="widthPx"
      :height="heightPx"
    >
      <!-- Zone eau pleine -->
      <rect
        :x="0"
        :y="waterRect.y"
        :width="widthPx"
        :height="waterRect.height"
        fill="rgba(30,80,120,0.35)"
      />
      <!-- Dégradé mer vers sable -->
      <defs>
        <linearGradient id="waterGrad" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="rgba(79,216,192,0.22)" />
          <stop offset="100%" stop-color="rgba(20,60,100,0.45)" />
        </linearGradient>
      </defs>
      <rect
        :x="0"
        :y="waterRect.y"
        :width="widthPx"
        :height="waterRect.height"
        fill="url(#waterGrad)"
      />
      <!-- Lignes de vagues -->
      <path
        :d="wave1"
        fill="none"
        stroke="rgba(79,216,192,0.30)"
        stroke-width="1.5"
        stroke-linecap="round"
      />
      <path
        :d="wave2"
        fill="none"
        stroke="rgba(79,216,192,0.18)"
        stroke-width="1"
        stroke-linecap="round"
        stroke-dasharray="8 6"
      />
    </svg>

    <!-- ── Canopée (forêt / marais / plaines) ── -->
    <svg
      v-if="showCanopy"
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
        :fill="canopyColor"
      />
    </svg>

    <!-- ── Rochers (rocky / montagne) ── -->
    <svg
      v-if="showRocks"
      class="scene-map-layer"
      :width="widthPx"
      :height="heightPx"
      style="opacity: 0.40"
    >
      <ellipse
        v-for="(r, i) in rockClusters"
        :key="i"
        :cx="r.x * widthPx"
        :cy="r.y * heightPx"
        :rx="r.r * widthPx * 0.9"
        :ry="r.r * heightPx * 0.55"
        fill="rgba(100,85,65,0.35)"
        stroke="rgba(160,140,100,0.18)"
        stroke-width="1"
      />
    </svg>

    <!-- ── Torches / halos (donjon / grotte) ── -->
    <svg
      v-if="showTorches"
      class="scene-map-layer"
      :width="widthPx"
      :height="heightPx"
    >
      <defs>
        <radialGradient
          v-for="(t, i) in torchPositions"
          :key="`tg${i}`"
          :id="`tg${i}`"
          :cx="t.cx"
          :cy="t.cy"
          r="0.18"
          gradientUnits="objectBoundingBox"
        >
          <stop offset="0%" :stop-color="theme === 'dungeon' ? 'rgba(255,160,60,0.28)' : 'rgba(79,216,192,0.20)'" />
          <stop offset="100%" stop-color="transparent" />
        </radialGradient>
      </defs>
      <rect
        v-for="(t, i) in torchPositions"
        :key="`tr${i}`"
        x="0" y="0"
        :width="widthPx"
        :height="heightPx"
        :fill="`url(#tg${i})`"
      />
    </svg>

    <!-- ── Piste serpentine ── -->
    <svg
      v-if="showTrack"
      class="scene-map-layer"
      :width="widthPx"
      :height="heightPx"
    >
      <path
        :d="pathTrack()"
        fill="none"
        :stroke="trackVisual.outerColor"
        :stroke-width="cell * trackVisual.outerWidthPct"
        :stroke-linecap="trackVisual.strokeLinecap ?? 'round'"
      />
      <path
        :d="pathTrack()"
        fill="none"
        :stroke="trackVisual.innerColor"
        :stroke-width="cell * trackVisual.innerWidthPct"
        :stroke-dasharray="trackVisual.innerDash"
        :stroke-linecap="trackVisual.strokeLinecap ?? 'round'"
      />
    </svg>

    <!-- ── Grille ── -->
    <svg
      class="scene-map-layer"
      :width="widthPx"
      :height="heightPx"
    >
      <line
        v-for="(x, i) in grid.v"
        :key="`v${i}`"
        :x1="x" :y1="0"
        :x2="x" :y2="heightPx"
        :stroke="biome.gridColor"
        stroke-width="1"
      />
      <line
        v-for="(y, i) in grid.h"
        :key="`h${i}`"
        :x1="0" :y1="y"
        :x2="widthPx" :y2="y"
        :stroke="biome.gridColor"
        stroke-width="1"
      />
    </svg>

    <!-- ── Coords ── -->
    <div class="scene-map-coord top-left">A1</div>
    <div class="scene-map-coord bottom-right">
      {{ String.fromCharCode(64 + cols) }}{{ rows }} · {{ cols }}×{{ rows }} m
    </div>

    <!-- ── POI tokens ── -->
    <PoiToken
      v-for="poi in pois"
      :key="poi.id"
      :poi="poi"
      :cell="cell"
      :selected="isSelected(poi.id)"
      :highlighted="isHighlighted(poi.id)"
      @click="onClick"
    />

    <!-- ── Hero tokens ── -->
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
  overflow: hidden;
  box-shadow: inset 0 0 80px rgba(0, 0, 0, 0.7), 0 6px 28px rgba(0, 0, 0, 0.5);
  flex-shrink: 0;
  transition: background 0.4s ease;
}

.scene-map-fog {
  position: absolute;
  inset: 0;
  pointer-events: none;
  animation: fog-slow-pulse 8s ease-in-out infinite alternate;
}

@keyframes fog-slow-pulse {
  0% { opacity: 0.82; transform: scale(1.0); }
  50% { opacity: 0.95; transform: scale(1.04); }
  100% { opacity: 0.78; transform: scale(0.98); }
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

.scene-map-coord.top-left  { top: 4px; left: 4px; }
.scene-map-coord.bottom-right { bottom: 4px; right: 4px; }
</style>
