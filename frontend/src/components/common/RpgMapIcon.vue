<script setup lang="ts">
import { computed } from 'vue'
import {
  resolveRpgMapIcon,
  type RpgMapIconId,
  type RpgMapIconState,
  type RpgMapIconVariant,
} from '../../icons/rpgMapIcons'

const props = withDefaults(defineProps<{
  iconId: RpgMapIconId | string | null | undefined
  variant?: RpgMapIconVariant
  size?: number | string
  state?: RpgMapIconState
  label?: string
  decorative?: boolean
}>(), {
  variant: 'color',
  size: 24,
  state: 'normal',
  label: undefined,
  decorative: false,
})

const icon = computed(() => resolveRpgMapIcon(props.iconId))
const src = computed(() => props.variant === 'mono' ? icon.value.monoSrc : icon.value.colorSrc)
const sizeValue = computed(() => typeof props.size === 'number' ? `${props.size}px` : props.size)
const accessibleLabel = computed(() => props.label || icon.value.name)
</script>

<template>
  <span
    class="rpg-map-icon"
    :class="`is-${state}`"
    :style="{
      '--rpg-map-icon-size': sizeValue,
      '--rpg-map-icon-color': icon.color,
    }"
    :role="decorative ? undefined : 'img'"
    :aria-label="decorative ? undefined : accessibleLabel"
    :aria-hidden="decorative ? 'true' : undefined"
    :title="decorative ? undefined : accessibleLabel"
    :data-icon-id="icon.id"
    :data-icon-variant="variant"
  >
    <img
      class="rpg-map-icon__img"
      :src="src"
      alt=""
      aria-hidden="true"
      draggable="false"
    >
  </span>
</template>

<style scoped>
.rpg-map-icon {
  display: inline-flex;
  width: var(--rpg-map-icon-size);
  height: var(--rpg-map-icon-size);
  flex: none;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  color: var(--rpg-map-icon-color);
  background: transparent;
  transition: background 120ms ease, box-shadow 120ms ease, filter 120ms ease, opacity 120ms ease;
}

.rpg-map-icon__img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}

.rpg-map-icon.is-hover {
  background: rgba(247, 236, 208, 0.08);
}

.rpg-map-icon.is-active {
  background: rgba(240, 199, 100, 0.12);
  box-shadow: 0 0 0 2px #f0c764;
  filter: drop-shadow(0 0 4px currentColor);
}

.rpg-map-icon.is-disabled {
  opacity: 0.3;
}
</style>
