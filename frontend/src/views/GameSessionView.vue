<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useGameStore } from '../stores/game'
import { useCharacterStore } from '../stores/character'
import { useSessionStore } from '../stores/session'
import { useWebSocket } from '../composables/useWebSocket'
import { gameApi } from '../services/api'
import NarrativeLog from '../components/narrative/NarrativeLog.vue'
import CombatTracker from '../components/combat/CombatTracker.vue'
import CharacterSummary from '../components/character/CharacterSummary.vue'
import ActionBar from '../components/common/ActionBar.vue'
import SaveLoadPanel from '../components/ui/SaveLoadPanel.vue'

const route = useRoute()
const router = useRouter()
const sessionId = route.params.id as string

const gameStore = useGameStore()
const charStore = useCharacterStore()
const sessionStore = useSessionStore()

const { connect, disconnect, sendAction } = useWebSocket(sessionId)

const startingGame = ref(false)
const showSaveLoad = ref(false)

// Phase-based UI flags
const needsStart = computed(() =>
  ['lobby', 'character_creation'].includes(gameStore.phase),
)
const canStartCombat = computed(() => gameStore.phase === 'exploration')
const canRest = computed(() =>
  ['exploration', 'encounter_end'].includes(gameStore.phase),
)

function handleAction(
  actionType: string,
  content?: string,
  targetId?: string,
  extra?: Record<string, unknown>,
) {
  const charId = charStore.myCharacter?.id

  if (actionType === 'free_text' && content) {
    gameStore.addPlayerEntry(content, charStore.myCharacter?.name)
  }

  sendAction(actionType, content, charId, targetId, extra)
}

async function startGame() {
  startingGame.value = true
  try {
    await gameApi.start(sessionId)
    // Server will broadcast phase_change + session_state + narration via WS
  } catch (e) {
    gameStore.setError('Impossible de démarrer la partie.')
  } finally {
    startingGame.value = false
  }
}

function startCombat() {
  sendAction('start_combat', undefined, charStore.myCharacter?.id)
}

function takeRest() {
  sendAction('take_rest', undefined, charStore.myCharacter?.id)
}

onMounted(async () => {
  gameStore.reset()

  const session = sessionStore.currentSession
  if (!session) {
    try {
      const loaded = await import('../services/api').then(m => m.sessionApi.get(sessionId))
      sessionStore.setCurrentSession(loaded)
    } catch {
      router.push({ name: 'lobby' })
      return
    }
  }

  await charStore.loadSessionCharacters(sessionId)

  const humanChar = charStore.sessionCharacters.find((c) => !c.is_ai)
  if (humanChar) charStore.setMyCharacter(humanChar)

  // Restaurer l'historique narratif depuis la DB avant d'ouvrir le WebSocket
  try {
    const history = await gameApi.getHistory(sessionId)
    if (history.messages.length > 0) {
      gameStore.restoreHistory(history.messages)
    }
  } catch {
    // L'historique est facultatif — ne pas bloquer la connexion
  }

  connect(charStore.myCharacter?.id)
})

onUnmounted(() => {
  disconnect()
})
</script>

<template>
  <div class="relative flex h-screen flex-col overflow-hidden bg-ink text-parchment">

    <!-- Top bar -->
    <header class="flex items-center justify-between border-b border-gold/20 bg-ink/90 px-6 py-2 shrink-0 gap-4">
      <div class="flex items-center gap-3 shrink-0">
        <button
          class="text-parchment/50 hover:text-parchment transition-colors text-sm"
          @click="router.push({ name: 'lobby' })"
        >← Lobby</button>
        <span class="text-gold/30">|</span>
        <h1 class="font-semibold text-parchment">
          {{ sessionStore.currentSession?.name ?? 'Session' }}
        </h1>
      </div>

      <!-- Game control buttons -->
      <div class="flex items-center gap-2">
        <!-- Start game (lobby / character_creation phase) -->
        <button
          v-if="needsStart"
          :disabled="startingGame || !gameStore.connected"
          class="rounded border border-gold/60 bg-gold/15 px-4 py-1 text-sm font-semibold text-gold hover:bg-gold/25 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          @click="startGame"
        >
          {{ startingGame ? 'Démarrage...' : 'Démarrer la partie' }}
        </button>

        <!-- Start combat (exploration phase) -->
        <button
          v-if="canStartCombat"
          class="rounded border border-blood/60 bg-blood/10 px-3 py-1 text-sm font-semibold text-blood hover:bg-blood/20 transition-colors"
          @click="startCombat"
        >
          ⚔ Combat
        </button>

        <!-- Take rest (exploration / encounter_end) -->
        <button
          v-if="canRest"
          class="rounded border border-arcane/40 bg-arcane/10 px-3 py-1 text-sm font-semibold text-arcane hover:bg-arcane/20 transition-colors"
          @click="takeRest"
        >
          ☽ Repos
        </button>
      </div>

      <div class="flex items-center gap-3 text-sm shrink-0">
        <span class="text-parchment/40">Phase :</span>
        <span class="font-semibold text-gold capitalize">{{ gameStore.phase }}</span>
        <button
          class="ml-2 rounded border border-parchment/20 bg-parchment/5 px-3 py-1 text-xs text-parchment/60 hover:text-parchment hover:border-parchment/40 transition-colors"
          @click="showSaveLoad = !showSaveLoad"
        >
          {{ showSaveLoad ? '✕ Fermer' : '💾 Sauvegardes' }}
        </button>
      </div>
    </header>

    <!-- Save/Load panel (slide-in overlay) -->
    <div
      v-if="showSaveLoad"
      class="absolute top-12 right-0 z-50 w-80 border border-gold/30 bg-ink shadow-lg rounded-bl-lg p-4"
    >
      <h2 class="mb-3 text-sm font-semibold text-gold">Sauvegardes</h2>
      <SaveLoadPanel :session-id="sessionId" />
    </div>

    <!-- Main layout: grows to fill remaining height -->
    <div class="flex flex-1 overflow-hidden">

      <!-- Left panel: NarrativeLog (60%) -->
      <section class="flex w-[60%] flex-col overflow-hidden border-r border-gold/20">
        <NarrativeLog />
      </section>

      <!-- Right panel (40%) -->
      <section class="flex w-[40%] flex-col overflow-hidden">

        <!-- CombatTracker (top right, ~50% of right panel) -->
        <div class="flex-1 overflow-hidden border-b border-gold/20">
          <CombatTracker />
        </div>

        <!-- CharacterSummary (bottom right, ~50% of right panel) -->
        <div class="flex-1 overflow-hidden">
          <CharacterSummary />
        </div>

      </section>
    </div>

    <!-- ActionBar pinned at bottom, full width -->
    <ActionBar @action="handleAction" />
  </div>
</template>
