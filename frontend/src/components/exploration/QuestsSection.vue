<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../../stores/game'
import CollapsibleSection from './CollapsibleSection.vue'
import QuestPanel from '../journal/QuestPanel.vue'

const gameStore = useGameStore()
const activeQuestsCount = computed(
  () => gameStore.quests.filter((q) => q.status === 'active').length,
)
</script>

<template>
  <CollapsibleSection id="quests" eyebrow="◈ Quêtes en cours" :count="activeQuestsCount">
    <QuestPanel />
  </CollapsibleSection>
</template>
