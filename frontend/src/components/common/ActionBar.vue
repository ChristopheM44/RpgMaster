<script setup lang="ts">
import { ref, computed } from 'vue'
import { useGameStore } from '../../stores/game'
import { useCharacterStore } from '../../stores/character'

const emit = defineEmits<{
  action: [actionType: string, content?: string, targetId?: string]
}>()

const gameStore = useGameStore()
const charStore = useCharacterStore()

const input = ref('')
const isMyTurn = computed(
  () => gameStore.currentTurnId === charStore.myCharacter?.id,
)

const combatActions = [
  { label: 'Attaquer', type: 'attack', icon: '⚔' },
  { label: 'Sort', type: 'cast_spell', icon: '✦' },
  { label: 'Objet', type: 'use_item', icon: '🎒' },
  { label: 'Dash', type: 'move', icon: '💨' },
  { label: 'Fin du tour', type: 'end_turn', icon: '⏭' },
]

function submitText() {
  const text = input.value.trim()
  if (!text) return
  emit('action', 'free_text', text)
  input.value = ''
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submitText()
  }
}
</script>

<template>
  <div class="border-t border-gold/20 bg-ink/80 px-4 py-3 space-y-2">
    <!-- Combat action buttons (visible only in combat + my turn) -->
    <div v-if="gameStore.isInCombat" class="flex flex-wrap gap-2">
      <button
        v-for="action in combatActions"
        :key="action.type"
        class="flex items-center gap-1.5 rounded border px-3 py-1.5 text-sm font-semibold transition-colors"
        :class="isMyTurn
          ? 'border-gold/40 text-parchment hover:bg-gold/10 hover:border-gold cursor-pointer'
          : 'border-gold/10 text-parchment/30 cursor-not-allowed'"
        :disabled="!isMyTurn"
        @click="emit('action', action.type)"
      >
        <span>{{ action.icon }}</span>
        <span>{{ action.label }}</span>
      </button>

      <span v-if="!isMyTurn" class="ml-auto text-xs text-parchment/30 self-center italic">
        En attente de votre tour...
      </span>
    </div>

    <!-- Free text input -->
    <div class="flex gap-2">
      <textarea
        v-model="input"
        rows="2"
        placeholder="Décrivez votre action ou parlez à vos compagnons..."
        class="flex-1 resize-none rounded border border-gold/20 bg-ink px-3 py-2 text-sm text-parchment placeholder-parchment/30 focus:border-gold/50 focus:outline-none"
        @keydown="onKeydown"
      />
      <button
        class="self-end rounded border border-gold/40 bg-gold/10 px-4 py-2 text-sm font-semibold text-gold hover:bg-gold/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        :disabled="!input.trim() || !gameStore.connected"
        @click="submitText"
      >
        Envoyer
      </button>
    </div>

    <!-- Connection status -->
    <div class="flex items-center gap-1.5 text-xs">
      <span
        class="inline-block h-2 w-2 rounded-full"
        :class="gameStore.connected ? 'bg-green-500' : 'bg-blood animate-pulse'"
      />
      <span class="text-parchment/40">
        {{ gameStore.connected ? `Connecté · Phase : ${gameStore.phase}` : 'Déconnecté' }}
      </span>
    </div>
  </div>
</template>
