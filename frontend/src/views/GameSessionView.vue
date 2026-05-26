<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useGameStore } from '../stores/game'
import { useCharacterStore } from '../stores/character'
import { useSessionStore } from '../stores/session'
import { useWebSocket } from '../composables/useWebSocket'
import { gameApi } from '../services/api'
import NarrativeLog from '../components/narrative/NarrativeLog.vue'
import ExplorationLayout from '../components/exploration/ExplorationLayout.vue'
import CombatLayout from '../components/combat/CombatLayout.vue'
import Battlemap from '../components/combat/Battlemap.vue'
import MapTabs from '../components/map/MapTabs.vue'
import ActionBar from '../components/common/ActionBar.vue'
import SaveLoadPanel from '../components/ui/SaveLoadPanel.vue'
import AdventureStartModal from '../components/ui/AdventureStartModal.vue'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'
import RestDialog from '../components/ui/RestDialog.vue'
import LevelUpModal from '../components/character/LevelUpModal.vue'
import LootNotification from '../components/combat/LootNotification.vue'
import { buildScenePoiInteractionPrompt } from '../utils/scenePoiInteractions'
import type { ScenePoiInteraction } from '../types'

const route = useRoute()
const router = useRouter()
const sessionId = route.params.id as string

const gameStore = useGameStore()
const charStore = useCharacterStore()
const sessionStore = useSessionStore()

const { connect, disconnect, reconnect, sendAction, triggerAiReactions, reconnectCount, isReconnecting, isDisconnected } = useWebSocket(sessionId)

const startingGame = ref(false)
const showSaveLoad = ref(false)
const showStartModal = ref(false)
const routeStartPending = ref(route.query.start === '1')
const showLobbyConfirm = ref(false)
const showEndCombatConfirm = ref(false)
const showRestDialog = ref(false)
type MapInteractionMode = 'inspect' | 'move' | 'attack' | 'spell'
const mobileMapMode = ref<MapInteractionMode>('inspect')

async function initSession() {
  const shouldStartAfterConnect = routeStartPending.value
  gameStore.reset()
  if (shouldStartAfterConnect) {
    gameStore.setProcessing(true)
  }
  disconnect()

  try {
    const loaded = await import('../services/api').then(m => m.sessionApi.get(sessionId))
    sessionStore.setCurrentSession(loaded)
  } catch {
    router.push({ name: 'lobby' })
    return
  }

  if (sessionStore.currentSession) {
    gameStore.phase = sessionStore.currentSession.status
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

  if (['lobby', 'character_creation'].includes(gameStore.phase) && !routeStartPending.value) {
    router.replace({ name: 'character-setup', params: { id: sessionId } })
    return
  }

  connect(charStore.myCharacter?.id)
  await startPendingRouteSession()
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
const hasAiCompanions = computed(() =>
  charStore.sessionCharacters.some((c) => c.is_ai),
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

async function handleStartConfirm(
  mode: 'libre' | 'script' | 'auto',
  script?: string,
  options?: {
    adventure_preset?: string
    biome?: string
    weather?: string
    tone?: string
  }
) {
  showStartModal.value = false
  startingGame.value = true
  gameStore.setProcessing(true)
  try {
    const body =
      mode === 'script' && script
        ? { adventure_script: script }
        : {
            auto_generate: mode === 'auto',
            adventure_preset: options?.adventure_preset,
            biome: options?.biome,
            weather: options?.weather,
            tone: options?.tone,
          }
    const result = await gameApi.start(sessionId, body)
    if (result.status === 'already_started') {
      gameStore.setProcessing(false)
    }
  } catch {
    gameStore.setError('Impossible de démarrer la partie.')
  } finally {
    startingGame.value = false
  }
}

async function startPendingRouteSession() {
  if (!routeStartPending.value || !gameStore.connected) return
  routeStartPending.value = false
  gameStore.setProcessing(true)
  try {
    const mode = route.query.mode as string
    const script = route.query.script as string
    const adventure_preset = route.query.adventure_preset as string
    const biome = route.query.biome as string
    const weather = route.query.weather as string
    const tone = route.query.tone as string

    const body =
      mode === 'script' && script
        ? { adventure_script: script }
        : {
            auto_generate: mode === 'auto',
            adventure_preset: adventure_preset || undefined,
            biome: biome || undefined,
            weather: weather || undefined,
            tone: tone || undefined,
          }
    await gameApi.start(sessionId, body)

    // Fetch state and history after game starting to guarantee UI synchronization
    // regardless of any WebSocket delays or missed events.
    const state = await gameApi.getState(sessionId)
    gameStore.applySessionState(state)

    const history = await gameApi.getHistory(sessionId)
    if (history.messages.length > 0) {
      gameStore.restoreHistory(history.messages)
    }

    gameStore.setProcessing(false)
  } catch {
    gameStore.setError('Impossible de démarrer la partie.')
    gameStore.setProcessing(false)
  } finally {
    const nextQuery = { ...route.query }
    delete nextQuery.start
    delete nextQuery.mode
    delete nextQuery.script
    delete nextQuery.adventure_preset
    delete nextQuery.biome
    delete nextQuery.weather
    delete nextQuery.tone
    await router.replace({ name: 'game-session', params: { id: sessionId }, query: nextQuery })
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

function handleAsiChoice(payload: { characterId: string; mode: 'plus_two'; ability: string }) {
  sendAction('asi_choice', undefined, payload.characterId, undefined, {
    mode: payload.mode,
    ability: payload.ability,
  })
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

watch(() => gameStore.connected, (connected) => {
  if (connected) void startPendingRouteSession()
})

// ── Pill couleur & label par phase ────────────────────────────────────────
type PhaseStyle = { label: string; color: string; bg: string; border: string }

const PHASE_STYLES: Record<string, PhaseStyle> = {
  lobby:               { label: "Salle d'attente",  color: 'var(--color-text-muted)',     bg: 'rgba(247,236,208,0.05)', border: 'var(--color-border)' },
  character_creation:  { label: 'Création',         color: 'var(--color-arcane)',         bg: 'rgba(192,144,255,0.12)', border: 'rgba(192,144,255,0.4)' },
  exploration:         { label: 'Exploration',      color: 'var(--color-green)',          bg: 'linear-gradient(135deg, rgba(111,217,111,0.18), rgba(111,217,111,0.04))', border: 'rgba(111,217,111,0.4)' },
  encounter_start:     { label: 'Rencontre',        color: 'var(--color-blood)',          bg: 'rgba(232,69,69,0.12)',   border: 'rgba(232,69,69,0.4)' },
  combat:              { label: 'Combat',           color: 'var(--color-blood)',          bg: 'rgba(232,69,69,0.12)',   border: 'rgba(232,69,69,0.4)' },
  encounter_end:       { label: 'Fin rencontre',    color: 'var(--color-gold)',           bg: 'rgba(240,199,100,0.12)', border: 'rgba(240,199,100,0.4)' },
  rest:                { label: 'Repos',            color: 'var(--color-arcane)',         bg: 'rgba(192,144,255,0.18)', border: 'rgba(192,144,255,0.4)' },
  level_up:            { label: 'Montée',           color: 'var(--color-gold)',           bg: 'rgba(240,199,100,0.18)', border: 'rgba(240,199,100,0.4)' },
  session_end:         { label: 'Terminée',         color: 'var(--color-text-dim)',       bg: 'rgba(247,236,208,0.03)', border: 'var(--color-border)' },
}

const phaseStyle = computed<PhaseStyle>(() => PHASE_STYLES[gameStore.phase] ?? PHASE_STYLES.lobby!)

// ── Métadonnées contextuelles (lieu · jour · météo) ──
const contextLocation = computed(() => {
  const journal = gameStore.adventureJournal
  if (journal?.location_place) return journal.location_place

  if (gameStore.regionMap) {
    const currentNode = gameStore.regionMap.nodes.find(
      (node) => node.id === gameStore.regionMap?.current_node_id
    )
    if (currentNode?.name) return currentNode.name
  }
  return null
})
const contextMeta = computed(() => {
  const journal = gameStore.adventureJournal
  if (!journal) return null

  const TIME_LABEL: Record<string, string> = {
    dawn: 'aube',
    morning: 'matin',
    noon: 'midi',
    afternoon: 'après-midi',
    dusk: 'crépuscule',
    night: 'nuit',
  }
  const time = TIME_LABEL[journal.time_of_day] ?? journal.time_of_day

  const parts = [
    `Jour ${journal.day_number}`,
    time,
    journal.weather
  ].filter(Boolean)

  return parts.join(' · ')
})

const showLoader = computed(() => !gameStore.currentScene)

onMounted(initSession)
onUnmounted(() => { disconnect() })
</script>

<template>
  <div class="rpg-game-root flex h-full flex-col overflow-hidden">
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

    <!-- ─── V2 Header (56px) — logo + pill phase + actions ──────────────── -->
    <header class="exploration-header">
      <!-- Brand block -->
      <div class="exph-brand">
        <div class="exph-logo">⚔</div>
        <div class="exph-brand-meta">
          <div class="exph-brand-title">RPGMASTER</div>
          <div class="exph-brand-sub">{{ sessionStore.currentSession?.name ?? '—' }}</div>
        </div>
      </div>

      <!-- Phase pill -->
      <div class="exph-pill-wrap">
        <div
          class="exph-pill"
          :style="{ background: phaseStyle.bg, borderColor: phaseStyle.border }"
        >
          <span
            class="exph-pill-dot"
            :style="{
              background: phaseStyle.color,
              boxShadow: `0 0 8px ${phaseStyle.color}`,
            }"
          />
          <span
            class="exph-pill-label"
            :style="{ color: phaseStyle.color }"
          >{{ phaseStyle.label }}</span>

          <template v-if="contextLocation">
            <span class="exph-pill-sep">·</span>
            <span class="exph-pill-loc">{{ contextLocation }}</span>
          </template>
          <template v-if="contextMeta">
            <span class="exph-pill-sep">·</span>
            <span class="exph-pill-meta">{{ contextMeta }}</span>
          </template>
          <template v-if="gameStore.isInCombat">
            <span class="exph-pill-sep">·</span>
            <span class="exph-pill-round">R{{ gameStore.roundNumber || 1 }}</span>
          </template>
          <template v-if="gameStore.isGmThinking || gameStore.isAnyAiThinking">
            <span class="exph-pill-sep">·</span>
            <span class="exph-pill-thinking">{{ gameStore.isGmThinking ? 'MJ' : 'IA' }}</span>
          </template>
        </div>
      </div>

      <div style="flex: 1" />

      <!-- Right cluster -->
      <div class="exph-actions">
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

        <button
          v-if="gameStore.phase === 'exploration' && hasAiCompanions"
          class="rpg-btn-tonal tone-arcane !py-1.5 !text-[11px]"
          title="Demander aux compagnons IA de réagir maintenant"
          @click="handleTriggerAi"
        >🤖 IA réagit</button>

        <button
          class="rpg-btn-secondary !py-1.5 !px-4 !text-[11px]"
          @click="showSaveLoad = !showSaveLoad"
        >💾 Sauvegarder</button>

        <div class="exph-divider" />

        <div class="exph-online">
          <span
            class="exph-online-dot"
            :class="{ 'rpg-pulse': isReconnecting }"
            :style="{
              background: gameStore.connected ? 'var(--color-green)' : isReconnecting ? 'var(--color-arcane)' : 'var(--color-blood)',
              boxShadow: gameStore.connected ? '0 0 8px var(--color-green)' : 'none',
            }"
          />
          <span class="hidden md:inline">{{ gameStore.connected ? 'En ligne' : 'Hors ligne' }}</span>
        </div>

        <button
          class="rpg-btn-secondary !py-1.5 !px-4 !text-[11px] shrink-0"
          @click="requestGoToLobby"
        >← Lobby</button>
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

    <!-- MapTabs (legacy) : caché en exploration V2 — le scope est piloté par ScopeTabs dans MapColumn. -->
    <MapTabs
      v-if="gameStore.phase !== 'exploration' && (gameStore.regionMap || Object.keys(gameStore.cityMaps).length > 0)"
      :session-id="sessionId"
      @action="handleAction"
    />

    <!-- ─── Cinematic Loader ─── -->
    <div v-if="showLoader" class="flex-1 flex flex-col justify-center items-center p-8 text-center bg-[#0e0d14] relative z-20">
      <div class="loader-wrap flex flex-col items-center">
        <!-- Animated visual spinner -->
        <div class="relative w-24 h-24 mb-8 flex items-center justify-center">
          <div class="absolute inset-0 rounded-full border border-[#f0c764]/10 animate-[spin_6s_linear_infinite]" />
          <div class="absolute inset-2 rounded-full border-t-2 border-r-2 border-[#ff8247] animate-[spin_1.5s_linear_infinite]" />
          <div class="absolute inset-4 rounded-full border-b-2 border-l-2 border-[#c090ff] animate-[spin_2s_linear_infinite] opacity-60" />
          <span class="text-2xl animate-[pulse_1.5s_ease-in-out_infinite] text-[#f0c764]">✦</span>
        </div>

        <h2 class="font-display text-xl md:text-2xl font-bold text-[#f0c764] tracking-widest uppercase mb-4 animate-[pulse_2s_ease-in-out_infinite]">
          Le Maître du Jeu IA prépare la scène...
        </h2>
        <p class="font-serif text-sm md:text-base italic text-[rgba(247,236,208,0.75)] max-w-md leading-relaxed">
          Tissage de l'intrigue, placement des décors tactiques et des personnages dans l'espace physique...
        </p>
      </div>
    </div>

    <!-- ─── Game Session Layouts ─── -->
    <template v-else>
      <!-- ─── Desktop layouts (md+) ─────────────────────────────────────────── -->
      <CombatLayout
        v-if="gameStore.isInCombat"
        @action="handleAction"
        @end-combat="confirmEndCombat"
        @open-sheet="openSheet"
      />
      <ExplorationLayout
        v-else
        class="hidden md:flex"
        @action="handleAction"
        @open-sheet="openSheet"
      />

    <LootNotification />

    <LevelUpModal
      :visible="gameStore.phase === 'level_up'"
      :characters="charStore.sessionCharacters"
      @asi-choice="handleAsiChoice"
    />

    <!-- ─── Mobile layout (V1, V2 desktop-only) ────────────────────────── -->
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
          @flee="(exitId) => handleAction('flee', exitId)"
        />
      </div>
      <NarrativeLog />
    </div>

    <!-- ─── ActionBar (mobile only) ─────────────────────────────────────── -->
    <div class="md:hidden">
      <ActionBar
        v-if="!gameStore.isInCombat"
        @action="handleAction"
      />
      <ActionBar
        v-else
        @action="handleAction"
        @map-mode="(mode) => { mobileMapMode = mode }"
      />
    </div>

    </template>

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

<style scoped>
/* ─ V2 Header (56px) ────────────────────────────────────────────────── */
.exploration-header {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  gap: 14px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--color-border);
  background: linear-gradient(180deg, var(--color-bg-elev), transparent);
  position: relative;
  z-index: 3;
}

.exph-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.exph-logo {
  width: 30px;
  height: 30px;
  border-radius: 7px;
  background: linear-gradient(135deg, var(--color-ember), var(--color-gold));
  color: var(--color-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 700;
  box-shadow: 0 0 16px rgba(255, 130, 71, 0.3);
}

.exph-brand-meta { line-height: 1.15; }

.exph-brand-title {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--color-parchment);
}

.exph-brand-sub {
  font-size: 9px;
  color: var(--color-text-dim);
  letter-spacing: 1px;
  text-transform: uppercase;
}

/* Pill wrapper */
.exph-pill-wrap {
  display: flex;
  align-items: center;
  padding-left: 14px;
  margin-left: 6px;
  border-left: 1px solid var(--color-border);
}

.exph-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid;
  white-space: nowrap;
}

.exph-pill-dot {
  width: 7px;
  height: 7px;
  border-radius: 4px;
}

.exph-pill-label {
  font-weight: 700;
  letter-spacing: 1px;
  font-size: 10px;
  text-transform: uppercase;
}

.exph-pill-sep {
  color: rgba(247, 236, 208, 0.5);
}

.exph-pill-loc {
  font-family: var(--font-serif);
  font-style: italic;
  color: var(--color-parchment-dark);
  font-size: 11px;
}

.exph-pill-meta {
  font-size: 10px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}

.exph-pill-round {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--color-gold);
  font-size: 11px;
}

.exph-pill-thinking {
  font-size: 10px;
  color: var(--color-gold);
  font-weight: 700;
  letter-spacing: 1px;
}

/* Actions */
.exph-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.exph-divider {
  width: 1px;
  height: 18px;
  background: var(--color-border);
  margin: 0 4px;
}

.exph-online {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: var(--color-green);
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.exph-online-dot {
  width: 7px;
  height: 7px;
  border-radius: 4px;
}
</style>
