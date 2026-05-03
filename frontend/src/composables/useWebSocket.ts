import { ref, computed, onUnmounted } from 'vue'
import { useGameStore } from '../stores/game'
import { useCharacterStore } from '../stores/character'
import { useAudio } from './useAudio'
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
} from '../types'

const WS_BASE = 'ws://localhost:8000'
const ACCESS_TOKEN = import.meta.env.VITE_RPGMASTER_ACCESS_TOKEN?.trim()
const PING_INTERVAL_MS = 25_000
const RECONNECT_DELAY_MS = 3_000
const MAX_RECONNECTS = 5

export function useWebSocket(sessionId: string) {
  const gameStore = useGameStore()
  const charStore = useCharacterStore()
  const audio = useAudio()
  const ws = ref<WebSocket | null>(null)
  const reconnectCount = ref(0)
  let pingTimer: ReturnType<typeof setInterval> | null = null
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

      pingTimer = setInterval(() => send({ type: 'ping' }), PING_INTERVAL_MS)
    }

    socket.onmessage = (event) => {
      try {
        const msg: unknown = JSON.parse(event.data)
        if (isWsEvent(msg)) handleEvent(msg)
      } catch {
        // ignore malformed messages
      }
    }

    socket.onclose = () => {
      cleanup()
      gameStore.setConnected(false)
      if (!intentionalClose && reconnectCount.value < MAX_RECONNECTS) {
        reconnectCount.value++
        const delay = RECONNECT_DELAY_MS * reconnectCount.value
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
        gameStore.applySessionState(msg.payload as SessionStatePayload)
        break
      case 'narration':
        gameStore.addNarration(msg.payload as NarrationPayload)
        break
      case 'roll_result':
        gameStore.addRollResult(msg.payload as RollResultPayload)
        break
      case 'turn_start':
        gameStore.applyTurnStart(msg.payload as TurnStartPayload)
        break
      case 'turn_end':
      case 'round_start':
      case 'player_joined':
      case 'player_left':
        gameStore.setProcessing(false)
        break
      case 'ai_thinking':
        gameStore.applyAiThinking(msg.payload as AiThinkingPayload)
        break
      case 'phase_change':
        gameStore.setProcessing(false)
        gameStore.applyPhaseChange((msg.payload as PhaseChangePayload).phase)
        break
      case 'combat_start': {
        const p = msg.payload as CombatStartPayload
        gameStore.setCombatants(p.combatants)
        if (p.grid_config) gameStore.setGridConfig(p.grid_config)
        gameStore.setGridDecoration(p.grid_decoration)
        break
      }
      case 'hp_changed': {
        const p = msg.payload as HpChangedPayload
        gameStore.applyHpChanged(p)
        charStore.updateHp(p.combatant_id, p.hp)
        break
      }
      case 'condition_changed': {
        const p = msg.payload as ConditionChangedPayload
        gameStore.applyConditionChanged(p.combatant_id, p.condition, p.added)
        break
      }
      case 'death_save_updated': {
        const p = msg.payload as DeathSaveUpdatedPayload
        gameStore.applyDeathSaveUpdated(p.combatant_id, p.death_saves)
        break
      }
      case 'spell_slot_updated': {
        const p = msg.payload as SpellSlotUpdatedPayload
        charStore.updateSpellSlots(p.character_id, p.spell_slots)
        break
      }
      case 'equipment_updated': {
        const p = msg.payload as EquipmentUpdatedPayload
        charStore.updateEquipment(p.character_id, p.equipment)
        break
      }
      case 'hit_dice_updated': {
        const p = msg.payload as HitDiceUpdatedPayload
        charStore.updateHitDice(p.character_id, p.hit_dice)
        break
      }
      case 'combat_action':
        gameStore.addCombatAction(msg.payload as CombatActionPayload)
        break
      case 'combatant_moved':
        gameStore.moveCombatant(msg.payload as CombatantMovedPayload)
        break
      case 'combatant_status_changed':
        gameStore.applyCombatantStatusChanged(msg.payload as CombatantStatusChangedPayload)
        break
      case 'combatant_removed':
        gameStore.removeCombatant((msg.payload as CombatantRemovedPayload).combatant_id)
        break
      case 'combat_end':
        gameStore.setProcessing(false)
        gameStore.applyPhaseChange('exploration')
        break
      case 'audio':
        audio.playAudioB64((msg.payload as AudioPayload).audio_b64)
        break
      case 'error':
        gameStore.setError((msg.payload as { message: string }).message)
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
        gameStore.applySceneLayout(msg.payload as SceneLayoutChangedPayload)
        break
      case 'pong':
        break
    }
  }

  function send(data: Record<string, unknown>) {
    if (ws.value?.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify(data))
    }
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
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
  }

  onUnmounted(disconnect)

  return { connect, disconnect, reconnect, send, sendAction, toggleAiControl, triggerAiReactions, reconnectCount, isReconnecting, isDisconnected }
}

function buildWsUrl(sessionId: string): string {
  const url = new URL(`${WS_BASE}/ws/game/${sessionId}`)
  if (ACCESS_TOKEN) url.searchParams.set('access_token', ACCESS_TOKEN)
  return url.toString()
}

function isWsEvent(value: unknown): value is WsEvent {
  return (
    typeof value === 'object'
    && value !== null
    && typeof (value as { event_type?: unknown }).event_type === 'string'
    && 'payload' in value
  )
}
