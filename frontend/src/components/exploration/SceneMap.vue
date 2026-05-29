<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '../../stores/session'
import { useGameStore } from '../../stores/game'
import { useExplorationParty } from '../../composables/useExplorationParty'
import { useExplorationPois } from '../../composables/useExplorationPois'
import LocalMapCanvas from '../map/LocalMapCanvas.vue'
import HeroToken from './HeroToken.vue'
import PoiToken from './PoiToken.vue'
import type { SceneElement } from '../../types'

const props = withDefaults(defineProps<{
  cell?: number
}>(), {
  cell: 44,
})

const sessionStore = useSessionStore()
const gameStore = useGameStore()
const { party } = useExplorationParty()
const { pois } = useExplorationPois()

const selectedElementId = computed(() => {
  const selected = pois.value.find((poi) => poi.id === sessionStore.selectedId)
  return selected?.elementId ?? null
})

function isSelected(id: string) {
  return sessionStore.selectedId === id
}

function isHighlighted(id: string) {
  return sessionStore.highlightedIds.includes(id)
}

function onClick(id: string) {
  sessionStore.selectEntity(id)
}

function onElementClick(element: SceneElement) {
  const linked = pois.value.find((poi) => poi.elementId === element.id)
  if (linked) sessionStore.selectEntity(linked.id)
}
</script>

<template>
  <LocalMapCanvas
    :scene="gameStore.currentScene"
    :cell="cell"
    mode="exploration"
    :selected-element-id="selectedElementId"
    @element-click="onElementClick"
  >
    <PoiToken
      v-for="poi in pois"
      :key="poi.id"
      :poi="poi"
      :cell="cell"
      :selected="isSelected(poi.id)"
      :highlighted="isHighlighted(poi.id)"
      @click="onClick"
    />

    <HeroToken
      v-for="hero in party"
      :key="hero.id"
      :hero="hero"
      :cell="cell"
      :selected="isSelected(hero.id)"
      :highlighted="isHighlighted(hero.id)"
      @click="onClick"
    />
  </LocalMapCanvas>
</template>
