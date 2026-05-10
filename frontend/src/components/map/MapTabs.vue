<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useGameStore } from '../../stores/game'
import CityMap from './CityMap.vue'
import RegionMap from './RegionMap.vue'
import type { MapNode } from '../../types'

const props = defineProps<{
  sessionId: string
}>()

const emit = defineEmits<{
  action: [actionType: string, content?: string, targetId?: string, extra?: Record<string, unknown>]
}>()

type MapTab = 'scene' | 'city' | 'region'

const gameStore = useGameStore()
const storageKey = computed(() => `rpgmaster.map_tabs.${props.sessionId}`)
const activeTab = ref<MapTab>(readStoredTab())

const cityList = computed(() => Object.values(gameStore.cityMaps))
const activeCity = computed(() => {
  const activeId = gameStore.activeCityId
  return (activeId && gameStore.cityMaps[activeId]) || cityList.value[0] || null
})
const readonly = computed(() => gameStore.isInCombat)

watch(activeTab, (next) => {
  try {
    localStorage.setItem(storageKey.value, next)
  } catch {
    // Optional persistence only.
  }
})

watch(() => [gameStore.regionMap?.id, cityList.value.length] as const, () => {
  if (activeTab.value === 'city' && !activeCity.value) activeTab.value = 'scene'
  if (activeTab.value === 'region' && !gameStore.regionMap) activeTab.value = 'scene'
})

function readStoredTab(): MapTab {
  try {
    const stored = localStorage.getItem(storageKey.value)
    if (stored === 'scene' || stored === 'city' || stored === 'region') return stored
  } catch {
    // ignore
  }
  return 'scene'
}

function travelTo(node: MapNode) {
  emit('action', 'free_text', `Je voyage vers ${node.name}.`)
}

function approach(node: MapNode) {
  emit('action', 'free_text', `Je m'approche de ${node.name}.`)
}
</script>

<template>
  <section class="map-tabs">
    <div class="map-tabs__bar" role="tablist" aria-label="Cartes">
      <button
        type="button"
        class="map-tabs__tab"
        :class="{ 'is-active': activeTab === 'scene' }"
        @click="activeTab = 'scene'"
      >
        Scène
      </button>
      <button
        type="button"
        class="map-tabs__tab"
        :class="{ 'is-active': activeTab === 'city' }"
        :disabled="!activeCity"
        @click="activeTab = 'city'"
      >
        Ville
      </button>
      <button
        type="button"
        class="map-tabs__tab"
        :class="{ 'is-active': activeTab === 'region' }"
        :disabled="!gameStore.regionMap"
        @click="activeTab = 'region'"
      >
        Région
      </button>
      <span v-if="readonly" class="map-tabs__readonly">lecture seule</span>
    </div>
    <RegionMap
      v-if="activeTab === 'region'"
      :map="gameStore.regionMap"
      :readonly="readonly"
      @travel="travelTo"
      @open-city="(cityId) => { gameStore.activeCityId = cityId; activeTab = 'city' }"
    />
    <CityMap
      v-else-if="activeTab === 'city'"
      :map="activeCity"
      :readonly="readonly"
      @approach="approach"
    />
  </section>
</template>

<style scoped>
.map-tabs {
  flex: none;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
}

.map-tabs__bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: var(--color-bg-elev);
}

.map-tabs__tab {
  min-width: 78px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 7px 10px;
  color: var(--color-text-muted);
  background: transparent;
}

.map-tabs__tab.is-active {
  color: var(--color-gold);
  border-color: var(--color-gold);
  background: var(--color-gold-deep);
}

.map-tabs__tab:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.map-tabs__readonly {
  margin-left: auto;
  color: var(--color-text-dim);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
</style>
