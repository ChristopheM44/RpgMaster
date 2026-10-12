<script setup lang="ts">
// Plan de Ville (refonte lot 5) : quartiers en aplats, rues pavées, bâtiments
// nommés avec picto, position du groupe, sorties de ville fléchées vers le bord.
// Même cadre que la Région (plein cadre, zoom/déplacement, étiquettes sans
// chevauchement).
import { computed, ref } from 'vue'
import { useSessionStore } from '../../stores/session'
import { useGameStore } from '../../stores/game'
import { resolveMapDecor } from '../../composables/useMapDecor'
import { useMapViewport } from '../../composables/useMapViewport'
import type { MapDecor, MapNode } from '../../types'
import MapGlyph from './MapGlyph.vue'
import {
  edgeState,
  glyphFor,
  measureLabel,
  placeLabels,
  project,
  STATUS_PRIORITY,
  visibleEdges,
  type LabelRequest,
  type Point,
} from './mapLayout'

const BUILDING_HALF = 15
const SQUARE_RADIUS = 18
const DISTRICT_RADIUS = { x: 13, y: 9 } // unités carte

const sessionStore = useSessionStore()
const gameStore = useGameStore()

const city = computed(() => {
  const id = gameStore.activeCityId
  return id ? gameStore.cityMaps[id] : undefined
})
const nodes = computed<MapNode[]>(() => city.value?.nodes ?? [])
const byId = computed(() => new Map(nodes.value.map((node) => [node.id, node])))
const edges = computed(() => visibleEdges(city.value?.edges ?? [], byId.value))
const currentNodeId = computed(() => city.value?.current_node_id)
const visualAsset = computed(() => city.value?.visual_asset)
const visualAssetReady = computed(() => visualAsset.value?.status === 'ready' && Boolean(visualAsset.value.url))
const visualAssetGenerating = computed(
  () => visualAsset.value?.status === 'prompt_ready' || visualAsset.value?.status === 'generating',
)

const decor = computed<MapDecor>(() =>
  resolveMapDecor(city.value?.decor, city.value?.background_seed ?? city.value?.id ?? 'city', 'city'),
)

const root = ref<HTMLElement | null>(null)
const points = computed(() => nodes.value.map((node) => node.position))
const resetKey = computed(() => city.value?.id ?? '')
const viewport = useMapViewport(root, points, resetKey, { padding: 90, minSpan: 36 })
const { width, height, view, isAdjusted } = viewport

const worldTransform = computed(() => `translate(${view.value.tx} ${view.value.ty}) scale(${view.value.scale})`)

const districts = computed(() => nodes.value.filter((node) => node.kind === 'district'))

const places = computed(() =>
  nodes.value.map((node) => ({
    node,
    ...project(view.value, node.position),
    glyph: glyphFor(node, 'city'),
    shape: node.kind === 'square' ? 'square' : node.kind === 'district' ? 'district' : 'building',
  })),
)

const streets = computed(() =>
  edges.value.map((edge) => {
    const a = project(view.value, byId.value.get(edge.from)!.position)
    const b = project(view.value, byId.value.get(edge.to)!.position)
    return { edge, d: `M ${a.x} ${a.y} L ${b.x} ${b.y}`, state: edgeState(edge, byId.value) }
  }),
)

/** Sortie de ville : flèche de la porte vers le bord du cadre le plus proche de sa direction. */
const exits = computed(() => {
  if (!nodes.value.length || width.value <= 0) return []
  const center: Point = project(view.value, {
    x: nodes.value.reduce((sum, node) => sum + node.position.x, 0) / nodes.value.length,
    y: nodes.value.reduce((sum, node) => sum + node.position.y, 0) / nodes.value.length,
  })
  return places.value
    .filter((place) => place.node.kind === 'gate')
    .map((place) => {
      let dx = place.x - center.x
      let dy = place.y - center.y
      const length = Math.hypot(dx, dy) || 1
      dx /= length
      dy /= length
      if (length < 2) {
        dx = 1
        dy = 0
      }
      const margin = 36
      const tx = dx > 0 ? (width.value - margin - place.x) / dx : dx < 0 ? (margin - place.x) / dx : Infinity
      const ty = dy > 0 ? (height.value - margin - place.y) / dy : dy < 0 ? (margin - place.y) / dy : Infinity
      const reach = Math.max(BUILDING_HALF + 24, Math.min(tx, ty))
      const start = { x: place.x + dx * (BUILDING_HALF + 6), y: place.y + dy * (BUILDING_HALF + 6) }
      const end = { x: place.x + dx * reach, y: place.y + dy * reach }
      const angle = (Math.atan2(dy, dx) * 180) / Math.PI
      return { id: place.node.id, start, end, angle }
    })
})

const labels = computed(() => {
  const requests: (LabelRequest & { lines: string[]; node: MapNode })[] = places.value.map((place) => {
    const metrics = measureLabel(place.node.short_label ?? place.node.name, { fontPx: 11, maxWidth: 150 })
    const isHere = place.node.id === currentNodeId.value
    return {
      id: place.node.id,
      x: place.x,
      y: place.y,
      width: Math.max(metrics.width, isHere ? 92 : 0),
      height: metrics.height + (isHere ? 12 : 0),
      radius: place.shape === 'square' ? SQUARE_RADIUS + 2 : BUILDING_HALF + 4,
      priority: STATUS_PRIORITY[place.node.status] ?? 3,
      lines: metrics.lines,
      node: place.node,
    }
  })
  const placed = placeLabels(requests, { width: width.value, height: height.value })
  const byRequest = new Map(requests.map((request) => [request.id, request]))
  return placed.map((label) => ({ ...label, request: byRequest.get(label.id)! }))
})

const party = computed(() => places.value.find((place) => place.node.id === currentNodeId.value) ?? null)

let suppressClick = false
function onPointerUp(): void {
  suppressClick = viewport.onPointerUp()
}
function select(id: string): void {
  if (suppressClick) {
    suppressClick = false
    return
  }
  sessionStore.selectEntity(id)
}

function isSelected(id: string): boolean {
  return sessionStore.selectedId === id
}
function isHighlighted(id: string): boolean {
  return sessionStore.highlightedIds.includes(id)
}
</script>

<template>
  <div
    ref="root"
    class="wmap wmap--city"
    @wheel="viewport.onWheel"
    @pointerdown="viewport.onPointerDown"
    @pointermove="viewport.onPointerMove"
    @pointerup="onPointerUp"
    @pointerleave="onPointerUp"
  >
    <svg
      v-if="city && width > 0"
      class="wmap-svg"
      :width="width"
      :height="height"
      :viewBox="`0 0 ${width} ${height}`"
      role="img"
      :aria-label="`Plan de ${city.name}`"
    >
      <g :transform="worldTransform">
        <image
          v-if="visualAssetReady"
          :href="visualAsset?.url"
          x="0"
          y="0"
          width="100"
          height="100"
          preserveAspectRatio="none"
          class="wmap-asset"
        />
        <circle
          v-for="(forest, i) in decor.forests ?? []"
          :key="`forest-${i}`"
          class="wmap-forest"
          :cx="forest.x"
          :cy="forest.y"
          :r="forest.radius ?? 3"
        />
        <path v-if="decor.river" class="wmap-river" :d="decor.river.path" :stroke-width="(decor.river.width ?? 1.5) * 0.8" />
        <!-- Quartiers : aplats sous les rues. -->
        <ellipse
          v-for="district in districts"
          :key="`district-${district.id}`"
          class="wmap-district"
          :class="`is-${district.status}`"
          :cx="district.position.x"
          :cy="district.position.y"
          :rx="DISTRICT_RADIUS.x"
          :ry="DISTRICT_RADIUS.y"
          vector-effect="non-scaling-stroke"
        />
      </g>

      <!-- Rues : bordure sombre, chaussée, axe pointillé. -->
      <g class="wmap-streets">
        <path
          v-for="item in streets"
          :key="`casing-${item.edge.id}`"
          class="wmap-street-casing"
          :class="`kind-${item.edge.kind}`"
          :d="item.d"
        />
        <template v-for="item in streets" :key="item.edge.id">
          <path class="wmap-street" :class="[`kind-${item.edge.kind}`, `state-${item.state}`]" :d="item.d" />
          <path v-if="item.edge.kind !== 'alley'" class="wmap-street-dash" :d="item.d" />
        </template>
      </g>

      <!-- Sorties de ville : flèche vers le bord, vers la région. -->
      <g v-for="exit in exits" :key="`exit-${exit.id}`">
        <path class="wmap-exit-arrow" :d="`M ${exit.start.x} ${exit.start.y} L ${exit.end.x} ${exit.end.y}`" />
        <polygon
          class="wmap-exit-head"
          points="0,0 -11,-6 -11,6"
          :transform="`translate(${exit.end.x} ${exit.end.y}) rotate(${exit.angle})`"
        />
      </g>

      <g
        v-for="place in places"
        :key="place.node.id"
        class="wmap-node"
        :class="[
          `is-${place.node.status}`,
          { 'is-selected': isSelected(place.node.id), 'is-highlighted': isHighlighted(place.node.id) },
        ]"
        :transform="`translate(${place.x} ${place.y})`"
        role="button"
        :aria-label="place.node.name"
        @click.stop="select(place.node.id)"
      >
        <circle v-if="place.shape === 'square'" class="wmap-building" :r="SQUARE_RADIUS" />
        <circle v-else-if="place.shape === 'district'" class="wmap-node-disc" :r="BUILDING_HALF - 2" />
        <rect
          v-else
          class="wmap-building"
          :x="-BUILDING_HALF"
          :y="-BUILDING_HALF"
          :width="BUILDING_HALF * 2"
          :height="BUILDING_HALF * 2"
          rx="5"
        />
        <MapGlyph :glyph="place.glyph" :size="place.shape === 'district' ? 15 : 18" />
      </g>

      <!-- Position du groupe : pion doré au-dessus du lieu courant. -->
      <g v-if="party" :transform="`translate(${party.x + BUILDING_HALF + 4} ${party.y - BUILDING_HALF - 6})`">
        <path class="wmap-party" d="M0 -14a4.5 4.5 0 1 1 0.01 0Zm-7 16c0-6 3-9 7-9s7 3 7 9Z" />
      </g>
    </svg>

    <div
      v-for="label in labels"
      :key="`label-${label.id}`"
      class="wmap-label"
      :class="[`is-${label.request.node.status}`, { 'is-selected': isSelected(label.id) }]"
      :style="{ left: `${label.left}px`, top: `${label.top}px`, width: `${label.width}px` }"
      :title="label.request.node.name"
    >
      <span v-if="label.id === currentNodeId" class="wmap-label-kicker">Vous êtes ici</span>
      <span v-for="(line, i) in label.request.lines" :key="i" class="wmap-label-line">{{ line }}</span>
    </div>

    <div v-if="!city" class="wmap-empty">
      <span class="rpg-eyebrow">✦ Ville</span>
      <p>Aucune carte de ville chargée pour cette session.</p>
    </div>

    <template v-if="city">
      <div class="wmap-title"><span class="rpg-sparkle">✦</span>{{ city.name }}</div>
      <div class="wmap-tools">
        <div v-if="visualAssetGenerating" class="wmap-badge">
          <span class="wmap-spinner" />{{ visualAsset?.status === 'generating' ? 'Génération…' : 'En attente…' }}
        </div>
        <button v-if="isAdjusted" type="button" class="wmap-tool" @click="viewport.recenter()">◎ Recentrer</button>
      </div>
      <div class="wmap-legend">
        <span class="wmap-key is-current">Vous</span>
        <span class="wmap-key is-visited">Visité</span>
        <span class="wmap-key is-known">Connu</span>
        <span v-if="exits.length" class="wmap-key-exit">⇢ Sortie de ville</span>
      </div>
    </template>
  </div>
</template>

<style src="./worldMap.css"></style>
