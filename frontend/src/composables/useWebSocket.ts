import { ref, onUnmounted } from 'vue'
import { useGameStore } from '../stores/game'
import { useCharacterStore } from '../stores/character'
import { useAudio } from './useAudio'
import type {
  WsEvent,
  SessionStatePayload,
  NarrationPayload,
  RollResultPayload,
  TurnStartPayload,
  PhaseChangePayload,
  CombatStartPayload,
  HpChangedPayload,
  SpellSlotUpdatedPayload,
  AudioPayload,
} from '../types'

const WS_BASE = 'ws://localhost:8000'
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

  function connect(characterId?: string) {
    if (ws.value?.readyState === WebSocket.OPEN) return

    const socket = new WebSocket(`${WS_BASE}/ws/game/${sessionId}`)
    ws.value = socket

    socket.onopen = () => {
      gameStore.setConnected(true)
      reconnectCount.value = 0

      if (characterId) {
        send({ type: 'join', character_id: characterId })
      }

      pingTimer = setInterval(() => send({ type: 'ping' }), PING_INTERVAL_MS)
    }

    socket.onmessage = (event) => {
      try {
        const msg: WsEvent = JSON.parse(event.data)
        handleEvent(msg)
      } catch {
        // ignore malformed messages
      }
    }

    socket.onclose = () => {
      cleanup()
      gameStore.setConnected(false)
      if (reconnectCount.value < MAX_RECONNECTS) {
        reconnectCount.value++
        reconnectTimer = setTimeout(() => connect(characterId), RECONNECT_DELAY_MS)
      }
    }

    socket.onerror = () => {
      gameStore.setError('Erreur de connexion WebSocket.')
    }
  }

  function handleEvent(msg: WsEvent) {
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
      case 'phase_change':
        gameStore.applyPhaseChange((msg.payload as PhaseChangePayload).phase)
        break
      case 'combat_start':
        gameStore.setCombatants((msg.payload as CombatStartPayload).combatants)
        break
      case 'hp_changed': {
        const p = msg.payload as HpChangedPayload
        gameStore.applyHpChanged(p)
        charStore.updateHp(p.combatant_id, p.hp)
        break
      }
      case 'spell_slot_updated': {
        const p = msg.payload as SpellSlotUpdatedPayload
        charStore.updateSpellSlots(p.character_id, p.spell_slots)
        break
      }
      case 'combat_end':
        gameStore.setCombatants([])
        break
      case 'audio':
        audio.playAudioB64((msg.payload as AudioPayload).audio_b64)
        break
      case 'error':
        gameStore.setError((msg.payload as { message: string }).message)
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
    send({
      type: 'action',
      action_type: actionType,
      content,
      character_id: characterId,
      target_id: targetId,
      ...extra,
    })
  }

  function disconnect() {
    cleanup()
    ws.value?.close()
    ws.value = null
  }

  function cleanup() {
    if (pingTimer) { clearInterval(pingTimer); pingTimer = null }
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
  }

  onUnmounted(disconnect)

  return { connect, disconnect, send, sendAction }
}
