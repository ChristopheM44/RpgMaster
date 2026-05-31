<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '../../stores/session'
import { useGameStore } from '../../stores/game'
import { useQuestStore } from '../../stores/quest'
import { useExplorationParty } from '../../composables/useExplorationParty'
import { useExplorationPois } from '../../composables/useExplorationPois'
import ScopeTabs from './ScopeTabs.vue'
import SceneMap from './SceneMap.vue'
import TownMap from './TownMap.vue'
import RegionMap from './RegionMap.vue'
import MapLegend from './MapLegend.vue'
import SelectionInspector from './SelectionInspector.vue'
import CarnetPopover from './CarnetPopover.vue'

const emit = defineEmits<{
  act: [id: string]
  approach: [id: string]
  openSheet: [id: string]
}>()

const sessionStore = useSessionStore()
const gameStore = useGameStore()
const questStore = useQuestStore()
const { party } = useExplorationParty()
const { reperes, sorties } = useExplorationPois()

const activeCity = computed(() => {
  const id = gameStore.activeCityId
  if (!id) return undefined
  return gameStore.cityMaps[id]
})

const titleByScope = computed(() => {
  switch (sessionStore.mapScope) {
    case 'ville':  return activeCity.value?.name ?? '—'
    case 'region': return gameStore.regionMap?.name ?? '—'
    default:        return gameStore.adventureJournal?.location_place ?? gameStore.currentScene?.scene_id ?? 'Scène'
  }
})

const metaByScope = computed(() => {
  switch (sessionStore.mapScope) {
    case 'ville': {
      const n = activeCity.value?.nodes.length ?? 0
      return `${n} bâtiment${n > 1 ? 's' : ''}`
    }
    case 'region': {
      const n = gameStore.regionMap?.nodes.length ?? 0
      return `${n} lieu${n > 1 ? 'x' : ''}`
    }
    default: {
      const scene = gameStore.currentScene
      const dims = scene ? `${scene.cols} × ${scene.rows} m` : '—'
      return `${dims} · ${party.value.length} héros · ${reperes.value.length} repère${reperes.value.length > 1 ? 's' : ''} · ${sorties.value.length} sortie${sorties.value.length > 1 ? 's' : ''}`
    }
  }
})

const questCount = computed(() => questStore.quests.length)

function toggleCarnet() {
  sessionStore.toggleCarnet()
}
</script>

<template>
  <section class="map-column">
    <!-- Top bar -->
    <div class="map-topbar">
      <ScopeTabs />

      <div class="map-topbar-title">
        <span class="map-topbar-title-name">{{ titleByScope }}</span>
        <span class="map-topbar-sep">·</span>
        <span class="map-topbar-meta">{{ metaByScope }}</span>
      </div>

      <button class="map-tool" title="Plein écran">⛶ Plein écran</button>

      <button
        class="carnet-btn"
        :class="{ 'is-open': sessionStore.carnetOpen }"
        @click="toggleCarnet"
      >
        <span class="carnet-btn-icon">📖</span>
        <span class="carnet-btn-label">Carnet</span>
        <span class="carnet-btn-badge">{{ questCount }}</span>
      </button>
    </div>

    <!-- Canvas -->
    <div class="map-canvas">
      <SceneMap v-if="sessionStore.mapScope === 'scene'" />
      <TownMap v-else-if="sessionStore.mapScope === 'ville'" :width="640" :height="580" />
      <RegionMap v-else :width="640" :height="580" />

      <!-- Inspector -->
      <SelectionInspector
        v-if="sessionStore.selectedId"
        @act="(id: string) => emit('act', id)"
        @approach="(id: string) => emit('approach', id)"
        @open-sheet="(id) => emit('openSheet', id)"
      />

      <!-- Carnet popover -->
      <CarnetPopover @open-sheet="(id) => emit('openSheet', id)" />

      <!-- Legend (scene only) -->
      <MapLegend v-if="sessionStore.mapScope === 'scene'" />
    </div>
  </section>
</template>

<style scoped>
.map-column {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  position: relative;
  border-right: 1px solid var(--color-border);
}

.map-topbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--color-border);
  background: rgba(14, 13, 20, 0.4);
  flex-shrink: 0;
  height: 44px;
}

.map-topbar-title {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.map-topbar-title-name {
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  color: var(--color-parchment);
  letter-spacing: 1.5px;
  text-transform: uppercase;
  white-space: nowrap;
}

.map-topbar-sep { color: var(--color-text-dim); }

.map-topbar-meta {
  font-size: 10px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.map-tool {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 9px;
  background: rgba(14, 13, 20, 0.7);
  backdrop-filter: blur(8px);
  border: 1px solid var(--color-border);
  border-radius: 5px;
  color: var(--color-parchment-dark);
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.carnet-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: 6px;
  background: transparent;
  border: 1px solid var(--color-border-strong);
  color: var(--color-parchment-dark);
  font-family: var(--font-display);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  cursor: pointer;
  white-space: nowrap;
  transition: background 120ms, color 120ms, border-color 120ms;
}

.carnet-btn.is-open {
  background: linear-gradient(135deg, rgba(240, 199, 100, 0.20), rgba(240, 199, 100, 0.05));
  border-color: var(--color-gold);
  color: var(--color-gold);
}

.carnet-btn-icon { font-size: 12px; }

.carnet-btn-badge {
  font-size: 8px;
  padding: 1px 5px;
  border-radius: 999px;
  background: rgba(255, 235, 180, 0.08);
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}

.carnet-btn.is-open .carnet-btn-badge {
  background: rgba(240, 199, 100, 0.3);
  color: var(--color-gold);
}

.map-canvas {
  flex: 1;
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
  overflow: hidden;
  position: relative;
}
</style>
