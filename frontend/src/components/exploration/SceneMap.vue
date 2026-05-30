<script setup lang="ts">
import { computed, ref } from 'vue'
import { useSessionStore } from '../../stores/session'
import { useGameStore } from '../../stores/game'
import { useExplorationParty } from '../../composables/useExplorationParty'
import { useExplorationPois } from '../../composables/useExplorationPois'
import {
  elementCenter,
  entityForElement,
  entityForHero,
  entityForPoi,
  type MapInspectableEntity,
  useMapInspectables,
} from '../../composables/useMapInspectables'
import LocalMapCanvas from '../map/LocalMapCanvas.vue'
import HeroToken from './HeroToken.vue'
import PoiToken from './PoiToken.vue'
import MapTooltip from './MapTooltip.vue'
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
const { findElement, linkedEntityIdForElement } = useMapInspectables()

const tooltip = ref<{ entity: MapInspectableEntity; x: number; y: number } | null>(null)

const selectedElementId = computed(() => {
  const selected = pois.value.find((poi) => poi.id === sessionStore.selectedId)
  if (selected?.elementId) return selected.elementId
  return findElement(sessionStore.selectedId)?.id ?? null
})

const mapWidth = computed(() => (gameStore.currentScene?.cols ?? 12) * props.cell)
const mapHeight = computed(() => (gameStore.currentScene?.rows ?? 12) * props.cell)

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
  if (linked) {
    sessionStore.selectEntity(linked.id)
    return
  }
  if (element.interactive) sessionStore.selectEntity(element.id)
}

function showHeroTooltip(id: string) {
  const hero = party.value.find((item) => item.id === id)
  if (!hero) return
  tooltip.value = {
    entity: entityForHero(hero),
    x: hero.x * props.cell + props.cell / 2,
    y: hero.y * props.cell + 2,
  }
}

function showPoiTooltip(id: string) {
  const poi = pois.value.find((item) => item.id === id)
  if (!poi) return
  tooltip.value = {
    entity: entityForPoi(poi),
    x: poi.x * props.cell + props.cell / 2,
    y: poi.y * props.cell + 2,
  }
}

function showElementTooltip(element: SceneElement | null) {
  if (!element) {
    hideTooltip()
    return
  }

  const linked = pois.value.find((poi) => poi.elementId === element.id)
  const center = elementCenter(element.geometry)
  tooltip.value = {
    entity: linked
      ? entityForPoi(linked)
      : entityForElement(element, linkedEntityIdForElement(element.id)),
    x: center.col * props.cell,
    y: center.row * props.cell,
  }
}

function hideTooltip() {
  tooltip.value = null
}
</script>

<template>
  <LocalMapCanvas
    :scene="gameStore.currentScene"
    :cell="cell"
    mode="exploration"
    :selected-element-id="selectedElementId"
    @element-click="onElementClick"
    @element-hover="showElementTooltip"
  >
    <PoiToken
      v-for="poi in pois"
      :key="poi.id"
      :poi="poi"
      :cell="cell"
      :selected="isSelected(poi.id)"
      :highlighted="isHighlighted(poi.id)"
      @click="onClick"
      @tooltip-show="showPoiTooltip"
      @tooltip-hide="hideTooltip"
    />

    <HeroToken
      v-for="hero in party"
      :key="hero.id"
      :hero="hero"
      :cell="cell"
      :selected="isSelected(hero.id)"
      :highlighted="isHighlighted(hero.id)"
      @click="onClick"
      @tooltip-show="showHeroTooltip"
      @tooltip-hide="hideTooltip"
    />

    <MapTooltip
      v-if="tooltip"
      :entity="tooltip.entity"
      :x="tooltip.x"
      :y="tooltip.y"
      :bounds-width="mapWidth"
      :bounds-height="mapHeight"
    />
  </LocalMapCanvas>
</template>
