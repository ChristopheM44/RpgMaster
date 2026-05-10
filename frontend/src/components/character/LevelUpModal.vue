<script setup lang="ts">
import { computed } from 'vue'
import type { Character } from '../../types'

const props = defineProps<{ characters: Character[]; visible: boolean }>()
const emit = defineEmits<{
  asiChoice: [payload: { characterId: string; mode: 'plus_two'; ability: string }]
}>()

const pending = computed(() => props.characters.find((character) => character.pending_asi) ?? null)
const ABILITIES = ['str', 'dex', 'con', 'int', 'wis', 'cha']
</script>

<template>
  <div
    v-if="visible || pending"
    class="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4"
  >
    <div class="rpg-save-popover w-full max-w-md rounded-xl border p-5 shadow-2xl">
      <div class="rpg-eyebrow rpg-text-gold mb-2">Montée de niveau</div>
      <h2 class="rpg-text-main font-display text-xl font-bold">Progression appliquée</h2>
      <p class="rpg-text-muted mt-2 text-sm">
        Les PV, dés de vie et emplacements de sorts ont été mis à jour.
      </p>

      <div v-if="pending" class="mt-4">
        <div class="rpg-text-muted mb-2 text-xs">
          ASI en attente pour {{ pending.name }}
        </div>
        <div class="grid grid-cols-3 gap-2">
          <button
            v-for="ability in ABILITIES"
            :key="ability"
            class="rpg-btn-secondary justify-center !py-1.5 !text-[11px]"
            @click="emit('asiChoice', { characterId: pending.id, mode: 'plus_two', ability })"
          >
            +2 {{ ability.toUpperCase() }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
