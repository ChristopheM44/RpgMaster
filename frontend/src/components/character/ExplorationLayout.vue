<script setup lang="ts">
import { useGameStore } from '../../stores/game'
import NarrativeLog from '../narrative/NarrativeLog.vue'
import AdventureLogPanel from '../exploration/AdventureLogPanel.vue'
import Battlemap from '../combat/Battlemap.vue'
import { buildScenePoiInteractionPrompt } from '../../utils/scenePoiInteractions'
import type { ScenePoiInteraction } from '../../types'

const emit = defineEmits<{
  action: [actionType: string, content?: string, targetId?: string, extra?: Record<string, unknown>]
  startCombat: []
  openSheet: [id: string]
}>()

const gameStore = useGameStore()

function handleSceneExit(_exitId: string, label: string) {
  emit('action', 'free_text', `Je me dirige vers ${label}.`)
}

function handleScenePoi(_poiId: string, name: string, interaction?: ScenePoiInteraction) {
  emit('action', 'free_text', buildScenePoiInteractionPrompt(name, interaction))
}
</script>

<template>
  <div class="hidden min-h-0 flex-1 overflow-hidden md:flex">
    <section
      class="rpg-border flex min-h-0 flex-1 flex-col overflow-hidden border-r"
    >
      <div
        v-if="gameStore.currentScene"
        class="rpg-border shrink-0 border-b"
      >
        <Battlemap
          mode="exploration"
          :scene-layout="gameStore.currentScene"
          @scene-exit="handleSceneExit"
          @scene-poi="handleScenePoi"
        />
      </div>
      <NarrativeLog />
    </section>

    <AdventureLogPanel @open-sheet="(id: string) => $emit('openSheet', id)" />
  </div>
</template>
