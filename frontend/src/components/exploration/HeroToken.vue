<script setup lang="ts">
import { computed } from 'vue'
import type { ExHero } from '../../fixtures/exploration'

const props = defineProps<{
  hero: ExHero
  cell: number
  selected: boolean
  highlighted: boolean
}>()

const emit = defineEmits<{ click: [id: string] }>()

const hpPct = computed(() => (props.hero.hp / Math.max(1, props.hero.hpMax)) * 100)
const hpColor = computed(() => {
  const r = props.hero.hp / Math.max(1, props.hero.hpMax)
  return r > 0.5 ? 'var(--color-green)' : r > 0.25 ? '#e5b93a' : 'var(--color-blood)'
})

const tokenFontPx = computed(() => Math.max(10, Math.round(props.cell * 0.32)))

const ring = computed(() => {
  if (props.selected) return '0 0 0 2px var(--color-gold), 0 0 18px rgba(240,199,100,0.8)'
  if (props.highlighted) return '0 0 0 2px var(--color-ember), 0 0 12px rgba(255,130,71,0.6)'
  return 'inset 0 -6px 10px rgba(0,0,0,0.4), 0 2px 6px rgba(0,0,0,0.6)'
})

const style = computed(() => ({
  left: `${props.hero.x * props.cell + 3}px`,
  top: `${props.hero.y * props.cell + 3}px`,
  width: `${props.cell - 6}px`,
  height: `${props.cell - 6}px`,
  background: `radial-gradient(circle at 30% 30%, ${props.hero.color}, ${props.hero.color}cc 60%, ${props.hero.color}88)`,
  borderColor: props.hero.isMe ? 'var(--color-gold)' : 'rgba(247,236,208,0.5)',
  boxShadow: ring.value,
  transform: props.selected ? 'scale(1.06)' : 'scale(1)',
  zIndex: props.selected ? 5 : 3,
}))
</script>

<template>
  <div
    class="hero-token"
    :style="style"
    @click.stop="emit('click', hero.id)"
  >
    <span
      class="hero-token-label"
      :style="{ fontSize: `${tokenFontPx}px` }"
    >{{ hero.token }}</span>

    <span
      class="hero-token-badge"
      :class="{ 'is-me': hero.isMe, 'is-ally': !hero.isMe && !hero.ai }"
    >{{ hero.isMe ? 'VOUS' : hero.ai ? 'IA' : 'ALLIÉ' }}</span>

    <div class="hero-token-hp">
      <div class="hero-token-hp-fill" :style="{ width: `${hpPct}%`, background: hpColor }" />
    </div>
  </div>
</template>

<style scoped>
.hero-token {
  position: absolute;
  border-radius: 50%;
  border: 1.5px solid;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 120ms, box-shadow 120ms;
}

.hero-token-label {
  font-family: var(--font-display);
  font-weight: 700;
  color: var(--color-bg);
  line-height: 1;
  pointer-events: none;
}

.hero-token-badge {
  position: absolute;
  top: -8px;
  left: -2px;
  background: var(--color-bg-elev);
  color: var(--color-parchment-dark);
  font-size: 8px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 999px;
  border: 1px solid var(--color-border-strong);
  font-family: var(--font-display);
  letter-spacing: 0.5px;
  pointer-events: none;
}

.hero-token-badge.is-me {
  background: var(--color-gold);
  color: var(--color-bg);
  border-color: var(--color-gold);
}

.hero-token-badge.is-ally {
  background: rgba(79, 216, 192, 0.16);
  color: var(--color-teal);
  border-color: rgba(79, 216, 192, 0.5);
}

.hero-token-hp {
  position: absolute;
  bottom: -7px;
  left: 1px;
  right: 1px;
  height: 3px;
  border-radius: 2px;
  background: rgba(0, 0, 0, 0.7);
  overflow: hidden;
  pointer-events: none;
}

.hero-token-hp-fill {
  height: 100%;
  transition: width 200ms ease, background 200ms ease;
}
</style>
