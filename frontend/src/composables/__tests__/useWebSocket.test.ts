import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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
})
