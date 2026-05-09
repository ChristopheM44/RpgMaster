import { ref, computed, onUnmounted } from 'vue'
import { useGameStore } from '../stores/game'
import { useCharacterStore } from '../stores/character'
import { useAudio } from './useAudio'
import { WS_EVENT_TYPES_LIST } from '../types'
import type {
  WsEvent,
  SessionStatePayload,
  NarrationPayload,
  RollResultPayload,
  TurnStartPayload,
  AiThinkingPayload,
  PhaseChangePayload,
  CombatStartPayload,
  HpChangedPayload,
  ConditionChangedPayload,
  DeathSaveUpdatedPayload,
  SpellSlotUpdatedPayload,
  EquipmentUpdatedPayload,
  HitDiceUpdatedPayload,
  AudioPayload,
  CombatActionPayload,
  CombatantMovedPayload,
  CombatantStatusChangedPayload,
  CombatantRemovedPayload,
  SceneLayoutChangedPayload,
  GridPosition,
} from '../types'

const WS_BASE = 'ws://localhost:8000'
const ACCESS_TOKEN = import.meta.env.VITE_RPGMASTER_ACCESS_TOKEN?.trim()
const PING_INTERVAL_MS = 25_000
const PONG_TIMEOUT_MS = 90_000
const BASE_RECONNECT_DELAY_MS = 1_000
const MAX_RECONNECT_DELAY_MS = 30_000
const MAX_RECONNECTS = 10
const WS_EVENT_TYPES = new Set<string>(WS_EVENT_TYPES_LIST)

export function useWebSocket(sessionId: string) {
  const gameStore = useGameStore()
  const charStore = useCharacterStore()
  const audio = useAudio()
  const ws = ref<WebSocket | null>(null)
  const reconnectCount = ref(0)
  let pingTimer: ReturnType<typeof setInterval> | null = null
  let pongTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let intentionalClose = false
  let pendingCharacterId: string | undefined
  const characterStorageKey = `rpgmaster.ws.${sessionId}.character_id`

  const isReconnecting = computed(
    () => !gameStore.connected && reconnectCount.value > 0 && reconnectCount.value < MAX_RECONNECTS,
  )

  const isDisconnected = computed(
    () => !gameStore.connected && reconnectCount.value >= MAX_RECONNECTS,
  )

  function readStoredCharacterId(): string | undefined {
    try {
      return sessionStorage.getItem(characterStorageKey) || undefined
    } catch {
      return undefined
    }
  }

  function rememberCharacterId(characterId?: string): string | undefined {
    const next = characterId ?? readStoredCharacterId()
    if (next) {
      try {
        sessionStorage.setItem(characterStorageKey, next)
      } catch {
        // Storage can be unavailable in private contexts; reconnect still uses memory.
      }
    }
    return next
  }

  function connect(characterId?: string) {
    intentionalClose = false
    pendingCharacterId = rememberCharacterId(characterId)
    // Prevent duplicate connections: skip if already open or connecting
    if (ws.value && ws.value.readyState !== WebSocket.CLOSED) return

    const socket = new WebSocket(buildWsUrl(sessionId))
    ws.value = socket

    socket.onopen = () => {
      reconnectCount.value = 0
      gameStore.setConnected(true)

      if (pendingCharacterId) {
        send({ type: 'join', character_id: pendingCharacterId })
      }

      sendPing()
      pingTimer = setInterval(sendPing, PING_INTERVAL_MS)
    }

    socket.onmessage = (event) => {
      try {
        const msg: unknown = JSON.parse(event.data)
        if (isWsEvent(msg)) handleEvent(msg)
      } catch {
        // ignore malformed messages
      }
    }

    socket.onclose = (event) => {
      console.warn('[WS] closed — code:', event.code, 'reason:', event.reason || '(none)')
      cleanup()
      gameStore.setConnected(false)
      gameStore.clearProcessingState()
      if (!intentionalClose && reconnectCount.value < MAX_RECONNECTS) {
        reconnectCount.value++
        const delay = reconnectDelayMs(reconnectCount.value)
        reconnectTimer = setTimeout(() => connect(pendingCharacterId), delay)
      } else if (!intentionalClose && reconnectCount.value >= MAX_RECONNECTS) {
        gameStore.setError('Connexion perdue. Rechargez la page pour rejoindre la session.')
      }
    }

    socket.onerror = () => {
      // onclose will fire immediately after, which handles reconnect
    }
  }

  function handleEvent(msg: WsEvent) {
    if (!gameStore.consumeEventId(msg.event_id)) return

    switch (msg.event_type) {
      case 'session_state':
        if (isSessionStatePayload(msg.payload)) gameStore.applySessionState(msg.payload)
        break
      case 'narration':
      case 'dialogue':
        if (isNarrationPayload(msg.payload)) gameStore.addNarration(msg.payload)
        break
      case 'roll_result':
        if (isRollResultPayload(msg.payload)) gameStore.addRollResult(msg.payload)
        break
      case 'turn_start':
        if (isTurnStartPayload(msg.payload)) gameStore.applyTurnStart(msg.payload)
        break
      case 'turn_end':
      case 'round_start':
      case 'player_joined':
      case 'player_left':
        gameStore.setProcessing(false)
        break
      case 'ai_thinking':
        if (isAiThinkingPayload(msg.payload)) gameStore.applyAiThinking(msg.payload)
        break
      case 'phase_change':
        gameStore.setProcessing(false)
        if (isPhaseChangePayload(msg.payload)) gameStore.applyPhaseChange(msg.payload.phase)
        break
      case 'combat_start': {
        if (isCombatStartPayload(msg.payload)) {
          const p = msg.payload
          gameStore.setCombatants(p.combatants)
          if (p.grid_config) gameStore.setGridConfig(p.grid_config)
          gameStore.setGridDecoration(p.grid_decoration)
        }
        break
      }
      case 'hp_changed': {
        if (isHpChangedPayload(msg.payload)) {
          const p = msg.payload
          gameStore.applyHpChanged(p)
          charStore.updateHp(p.combatant_id, p.hp)
        }
        break
      }
      case 'condition_changed': {
        if (isConditionChangedPayload(msg.payload)) {
          const p = msg.payload
          gameStore.applyConditionChanged(p.combatant_id, p.condition, p.added)
        }
        break
      }
      case 'death_save_updated': {
        if (isDeathSaveUpdatedPayload(msg.payload)) {
          const p = msg.payload
          gameStore.applyDeathSaveUpdated(p.combatant_id, p.death_saves)
        }
        break
      }
      case 'spell_slot_updated': {
        if (isSpellSlotUpdatedPayload(msg.payload)) {
          const p = msg.payload
          charStore.updateSpellSlots(p.character_id, p.spell_slots)
        }
        break
      }
      case 'equipment_updated': {
        if (isEquipmentUpdatedPayload(msg.payload)) {
          const p = msg.payload
          charStore.updateEquipment(p.character_id, p.equipment)
        }
        break
      }
      case 'hit_dice_updated': {
        if (isHitDiceUpdatedPayload(msg.payload)) {
          const p = msg.payload
          charStore.updateHitDice(p.character_id, p.hit_dice)
        }
        break
      }
      case 'combat_action':
        if (isCombatActionPayload(msg.payload)) gameStore.addCombatAction(msg.payload)
        break
      case 'combatant_moved':
        if (isCombatantMovedPayload(msg.payload)) gameStore.moveCombatant(msg.payload)
        break
      case 'combatant_status_changed':
        if (isCombatantStatusChangedPayload(msg.payload)) gameStore.applyCombatantStatusChanged(msg.payload)
        break
      case 'combatant_removed':
        if (isCombatantRemovedPayload(msg.payload)) gameStore.removeCombatant(msg.payload.combatant_id)
        break
      case 'combat_end':
        gameStore.setProcessing(false)
        break
      case 'audio':
        if (isAudioPayload(msg.payload)) audio.playAudioB64(msg.payload.audio_b64)
        break
      case 'error':
        if (isErrorPayload(msg.payload)) gameStore.setError(msg.payload.message)
        break
      case 'journal_updated':
        gameStore.applyJournalUpdated(msg.payload as { journal: import('../types').AdventureJournal })
        break
      case 'quest_updated':
        gameStore.applyQuestUpdated(msg.payload as { quests: import('../types').Quest[] })
        break
      case 'chronicle_updated':
        gameStore.applyChronicleUpdated(msg.payload as { chronicle: import('../types').ChronicleEntry[] })
        break
      case 'scene_layout_changed':
        if (isSceneLayoutChangedPayload(msg.payload)) gameStore.applySceneLayout(msg.payload)
        break
      case 'damage_applied':
        break
      case 'pong':
        clearPongTimer()
        break
    }
  }

  function send(data: Record<string, unknown>) {
    if (ws.value?.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify(data))
    }
  }

  function sendPing() {
    if (ws.value?.readyState !== WebSocket.OPEN) return
    clearPongTimer()
    send({ type: 'ping' })
    pongTimer = setTimeout(() => {
      if (ws.value?.readyState === WebSocket.OPEN) {
        ws.value.close()
      }
    }, PONG_TIMEOUT_MS)
  }

  function sendAction(
    actionType: string,
    content?: string,
    characterId?: string,
    targetId?: string,
    extra?: Record<string, unknown>,
  ) {
    // Mark as processing — cleared when narration or error arrives
    if (gameStore.connected) {
      gameStore.setProcessing(true)
    }
    send({
      type: 'action',
      action_type: actionType,
      content,
      character_id: characterId,
      target_id: targetId,
      ...extra,
    })
  }

  function toggleAiControl(characterId: string, nextIsAi: boolean) {
    send({ type: 'toggle_ai_control', character_id: characterId, is_ai: nextIsAi })
  }

  function triggerAiReactions(triggerCharacterId?: string) {
    if (gameStore.connected) {
      gameStore.setProcessing(true)
    }
    send({ type: 'trigger_ai_reactions', character_id: triggerCharacterId })
  }

  function reconnect() {
    reconnectCount.value = 0
    gameStore.setError(null)
    connect(pendingCharacterId ?? readStoredCharacterId())
  }

  function disconnect() {
    intentionalClose = true
    cleanup()
    ws.value?.close()
    ws.value = null
    reconnectCount.value = 0
  }

  function cleanup() {
    if (pingTimer) { clearInterval(pingTimer); pingTimer = null }
    clearPongTimer()
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
  }

  function clearPongTimer() {
    if (pongTimer) { clearTimeout(pongTimer); pongTimer = null }
  }

  onUnmounted(disconnect)

  return { connect, disconnect, reconnect, send, sendAction, toggleAiControl, triggerAiReactions, reconnectCount, isReconnecting, isDisconnected }
}

function buildWsUrl(sessionId: string): string {
  const url = new URL(`${WS_BASE}/ws/game/${sessionId}`)
  if (ACCESS_TOKEN) url.searchParams.set('access_token', ACCESS_TOKEN)
  return url.toString()
}

function reconnectDelayMs(attempt: number): number {
  const exponential = Math.min(
    MAX_RECONNECT_DELAY_MS,
    BASE_RECONNECT_DELAY_MS * 2 ** Math.max(0, attempt - 1),
  )
  const jitter = Math.floor(Math.random() * Math.min(1_000, exponential * 0.25))
  return exponential + jitter
}

function isWsEvent(value: unknown): value is WsEvent {
  return (
    isRecord(value)
    && typeof value.event_type === 'string'
    && WS_EVENT_TYPES.has(value.event_type)
    && 'payload' in value
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isSessionStatePayload(value: unknown): value is SessionStatePayload {
  return (
    isRecord(value)
    && typeof value.phase === 'string'
    && typeof value.turn_number === 'number'
    && typeof value.round_number === 'number'
    && Array.isArray(value.turn_order)
    && typeof value.current_turn_index === 'number'
    && Array.isArray(value.valid_transitions)
  )
}

function isNarrationPayload(value: unknown): value is NarrationPayload {
  return isRecord(value) && typeof value.text === 'string'
}

function isRollResultPayload(value: unknown): value is RollResultPayload {
  return (
    isRecord(value)
    && Array.isArray(value.rolls)
    && typeof value.total === 'number'
    && typeof value.modifier === 'number'
  )
}

function isTurnStartPayload(value: unknown): value is TurnStartPayload {
  return isRecord(value) && typeof value.combatant_id === 'string'
}

function isAiThinkingPayload(value: unknown): value is AiThinkingPayload {
  return isRecord(value) && typeof value.agent_kind === 'string' && typeof value.thinking === 'boolean'
}

function isPhaseChangePayload(value: unknown): value is PhaseChangePayload {
  return isRecord(value) && typeof value.phase === 'string'
}

function isCombatStartPayload(value: unknown): value is CombatStartPayload {
  return isRecord(value) && Array.isArray(value.combatants)
}

function isHpChangedPayload(value: unknown): value is HpChangedPayload {
  return isRecord(value) && typeof value.combatant_id === 'string' && typeof value.hp === 'number'
}

function isConditionChangedPayload(value: unknown): value is ConditionChangedPayload {
  return (
    isRecord(value)
    && typeof value.combatant_id === 'string'
    && typeof value.condition === 'string'
    && typeof value.added === 'boolean'
  )
}

function isDeathSaveUpdatedPayload(value: unknown): value is DeathSaveUpdatedPayload {
  return isRecord(value) && typeof value.combatant_id === 'string' && isRecord(value.death_saves)
}

function isSpellSlotUpdatedPayload(value: unknown): value is SpellSlotUpdatedPayload {
  return isRecord(value) && typeof value.character_id === 'string' && isRecord(value.spell_slots)
}

function isEquipmentUpdatedPayload(value: unknown): value is EquipmentUpdatedPayload {
  return isRecord(value) && typeof value.character_id === 'string' && Array.isArray(value.equipment)
}

function isHitDiceUpdatedPayload(value: unknown): value is HitDiceUpdatedPayload {
  return isRecord(value) && typeof value.character_id === 'string' && isRecord(value.hit_dice)
}

function isGridPosition(value: unknown): value is GridPosition {
  return isRecord(value) && typeof value.col === 'number' && typeof value.row === 'number'
}

function isCombatActionPayload(value: unknown): value is CombatActionPayload {
  return (
    isRecord(value)
    && typeof value.attacker_id === 'string'
    && typeof value.attacker_name === 'string'
    && (typeof value.target_id === 'string' || value.target_id === null)
    && typeof value.target_name === 'string'
    && typeof value.action_type === 'string'
    && typeof value.action_name === 'string'
    && typeof value.d20 === 'number'
    && typeof value.attack_roll === 'number'
    && typeof value.attack_bonus === 'number'
    && typeof value.target_ac === 'number'
    && typeof value.hit === 'boolean'
    && typeof value.critical === 'boolean'
    && (typeof value.damage === 'number' || value.damage === null)
    && typeof value.damage_notation === 'string'
  )
}

function isCombatantMovedPayload(value: unknown): value is CombatantMovedPayload {
  return (
    isRecord(value)
    && typeof value.combatant_id === 'string'
    && isGridPosition(value.position)
    && typeof value.movement_used_m === 'number'
  )
}

function isCombatantStatusChangedPayload(value: unknown): value is CombatantStatusChangedPayload {
  return (
    isRecord(value)
    && typeof value.combatant_id === 'string'
    && typeof value.status === 'string'
    && (value.combatant_name === undefined || typeof value.combatant_name === 'string')
    && (value.reason === undefined || typeof value.reason === 'string')
  )
}

function isCombatantRemovedPayload(value: unknown): value is CombatantRemovedPayload {
  return isRecord(value) && typeof value.combatant_id === 'string'
}

function isSceneLayoutChangedPayload(value: unknown): value is SceneLayoutChangedPayload {
  return (
    isRecord(value)
    && isRecord(value.scene)
    && typeof value.scene.cols === 'number'
    && typeof value.scene.rows === 'number'
  )
}

function isAudioPayload(value: unknown): value is AudioPayload {
  return isRecord(value) && typeof value.audio_b64 === 'string'
}

function isErrorPayload(value: unknown): value is { message: string } {
  return isRecord(value) && typeof value.message === 'string'
}
