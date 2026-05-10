<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useGameStore } from '../stores/game'
import { useCharacterStore } from '../stores/character'
import { useSessionStore } from '../stores/session'
import { useWebSocket } from '../composables/useWebSocket'
import { gameApi } from '../services/api'
import NarrativeLog from '../components/narrative/NarrativeLog.vue'
import ExplorationLayout from '../components/character/ExplorationLayout.vue'
import CombatLayout from '../components/combat/CombatLayout.vue'
import Battlemap from '../components/combat/Battlemap.vue'
import MapTabs from '../components/map/MapTabs.vue'
import ActionBar from '../components/common/ActionBar.vue'
import SaveLoadPanel from '../components/ui/SaveLoadPanel.vue'
import AdventureStartModal from '../components/ui/AdventureStartModal.vue'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'
import RestDialog from '../components/ui/RestDialog.vue'
import { buildScenePoiInteractionPrompt } from '../utils/scenePoiInteractions'
import type { ScenePoiInteraction } from '../types'

const route = useRoute()
const router = useRouter()
const sessionId = route.params.id as string

const gameStore = useGameStore()
const charStore = useCharacterStore()
const sessionStore = useSessionStore()

const { connect, disconnect, reconnect, sendAction, toggleAiControl, triggerAiReactions, reconnectCount, isReconnecting, isDisconnected } = useWebSocket(sessionId)

const startingGame = ref(false)
const showSaveLoad = ref(false)
const showStartModal = ref(false)
const showLobbyConfirm = ref(false)
const showEndCombatConfirm = ref(false)
const showRestDialog = ref(false)
type MapInteractionMode = 'inspect' | 'move' | 'attack' | 'spell'
const mobileMapMode = ref<MapInteractionMode>('inspect')

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

function requestGoToLobby() {
  if (!gameStore.connected) {
    confirmGoToLobby()
    return
  }
  showLobbyConfirm.value = true
}

function confirmGoToLobby() {
  showLobbyConfirm.value = false
  disconnect()
  router.push({ name: 'lobby' })
}

const needsStart = computed(() =>
  ['lobby', 'character_creation'].includes(gameStore.phase),
)
const canStartCombat = computed(() =>
  ['exploration', 'encounter_start'].includes(gameStore.phase),
)
const startCombatLabel = computed(() =>
  gameStore.phase === 'encounter_start' ? '⚔ Engager' : '⚔ Combat',
)
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
  const selectedTarget = gameStore.combatants.find(
    (c) => c.id === gameStore.selectedCombatantId && c.kind === 'monster' && c.hp_current > 0,
  )
  const resolvedTargetId =
    targetId ?? (actionType === 'free_text' && gameStore.isInCombat ? selectedTarget?.id : undefined)
  if (actionType === 'free_text' && content) {
    gameStore.addPlayerEntry(content, charStore.myCharacter?.name)
  }
  sendAction(actionType, content, charId, resolvedTargetId, extra)
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
function openRestDialog() { showRestDialog.value = true }
function takeShortRest(spend: Record<string, number>) {
  showRestDialog.value = false
  sendAction('short_rest', undefined, charStore.myCharacter?.id, undefined, {
    hit_dice_spend: spend,
  })
}
function takeLongRest() {
  showRestDialog.value = false
  sendAction('long_rest', undefined, charStore.myCharacter?.id)
}
function resetCombat() { sendAction('reset_combat', undefined, charStore.myCharacter?.id) }
function dismissError() { gameStore.setError(null) }
function confirmEndCombat() { showEndCombatConfirm.value = true }
function openSheet(id: string) {
  router.push({ name: 'character-sheet', params: { charId: id }, query: { session: sessionId } })
}

function endCombat() {
  showEndCombatConfirm.value = false
  resetCombat()
}

function handleTriggerAi() {
  triggerAiReactions()
}

function handleSceneExit(_exitId: string, label: string) {
  handleAction('free_text', `Je me dirige vers ${label}.`)
}

function handleScenePoi(_poiId: string, name: string, interaction?: ScenePoiInteraction) {
  handleAction('free_text', buildScenePoiInteractionPrompt(name, interaction))
}

const mobileIsMyTurn = computed(() => gameStore.currentTurnId === charStore.myCharacter?.id)
const mobileSpeedM = computed(() => {
  const movement = gameStore.combatants.find((c) => c.id === charStore.myCharacter?.id)?.action_economy?.movement
  return movement ?? 9
})

function handleMobileMapMove(col: number, row: number) {
  handleAction('move', `${col},${row}`)
  mobileMapMode.value = 'inspect'
}

function handleMobileMapTarget(targetId: string, mode: MapInteractionMode) {
  gameStore.setSelectedCombatant(targetId)
  if (mode === 'attack') {
    handleAction('attack', undefined, targetId)
    mobileMapMode.value = 'inspect'
  }
}

watch(() => gameStore.currentTurnId, (turnId) => {
  if (!turnId) return
  const activeHuman = charStore.sessionCharacters.find(
    (c) => c.id === turnId && !c.is_ai,
  )
  if (activeHuman) charStore.setMyCharacter(activeHuman)
})

const PHASE_LABELS: Record<string, string> = {
  lobby: 'Salle d\'attente',
  character_creation: 'Création',
  exploration: 'Exploration',
  encounter_start: 'Rencontre',
  combat: 'Combat',
  encounter_end: 'Fin rencontre',
  rest: 'Repos',
  level_up: 'Montée',
  session_end: 'Terminée',
}

const PHASE_TONES: Record<string, string> = {
  lobby: 'rpg-tone-muted',
  character_creation: 'rpg-tone-arcane',
  exploration: 'rpg-tone-green',
  encounter_start: 'rpg-tone-blood',
  combat: 'rpg-tone-blood',
  encounter_end: 'rpg-tone-gold',
  rest: 'rpg-tone-teal',
  level_up: 'rpg-tone-gold',
  session_end: 'rpg-tone-dim',
}

const phaseLabel = computed(() => PHASE_LABELS[gameStore.phase] ?? gameStore.phase)
const phaseTone = computed(() => PHASE_TONES[gameStore.phase] ?? 'rpg-tone-muted')

onMounted(initSession)
onUnmounted(() => { disconnect() })
</script>

<template>
  <div
    class="rpg-game-root flex h-full flex-col overflow-hidden"
  >
    <!-- ─── Error / reconnect banners ─────────────────────────────────────── -->
    <div
      v-if="gameStore.error"
      class="rpg-game-banner rpg-tone-blood flex shrink-0 items-center justify-between gap-3 border-b px-6 py-2 text-sm"
    >
      <span>⚠ {{ gameStore.error }}</span>
      <button class="opacity-70 hover:opacity-100" @click="dismissError">✕</button>
    </div>
    <div
      v-if="isReconnecting"
      class="rpg-game-banner rpg-tone-arcane flex shrink-0 items-center gap-2 border-b px-6 py-1.5 text-xs"
    >
      <span class="rpg-pulse">◉</span>
      <span>Reconnexion… (tentative {{ reconnectCount }}/5)</span>
    </div>
    <div
      v-if="isDisconnected"
      class="rpg-game-banner rpg-tone-blood flex shrink-0 items-center justify-between gap-3 border-b px-6 py-1.5 text-xs"
    >
      <span>● Connexion perdue</span>
      <button class="rpg-btn-tonal tone-blood !py-1 !px-3 !text-[10px]" @click="reconnect">Reconnecter</button>
    </div>

    <!-- ─── Standalone header ─────────────────────────────────────────────── -->
    <header
      class="rpg-game-header flex h-14 shrink-0 items-center gap-6 border-b px-6"
    >
      <!-- Left: logo + session name -->
      <div class="flex shrink-0 items-center gap-3">
        <div
          class="rpg-brand-mark flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm font-bold"
        >⚔</div>
        <div>
          <div class="font-display text-[15px] font-bold tracking-[0.1em]">RPGMASTER</div>
          <div
            class="rpg-text-dim text-[10px] font-semibold uppercase tracking-[0.2em] leading-none"
          >{{ sessionStore.currentSession?.name ?? '—' }}</div>
        </div>
      </div>

      <!-- Centre: phase + actions -->
      <div class="flex flex-1 items-center justify-center gap-2">
        <!-- Phase info -->
        <div class="rpg-text-muted flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em]">
          <span>Phase</span>
          <span
            class="font-display font-bold"
            :class="[phaseTone, 'rpg-tone-text']"
          >{{ phaseLabel }}</span>
          <template v-if="gameStore.isGmThinking">
            <span class="rpg-text-dim">·</span>
            <span class="rpg-text-gold rpg-pulse">MJ</span>
          </template>
          <template v-else-if="gameStore.isAnyAiThinking">
            <span class="rpg-text-dim">·</span>
            <span class="rpg-text-gold rpg-pulse">IA</span>
          </template>
          <span v-if="gameStore.isInCombat" class="rpg-text-dim">·</span>
          <span
            v-if="gameStore.isInCombat"
            class="rpg-text-muted font-mono"
          >Tour {{ gameStore.roundNumber }}</span>
        </div>

        <div class="rpg-divider-vertical h-4 w-px mx-1" />

        <!-- Action buttons -->
        <button
          v-if="needsStart"
          :disabled="startingGame || !gameStore.connected"
          class="rpg-btn-primary !py-1.5 !px-4 !text-[11px]"
          @click="showStartModal = true"
        >{{ startingGame ? '…' : 'Lancer ⚔' }}</button>

        <button
          v-if="canStartCombat"
          class="rpg-btn-tonal tone-blood !py-1.5 !text-[11px]"
          @click="startCombat"
        >{{ startCombatLabel }}</button>

        <button
          v-if="canRest"
          class="rpg-btn-tonal tone-arcane !py-1.5 !text-[11px]"
          @click="openRestDialog"
        >☽ Repos</button>

        <button
          v-if="gameStore.isInCombat"
          class="rpg-btn-tonal tone-blood !py-1.5 !text-[10px]"
          @click="confirmEndCombat"
        >✕ Fin de combat</button>

        <!-- AI reactions (exploration only) -->
        <button
          v-if="gameStore.phase === 'exploration' && charStore.sessionCharacters.some(c => c.is_ai)"
          class="rpg-btn-tonal tone-arcane !py-1.5 !text-[11px]"
          title="Demander aux compagnons IA de réagir maintenant"
          @click="handleTriggerAi"
        >🤖 IA réagit</button>

        <!-- Save -->
        <button
          class="rpg-btn-secondary !py-1.5 !px-4 !text-[11px]"
          @click="showSaveLoad = !showSaveLoad"
        >💾 Sauvegarder</button>
      </div>

      <!-- Right: Lobby + connection status -->
      <div class="flex shrink-0 items-center gap-3">
        <button
          class="rpg-btn-secondary !py-1 !px-3 !text-[11px] shrink-0"
          @click="requestGoToLobby"
        >← Lobby</button>
        <div class="rpg-text-muted flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.18em]">
          <span
            class="h-2 w-2 rounded-full"
            :class="{ 'rpg-pulse': isReconnecting }"
            :style="{
              background: gameStore.connected ? 'var(--color-green)' : isReconnecting ? 'var(--color-arcane)' : 'var(--color-blood)',
              boxShadow: gameStore.connected ? '0 0 6px var(--color-green)' : 'none',
            }"
          />
          <span class="hidden md:inline">{{ gameStore.connected ? 'En ligne' : 'Hors ligne' }}</span>
        </div>
      </div>
    </header>

    <!-- Save/Load dropdown -->
    <div
      v-if="showSaveLoad"
      class="rpg-save-popover fixed right-6 top-14 z-50 w-80 rounded-b-xl border p-5 shadow-2xl"
    >
      <div class="rpg-eyebrow mb-3">✦ Sauvegardes</div>
      <SaveLoadPanel :session-id="sessionId" @load-complete="handleLoadComplete" />
    </div>

    <MapTabs
      v-if="gameStore.regionMap || Object.keys(gameStore.cityMaps).length > 0"
      :session-id="sessionId"
      @action="handleAction"
    />

    <CombatLayout
      v-if="gameStore.isInCombat"
      @action="handleAction"
      @end-combat="confirmEndCombat"
      @open-sheet="openSheet"
    />
    <ExplorationLayout
      v-else
      @action="handleAction"
      @start-combat="startCombat"
      @open-sheet="openSheet"
    />

    <!-- ─── Mobile layout ────────────────────────────────────────────────── -->
    <div class="flex min-h-0 flex-1 flex-col overflow-hidden md:hidden">
      <div
        v-if="!gameStore.isInCombat && gameStore.currentScene"
        class="rpg-border shrink-0 border-b"
      >
        <Battlemap
          mode="exploration"
          :scene-layout="gameStore.currentScene"
          @scene-exit="handleSceneExit"
          @scene-poi="handleScenePoi"
        />
      </div>
      <div
        v-else-if="gameStore.isInCombat"
        class="rpg-border shrink-0 border-b"
      >
        <Battlemap
          :my-character-id="charStore.myCharacter?.id"
          :is-my-turn="mobileIsMyTurn"
          :speed-m="mobileSpeedM"
          :interaction-mode="mobileMapMode"
          panel-height="390px"
          @move="handleMobileMapMove"
          @target="handleMobileMapTarget"
          @mode-change="(mode) => { mobileMapMode = mode }"
        />
      </div>
      <NarrativeLog />
    </div>

    <!-- ─── ActionBar ─────────────────────────────────────────────────────── -->
    <ActionBar v-if="!gameStore.isInCombat" @action="handleAction" />
    <div v-else class="md:hidden">
      <ActionBar
        @action="handleAction"
        @map-mode="(mode) => { mobileMapMode = mode }"
      />
    </div>

    <!-- Adventure start modal -->
    <AdventureStartModal
      v-if="showStartModal"
      @confirm="handleStartConfirm"
      @cancel="showStartModal = false"
    />

    <RestDialog
      v-if="showRestDialog"
      :characters="charStore.sessionCharacters"
      @confirm-short="takeShortRest"
      @confirm-long="takeLongRest"
      @cancel="showRestDialog = false"
    />

    <!-- Quitter la session -->
    <ConfirmDialog
      v-if="showLobbyConfirm"
      title="Quitter la session ?"
      message="Vous serez déconnecté et retournerez au Lobby. La progression non sauvegardée peut être perdue."
      confirm-label="Quitter"
      cancel-label="Rester"
      tone="warning"
      @confirm="confirmGoToLobby"
      @cancel="showLobbyConfirm = false"
    />

    <ConfirmDialog
      v-if="showEndCombatConfirm"
      title="Terminer le combat ?"
      message="Le combat sera annulé et la session reviendra en exploration."
      confirm-label="Terminer"
      cancel-label="Continuer"
      tone="warning"
      @confirm="endCombat"
      @cancel="showEndCombatConfirm = false"
    />
  </div>
</template>
