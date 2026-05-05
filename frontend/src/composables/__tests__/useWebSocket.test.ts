import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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
})
