<script setup lang="ts">
// Point de montage du moteur 3D : canvas WebGL + import dynamique du moteur
// (chunk séparé), ResizeObserver, pause hors écran, perte de contexte WebGL.
// Les overlays HTML (tooltip, badges, panneaux) passent par le <slot>.
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import type {
  ArrivalSpec,
  GridPoint,
  PickResult,
  SceneRuntimeHandle,
  SceneSpec,
  ZoomPreset,
} from '../../engine3d/types'
import { chebyshevLine } from '../../engine3d/utils/gridMath'

const props = defineProps<{
  spec: SceneSpec | null
}>()

const emit = defineEmits<{
  pick: [pick: PickResult, screen: { x: number; y: number }]
  hover: [pick: PickResult | null, screen: { x: number; y: number }]
}>()

const host = ref<HTMLDivElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)
const labels = ref<HTMLDivElement | null>(null)
const runtime = shallowRef<SceneRuntimeHandle | null>(null)
const loading = ref(true)

// Luminosité réglable par le joueur (exposition + plancher ambiant), persistée.
const BRIGHTNESS_KEY = 'rpg-scene-brightness'
function loadBrightness(): number {
  try {
    const raw = Number(localStorage.getItem(BRIGHTNESS_KEY))
    return Number.isFinite(raw) && raw >= 0.5 && raw <= 2 ? raw : 1
  } catch {
    return 1 // localStorage indisponible (SSR/tests)
  }
}
const brightness = ref(loadBrightness())

let resizeObserver: ResizeObserver | null = null
let intersectionObserver: IntersectionObserver | null = null
let disposed = false

async function boot(): Promise<void> {
  if (!canvas.value || disposed) return
  try {
    const { createSceneRuntime } = await import('../../engine3d')
    if (disposed || !canvas.value) return
    runtime.value = createSceneRuntime(canvas.value, {
      onClick: (pick, screen) => emit('pick', pick, screen),
      onHover: (pick, screen) => emit('hover', pick, screen),
    })
    loading.value = false
    runtime.value.attachLabels?.(labels.value)
    runtime.value.setBrightness(brightness.value)
    if (props.spec) applySpec(props.spec)
    runtime.value.resize()
  } catch (error) {
    // WebGL indisponible (vieux GPU, jsdom…) : on reste sur l'écran d'attente.
    console.warn('[Scene3DCanvas] init WebGL impossible', error)
  }
}

onMounted(() => {
  void boot()

  if (host.value && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => runtime.value?.resize())
    resizeObserver.observe(host.value)
  }
  if (host.value && typeof IntersectionObserver !== 'undefined') {
    intersectionObserver = new IntersectionObserver((entries) => {
      runtime.value?.setRunning(entries.some((entry) => entry.isIntersecting))
    })
    intersectionObserver.observe(host.value)
  }
  canvas.value?.addEventListener('webglcontextlost', onContextLost)
})

function onContextLost(event: Event): void {
  // Rebuild complet au retour de contexte : plus sûr que la restauration fine.
  event.preventDefault()
  runtime.value?.dispose()
  runtime.value = null
  loading.value = true
  setTimeout(() => {
    if (!disposed) void boot()
  }, 250)
}

// ─── Transitions de scène ────────────────────────────────────────────────────
// Changement de scene_id : le groupe marche vers la sortie empruntée pendant un
// travelling, fondu au noir, reconstruction, puis la caméra part de l'accès
// d'arrivée et recule (continuité posée par le backend : spec.arrival).
const FADE_MS = 260
const fading = ref(false)
const arrivalBanner = ref<ArrivalSpec | null>(null)
let appliedSceneId: string | null = null
let appliedSpec: SceneSpec | null = null
let transitioning = false
let queuedSpec: SceneSpec | null = null
let bannerTimer: ReturnType<typeof setTimeout> | null = null

function prefersReducedMotion(): boolean {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    return false
  }
}

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

function applySpec(spec: SceneSpec): void {
  const rt = runtime.value
  if (!rt) return
  if (transitioning) {
    queuedSpec = spec
    return
  }
  const sceneId = spec.ground.sceneId
  if (appliedSceneId !== null && sceneId !== appliedSceneId) {
    void runTransition(rt, spec)
    return
  }
  appliedSceneId = sceneId
  appliedSpec = spec
  rt.update(spec)
}

async function runTransition(rt: SceneRuntimeHandle, spec: SceneSpec): Promise<void> {
  transitioning = true
  const reduced = prefersReducedMotion()
  const previous = appliedSpec
  const viaId = spec.arrival?.viaExitId
  const via = viaId ? previous?.tokens.find((token) => token.id === viaId) : undefined
  if (!reduced && previous && via && rt.focusCell) {
    for (const hero of previous.tokens.filter((token) => token.kind === 'hero')) {
      rt.moveToken(hero.id, chebyshevLine({ col: hero.col, row: hero.row }, { col: via.col, row: via.row }))
    }
    // Garde-fou : la boucle rAF est en pause hors écran, la promesse ne se résoudrait pas.
    await Promise.race([rt.focusCell(via.col, via.row, 0.9), wait(1400)])
  }
  fading.value = true
  await wait(FADE_MS)
  if (disposed || runtime.value !== rt) {
    transitioning = false
    return
  }
  appliedSceneId = spec.ground.sceneId
  appliedSpec = spec
  rt.update(spec)
  if (spec.arrival && !reduced) rt.arriveAt?.(spec.arrival.col, spec.arrival.row, 1.0)
  fading.value = false
  showArrivalBanner(spec.arrival ?? null)
  await wait(FADE_MS)
  transitioning = false
  if (queuedSpec) {
    const next = queuedSpec
    queuedSpec = null
    applySpec(next)
  }
}

function showArrivalBanner(arrival: ArrivalSpec | null): void {
  if (bannerTimer) clearTimeout(bannerTimer)
  arrivalBanner.value = arrival
  if (arrival) bannerTimer = setTimeout(() => { arrivalBanner.value = null }, 4500)
}

const ARRIVAL_DIRECTION: Record<ArrivalSpec['verticalDirection'], { icon: string; text: string }> = {
  up: { icon: '↑', text: "Au pied d'un escalier qui remonte d'où vous venez" },
  down: { icon: '↓', text: "En haut d'un escalier qui redescend d'où vous venez" },
  level: { icon: '↩', text: 'Le chemin par lequel vous êtes arrivés' },
}

watch(() => props.spec, (spec) => {
  if (spec) applySpec(spec)
})

watch(brightness, (value) => {
  runtime.value?.setBrightness(value)
  try {
    localStorage.setItem(BRIGHTNESS_KEY, String(value))
  } catch {
    /* localStorage indisponible (SSR/tests) */
  }
})

onBeforeUnmount(() => {
  disposed = true
  if (bannerTimer) clearTimeout(bannerTimer)
  canvas.value?.removeEventListener('webglcontextlost', onContextLost)
  resizeObserver?.disconnect()
  intersectionObserver?.disconnect()
  runtime.value?.dispose()
  runtime.value = null
})

function moveToken(id: string, path: GridPoint[]): void {
  runtime.value?.moveToken(id, path)
}

function projectToken(id: string): { x: number; y: number } | null {
  return runtime.value?.projectToken(id) ?? null
}

function projectCell(col: number, row: number): { x: number; y: number } | null {
  return runtime.value?.projectCell(col, row) ?? null
}

function setZoomPreset(preset: ZoomPreset): void {
  runtime.value?.setZoomPreset(preset)
}

defineExpose({ moveToken, projectToken, projectCell, setZoomPreset })
</script>

<template>
  <div ref="host" class="scene3d-frame">
    <canvas ref="canvas" class="scene3d-canvas" data-testid="scene3d-canvas" />

    <div v-if="loading" class="scene3d-loading">
      <span class="scene3d-loading-spinner" />Préparation de la scène…
    </div>

    <!-- Étiquettes DOM projetées par le moteur (noms, repères, bannières de sortie). -->
    <div ref="labels" class="scene3d-labels" aria-live="off" />

    <template v-if="spec">
      <!-- Réglage de luminosité de la scène (exposition). -->
      <label class="scene3d-brightness" title="Luminosité de la scène">
        <span class="scene3d-brightness-icon" aria-hidden="true">☀</span>
        <input
          v-model.number="brightness"
          type="range"
          min="0.5"
          max="2"
          step="0.05"
          class="scene3d-brightness-range"
          aria-label="Luminosité de la scène"
        />
      </label>
    </template>

    <!-- Bandeau d'arrivée (transition de scène) — teal = accès d'arrivée. -->
    <Transition name="scene3d-arrival">
      <div v-if="arrivalBanner" class="scene3d-arrival" role="status">
        <span class="scene3d-arrival-dir" aria-hidden="true">
          {{ ARRIVAL_DIRECTION[arrivalBanner.verticalDirection].icon }}
        </span>
        <span class="scene3d-arrival-text">
          <span class="scene3d-arrival-kicker">Arrivée · {{ arrivalBanner.label }}</span>
          <span>{{ ARRIVAL_DIRECTION[arrivalBanner.verticalDirection].text }}</span>
        </span>
      </div>
    </Transition>

    <div class="scene3d-fade" :class="{ active: fading }" aria-hidden="true" />

    <slot />
  </div>
</template>

<style scoped>
.scene3d-frame {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 220px;
  border: 1px solid var(--color-border-strong);
  border-radius: 10px;
  overflow: hidden;
  background: var(--color-bg);
  box-shadow: inset 0 0 80px rgba(0, 0, 0, 0.55), 0 6px 28px rgba(0, 0, 0, 0.45);
}

.scene3d-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
  touch-action: none;
}

.scene3d-loading {
  position: absolute;
  inset: 0;
  z-index: 4;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--color-text-muted);
  font: 500 11px/1 var(--font-display);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  background: var(--color-bg);
  pointer-events: none;
}

.scene3d-loading-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-ember);
  border-radius: 50%;
  animation: scene3d-spin 0.8s linear infinite;
}

@keyframes scene3d-spin {
  to { transform: rotate(360deg); }
}

.scene3d-labels {
  position: absolute;
  inset: 0;
  z-index: 3;
  overflow: hidden;
  pointer-events: none;
}

.scene3d-brightness {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 6;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 9px 3px 8px;
  background: rgba(14, 13, 20, 0.72);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  pointer-events: auto;
  opacity: 0.55;
  transition: opacity 120ms ease;
}

.scene3d-brightness:hover {
  opacity: 1;
}

.scene3d-brightness-icon {
  font-size: 11px;
  line-height: 1;
  color: var(--color-gold);
}

.scene3d-fade {
  position: absolute;
  inset: 0;
  z-index: 7;
  background: var(--color-bg);
  opacity: 0;
  pointer-events: none;
  transition: opacity 260ms ease;
}

.scene3d-fade.active {
  opacity: 1;
}

.scene3d-arrival {
  position: absolute;
  left: 50%;
  bottom: 14px;
  z-index: 8;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: calc(100% - 32px);
  padding: 8px 14px 8px 9px;
  background: rgba(14, 13, 20, 0.9);
  border: 1px solid var(--color-border-strong);
  border-left: 3px solid var(--color-teal);
  border-radius: 8px;
  color: var(--color-parchment);
  font: 400 13px/1.35 var(--font-serif);
  pointer-events: none;
}

.scene3d-arrival-dir {
  display: grid;
  place-items: center;
  flex: none;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  background: var(--color-teal);
  color: var(--color-bg);
  font: 700 15px/1 var(--font-body);
}

.scene3d-arrival-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.scene3d-arrival-kicker {
  font: 700 10px/1.4 var(--font-display);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--color-teal);
}

.scene3d-arrival-enter-active,
.scene3d-arrival-leave-active {
  transition: opacity 200ms ease, transform 200ms ease;
}

.scene3d-arrival-enter-from,
.scene3d-arrival-leave-to {
  opacity: 0;
  transform: translate(-50%, 8px);
}

@media (prefers-reduced-motion: reduce) {
  .scene3d-fade,
  .scene3d-arrival-enter-active,
  .scene3d-arrival-leave-active {
    transition: none;
  }
}

.scene3d-brightness-range {
  width: 84px;
  height: 3px;
  accent-color: var(--color-ember);
  cursor: pointer;
}
</style>

<!--
  Vocabulaire d'indicateurs (lot 3) — styles NON scopés : les étiquettes sont
  créées par le moteur (engine3d/layers/LabelLayer.ts), hors du rendu Vue.
  or = vous / décisions · arcane = compagnon IA · teal = PNJ, allié, arrivée ·
  sang = ennemi · ember = repère à examiner.
-->
<style>
.e3d-label {
  position: absolute;
  left: 0;
  top: 0;
  white-space: nowrap;
  will-change: transform;
  pointer-events: none;
}

.e3d-plate {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 2px 7px 3px;
  border-radius: 5px;
  background: rgba(14, 13, 20, 0.66);
  border: 1px solid var(--color-border);
  font: 700 10px/1.2 var(--font-display);
  letter-spacing: 0.08em;
  color: var(--color-parchment);
}

.e3d-plate.e3d-role-you { color: var(--color-gold); border-color: rgba(240, 199, 100, 0.45); }
.e3d-plate.e3d-role-ai { color: var(--color-arcane); }
.e3d-plate.e3d-role-ally,
.e3d-plate.e3d-role-npc { color: var(--color-teal); }
.e3d-plate.e3d-role-enemy { color: var(--color-blood); border-color: rgba(232, 69, 69, 0.4); }
.e3d-plate.is-active { box-shadow: 0 0 0 1px var(--color-gold), 0 0 12px rgba(240, 199, 100, 0.35); }
.e3d-plate.is-defeated { opacity: 0.5; text-decoration: line-through; }

.e3d-plate-hp {
  width: 40px;
  height: 3px;
  border-radius: 2px;
  background: rgba(0, 0, 0, 0.65);
  overflow: hidden;
}

.e3d-plate-hp i { display: block; height: 100%; }
.e3d-plate-hp i.is-ok { background: var(--color-green); }
.e3d-plate-hp i.is-hurt { background: var(--color-gold); }
.e3d-plate-hp i.is-critical { background: var(--color-blood); }

.e3d-pin {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 2px 7px;
  border-radius: 5px;
  background: rgba(14, 13, 20, 0.66);
  border: 1px solid rgba(255, 130, 71, 0.4);
  font: 600 11px/1.3 var(--font-body);
  color: var(--color-parchment);
}

.e3d-pin-glyph { color: var(--color-ember); }
.e3d-poi-loot .e3d-pin-glyph { color: var(--color-gold); }
.e3d-poi-cover .e3d-pin-glyph { color: var(--color-teal); }

.e3d-banner {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 4px 10px 4px 5px;
  border-radius: 7px;
  background: rgba(14, 13, 20, 0.86);
  border: 1px solid rgba(240, 199, 100, 0.55);
  box-shadow: 0 6px 18px -6px rgba(0, 0, 0, 0.8);
  color: var(--color-parchment);
  font: 400 12px/1.15 var(--font-serif);
  text-align: left;
  cursor: pointer;
  pointer-events: auto;
  transition: border-color 120ms ease, background 120ms ease;
}

.e3d-banner:hover,
.e3d-banner:focus-visible,
.e3d-banner.is-selected,
.e3d-banner.is-highlighted {
  border-color: var(--color-gold);
  background: rgba(42, 38, 64, 0.95);
  outline: none;
}

.e3d-banner-dir {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 5px;
  background: linear-gradient(135deg, var(--color-ember), var(--color-gold));
  color: var(--color-bg);
  font: 700 14px/1 var(--font-body);
}

.e3d-banner-text {
  display: flex;
  flex-direction: column;
}

.e3d-banner-text b {
  font: 700 9px/1.3 var(--font-display);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--color-gold);
}

.e3d-banner.is-arrival { border-color: rgba(79, 216, 192, 0.55); }
.e3d-banner.is-arrival .e3d-banner-dir { background: var(--color-teal); }
.e3d-banner.is-arrival .e3d-banner-text b { color: var(--color-teal); }
.e3d-banner.is-inactive { opacity: 0.6; }

.e3d-plate.is-selected,
.e3d-pin.is-selected { border-color: var(--color-gold); }
.e3d-plate.is-highlighted,
.e3d-pin.is-highlighted { border-color: var(--color-ember); }
</style>
