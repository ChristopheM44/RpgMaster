<script setup lang="ts">
import { useGameStore } from '../../stores/game'
import NarrativeLog from '../narrative/NarrativeLog.vue'
import AdventureLogPanel from '../exploration/AdventureLogPanel.vue'
import Battlemap from '../combat/Battlemap.vue'

const emit = defineEmits<{
  action: [actionType: string, content?: string, targetId?: string, extra?: Record<string, unknown>]
  startCombat: []
  openSheet: [id: string]
}>()

const gameStore = useGameStore()

function handleSceneExit(_exitId: string, label: string) {
  emit('action', 'free_text', `Je me dirige vers ${label}.`)
}

function handleScenePoi(_poiId: string, name: string) {
  emit('action', 'free_text', `J'examine ${name}.`)
}
</script>

<template>
  <div class="hidden min-h-0 flex-1 overflow-hidden md:flex">
    <section
      class="flex min-h-0 flex-1 flex-col overflow-hidden border-r"
      :style="{ borderColor: 'var(--color-border)' }"
    >
      <div
        v-if="gameStore.currentScene"
        class="shrink-0 border-b"
        :style="{ borderColor: 'var(--color-border)' }"
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
