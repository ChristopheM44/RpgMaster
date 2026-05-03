<script setup lang="ts">
import { computed, ref } from 'vue'
import { useCharacterStore } from '../../stores/character'
import { useGameStore } from '../../stores/game'
import NarrativeLog from '../narrative/NarrativeLog.vue'
import ActionBar from '../common/ActionBar.vue'
import Battlemap from './Battlemap.vue'
import InitiativeTracker from './InitiativeTracker.vue'
import SelectedDetailPanel from './SelectedDetailPanel.vue'

const emit = defineEmits<{
  action: [actionType: string, content?: string, targetId?: string, extra?: Record<string, unknown>]
  endCombat: []
  openSheet: [id: string]
}>()

const gameStore = useGameStore()
const charStore = useCharacterStore()

const isMyTurn = computed(() => gameStore.currentTurnId === charStore.myCharacter?.id)
const speedM = computed(() => {
  const movement = gameStore.combatants.find((c) => c.id === charStore.myCharacter?.id)?.action_economy?.movement
  return movement ? movement * 0.3048 : 9
})

type MapInteractionMode = 'inspect' | 'move' | 'attack' | 'spell'
const mapMode = ref<MapInteractionMode>('inspect')

function handleMapMove(col: number, row: number) {
  emit('action', 'move', undefined, undefined, { col, row })
  mapMode.value = 'inspect'
}

function handleMapTarget(targetId: string, mode: MapInteractionMode) {
  gameStore.setSelectedCombatant(targetId)
  if (mode === 'attack') {
    emit('action', 'attack', undefined, targetId)
    mapMode.value = 'inspect'
  }
}
</script>

<template>
  <div class="hidden min-h-0 flex-1 overflow-hidden md:flex">
    <InitiativeTracker />

    <main class="flex min-w-0 flex-1 flex-col overflow-hidden">
      <div class="flex min-h-0 flex-[1.45] overflow-hidden">
        <Battlemap
          :my-character-id="charStore.myCharacter?.id"
          :is-my-turn="isMyTurn"
          :speed-m="speedM"
          :interaction-mode="mapMode"
          @move="handleMapMove"
          @target="handleMapTarget"
          @mode-change="(mode) => { mapMode = mode }"
        />
      </div>

      <section
        class="flex min-h-[220px] flex-1 flex-col overflow-hidden border-t"
        :style="{ borderColor: 'var(--color-border)' }"
      >
        <NarrativeLog />
      </section>

      <ActionBar
        variant="combat-immersive"
        @action="(...args) => emit('action', ...args)"
        @map-mode="(mode) => { mapMode = mode }"
      />
    </main>

    <SelectedDetailPanel @open-sheet="(id) => emit('openSheet', id)" />
  </div>
</template>
