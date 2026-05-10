<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import NodeMap from './NodeMap.vue'
import { findReachableNodes } from '../../utils/mapGraph'
import type { MapNode, RegionMap } from '../../types'

const props = defineProps<{
  map: RegionMap | null
  readonly?: boolean
}>()

const emit = defineEmits<{
  travel: [node: MapNode]
  openCity: [cityId: string]
}>()

const selectedId = ref<string | null>(null)
const selectedNode = computed(() =>
  props.map?.nodes.find((node) => node.id === selectedId.value)
  ?? props.map?.nodes.find((node) => node.id === props.map?.current_node_id)
  ?? props.map?.nodes[0]
  ?? null,
)
const reachableNodes = computed(() =>
  props.map ? findReachableNodes(props.map.nodes, props.map.edges, props.map.current_node_id) : [],
)
const reachableIds = computed(() => reachableNodes.value.map((node) => node.id))
const canTravel = computed(() =>
  Boolean(selectedNode.value && reachableIds.value.includes(selectedNode.value.id) && !props.readonly),
)

watch(() => props.map?.id, () => {
  selectedId.value = props.map?.current_node_id ?? props.map?.nodes[0]?.id ?? null
}, { immediate: true })

function selectNode(node: MapNode) {
  selectedId.value = node.id
  if (node.city_id) emit('openCity', node.city_id)
}
</script>

<template>
  <section class="region-map">
    <NodeMap
      :nodes="map?.nodes ?? []"
      :edges="map?.edges ?? []"
      :current-node-id="map?.current_node_id"
      :selected-node-id="selectedNode?.id"
      :background-seed="map?.background_seed"
      :reachable-node-ids="reachableIds"
      :readonly="readonly"
      @select="selectNode"
    />
    <aside class="region-map__detail">
      <div>
        <p class="rpg-eyebrow">Région</p>
        <h3>{{ selectedNode?.name ?? map?.name ?? 'Carte régionale' }}</h3>
        <p class="region-map__meta">
          {{ selectedNode?.kind ?? 'Aucun lieu connu' }}
          <span v-if="selectedNode">· {{ selectedNode.status }}</span>
        </p>
      </div>
      <p class="region-map__description">
        {{ selectedNode?.description ?? 'La géographie se dessinera au fil des voyages.' }}
      </p>
      <div class="region-map__actions">
        <button
          v-if="selectedNode?.city_id"
          type="button"
          class="region-map__button"
          @click="emit('openCity', selectedNode.city_id!)"
        >
          Ouvrir la ville
        </button>
        <button
          v-if="!readonly"
          type="button"
          class="region-map__button is-primary"
          :disabled="!canTravel"
          @click="selectedNode && emit('travel', selectedNode)"
        >
          Voyager
        </button>
      </div>
    </aside>
  </section>
</template>

<style scoped>
.region-map {
  display: grid;
  min-height: 0;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 320px);
}

.region-map__detail {
  display: flex;
  min-height: 320px;
  flex-direction: column;
  justify-content: space-between;
  gap: 18px;
  border-left: 1px solid var(--color-border);
  padding: 18px;
  background: var(--color-bg-elev);
}

.region-map__detail h3 {
  margin-top: 4px;
  font-size: 18px;
}

.region-map__meta,
.region-map__description {
  color: var(--color-text-muted);
}

.region-map__description {
  line-height: 1.5;
}

.region-map__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.region-map__button {
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  padding: 8px 12px;
  color: var(--color-parchment);
  background: var(--color-surface);
}

.region-map__button.is-primary {
  color: var(--color-bg);
  background: var(--color-gold);
  border-color: var(--color-gold);
}

.region-map__button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

@media (max-width: 860px) {
  .region-map {
    grid-template-columns: 1fr;
  }

  .region-map__detail {
    min-height: auto;
    border-left: 0;
    border-top: 1px solid var(--color-border);
  }
}
</style>
