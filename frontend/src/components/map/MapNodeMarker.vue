<script setup lang="ts">
import { computed } from 'vue'
import RpgMapIcon from '../common/RpgMapIcon.vue'
import type { MapNode, NodeStatus } from '../../types'
import type { RpgMapIconId } from '../../icons/rpgMapIcons'

const props = defineProps<{
  node: MapNode
  selected?: boolean
  reachable?: boolean
}>()

const statusSymbol: Record<NodeStatus, string> = {
  visited: '✓',
  known: '○',
  current: '✦',
  rumored: '?',
}

const iconId = computed<RpgMapIconId>(() => {
  if (props.node.icon) return props.node.icon as RpgMapIconId
  if (props.node.kind === 'settlement') return 'region-settlement'
  if (props.node.kind === 'landmark') return 'region-landmark'
  if (props.node.kind === 'dungeon') return 'region-dungeon'
  if (props.node.kind === 'crossroads') return 'region-crossroads'
  if (props.node.kind === 'ruin') return 'ruins'
  if (props.node.kind === 'gate') return 'door'
  if (props.node.kind === 'temple') return 'region-landmark'
  if (props.node.kind === 'tavern' || props.node.kind === 'shop') return 'poi'
  return 'unknown-zone'
})
</script>

<template>
  <span
    class="map-node-marker"
    :class="[
      `is-${node.status}`,
      { 'is-selected': selected, 'is-reachable': reachable },
    ]"
  >
    <span class="map-node-marker__icon">
      <RpgMapIcon :icon-id="iconId" :size="20" decorative />
    </span>
    <span class="map-node-marker__status">{{ statusSymbol[node.status] }}</span>
  </span>
</template>

<style scoped>
.map-node-marker {
  position: relative;
  display: inline-flex;
  width: 36px;
  height: 36px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  border: 1px solid var(--color-border-strong);
  background: color-mix(in srgb, var(--color-bg-elev) 86%, transparent);
  box-shadow: 0 6px 18px color-mix(in srgb, var(--color-bg) 55%, transparent);
}

.map-node-marker__icon {
  display: inline-flex;
}

.map-node-marker__status {
  position: absolute;
  right: -4px;
  bottom: -4px;
  display: inline-flex;
  width: 18px;
  height: 18px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: var(--color-bg);
  border: 1px solid var(--color-border-strong);
  color: var(--color-gold);
  font-size: 11px;
  line-height: 1;
}

.map-node-marker.is-current {
  border-color: var(--color-gold);
  animation: map-marker-pulse 1600ms ease-in-out infinite;
}

.map-node-marker.is-visited .map-node-marker__status {
  color: var(--color-green);
}

.map-node-marker.is-rumored {
  background:
    repeating-linear-gradient(
      135deg,
      color-mix(in srgb, var(--color-arcane) 16%, transparent) 0 4px,
      transparent 4px 8px
    ),
    color-mix(in srgb, var(--color-bg-elev) 86%, transparent);
}

.map-node-marker.is-selected,
.map-node-marker.is-reachable {
  box-shadow:
    0 0 0 2px var(--color-gold),
    0 8px 20px color-mix(in srgb, var(--color-bg) 60%, transparent);
}

@keyframes map-marker-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.06); }
}
</style>
