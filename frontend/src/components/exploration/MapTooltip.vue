<script setup lang="ts">
import { computed } from 'vue'
import type { MapInspectableEntity } from '../../composables/useMapInspectables'

const props = defineProps<{
  entity: MapInspectableEntity
  x: number
  y: number
  boundsWidth: number
  boundsHeight: number
}>()

const toneVar = computed(() => {
  const tone = props.entity.tone === 'text' ? 'parchment' : props.entity.tone
  return `var(--color-${tone})`
})

const placement = computed(() => ({
  horizontal: props.x > props.boundsWidth - 230 ? 'left' : 'right',
  vertical: props.y < 96 ? 'below' : 'above',
}))

const style = computed(() => {
  const x = placement.value.horizontal === 'right'
    ? Math.min(props.boundsWidth - 12, props.x + 12)
    : Math.max(12, props.x - 12)
  const y = placement.value.vertical === 'below'
    ? Math.min(props.boundsHeight - 12, props.y + 12)
    : Math.max(12, props.y - 12)

  return {
    left: `${x}px`,
    top: `${y}px`,
    transform: [
      placement.value.horizontal === 'right' ? 'translateX(0)' : 'translateX(-100%)',
      placement.value.vertical === 'below' ? 'translateY(0)' : 'translateY(-100%)',
    ].join(' '),
    '--map-tooltip-tone': toneVar.value,
  }
})

const meta = computed(() => {
  if (props.entity.destination) return `Destination : ${props.entity.destination}`
  if (props.entity.actionLabel) return `Action : ${props.entity.actionLabel}`
  return ''
})
</script>

<template>
  <aside
    class="map-tooltip"
    :style="style"
    role="tooltip"
  >
    <div class="map-tooltip-eyebrow">
      <span>{{ entity.label }}</span>
      <span v-if="entity.coordinate">· {{ entity.coordinate }}</span>
    </div>
    <div class="map-tooltip-title">{{ entity.title }}</div>
    <p v-if="entity.description" class="map-tooltip-desc">{{ entity.description }}</p>
    <div v-if="meta" class="map-tooltip-meta">{{ meta }}</div>
  </aside>
</template>

<style scoped>
.map-tooltip {
  position: absolute;
  z-index: 12;
  width: min(230px, calc(100% - 24px));
  padding: 9px 10px;
  border: 1px solid color-mix(in srgb, var(--map-tooltip-tone) 46%, transparent);
  border-radius: 6px;
  background:
    linear-gradient(180deg, rgba(31, 28, 46, 0.96), rgba(24, 22, 35, 0.96));
  box-shadow:
    0 12px 28px rgba(0, 0, 0, 0.58),
    0 0 18px color-mix(in srgb, var(--map-tooltip-tone) 18%, transparent);
  color: var(--color-parchment);
  pointer-events: none;
  backdrop-filter: blur(8px);
}

.map-tooltip-eyebrow {
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  color: var(--map-tooltip-tone);
  text-transform: uppercase;
}

.map-tooltip-title {
  margin-top: 3px;
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 700;
  color: var(--color-parchment);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.map-tooltip-desc {
  margin: 5px 0 0;
  font-size: 11px;
  line-height: 1.35;
  color: var(--color-parchment-dark);
}

.map-tooltip-meta {
  margin-top: 6px;
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--color-text-muted);
}
</style>
