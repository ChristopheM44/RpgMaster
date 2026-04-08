<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useGameStore } from '../stores/game'
import { useCharacterStore } from '../stores/character'
import { useSessionStore } from '../stores/session'
import { useWebSocket } from '../composables/useWebSocket'
import { gameApi } from '../services/api'
import NarrativeLog from '../components/narrative/NarrativeLog.vue'
import CombatTracker from '../components/combat/CombatTracker.vue'
import TacticalGrid from '../components/combat/TacticalGrid.vue'
import CharacterSummary from '../components/character/CharacterSummary.vue'
import ActionBar from '../components/common/ActionBar.vue'
import SaveLoadPanel from '../components/ui/SaveLoadPanel.vue'
import AdventureStartModal from '../components/ui/AdventureStartModal.vue'

const route = useRoute()
const router = useRouter()
const sessionId = route.params.id as string

const gameStore = useGameStore()
const charStore = useCharacterStore()
const sessionStore = useSessionStore()

const { connect, disconnect, reconnect, sendAction, reconnectCount, isReconnecting, isDisconnected } = useWebSocket(sessionId)

const startingGame = ref(false)
const showSaveLoad = ref(false)
const showStartModal = ref(false)

// Mobile tab navigation
type MobileTab = 'recit' | 'combat' | 'perso'
const activeTab = ref<MobileTab>('recit')

async function initSession() {
  gameStore.reset()
  disconnect()

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

  // Connexion initiale : utiliser le premier personnage humain pour le message join WS
  const humanChar = charStore.sessionCharacters.find((c) => !c.is_ai)
  if (humanChar) charStore.setMyCharacter(humanChar)

  try {
    const history = await gameApi.getHistory(sessionId)
    if (history.messages.length > 0) {
      gameStore.restoreHistory(history.messages)
    }
  } catch {
    // L'historique est facultatif — ne pas bloquer la connexion
  }

  connect(charStore.myCharacter?.id)
}

async function handleLoadComplete() {
  showSaveLoad.value = false
  await initSession()
}

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

async function handleStartConfirm(mode: 'libre' | 'script' | 'auto', script?: string) {
  showStartModal.value = false
  startingGame.value = true
  try {
    const body =
      mode === 'script' && script
        ? { adventure_script: script }
        : mode === 'auto'
          ? { auto_generate: true }
          : undefined
    await gameApi.start(sessionId, body)
    // Le serveur diffuse phase_change + session_state + narration via WS
  } catch {
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

function resetCombat() {
  sendAction('reset_combat', undefined, charStore.myCharacter?.id)
}

function dismissError() {
  gameStore.setError(null)
}

function handleMove(col: number, row: number) {
  const charId = charStore.myCharacter?.id
  sendAction('move', `${col},${row}`, charId)
}

const isMyTurn = computed(() =>
  gameStore.currentTurnId !== null &&
  gameStore.currentTurnId === charStore.myCharacter?.id
)

// Hot-seat : quand le tour change, mettre à jour le personnage actif si c'est un humain
watch(() => gameStore.currentTurnId, (turnId) => {
  if (!turnId) return
  const activeHuman = charStore.sessionCharacters.find(
    (c) => c.id === turnId && !c.is_ai,
  )
  if (activeHuman) charStore.setMyCharacter(activeHuman)
})

// Nom du combattant dont c'est le tour (pour l'indicateur)
const activeCombatantName = computed(() => {
  const c = gameStore.combatants.find((c) => c.id === gameStore.currentTurnId)
  return c?.name ?? null
})

const mySpeed = computed(() => {
  const char = charStore.myCharacter
  if (!char) return 9
  // Vitesse de déplacement en mètres (SRD FR : 9 m = 30 ft)
  return 9
})

onMounted(initSession)

onUnmounted(() => {
  disconnect()
})
</script>

<template>
  <div class="relative flex h-full flex-col overflow-hidden bg-ink text-parchment">

    <!-- Error banner -->
    <div
      v-if="gameStore.error"
      class="flex items-center justify-between gap-3 bg-blood/20 border-b border-blood/40 px-4 py-2 text-sm text-blood shrink-0"
    >
      <span>⚠ {{ gameStore.error }}</span>
      <button class="text-blood/70 hover:text-blood transition-colors" @click="dismissError">✕</button>
    </div>

    <!-- Reconnecting banner -->
    <div
      v-if="isReconnecting"
      class="flex items-center gap-2 bg-arcane/10 border-b border-arcane/30 px-4 py-1.5 text-xs text-arcane/80 shrink-0"
    >
      <span class="animate-pulse">◉</span>
      <span>Reconnexion en cours... (tentative {{ reconnectCount }}/5)</span>
    </div>

    <!-- Disconnected banner with manual reconnect -->
    <div
      v-if="isDisconnected"
      class="flex items-center justify-between gap-3 bg-blood/10 border-b border-blood/30 px-4 py-1.5 text-xs text-blood/90 shrink-0"
    >
      <span>● Connexion perdue</span>
      <button
        class="rounded border border-blood/50 bg-blood/15 px-3 py-0.5 font-semibold hover:bg-blood/30 transition-colors"
        @click="reconnect"
      >
        Reconnecter
      </button>
    </div>

    <!-- Top bar -->
    <header class="flex items-center justify-between border-b border-gold/20 bg-ink/90 px-3 py-2 shrink-0 gap-2">
      <div class="flex items-center gap-2 shrink-0 min-w-0">
        <button
          class="text-parchment/50 hover:text-parchment transition-colors text-sm shrink-0"
          @click="router.push({ name: 'lobby' })"
        >←</button>
        <span class="text-gold/30 shrink-0">|</span>
        <h1 class="font-semibold text-parchment truncate text-sm">
          {{ sessionStore.currentSession?.name ?? 'Session' }}
        </h1>
      </div>

      <!-- Game control buttons -->
      <div class="flex items-center gap-1.5 shrink-0">
        <!-- Start game (lobby / character_creation phase) -->
        <button
          v-if="needsStart"
          :disabled="startingGame || !gameStore.connected"
          class="rounded border border-gold/60 bg-gold/15 px-3 py-1 text-xs font-semibold text-gold hover:bg-gold/25 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          @click="showStartModal = true"
        >
          {{ startingGame ? '...' : "Lancer" }}
        </button>

        <!-- Start combat (exploration phase) -->
        <button
          v-if="canStartCombat"
          class="rounded border border-blood/60 bg-blood/10 px-2 py-1 text-xs font-semibold text-blood hover:bg-blood/20 transition-colors"
          @click="startCombat"
        >
          ⚔
        </button>

        <!-- Take rest (exploration / encounter_end) -->
        <button
          v-if="canRest"
          class="rounded border border-arcane/40 bg-arcane/10 px-2 py-1 text-xs font-semibold text-arcane hover:bg-arcane/20 transition-colors"
          @click="takeRest"
        >
          ☽
        </button>

        <!-- Reset combat [TEST] -->
        <button
          v-if="gameStore.isInCombat"
          class="rounded border border-parchment/30 bg-parchment/5 px-2 py-1 text-xs font-semibold text-parchment/50 hover:bg-parchment/10 hover:text-parchment/80 transition-colors"
          title="[TEST] Sortir du combat et restaurer les PV"
          @click="resetCombat"
        >
          ✕
        </button>
      </div>

      <div class="flex items-center gap-2 text-sm shrink-0">
        <!-- Connection status dot -->
        <span
          class="inline-block h-2 w-2 rounded-full shrink-0"
          :class="{
            'bg-green-500': gameStore.connected,
            'bg-arcane animate-pulse': isReconnecting,
            'bg-blood': isDisconnected,
            'bg-parchment/30': !gameStore.connected && !isReconnecting && !isDisconnected,
          }"
          :title="gameStore.connected ? 'Connecté' : isReconnecting ? 'Reconnexion...' : 'Déconnecté'"
        />

        <!-- Phase (desktop only) -->
        <span class="hidden md:flex items-center gap-1.5">
          <span class="text-parchment/40 text-xs">Phase :</span>
          <span class="font-semibold text-gold text-xs capitalize">{{ gameStore.phase }}</span>
        </span>
        <button
          class="rounded border border-parchment/20 bg-parchment/5 px-2 py-1 text-xs text-parchment/60 hover:text-parchment hover:border-parchment/40 transition-colors"
          @click="showSaveLoad = !showSaveLoad"
        >
          {{ showSaveLoad ? '✕' : '💾' }}
        </button>
      </div>
    </header>

    <!-- Save/Load panel (slide-in overlay) -->
    <div
      v-if="showSaveLoad"
      class="absolute top-10 right-0 z-50 w-72 border border-gold/30 bg-ink shadow-lg rounded-bl-lg p-4"
    >
      <h2 class="mb-3 text-sm font-semibold text-gold">Sauvegardes</h2>
      <SaveLoadPanel :session-id="sessionId" @load-complete="handleLoadComplete" />
    </div>

    <!-- ─── Desktop layout: 3 panels (md+) ─────────────────────────────────── -->
    <div class="hidden md:flex flex-1 min-h-0 overflow-hidden">

      <!-- Left panel: NarrativeLog (60%) -->
      <section class="flex w-[60%] flex-col min-h-0 overflow-hidden border-r border-gold/20">
        <NarrativeLog />
      </section>

      <!-- Right panel (40%) -->
      <section class="flex w-[40%] flex-col min-h-0 overflow-hidden">

        <!-- TacticalGrid (combat only) -->
        <div v-if="gameStore.isInCombat && gameStore.gridConfig" class="shrink-0 border-b border-gold/20 p-2">
          <TacticalGrid
            :my-character-id="charStore.myCharacter?.id"
            :is-my-turn="isMyTurn"
            :speed-m="mySpeed"
            @move="handleMove"
          />
        </div>

        <!-- CombatTracker (top right) -->
        <div class="flex flex-col flex-1 min-h-0 overflow-hidden border-b border-gold/20">
          <CombatTracker />
        </div>

        <!-- CharacterSummary (bottom right) -->
        <div class="flex flex-col flex-1 min-h-0 overflow-hidden">
          <CharacterSummary />
        </div>

      </section>
    </div>

    <!-- ─── Mobile layout: single panel with tab nav ────────────────────────── -->
    <div class="flex md:hidden flex-1 min-h-0 flex-col overflow-hidden">

      <!-- Active panel -->
      <div class="flex flex-col flex-1 min-h-0 overflow-hidden">
        <NarrativeLog v-if="activeTab === 'recit'" />
        <CombatTracker v-else-if="activeTab === 'combat'" />
        <CharacterSummary v-else-if="activeTab === 'perso'" />
      </div>

      <!-- Mobile tab bar -->
      <nav class="flex border-t border-gold/20 bg-ink/90 shrink-0">
        <button
          v-for="tab in ([
            { id: 'recit', label: 'Récit', icon: '📜' },
            { id: 'combat', label: 'Combat', icon: '⚔' },
            { id: 'perso', label: 'Perso', icon: '👤' },
          ] as const)"
          :key="tab.id"
          class="flex flex-1 flex-col items-center gap-0.5 py-2 text-xs transition-colors"
          :class="activeTab === tab.id
            ? 'text-gold border-t-2 border-gold -mt-px'
            : 'text-parchment/40 hover:text-parchment/70'"
          @click="activeTab = tab.id"
        >
          <span class="text-base leading-none">{{ tab.icon }}</span>
          <span>{{ tab.label }}</span>
        </button>
      </nav>
    </div>

    <!-- Tour actif (hot-seat) : indique quel personnage joue -->
    <div
      v-if="gameStore.isInCombat && activeCombatantName"
      class="shrink-0 border-t border-gold/10 bg-ink/60 px-4 py-1 text-center text-xs"
      :class="isMyTurn ? 'text-gold' : 'text-parchment/40'"
    >
      <span v-if="isMyTurn">Tour de <strong>{{ activeCombatantName }}</strong> — à vous de jouer !</span>
      <span v-else>Tour de <strong>{{ activeCombatantName }}</strong>...</span>
    </div>

    <!-- ActionBar pinned at bottom, full width -->
    <ActionBar @action="handleAction" />

    <!-- Adventure start modal -->
    <AdventureStartModal
      v-if="showStartModal"
      @confirm="handleStartConfirm"
      @cancel="showStartModal = false"
    />
  </div>
</template>
