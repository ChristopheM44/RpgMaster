<script setup lang="ts">
// Point de montage du moteur 3D : canvas WebGL + import dynamique du moteur
// (chunk séparé), ResizeObserver, pause hors écran, perte de contexte WebGL.
// Les overlays HTML (tooltip, badges, panneaux) passent par le <slot>.
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import type { GridPoint, PickResult, SceneRuntimeHandle, SceneSpec, ZoomPreset } from '../../engine3d/types'

const props = defineProps<{
  spec: SceneSpec | null
}>()

const emit = defineEmits<{
  pick: [pick: PickResult, screen: { x: number; y: number }]
  hover: [pick: PickResult | null, screen: { x: number; y: number }]
}>()

const host = ref<HTMLDivElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)
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
    runtime.value.setBrightness(brightness.value)
    if (props.spec) runtime.value.update(props.spec)
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

watch(() => props.spec, (spec) => {
  if (spec) runtime.value?.update(spec)
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

    <!-- Chips de coordonnées — parité local-map-coord. -->
    <template v-if="spec">
      <div class="scene3d-coord top-left">A1</div>
      <div class="scene3d-coord bottom-right">
        {{ String.fromCharCode(64 + spec.ground.cols) }}{{ spec.ground.rows }}
        · {{ spec.ground.cols }}×{{ spec.ground.rows }}
      </div>

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

.scene3d-coord {
  position: absolute;
  z-index: 5;
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--color-text-muted);
  background: rgba(14, 13, 20, 0.72);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 2px 5px;
  pointer-events: none;
}

.scene3d-coord.top-left {
  top: 6px;
  left: 6px;
}

.scene3d-coord.bottom-right {
  right: 6px;
  bottom: 6px;
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

.scene3d-brightness-range {
  width: 84px;
  height: 3px;
  accent-color: var(--color-ember);
  cursor: pointer;
}
</style>
