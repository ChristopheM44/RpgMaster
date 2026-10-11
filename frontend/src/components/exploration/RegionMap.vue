<script setup lang="ts">
// Carte de Région (refonte lot 5) : plein cadre sur parchemin sombre, pictos par
// type de lieu, étiquettes anti-collision, routes typées (parcourue / connue /
// rumeur), brouillard hors des lieux connus, échelle en jours de marche quand les
// trajets sont chiffrés. Molette = zoom, glisser = déplacer, « Recentrer ».
import { computed, ref, useId } from 'vue'
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
  unitsPerDay,
  visibleEdges,
  type LabelRequest,
} from './mapLayout'

const PIN_RADIUS = 15
const REVEAL_RADIUS_PX = 150

const sessionStore = useSessionStore()
const gameStore = useGameStore()
const uid = useId()

const region = computed(() => gameStore.regionMap)
const nodes = computed<MapNode[]>(() => region.value?.nodes ?? [])
const byId = computed(() => new Map(nodes.value.map((node) => [node.id, node])))
const edges = computed(() => visibleEdges(region.value?.edges ?? [], byId.value))
const currentNodeId = computed(() => region.value?.current_node_id)
const visualAsset = computed(() => region.value?.visual_asset)
const visualAssetReady = computed(() => visualAsset.value?.status === 'ready' && Boolean(visualAsset.value.url))
const visualAssetGenerating = computed(
  () => visualAsset.value?.status === 'prompt_ready' || visualAsset.value?.status === 'generating',
)

const decor = computed<MapDecor>(() =>
  resolveMapDecor(
    region.value?.decor,
    region.value?.background_seed ?? region.value?.id ?? 'region',
    'region',
    nodes.value.map((n) => `${n.id} ${n.name}`).join(' '),
  ),
)

const root = ref<HTMLElement | null>(null)
const points = computed(() => nodes.value.map((node) => node.position))
const resetKey = computed(() => region.value?.id ?? '')
const viewport = useMapViewport(root, points, resetKey)
const { width, height, view, isAdjusted } = viewport

const worldTransform = computed(() => `translate(${view.value.tx} ${view.value.ty}) scale(${view.value.scale})`)

const pins = computed(() =>
  nodes.value.map((node) => ({ node, ...project(view.value, node.position), glyph: glyphFor(node, 'region') })),
)

const edgePaths = computed(() =>
  edges.value.map((edge) => {
    const a = project(view.value, byId.value.get(edge.from)!.position)
    const b = project(view.value, byId.value.get(edge.to)!.position)
    // Légère courbe : une route n'est jamais une règle.
    const mx = (a.x + b.x) / 2 - (b.y - a.y) * 0.08
    const my = (a.y + b.y) / 2 + (b.x - a.x) * 0.08
    return { edge, d: `M ${a.x} ${a.y} Q ${mx} ${my} ${b.x} ${b.y}`, state: edgeState(edge, byId.value) }
  }),
)

/** Brouillard levé autour des lieux vus ou connus ; une rumeur reste dans la brume. */
const revealed = computed(() => pins.value.filter((pin) => pin.node.status !== 'rumored'))

const labels = computed(() => {
  const requests: (LabelRequest & { lines: string[]; node: MapNode })[] = pins.value.map((pin) => {
    const metrics = measureLabel(pin.node.short_label ?? pin.node.name, { fontPx: 11, maxWidth: 156 })
    const isHere = pin.node.id === currentNodeId.value
    return {
      id: pin.node.id,
      x: pin.x,
      y: pin.y,
      width: Math.max(metrics.width, isHere ? 92 : 0),
      height: metrics.height + (isHere ? 12 : 0),
      radius: PIN_RADIUS + 2,
      priority: STATUS_PRIORITY[pin.node.status] ?? 3,
      lines: metrics.lines,
      node: pin.node,
    }
  })
  const placed = placeLabels(requests, { width: width.value, height: height.value })
  const byRequest = new Map(requests.map((request) => [request.id, request]))
  return placed.map((label) => ({ ...label, request: byRequest.get(label.id)! }))
})

/** Barre d'échelle : 1, 2 ou 5 jours selon la place, seulement si les trajets sont chiffrés. */
const scaleBar = computed(() => {
  const units = unitsPerDay(edges.value, byId.value)
  if (!units) return null
  const perDay = units * view.value.scale
  const days = [0.5, 1, 2, 5, 10].find((d) => perDay * d >= 60) ?? 10
  const px = perDay * days
  if (px > 220) return null
  return { px, label: days === 0.5 ? '½ journée' : `${days} jour${days > 1 ? 's' : ''} de marche` }
})

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

/** Forêts : bosquets de petits conifères (spirale déterministe) plutôt que des disques. */
const trees = computed(() =>
  (decor.value.forests ?? []).flatMap((forest) => {
    const radius = forest.radius ?? 3
    const count = Math.max(3, Math.min(14, Math.round(radius * radius * 0.9)))
    return Array.from({ length: count }, (_, i) => {
      const angle = i * 2.39996
      const dist = Math.sqrt((i + 0.5) / count) * radius
      const x = forest.x + Math.cos(angle) * dist
      const y = forest.y + Math.sin(angle) * dist * 0.8
      return `${x},${y - 1.7} ${x - 0.75},${y + 0.4} ${x + 0.75},${y + 0.4}`
    })
  }),
)

/** Montagnes : versant éclairé + versant ombré (lumière venant de l'ouest). */
const mountains = computed(() =>
  (decor.value.mountains ?? []).map((mountain) => {
    const h = (mountain.height ?? 5) * 0.6
    const { x, y } = mountain
    return {
      lit: `${x},${y - h * 0.5} ${x - h * 0.85},${y + h} ${x + h * 0.85},${y + h}`,
      shade: `${x},${y - h * 0.5} ${x + h * 0.15},${y + h} ${x + h * 0.85},${y + h}`,
    }
  }),
)
</script>

<template>
  <div
    ref="root"
    class="wmap wmap--region"
    @wheel="viewport.onWheel"
    @pointerdown="viewport.onPointerDown"
    @pointermove="viewport.onPointerMove"
    @pointerup="onPointerUp"
    @pointerleave="onPointerUp"
  >
    <svg
      v-if="region && width > 0"
      class="wmap-svg"
      :width="width"
      :height="height"
      :viewBox="`0 0 ${width} ${height}`"
      role="img"
      :aria-label="`Carte de la région ${region.name}`"
    >
      <defs>
        <radialGradient :id="`${uid}-reveal`">
          <stop offset="0" stop-color="black" />
          <stop offset="0.55" stop-color="black" />
          <stop offset="1" stop-color="white" />
        </radialGradient>
        <mask :id="`${uid}-fog`" maskUnits="userSpaceOnUse" x="0" y="0" :width="width" :height="height">
          <rect x="0" y="0" :width="width" :height="height" fill="white" />
          <circle
            v-for="pin in revealed"
            :key="`reveal-${pin.node.id}`"
            :cx="pin.x"
            :cy="pin.y"
            :r="REVEAL_RADIUS_PX"
            :fill="`url(#${uid}-reveal)`"
          />
        </mask>
        <filter :id="`${uid}-grain`" x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="7" />
          <feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 0.92  0 0 0 0 0.75  0 0 0 0.06 0" />
        </filter>
      </defs>

      <!-- Monde (coordonnées 0..100) : image générée et décor sous la MÊME transformation que les lieux. -->
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
        <polygon
          v-if="decor.coastline && decor.coastline.points.length"
          class="wmap-sea"
          :points="decor.coastline.points.map((p) => `${p.x},${p.y}`).join(' ')"
        />
        <polygon v-for="(tree, i) in trees" :key="`tree-${i}`" class="wmap-tree" :points="tree" />
        <g v-for="(mountain, i) in mountains" :key="`mountain-${i}`">
          <polygon class="wmap-mountain" :points="mountain.lit" />
          <polygon class="wmap-mountain-shade" :points="mountain.shade" />
        </g>
        <path
          v-if="decor.river"
          class="wmap-river"
          :d="decor.river.path"
          :stroke-width="(decor.river.width ?? 1.5) * 0.8"
        />
        <path
          v-for="(d, i) in decor.decorative_roads ?? []"
          :key="`trail-${i}`"
          class="wmap-trail"
          :d="d"
          vector-effect="non-scaling-stroke"
        />
      </g>

      <rect class="wmap-grain" x="0" y="0" :width="width" :height="height" :filter="`url(#${uid}-grain)`" />

      <!-- Routes du graphe : type (route, sentier, fleuve…) × état (parcourue, connue, rumeur). -->
      <g class="wmap-edges">
        <template v-for="item in edgePaths" :key="item.edge.id">
          <path v-if="item.edge.kind === 'road'" class="wmap-edge-casing" :d="item.d" />
          <path class="wmap-edge" :class="[`kind-${item.edge.kind}`, `state-${item.state}`]" :d="item.d" />
        </template>
      </g>

      <rect class="wmap-fog" x="0" y="0" :width="width" :height="height" :mask="`url(#${uid}-fog)`" />

      <g
        v-for="pin in pins"
        :key="pin.node.id"
        class="wmap-node"
        :class="[
          `is-${pin.node.status}`,
          { 'is-selected': isSelected(pin.node.id), 'is-highlighted': isHighlighted(pin.node.id) },
        ]"
        :transform="`translate(${pin.x} ${pin.y})`"
        role="button"
        :aria-label="pin.node.name"
        @click.stop="select(pin.node.id)"
      >
        <circle v-if="pin.node.id === currentNodeId" class="wmap-node-pulse" :r="PIN_RADIUS + 9" />
        <circle class="wmap-node-disc" :r="PIN_RADIUS" />
        <MapGlyph :glyph="pin.glyph" :size="20" />
        <polygon
          v-if="pin.node.id === currentNodeId"
          class="wmap-here-marker"
          :points="`0,${-PIN_RADIUS - 3} -6,${-PIN_RADIUS - 13} 6,${-PIN_RADIUS - 13}`"
        />
      </g>
    </svg>

    <!-- Étiquettes (DOM, polices du design system), placées sans chevauchement. -->
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

    <div v-if="!region" class="wmap-empty">
      <span class="rpg-eyebrow">✦ Région</span>
      <p>Aucune région chargée pour cette session.</p>
    </div>

    <template v-if="region">
      <div class="wmap-title"><span class="rpg-sparkle">✦</span>{{ region.name }}</div>
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
        <span class="wmap-key is-rumored">Rumeur</span>
        <span v-if="scaleBar" class="wmap-scale">
          <i :style="{ width: `${scaleBar.px}px` }" />{{ scaleBar.label }}
        </span>
      </div>
      <svg class="wmap-compass" viewBox="-20 -20 40 40" width="40" height="40" aria-label="Nord en haut">
        <path class="wmap-compass-needle" d="M0 -15 4 0 0 3 -4 0Z" />
        <path class="wmap-compass-tail" d="M0 15 4 0 0 3 -4 0Z" />
        <text y="-17" text-anchor="middle">N</text>
      </svg>
    </template>
  </div>
</template>

<style src="./worldMap.css"></style>
