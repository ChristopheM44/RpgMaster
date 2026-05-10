<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import NodeMap from './NodeMap.vue'
import { findReachableNodes } from '../../utils/mapGraph'
import type { CityMap, MapNode } from '../../types'

const props = defineProps<{
  map: CityMap | null
  readonly?: boolean
}>()

const emit = defineEmits<{
  approach: [node: MapNode]
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

watch(() => props.map?.id, () => {
  selectedId.value = props.map?.current_node_id ?? props.map?.nodes[0]?.id ?? null
}, { immediate: true })
</script>

<template>
  <section class="city-map">
    <NodeMap
      :nodes="map?.nodes ?? []"
      :edges="map?.edges ?? []"
      :current-node-id="map?.current_node_id"
      :selected-node-id="selectedNode?.id"
      :background-seed="map?.background_seed"
      :reachable-node-ids="reachableIds"
      :readonly="readonly"
      @select="(node) => { selectedId = node.id }"
    />
    <aside class="city-map__detail">
      <div>
        <p class="rpg-eyebrow">Ville</p>
        <h3>{{ selectedNode?.name ?? map?.name ?? 'Carte urbaine' }}</h3>
        <p class="city-map__meta">
          {{ selectedNode?.kind ?? 'Aucun quartier connu' }}
          <span v-if="selectedNode">· {{ selectedNode.status }}</span>
        </p>
      </div>
      <p class="city-map__description">
        {{ selectedNode?.description ?? 'Les rues, places et repères apparaîtront avec l’exploration.' }}
      </p>
      <button
        v-if="!readonly"
        type="button"
        class="city-map__button"
        :disabled="!selectedNode"
        @click="selectedNode && emit('approach', selectedNode)"
      >
        S'approcher
      </button>
    </aside>
  </section>
</template>

<style scoped>
.city-map {
  display: grid;
  min-height: 0;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 320px);
}

.city-map__detail {
  display: flex;
  min-height: 320px;
  flex-direction: column;
  justify-content: space-between;
  gap: 18px;
  border-left: 1px solid var(--color-border);
  padding: 18px;
  background: var(--color-bg-elev);
}

.city-map__detail h3 {
  margin-top: 4px;
  font-size: 18px;
}

.city-map__meta,
.city-map__description {
  color: var(--color-text-muted);
}

.city-map__description {
  line-height: 1.5;
}

.city-map__button {
  align-self: flex-start;
  border: 1px solid var(--color-gold);
  border-radius: var(--radius-md);
  padding: 8px 12px;
  color: var(--color-bg);
  background: var(--color-gold);
}

.city-map__button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

@media (max-width: 860px) {
  .city-map {
    grid-template-columns: 1fr;
  }

  .city-map__detail {
    min-height: auto;
    border-left: 0;
    border-top: 1px solid var(--color-border);
  }
}
</style>
