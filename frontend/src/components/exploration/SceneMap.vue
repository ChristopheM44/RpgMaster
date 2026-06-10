<script setup lang="ts">
// Scène locale 3D (exploration). Même contrat qu'avant la refonte : sélection
// via sessionStore.selectEntity (POI lié prioritaire sur élément interactif),
// tooltip MapTooltip alimenté par useMapInspectables — seul le rendu change
// (Scene3DCanvas + buildSceneSpec à la place du SVG LocalMapCanvas).
import { computed, ref } from 'vue'
import { useSessionStore } from '../../stores/session'
import { useGameStore } from '../../stores/game'
import { useExplorationParty } from '../../composables/useExplorationParty'
import { useExplorationPois } from '../../composables/useExplorationPois'
import {
  entityForElement,
  entityForHero,
  entityForPoi,
  type MapInspectableEntity,
  useMapInspectables,
} from '../../composables/useMapInspectables'
import Scene3DCanvas from '../scene3d/Scene3DCanvas.vue'
import MapTooltip from './MapTooltip.vue'
import { buildSceneSpec } from '../../engine3d/adapters/sceneAdapter'
import type { PickResult } from '../../engine3d/types'

const sessionStore = useSessionStore()
const gameStore = useGameStore()
const { party } = useExplorationParty()
const { pois } = useExplorationPois()
const { findElement, linkedEntityIdForElement } = useMapInspectables()

const host = ref<HTMLDivElement | null>(null)
const tooltip = ref<{ entity: MapInspectableEntity; x: number; y: number } | null>(null)
const bounds = ref({ width: 640, height: 480 })

const spec = computed(() => buildSceneSpec({
  scene: gameStore.currentScene,
  heroes: party.value,
  pois: pois.value,
  selectedId: sessionStore.selectedId,
  highlightedIds: sessionStore.highlightedIds,
}))

function onPick(pick: PickResult): void {
  if (pick.type === 'token') {
    sessionStore.selectEntity(pick.id)
    return
  }
  if (pick.type === 'element') {
    const element = findElement(pick.id)
    if (!element) return
    // Parité SVG : un élément lié à un POI sélectionne le POI.
    const linked = pois.value.find((poi) => poi.elementId === element.id)
    if (linked) {
      sessionStore.selectEntity(linked.id)
      return
    }
    if (element.interactive) sessionStore.selectEntity(element.id)
  }
}

function onHover(pick: PickResult | null, screen: { x: number; y: number }): void {
  if (!pick || pick.type === 'cell') {
    tooltip.value = null
    return
  }
  if (host.value) {
    bounds.value = { width: host.value.clientWidth, height: host.value.clientHeight }
  }

  let entity: MapInspectableEntity | null = null
  if (pick.type === 'token') {
    const hero = party.value.find((item) => item.id === pick.id)
    if (hero) {
      entity = entityForHero(hero)
    } else {
      const poi = pois.value.find((item) => item.id === pick.id)
      if (poi) entity = entityForPoi(poi)
    }
  } else {
    const element = findElement(pick.id)
    if (element) {
      const linked = pois.value.find((poi) => poi.elementId === element.id)
      entity = linked ? entityForPoi(linked) : entityForElement(element, linkedEntityIdForElement(element.id))
    }
  }

  tooltip.value = entity ? { entity, x: screen.x, y: screen.y } : null
}
</script>

<template>
  <div ref="host" class="scene-map3d">
    <Scene3DCanvas :spec="spec" @pick="onPick" @hover="onHover">
      <MapTooltip
        v-if="tooltip"
        :entity="tooltip.entity"
        :x="tooltip.x"
        :y="tooltip.y"
        :bounds-width="bounds.width"
        :bounds-height="bounds.height"
      />
    </Scene3DCanvas>
  </div>
</template>

<style scoped>
.scene-map3d {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 260px;
}
</style>
