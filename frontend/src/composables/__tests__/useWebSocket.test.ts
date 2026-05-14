import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useCharacterStore } from '../../stores/character'
import { useGameStore } from '../../stores/game'
import { useWebSocket } from '../useWebSocket'

class WebSocketMock {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  static instances: WebSocketMock[] = []

  readyState = WebSocketMock.CONNECTING
  sent: string[] = []
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null

  constructor(public url: string) {
    WebSocketMock.instances.push(this)
  }

  send(data: string) {
    this.sent.push(data)
  }

  close() {
    this.readyState = WebSocketMock.CLOSED
    this.onclose?.()
  }

  open() {
    this.readyState = WebSocketMock.OPEN
    this.onopen?.()
  }
}

describe('useWebSocket', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sessionStorage.clear()
    WebSocketMock.instances = []
    vi.useRealTimers()
    vi.stubGlobal('WebSocket', WebSocketMock)
  })

  it('stores the joined character id and reuses it on a later connection', () => {
    const first = useWebSocket('session-1')
    first.connect('hero-1')
    WebSocketMock.instances[0]!.open()

    expect(JSON.parse(WebSocketMock.instances[0]!.sent[0]!)).toEqual({
      type: 'join',
      character_id: 'hero-1',
    })

    first.disconnect()

    const second = useWebSocket('session-1')
    second.connect()
    WebSocketMock.instances[1]!.open()

    expect(JSON.parse(WebSocketMock.instances[1]!.sent[0]!)).toEqual({
      type: 'join',
      character_id: 'hero-1',
    })

    second.disconnect()
    vi.unstubAllGlobals()
  })

  it('does not force exploration on combat_end before phase_change arrives', () => {
    const socket = useWebSocket('session-1')
    const gameStore = useGameStore()

    socket.connect('hero-1')
    WebSocketMock.instances[0]!.open()
    gameStore.applyPhaseChange('combat')

    WebSocketMock.instances[0]!.onmessage?.({
      data: JSON.stringify({
        event_type: 'combat_end',
        payload: { reason: 'victory' },
      }),
    })

    expect(gameStore.phase).toBe('combat')

    WebSocketMock.instances[0]!.onmessage?.({
      data: JSON.stringify({
        event_type: 'phase_change',
        payload: { phase: 'encounter_end' },
      }),
    })

    expect(gameStore.phase).toBe('encounter_end')

    socket.disconnect()
    vi.unstubAllGlobals()
  })

  it('ignores malformed critical payloads', () => {
    const socket = useWebSocket('session-1')
    const gameStore = useGameStore()

    socket.connect('hero-1')
    WebSocketMock.instances[0]!.open()
    gameStore.applyPhaseChange('combat')

    WebSocketMock.instances[0]!.onmessage?.({
      data: JSON.stringify({
        event_type: 'phase_change',
        payload: { phase: 42 },
      }),
    })

    expect(gameStore.phase).toBe('combat')

    socket.disconnect()
    vi.unstubAllGlobals()
  })

  it('handles dialogue events as narration entries', () => {
    const socket = useWebSocket('session-1')
    const gameStore = useGameStore()

    socket.connect('hero-1')
    WebSocketMock.instances[0]!.open()

    WebSocketMock.instances[0]!.onmessage?.({
      data: JSON.stringify({
        event_type: 'dialogue',
        payload: {
          text: 'Je reste avec toi.',
          speaker: 'Elara',
          entry_kind: 'dialogue',
        },
      }),
    })

    expect(gameStore.narrativeLog.at(-1)).toMatchObject({
      type: 'dialogue',
      text: 'Je reste avec toi.',
      speaker: 'Elara',
    })

    socket.disconnect()
    vi.unstubAllGlobals()
  })

  it('accepts social_outcome events without adding narrative entries', () => {
    const socket = useWebSocket('session-1')
    const gameStore = useGameStore()

    socket.connect('hero-1')
    WebSocketMock.instances[0]!.open()
    gameStore.setProcessing(true)

    WebSocketMock.instances[0]!.onmessage?.({
      data: JSON.stringify({
        event_type: 'social_outcome',
        payload: {
          npc_id: 'azaka',
          attitude: 'friendly',
          note: 'Azaka accepte de guider le groupe.',
        },
      }),
    })

    expect(gameStore.isProcessing).toBe(false)
    expect(gameStore.narrativeLog).toHaveLength(0)

    socket.disconnect()
    vi.unstubAllGlobals()
  })

  it('resets local state when the campaign reset event arrives', () => {
    const socket = useWebSocket('session-1')
    const gameStore = useGameStore()
    const charStore = useCharacterStore()
    const loadCharacters = vi.spyOn(charStore, 'loadSessionCharacters').mockResolvedValue()

    socket.connect('hero-1')
    WebSocketMock.instances[0]!.open()
    gameStore.applyPhaseChange('combat')
    gameStore.addNarration({ text: 'Ancien journal.' })

    WebSocketMock.instances[0]!.onmessage?.({
      data: JSON.stringify({
        event_type: 'session_reset',
        payload: { session_id: 'session-1' },
      }),
    })

    expect(gameStore.phase).toBe('lobby')
    expect(gameStore.narrativeLog).toHaveLength(0)
    expect(gameStore.connected).toBe(true)
    expect(loadCharacters).toHaveBeenCalledWith('session-1')

    loadCharacters.mockRestore()
    socket.disconnect()
    vi.unstubAllGlobals()
  })

  it('reconnects with exponential delay and jitter', () => {
    vi.useFakeTimers()
    vi.spyOn(Math, 'random').mockReturnValue(0)

    const socket = useWebSocket('session-1')
    socket.connect('hero-1')
    WebSocketMock.instances[0]!.open()

    WebSocketMock.instances[0]!.close()
    expect(socket.reconnectCount.value).toBe(1)
    vi.advanceTimersByTime(999)
    expect(WebSocketMock.instances).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(WebSocketMock.instances).toHaveLength(2)

    WebSocketMock.instances[1]!.close()
    expect(socket.reconnectCount.value).toBe(2)
    vi.advanceTimersByTime(1_999)
    expect(WebSocketMock.instances).toHaveLength(2)
    vi.advanceTimersByTime(1)
    expect(WebSocketMock.instances).toHaveLength(3)

    socket.disconnect()
    vi.restoreAllMocks()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('clears processing state when the socket closes', () => {
    const socket = useWebSocket('session-1')
    const gameStore = useGameStore()

    socket.connect('hero-1')
    WebSocketMock.instances[0]!.open()
    gameStore.setProcessing(true)
    gameStore.applyAiThinking({ agent_kind: 'gm', thinking: true })

    WebSocketMock.instances[0]!.close()

    expect(gameStore.isProcessing).toBe(false)
    expect(gameStore.isGmThinking).toBe(false)

    socket.disconnect()
    vi.unstubAllGlobals()
  })

  it('closes and reconnects when pong timeout expires', () => {
    vi.useFakeTimers()
    vi.spyOn(Math, 'random').mockReturnValue(0)

    const socket = useWebSocket('session-1')
    socket.connect('hero-1')
    WebSocketMock.instances[0]!.open()

    vi.advanceTimersByTime(90_000)

    expect(socket.reconnectCount.value).toBe(1)
    vi.advanceTimersByTime(1_000)
    expect(WebSocketMock.instances).toHaveLength(2)

    socket.disconnect()
    vi.restoreAllMocks()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('applies combatants carried by session_state', () => {
    const socket = useWebSocket('session-1')
    const gameStore = useGameStore()

    socket.connect('hero-1')
    WebSocketMock.instances[0]!.open()
    WebSocketMock.instances[0]!.onmessage?.({
      data: JSON.stringify({
        event_type: 'session_state',
        payload: {
          session_id: 'session-1',
          phase: 'combat',
          turn_number: 1,
          round_number: 1,
          turn_order: [{ id: 'hero-1', name: 'Aria', initiative: 15, is_ai: false, is_player: true }],
          current_turn_index: 0,
          valid_transitions: [],
          combatants: [{
            id: 'hero-1',
            name: 'Aria',
            initiative: 15,
            hp_current: 8,
            hp_max: 10,
            kind: 'pc',
            conditions: [],
            is_ai: false,
            is_active: true,
            ac: 14,
          }],
          grid_config: { cols: 10, rows: 8, cell_size_m: 1.5 },
          grid_decoration: { obstacles: [{ col: 1, row: 1 }] },
        },
      }),
    })

    expect(gameStore.combatants).toHaveLength(1)
    expect(gameStore.currentTurnId).toBe('hero-1')
    expect(gameStore.gridDecoration?.obstacles).toEqual([{ col: 1, row: 1 }])

    socket.disconnect()
    vi.unstubAllGlobals()
  })
})
