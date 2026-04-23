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

  const humanChar = charStore.sessionCharacters.find((c) => !c.is_ai)
  if (humanChar) charStore.setMyCharacter(humanChar)

  try {
    const history = await gameApi.getHistory(sessionId)
    if (history.messages.length > 0) {
      gameStore.restoreHistory(history.messages)
    }
  } catch {
    // optional
  }

  connect(charStore.myCharacter?.id)
}

async function handleLoadComplete() {
  showSaveLoad.value = false
  await initSession()
}

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
  } catch {
    gameStore.setError('Impossible de démarrer la partie.')
  } finally {
    startingGame.value = false
  }
}

function startCombat() { sendAction('start_combat', undefined, charStore.myCharacter?.id) }
function takeRest()    { sendAction('take_rest',    undefined, charStore.myCharacter?.id) }
function resetCombat() { sendAction('reset_combat', undefined, charStore.myCharacter?.id) }

function dismissError() { gameStore.setError(null) }

function handleMove(col: number, row: number) {
  const charId = charStore.myCharacter?.id
  sendAction('move', `${col},${row}`, charId)
}

const isMyTurn = computed(() =>
  gameStore.currentTurnId !== null &&
  gameStore.currentTurnId === charStore.myCharacter?.id
)

watch(() => gameStore.currentTurnId, (turnId) => {
  if (!turnId) return
  const activeHuman = charStore.sessionCharacters.find(
    (c) => c.id === turnId && !c.is_ai,
  )
  if (activeHuman) charStore.setMyCharacter(activeHuman)
})

const activeCombatantName = computed(() => {
  const c = gameStore.combatants.find((c) => c.id === gameStore.currentTurnId)
  return c?.name ?? null
})

const mySpeed = computed(() => {
  const char = charStore.myCharacter
  if (!char) return 9
  return 9
})

/** Phase → libellé FR éditorial */
const PHASE_LABELS: Record<string, string> = {
  lobby: 'Salle d\'attente',
  character_creation: 'Création de personnage',
  exploration: 'Exploration',
  encounter_start: 'Début de rencontre',
  combat: 'Combat',
  encounter_end: 'Fin de rencontre',
  rest: 'Repos',
  level_up: 'Montée de niveau',
  session_end: 'Session terminée',
}

const phaseLabel = computed(() => PHASE_LABELS[gameStore.phase] ?? gameStore.phase)

onMounted(initSession)
onUnmounted(() => { disconnect() })
</script>

<template>
  <div
    class="relative flex h-full flex-col overflow-hidden"
    :style="{ background: 'var(--color-bg)', color: 'var(--color-parchment)' }"
  >

    <!-- Error banner -->
    <div
      v-if="gameStore.error"
      class="flex shrink-0 items-center justify-between gap-3 border-b px-4 py-2 text-sm"
      :style="{
        background: 'rgba(232,69,69,0.12)',
        borderColor: 'rgba(232,69,69,0.3)',
        color: 'var(--color-blood-light)',
      }"
    >
      <span>⚠ {{ gameStore.error }}</span>
      <button class="opacity-70 transition hover:opacity-100" @click="dismissError">✕</button>
    </div>

    <!-- Reconnecting banner -->
    <div
      v-if="isReconnecting"
      class="flex shrink-0 items-center gap-2 border-b px-4 py-1.5 text-xs"
      :style="{
        background: 'rgba(192,144,255,0.08)',
        borderColor: 'rgba(192,144,255,0.25)',
        color: 'var(--color-arcane-light)',
      }"
    >
      <span class="rpg-pulse">◉</span>
      <span class="tracking-wide">Reconnexion en cours… (tentative {{ reconnectCount }}/5)</span>
    </div>

    <!-- Disconnected banner -->
    <div
      v-if="isDisconnected"
      class="flex shrink-0 items-center justify-between gap-3 border-b px-4 py-1.5 text-xs"
      :style="{
        background: 'rgba(232,69,69,0.08)',
        borderColor: 'rgba(232,69,69,0.25)',
        color: 'var(--color-blood-light)',
      }"
    >
      <span>● Connexion perdue</span>
      <button class="rpg-btn-tonal tone-blood !py-1 !px-3 !text-[10px]" @click="reconnect">
        Reconnecter
      </button>
    </div>

    <!-- Top bar -->
    <header
      class="flex shrink-0 items-center justify-between gap-3 border-b px-4 py-2.5"
      :style="{
        borderColor: 'var(--color-border)',
        background: 'linear-gradient(180deg, var(--color-bg-elev), rgba(24,22,35,0.9))',
      }"
    >
      <!-- Left cluster : back + title -->
      <div class="flex min-w-0 shrink-0 items-center gap-3">
        <button
          class="text-base transition"
          :style="{ color: 'var(--color-text-muted)' }"
          @click="router.push({ name: 'lobby' })"
        >←</button>
        <div class="h-5 w-px" :style="{ background: 'var(--color-border-strong)' }" />
        <h1
          class="truncate font-display text-sm font-bold tracking-[0.1em]"
          :style="{ color: 'var(--color-parchment)' }"
        >{{ sessionStore.currentSession?.name ?? 'SESSION' }}</h1>
      </div>

      <!-- Centre : game actions -->
      <div class="flex shrink-0 items-center gap-1.5">
        <button
          v-if="needsStart"
          :disabled="startingGame || !gameStore.connected"
          class="rpg-btn-primary !py-1.5 !px-4 !text-[11px]"
          @click="showStartModal = true"
        >
          {{ startingGame ? '…' : 'Lancer ⚔' }}
        </button>

        <button
          v-if="canStartCombat"
          class="rpg-btn-tonal tone-blood"
          title="Déclencher un combat"
          @click="startCombat"
        >⚔ Combat</button>

        <button
          v-if="canRest"
          class="rpg-btn-tonal tone-arcane"
          title="Prendre un repos"
          @click="takeRest"
        >☽ Repos</button>

        <button
          v-if="gameStore.isInCombat"
          class="rpg-btn-tonal tone-gold !text-[10px]"
          title="[TEST] Sortir du combat et restaurer les PV"
          @click="resetCombat"
        >✕ Reset</button>
      </div>

      <!-- Right cluster : status + save -->
      <div class="flex shrink-0 items-center gap-3">
        <!-- Connection + phase -->
        <div class="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.15em]">
          <span
            class="inline-block h-2 w-2 shrink-0 rounded-full"
            :class="{ 'rpg-pulse': isReconnecting }"
            :style="{
              background: gameStore.connected
                ? 'var(--color-green)'
                : isReconnecting
                  ? 'var(--color-arcane)'
                  : isDisconnected
                    ? 'var(--color-blood)'
                    : 'var(--color-text-dim)',
              boxShadow: gameStore.connected ? '0 0 6px var(--color-green)' : 'none',
            }"
            :title="gameStore.connected ? 'Connecté' : isReconnecting ? 'Reconnexion...' : 'Déconnecté'"
          />
          <span class="hidden md:inline" :style="{ color: 'var(--color-text-muted)' }">Phase</span>
          <span
            class="hidden md:inline font-display font-bold"
            :style="{ color: 'var(--color-gold)' }"
          >{{ phaseLabel }}</span>
        </div>

        <button
          class="rpg-btn-secondary !py-1 !px-3 !text-[11px]"
          @click="showSaveLoad = !showSaveLoad"
        >
          {{ showSaveLoad ? '✕ Fermer' : '💾 Sauver' }}
        </button>
      </div>
    </header>

    <!-- Save/Load panel -->
    <div
      v-if="showSaveLoad"
      class="absolute right-0 top-[54px] z-50 w-80 rounded-bl-xl border p-5 shadow-2xl"
      :style="{
        borderColor: 'var(--color-border-strong)',
        background: 'var(--color-bg-elev)',
        boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
      }"
    >
      <div class="rpg-eyebrow mb-3">✦ Sauvegardes</div>
      <SaveLoadPanel :session-id="sessionId" @load-complete="handleLoadComplete" />
    </div>

    <!-- ─── Desktop layout: 3 panels (md+) ─────────────────────────────────── -->
    <div class="hidden min-h-0 flex-1 overflow-hidden md:flex">

      <!-- Left panel: NarrativeLog (60%) -->
      <section
        class="flex w-[60%] min-h-0 flex-col overflow-hidden border-r"
        :style="{ borderColor: 'var(--color-border)' }"
      >
        <NarrativeLog />
      </section>

      <!-- Right panel (40%) -->
      <section class="flex w-[40%] min-h-0 flex-col overflow-hidden">

        <!-- TacticalGrid (combat only) -->
        <div
          v-if="gameStore.isInCombat && gameStore.gridConfig"
          class="shrink-0 border-b p-3"
          :style="{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elev)' }"
        >
          <TacticalGrid
            :my-character-id="charStore.myCharacter?.id"
            :is-my-turn="isMyTurn"
            :speed-m="mySpeed"
            @move="handleMove"
          />
        </div>

        <!-- CombatTracker (top right) -->
        <div
          class="flex flex-1 min-h-0 flex-col overflow-hidden border-b"
          :style="{ borderColor: 'var(--color-border)' }"
        >
          <CombatTracker />
        </div>

        <!-- CharacterSummary (bottom right) -->
        <div class="flex flex-1 min-h-0 flex-col overflow-hidden">
          <CharacterSummary />
        </div>

      </section>
    </div>

    <!-- ─── Mobile layout: single panel with tab nav ────────────────────────── -->
    <div class="flex min-h-0 flex-1 flex-col overflow-hidden md:hidden">

      <!-- Active panel -->
      <div class="flex flex-1 min-h-0 flex-col overflow-hidden">
        <NarrativeLog v-if="activeTab === 'recit'" />
        <CombatTracker v-else-if="activeTab === 'combat'" />
        <CharacterSummary v-else-if="activeTab === 'perso'" />
      </div>

      <!-- Mobile tab bar -->
      <nav
        class="flex shrink-0 border-t"
        :style="{
          borderColor: 'var(--color-border)',
          background: 'var(--color-bg-elev)',
        }"
      >
        <button
          v-for="tab in ([
            { id: 'recit',  label: 'Récit',  icon: '❦' },
            { id: 'combat', label: 'Combat', icon: '⚔' },
            { id: 'perso',  label: 'Perso',  icon: '✦' },
          ] as const)"
          :key="tab.id"
          class="flex flex-1 flex-col items-center gap-1 py-2.5 text-[10px] font-bold uppercase tracking-[0.15em] transition-colors"
          :style="{
            color: activeTab === tab.id ? 'var(--color-gold)' : 'var(--color-text-muted)',
            borderTop: activeTab === tab.id ? '2px solid var(--color-gold)' : '2px solid transparent',
            marginTop: activeTab === tab.id ? '-1px' : '0',
            background: activeTab === tab.id ? 'rgba(240,199,100,0.05)' : 'transparent',
          }"
          @click="activeTab = tab.id"
        >
          <span
            class="text-base leading-none"
            :style="{ color: activeTab === tab.id ? 'var(--color-ember)' : 'inherit' }"
          >{{ tab.icon }}</span>
          <span>{{ tab.label }}</span>
        </button>
      </nav>
    </div>

    <!-- Tour actif (hot-seat) -->
    <div
      v-if="gameStore.isInCombat && activeCombatantName"
      class="shrink-0 border-t px-6 py-1.5 text-center text-[11px] tracking-[0.1em] font-semibold uppercase"
      :style="{
        borderColor: 'var(--color-border)',
        background: isMyTurn ? 'rgba(255,130,71,0.1)' : 'rgba(14,13,20,0.6)',
        color: isMyTurn ? 'var(--color-ember)' : 'var(--color-text-muted)',
      }"
    >
      <span v-if="isMyTurn">
        ▶ Tour de
        <strong class="font-display" :style="{ color: 'var(--color-gold)' }">{{ activeCombatantName }}</strong>
        — à vous de jouer !
      </span>
      <span v-else>
        Tour de
        <strong class="font-display" :style="{ color: 'var(--color-parchment)' }">{{ activeCombatantName }}</strong>
        …
      </span>
    </div>

    <!-- ActionBar pinned at bottom -->
    <ActionBar @action="handleAction" />

    <!-- Adventure start modal -->
    <AdventureStartModal
      v-if="showStartModal"
      @confirm="handleStartConfirm"
      @cancel="showStartModal = false"
    />
  </div>
</template>
