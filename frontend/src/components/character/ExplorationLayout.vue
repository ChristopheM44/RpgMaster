<script setup lang="ts">
import { ref } from 'vue'
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
const showSceneMap = ref(true)

function handleSceneExit(_exitId: string, label: string) {
  emit('action', 'free_text', `Je me dirige vers ${label}.`)
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
        <button
          class="flex w-full items-center justify-between px-4 py-2 text-left"
          type="button"
          @click="showSceneMap = !showSceneMap"
        >
          <span class="rpg-eyebrow" :style="{ color: 'var(--color-gold)' }">Scène visible</span>
          <span class="text-xs" :style="{ color: 'var(--color-text-muted)' }">
            {{ showSceneMap ? 'Replier' : 'Déplier' }}
          </span>
        </button>
        <div v-if="showSceneMap" class="h-[360px] min-h-0">
          <Battlemap
            mode="exploration"
            :scene-layout="gameStore.currentScene"
            @scene-exit="handleSceneExit"
          />
        </div>
      </div>
      <NarrativeLog />
    </section>

    <AdventureLogPanel @open-sheet="(id: string) => $emit('openSheet', id)" />
  </div>
</template>
