/**
 * useMapViewport — cadrage plein cadre des cartes Région / Ville (refonte lot 5).
 *
 * Mesure le conteneur (ResizeObserver), cadre automatiquement les lieux sans
 * déformation (`fitViewport`), puis laisse le joueur zoomer (molette) et déplacer
 * (glisser). `recenter()` revient au cadrage automatique ; un changement de carte
 * (`resetKey`) aussi.
 */

import { computed, onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'
import { fitViewport, zoomAt, type Point, type Viewport } from '../components/exploration/mapLayout'

const ZOOM_STEP = 1.15
const DRAG_THRESHOLD_PX = 4

export function useMapViewport(
  root: Ref<HTMLElement | null>,
  points: Ref<Point[]>,
  resetKey: Ref<string>,
  options: { padding?: number; minSpan?: number } = {},
) {
  const width = ref(0)
  const height = ref(0)
  const userView = ref<Viewport | null>(null)
  let observer: ResizeObserver | null = null
  let drag: { x: number; y: number; view: Viewport; moved: boolean } | null = null

  const autoView = computed(() => fitViewport(points.value, width.value, height.value, options))
  const view = computed(() => userView.value ?? autoView.value)
  const isAdjusted = computed(() => userView.value !== null)

  function measure(): void {
    const el = root.value
    if (!el) return
    width.value = el.clientWidth
    height.value = el.clientHeight
  }

  onMounted(() => {
    measure()
    if (typeof ResizeObserver !== 'undefined' && root.value) {
      observer = new ResizeObserver(measure)
      observer.observe(root.value)
    }
  })
  onBeforeUnmount(() => observer?.disconnect())

  watch(resetKey, () => {
    userView.value = null
  })

  function bounds(): { min: number; max: number } {
    const base = autoView.value.scale
    return { min: base * 0.6, max: base * 4 }
  }

  function local(event: { clientX: number; clientY: number }): Point {
    const rect = root.value?.getBoundingClientRect()
    return { x: event.clientX - (rect?.left ?? 0), y: event.clientY - (rect?.top ?? 0) }
  }

  function onWheel(event: WheelEvent): void {
    event.preventDefault()
    const factor = event.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP
    userView.value = zoomAt(view.value, factor, local(event), bounds())
  }

  function onPointerDown(event: PointerEvent): void {
    if (event.button !== 0) return
    drag = { ...local(event), view: view.value, moved: false }
  }

  function onPointerMove(event: PointerEvent): void {
    if (!drag) return
    const point = local(event)
    const dx = point.x - drag.x
    const dy = point.y - drag.y
    if (!drag.moved && Math.hypot(dx, dy) < DRAG_THRESHOLD_PX) return
    drag.moved = true
    userView.value = { scale: drag.view.scale, tx: drag.view.tx + dx, ty: drag.view.ty + dy }
  }

  /** true si le geste était un glisser (le clic qui suit ne doit pas sélectionner). */
  function onPointerUp(): boolean {
    const moved = drag?.moved ?? false
    drag = null
    return moved
  }

  function recenter(): void {
    userView.value = null
  }

  return { width, height, view, isAdjusted, onWheel, onPointerDown, onPointerMove, onPointerUp, recenter }
}
