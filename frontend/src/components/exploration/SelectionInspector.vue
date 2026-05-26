<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '../../stores/session'
import { useExplorationParty } from '../../composables/useExplorationParty'
import { useExplorationPois } from '../../composables/useExplorationPois'

const sessionStore = useSessionStore()
const { findHero } = useExplorationParty()
const { findPoi } = useExplorationPois()

const emit = defineEmits<{
  act: [id: string]
  openSheet: [id: string]
}>()

const hero = computed(() => findHero(sessionStore.selectedId))
const poi = computed(() => findPoi(sessionStore.selectedId))

const isHero = computed(() => !!hero.value)
const isSortie = computed(() => poi.value?.kind === 'sortie')
const isRepere = computed(() => poi.value?.kind === 'repere')

const tone = computed<'ember' | 'arcane' | 'blood' | 'teal' | 'gold' | 'text'>(() => {
  if (hero.value) {
    if (hero.value.isMe) return 'ember'
    return hero.value.ai ? 'arcane' : 'teal'
  }
  if (!poi.value) return 'text'
  if (poi.value.kind === 'sortie') return 'gold'
  return poi.value.tone === 'text' ? 'text' : poi.value.tone
})

const toneVar = computed(() => `var(--color-${tone.value === 'text' ? 'parchment' : tone.value})`)
const toneHex = computed(() => {
  switch (tone.value) {
    case 'ember':  return '#ff8247'
    case 'arcane': return '#c090ff'
    case 'blood':  return '#e84545'
    case 'teal':   return '#4fd8c0'
    case 'gold':   return '#f0c764'
    default:        return '#f7ecd0'
  }
})

const eyebrow = computed(() => {
  if (isHero.value) {
    if (hero.value!.isMe) return 'Vous'
    return hero.value!.ai ? 'Compagnon IA' : 'Allié'
  }
  if (isSortie.value) return 'Sortie'
  if (isRepere.value) return 'Repère'
  return ''
})

const position = computed(() => hero.value?.pos ?? poi.value?.label ?? '')
const title = computed(() => hero.value?.name ?? poi.value?.title ?? '')

function close() {
  sessionStore.selectEntity(null)
}

function act() {
  if (sessionStore.selectedId) {
    emit('act', sessionStore.selectedId)
  }
}
</script>

<template>
  <div
    v-if="hero || poi"
    class="inspector"
    :style="{
      borderColor: `${toneHex}55`,
      boxShadow: `0 12px 36px rgba(0,0,0,0.6), 0 0 28px ${toneHex}25`,
    }"
  >
    <button class="inspector-close" @click="close">✕</button>

    <header class="inspector-header">
      <div
        class="inspector-avatar"
        :class="{ 'is-square': isSortie }"
        :style="{
          background: hero
            ? `radial-gradient(circle at 30% 30%, ${hero.color}, ${hero.color}aa)`
            : `radial-gradient(circle at 30% 30%, ${toneHex}55, ${toneHex}10)`,
          borderColor: hero ? (hero.isMe ? 'var(--color-gold)' : 'rgba(247,236,208,0.5)') : `${toneHex}80`,
          color: hero ? 'var(--color-bg)' : toneVar,
        }"
      >
        <span v-if="hero">{{ hero.token }}</span>
        <span v-else>{{ isSortie ? '↦' : '🔍' }}</span>
      </div>
      <div class="inspector-meta">
        <div class="inspector-eyebrow" :style="{ color: toneVar }">
          {{ eyebrow }} · {{ position }}
        </div>
        <div class="inspector-title">{{ title }}</div>
        <div v-if="hero" class="inspector-sub">
          Niv.1 · {{ hero.cls }} · {{ hero.species }}
        </div>
        <div v-else-if="isRepere && poi" class="inspector-sub">
          Test : <span class="inspector-skill" :style="{ color: toneVar }">{{ poi.skill }}</span> · DD {{ poi.dc }}
        </div>
        <div v-else-if="isSortie && poi" class="inspector-sub">
          Destination : <span class="inspector-skill" :style="{ color: toneVar }">{{ poi.dest }}</span>
        </div>
      </div>
    </header>

    <!-- Hero stats -->
    <div v-if="hero" class="inspector-stats">
      <div class="inspector-stat" :style="{ borderColor: 'rgba(111,217,111,0.25)' }">
        <span class="inspector-stat-value" style="color: var(--color-green)">{{ hero.hp }}/{{ hero.hpMax }}</span>
        <span class="inspector-stat-label">PV</span>
      </div>
      <div class="inspector-stat" :style="{ borderColor: 'rgba(240,199,100,0.25)' }">
        <span class="inspector-stat-value" style="color: var(--color-gold)">+2</span>
        <span class="inspector-stat-label">Init.</span>
      </div>
      <div class="inspector-stat" :style="{ borderColor: 'var(--color-border-strong)' }">
        <span class="inspector-stat-value">—</span>
        <span class="inspector-stat-label">État</span>
      </div>
    </div>

    <!-- POI desc -->
    <p v-if="poi" class="inspector-desc">{{ poi.desc }}</p>

    <!-- Actions -->
    <div class="inspector-actions">
      <template v-if="hero?.isMe">
        <button
          class="inspector-btn-primary"
          :style="{ background: `linear-gradient(135deg, var(--color-ember), #ff8247aa)` }"
          @click="emit('openSheet', hero.id)"
        >
          👤 Fiche
        </button>
      </template>
      <template v-else-if="hero?.ai">
        <button class="inspector-btn-outline" :style="{ color: 'var(--color-arcane)', borderColor: 'rgba(192,144,255,0.4)', background: 'rgba(192,144,255,0.14)' }">
          🤖 Faire réagir
        </button>
        <button
          class="inspector-btn-outline"
          :style="{ color: 'var(--color-gold)', borderColor: 'rgba(240,199,100,0.4)', background: 'rgba(240,199,100,0.14)' }"
          @click="emit('openSheet', hero.id)"
        >
          👁 Fiche
        </button>
      </template>
      <template v-else-if="hero">
        <button
          class="inspector-btn-outline"
          :style="{ color: 'var(--color-teal)', borderColor: 'rgba(79,216,192,0.4)', background: 'rgba(79,216,192,0.14)' }"
          @click="emit('openSheet', hero.id)"
        >
          👁 Fiche
        </button>
      </template>
      <template v-else-if="isRepere && poi">
        <button
          class="inspector-btn-primary"
          :style="{ background: `linear-gradient(135deg, ${toneHex}, ${toneHex}aa)` }"
          @click="act"
        >✦ {{ poi.skill }}</button>
        <button class="inspector-btn-outline" :style="{ color: 'var(--color-teal)', borderColor: 'rgba(79,216,192,0.4)', background: 'rgba(79,216,192,0.14)' }">
          ✥ Approcher
        </button>
      </template>
      <template v-else-if="isSortie && poi">
        <button
          class="inspector-btn-primary inspector-btn-wide"
          :style="{ background: `linear-gradient(135deg, ${toneHex}, ${toneHex}aa)` }"
          @click="act"
        >↦ S'y diriger</button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.inspector {
  position: absolute;
  top: 14px;
  right: 14px;
  width: 320px;
  padding: 14px;
  background: linear-gradient(180deg, var(--color-surface), var(--color-bg-elev));
  border: 1px solid;
  border-radius: 10px;
  z-index: 8;
  backdrop-filter: blur(6px);
}

.inspector-close {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 22px;
  height: 22px;
  border-radius: 4px;
  background: transparent;
  border: none;
  color: var(--color-text-muted);
  font-size: 14px;
  cursor: pointer;
}

.inspector-close:hover { color: var(--color-parchment); }

.inspector-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.inspector-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 2px solid;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 14px;
  flex-shrink: 0;
}

.inspector-avatar.is-square { border-radius: 8px; }

.inspector-meta {
  flex: 1;
  min-width: 0;
}

.inspector-eyebrow {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.inspector-title {
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  color: var(--color-parchment);
  line-height: 1.15;
}

.inspector-sub {
  font-size: 10px;
  color: var(--color-text-muted);
  font-family: var(--font-serif);
  font-style: italic;
}

.inspector-skill {
  font-weight: 700;
  font-family: var(--font-mono);
  font-style: normal;
}

.inspector-stats {
  display: flex;
  gap: 4px;
  margin-bottom: 10px;
}

.inspector-stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4px 6px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid;
  border-radius: 6px;
}

.inspector-stat-value {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  color: var(--color-parchment);
}

.inspector-stat-label {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--color-text-dim);
  text-transform: uppercase;
  margin-top: 2px;
}

.inspector-desc {
  font-family: var(--font-serif);
  font-size: 13px;
  line-height: 1.5;
  color: var(--color-parchment-dark);
  margin: 0 0 10px;
  text-wrap: pretty;
}

.inspector-actions {
  display: flex;
  gap: 5px;
}

.inspector-btn-primary,
.inspector-btn-outline {
  flex: 1;
  padding: 8px 0;
  border-radius: 5px;
  font-family: var(--font-display);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  cursor: pointer;
  border: 1px solid transparent;
}

.inspector-btn-primary {
  color: var(--color-bg);
  border: none;
}

.inspector-btn-outline {
  background: transparent;
}

.inspector-btn-wide { flex: 1; }
</style>
