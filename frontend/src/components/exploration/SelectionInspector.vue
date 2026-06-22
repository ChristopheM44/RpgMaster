<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '../../stores/session'
import { useExplorationParty } from '../../composables/useExplorationParty'
import { useExplorationPois } from '../../composables/useExplorationPois'
import {
  entityForElement,
  useMapInspectables,
  type MapInspectableEntity,
} from '../../composables/useMapInspectables'
import { tokens } from '../../types/tokens'

const sessionStore = useSessionStore()
const { findHero } = useExplorationParty()
const { findPoi } = useExplorationPois()
const { findElement, linkedEntityIdForElement } = useMapInspectables()

const emit = defineEmits<{
  act: [id: string]
  approach: [id: string]
  openSheet: [id: string]
}>()

const hero = computed(() => findHero(sessionStore.selectedId))
const poi = computed(() => findPoi(sessionStore.selectedId))
const element = computed(() => {
  if (hero.value || poi.value) return undefined
  return findElement(sessionStore.selectedId)
})
const elementInfo = computed<MapInspectableEntity | null>(() => (
  element.value
    ? entityForElement(element.value, linkedEntityIdForElement(element.value.id))
    : null
))

const isHero = computed(() => !!hero.value)
const isSortie = computed(() => poi.value?.kind === 'sortie')
const isPoi = computed(() => !!poi.value && !isSortie.value)
const isElement = computed(() => !!elementInfo.value)
const isSquareAvatar = computed(() => isSortie.value || isElement.value)

const tone = computed<'gold' | 'arcane' | 'blood' | 'teal' | 'text'>(() => {
  if (hero.value) {
    if (hero.value.isMe) return 'gold'
    return hero.value.ai ? 'arcane' : 'teal'
  }
  if (elementInfo.value) return elementInfo.value.tone
  if (!poi.value) return 'text'
  if (poi.value.kind === 'sortie') return 'gold'
  return poi.value.tone === 'text' ? 'text' : poi.value.tone
})

const toneVar = computed(() => `var(--color-${tone.value === 'text' ? 'parchment' : tone.value})`)
const toneHex = computed(() => {
  switch (tone.value) {
    case 'gold':   return tokens.gold
    case 'arcane': return tokens.arcane
    case 'blood':  return tokens.blood
    case 'teal':   return tokens.teal
    default:        return tokens.parchment
  }
})

const eyebrow = computed(() => {
  if (isHero.value) {
    if (hero.value!.isMe) return 'Vous'
    return hero.value!.ai ? 'Compagnon IA' : 'Allié'
  }
  if (elementInfo.value) return elementInfo.value.label
  if (isSortie.value) return 'Sortie'
  switch (poi.value?.kind) {
    case 'npc': return 'PNJ'
    case 'enemy': return 'Ennemi'
    case 'clue': return 'Indice'
    case 'hazard': return 'Danger'
    case 'cover': return 'Couvert'
    case 'loot': return 'Butin'
    case 'passage': return 'Passage'
    case 'fog': return 'Brouillard'
    case 'light': return 'Lumière'
    case 'ruins': return 'Vestiges'
    case 'safe': return 'Refuge'
    case 'unknown': return 'Inconnu'
    case 'exit': return 'Issue'
    case 'point': return 'Repère'
    default: return ''
  }
})

const title = computed(() => hero.value?.name ?? poi.value?.title ?? elementInfo.value?.title ?? '')
const position = computed(() => (
  hero.value?.pos
  ?? poi.value?.label
  ?? elementInfo.value?.coordinate
  ?? ''
))
const inspectorSymbol = computed(() => {
  if (element.value) {
    switch (element.value.kind) {
      case 'door': return '▭'
      case 'window': return '◇'
      case 'stairs': return '↧'
      case 'hazard': return '⚠'
      case 'cover':
      case 'furniture': return '◆'
      case 'light': return '✦'
      default: return '✦'
    }
  }
  if (poi.value?.iconSymbol) return poi.value.iconSymbol
  switch (poi.value?.kind) {
    case 'npc': return '◉'
    case 'enemy': return '⚔'
    case 'clue': return '✦'
    case 'hazard': return '⚠'
    case 'cover': return '◆'
    case 'loot': return '▣'
    case 'sortie': return '↦'
    default: return '✦'
  }
})
const description = computed(() => poi.value?.desc ?? elementInfo.value?.description ?? '')
const physicalState = computed(() => poi.value?.physicalState ?? element.value?.physical_state ?? '')
const stateLabel = computed(() => poi.value?.state ?? element.value?.state ?? '')
const facts = computed(() => poi.value?.facts ?? element.value?.facts ?? [])
const poiActionLabel = computed(() => (
  poi.value?.actionLabel
  ?? poi.value?.skill
  ?? (poi.value?.kind === 'npc' ? 'Parler' : 'Examiner')
))
const poiSubPrefix = computed(() => (
  poi.value?.dc !== undefined && poi.value?.dc !== null ? 'Test' : 'Action'
))
const poiSubValue = computed(() => {
  if (!poi.value) return ''
  if (poi.value.dc !== undefined && poi.value.dc !== null) {
    return `${poiActionLabel.value} · DD ${poi.value.dc}`
  }
  return poiActionLabel.value
})

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
    v-if="hero || poi || elementInfo"
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
        :class="{ 'is-square': isSquareAvatar }"
        :style="{
          background: hero
            ? `radial-gradient(circle at 30% 30%, ${hero.color}, ${hero.color}aa)`
            : `radial-gradient(circle at 30% 30%, ${toneHex}55, ${toneHex}10)`,
          borderColor: hero ? (hero.isMe ? 'var(--color-gold)' : 'rgba(247,236,208,0.5)') : `${toneHex}80`,
          color: hero ? 'var(--color-bg)' : toneVar,
        }"
      >
        <span v-if="hero">{{ hero.token }}</span>
        <span v-else>{{ inspectorSymbol }}</span>
      </div>
      <div class="inspector-meta">
        <div class="inspector-eyebrow" :style="{ color: toneVar }">
          {{ eyebrow }} · {{ position }}
        </div>
        <div class="inspector-title">{{ title }}</div>
        <div v-if="hero" class="inspector-sub">
          Niv.1 · {{ hero.cls }} · {{ hero.species }}
        </div>
        <div v-else-if="isPoi && poi" class="inspector-sub">
          {{ poiSubPrefix }} :
          <span class="inspector-skill" :style="{ color: toneVar }">{{ poiSubValue }}</span>
        </div>
        <div v-else-if="isSortie && poi" class="inspector-sub">
          Destination : <span class="inspector-skill" :style="{ color: toneVar }">{{ poi.dest }}</span>
        </div>
        <div v-else-if="isElement && elementInfo" class="inspector-sub">
          Nature : <span class="inspector-skill" :style="{ color: toneVar }">{{ elementInfo.label }}</span>
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
    <p v-if="description" class="inspector-desc">{{ description }}</p>
    <div v-if="physicalState || stateLabel || facts.length" class="inspector-facts">
      <div v-if="stateLabel" class="inspector-fact">
        <span>État</span>
        <strong>{{ stateLabel }}</strong>
      </div>
      <div v-if="physicalState" class="inspector-fact">
        <span>Matière</span>
        <strong>{{ physicalState }}</strong>
      </div>
      <div
        v-for="fact in facts"
        :key="fact"
        class="inspector-fact is-wide"
      >
        <span>Fait</span>
        <strong>{{ fact }}</strong>
      </div>
    </div>

    <!-- Actions -->
    <div v-if="hero || poi" class="inspector-actions">
      <template v-if="hero?.isMe">
        <button
          class="inspector-btn-primary"
          :style="{ background: `linear-gradient(135deg, var(--color-gold), color-mix(in srgb, var(--color-gold) 67%, transparent))` }"
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
      <template v-else-if="isPoi && poi">
        <button
          class="inspector-btn-primary"
          :style="{ background: `linear-gradient(135deg, ${toneHex}, ${toneHex}aa)` }"
          @click="act"
        >✦ {{ poiActionLabel }}</button>
        <button
          v-if="poi.kind !== 'npc'"
          class="inspector-btn-outline"
          :style="{ color: 'var(--color-teal)', borderColor: 'rgba(79,216,192,0.4)', background: 'rgba(79,216,192,0.14)' }"
          @click="emit('approach', poi.id)"
        >
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

.inspector-facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  margin: 0 0 10px;
}

.inspector-fact {
  min-width: 0;
  padding: 6px 7px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.18);
}

.inspector-fact.is-wide {
  grid-column: 1 / -1;
}

.inspector-fact span {
  display: block;
  font-family: var(--font-display);
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.inspector-fact strong {
  display: block;
  margin-top: 2px;
  overflow-wrap: anywhere;
  font-family: var(--font-serif);
  font-size: 11px;
  font-weight: 600;
  line-height: 1.35;
  color: var(--color-parchment);
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
