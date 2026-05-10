<script setup lang="ts">
import { computed } from 'vue'
import { useCharacterStore } from '../../stores/character'

const charStore = useCharacterStore()
const totalCoins = computed(() =>
  charStore.sessionCharacters.reduce((sum, character) => sum + character.gp + character.sp + character.cp, 0),
)
</script>

<template>
  <div v-if="totalCoins > 0" class="pointer-events-none fixed right-4 top-20 z-50 hidden md:block">
    <div class="rpg-save-popover rounded-lg border px-3 py-2 text-[11px] shadow-xl">
      <span class="rpg-text-gold font-bold">Butin</span>
      <span class="rpg-text-muted ml-2">inventaires synchronisés</span>
    </div>
  </div>
</template>
