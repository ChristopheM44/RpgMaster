<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../../stores/game'
import CollapsibleSection from './CollapsibleSection.vue'
import ChroniclersBook from '../journal/ChroniclersBook.vue'

const gameStore = useGameStore()
const chronicleCount = computed(() => gameStore.chronicle.length)
</script>

<template>
  <CollapsibleSection id="memory" eyebrow="◉ Carnet du chroniqueur" :count="chronicleCount">
    <ChroniclersBook />
  </CollapsibleSection>
</template>
