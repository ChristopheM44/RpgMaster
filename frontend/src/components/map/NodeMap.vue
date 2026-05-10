<script setup lang="ts">
import { computed } from 'vue'
import MapBackground from './MapBackground.vue'
import MapNodeMarker from './MapNodeMarker.vue'
import type { MapEdge, MapNode } from '../../types'

const props = withDefaults(defineProps<{
  nodes: MapNode[]
  edges: MapEdge[]
  currentNodeId?: string | null
  selectedNodeId?: string | null
  backgroundSeed?: string | null
  reachableNodeIds?: string[]
  readonly?: boolean
}>(), {
  currentNodeId: null,
  selectedNodeId: null,
  backgroundSeed: null,
  reachableNodeIds: () => [],
  readonly: false,
})

const emit = defineEmits<{
  select: [node: MapNode]
}>()

const nodeById = computed(() => new Map(props.nodes.map((node) => [node.id, node])))
const visibleEdges = computed(() =>
  props.edges
    .filter((edge) => !edge.hidden)
    .map((edge) => ({
      ...edge,
      fromNode: nodeById.value.get(edge.from),
      toNode: nodeById.value.get(edge.to),
    }))
    .filter((edge) => edge.fromNode && edge.toNode),
)
const reachableSet = computed(() => new Set(props.reachableNodeIds))
</script>

<template>
  <div class="node-map">
    <MapBackground :seed="backgroundSeed" />
    <svg class="node-map__edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <path
        v-for="edge in visibleEdges"
        :key="edge.id"
        class="node-map__edge"
        :class="`is-${edge.kind}`"
        :d="`M ${edge.fromNode!.position.x} ${edge.fromNode!.position.y} L ${edge.toNode!.position.x} ${edge.toNode!.position.y}`"
      />
    </svg>
    <button
      v-for="node in nodes"
      :key="node.id"
      class="node-map__node"
      type="button"
      :aria-label="node.name"
      :style="{ left: `${node.position.x}%`, top: `${node.position.y}%` }"
      @click="emit('select', node)"
    >
      <MapNodeMarker
        :node="{ ...node, status: node.id === currentNodeId ? 'current' : node.status }"
        :selected="node.id === selectedNodeId"
        :reachable="reachableSet.has(node.id)"
      />
      <span class="node-map__label">{{ node.short_label || node.name }}</span>
    </button>
    <p v-if="nodes.length === 0" class="node-map__empty">
      Aucune carte connue.
    </p>
  </div>
</template>

<style scoped>
.node-map {
  position: relative;
  min-height: 320px;
  overflow: hidden;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-elev);
}

.node-map__edges {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.node-map__edge {
  fill: none;
  stroke: var(--color-border-strong);
  stroke-width: 0.85;
  stroke-linecap: round;
  opacity: 0.85;
}

.node-map__edge.is-river,
.node-map__edge.is-sea_route {
  stroke: var(--color-teal);
  stroke-dasharray: 2 2;
}

.node-map__edge.is-secret,
.node-map__edge.is-alley {
  stroke: var(--color-arcane);
  stroke-dasharray: 1 2;
}

.node-map__node {
  position: absolute;
  display: inline-flex;
  min-width: 92px;
  max-width: 130px;
  transform: translate(-50%, -50%);
  flex-direction: column;
  align-items: center;
  gap: 5px;
  border: 0;
  background: transparent;
  color: var(--color-parchment);
  cursor: pointer;
}

.node-map__node:focus-visible {
  outline: 2px solid var(--color-gold);
  outline-offset: 3px;
  border-radius: var(--radius-md);
}

.node-map__label {
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  text-align: center;
  font-size: 11px;
  line-height: 1.2;
  color: var(--color-parchment-dark);
  text-shadow: 0 1px 2px var(--color-bg);
}

.node-map__empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: var(--color-text-muted);
}
</style>
