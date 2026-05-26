<script setup lang="ts">
import { computed } from 'vue'
import type { ExPoi } from '../../fixtures/exploration'

const props = defineProps<{
  poi: ExPoi
  cell: number
  selected: boolean
  highlighted: boolean
}>()

const emit = defineEmits<{ click: [id: string] }>()

const isSortie = computed(() => props.poi.kind === 'sortie')

const toneVar = computed(() => {
  switch (props.poi.tone) {
    case 'blood':  return 'var(--color-blood)'
    case 'arcane': return 'var(--color-arcane)'
    case 'teal':   return 'var(--color-teal)'
    case 'gold':   return 'var(--color-gold)'
    default:       return 'var(--color-parchment)'
  }
})

const toneHex = computed(() => {
  switch (props.poi.tone) {
    case 'blood':  return '#e84545'
    case 'arcane': return '#c090ff'
    case 'teal':   return '#4fd8c0'
    case 'gold':   return '#f0c764'
    default:       return '#f7ecd0'
  }
})

const ring = computed(() => {
  if (props.selected) return '0 0 0 2px var(--color-gold), 0 0 18px rgba(240,199,100,0.8)'
  if (props.highlighted) return '0 0 0 2px var(--color-ember), 0 0 12px rgba(255,130,71,0.6)'
  if (props.poi.active) return `0 0 0 2px ${toneHex.value}, 0 0 14px ${toneHex.value}aa`
  return '0 2px 6px rgba(0,0,0,0.5)'
})

const fontPx = computed(() => Math.max(11, Math.round(props.cell * 0.34)))

const style = computed(() => ({
  left: `${props.poi.x * props.cell + 6}px`,
  top: `${props.poi.y * props.cell + 6}px`,
  width: `${props.cell - 12}px`,
  height: `${props.cell - 12}px`,
  borderRadius: isSortie.value ? '8px' : '50%',
  background: `radial-gradient(circle at 30% 30%, ${toneHex.value}40, ${toneHex.value}10)`,
  borderColor: `${toneHex.value}80`,
  boxShadow: ring.value,
  transform: props.selected ? 'scale(1.06)' : 'scale(1)',
  zIndex: props.selected ? 6 : 4,
}))
</script>

<template>
  <div
    class="poi-token"
    :style="style"
    @click.stop="emit('click', poi.id)"
  >
    <span
      class="poi-token-icon"
      :style="{
        fontSize: `${fontPx}px`,
        color: toneVar,
        filter: `drop-shadow(0 0 6px ${toneHex}80)`,
      }"
    >{{ isSortie ? '↦' : '🔍' }}</span>

    <span
      class="poi-token-badge"
      :class="{ 'is-active': poi.active }"
      :style="{
        background: poi.active ? toneHex : 'var(--color-bg-elev)',
        color: poi.active ? 'var(--color-bg)' : toneHex,
        borderColor: `${toneHex}80`,
      }"
    >{{ poi.label }}</span>
  </div>
</template>

<style scoped>
.poi-token {
  position: absolute;
  border: 1.5px solid;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 120ms, box-shadow 120ms;
}

.poi-token-icon {
  line-height: 1;
  pointer-events: none;
}

.poi-token-badge {
  position: absolute;
  top: -8px;
  right: -6px;
  font-size: 8px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 999px;
  border: 1px solid;
  font-family: var(--font-mono);
  pointer-events: none;
}
</style>
