import { describe, expect, it, vi } from 'vitest'

import { useAudio } from '../useAudio'

describe('useAudio', () => {
  it('decodes base64 audio and starts playback', async () => {
    const source = {
      buffer: null as AudioBuffer | null,
      connect: vi.fn(),
      start: vi.fn(),
      stop: vi.fn(),
      onended: null as (() => void) | null,
    }
    const ctx = {
      state: 'suspended',
      destination: {},
      resume: vi.fn(async () => {
        ctx.state = 'running'
      }),
      decodeAudioData: vi.fn(async () => ({ duration: 1 }) as AudioBuffer),
      createBufferSource: vi.fn(() => source),
    }
    class AudioContextMock {
      constructor() {
        return ctx
      }
    }
    vi.stubGlobal('AudioContext', AudioContextMock)
    vi.stubGlobal('atob', vi.fn(() => String.fromCharCode(1, 2, 3)))

    const audio = useAudio()
    await audio.playAudioB64('AQID')

    expect(ctx.resume).toHaveBeenCalled()
    expect(ctx.decodeAudioData).toHaveBeenCalled()
    expect(ctx.createBufferSource).toHaveBeenCalled()
    expect(source.connect).toHaveBeenCalledWith(ctx.destination)
    expect(source.start).toHaveBeenCalled()
    expect(audio.error.value).toBeNull()
    expect(audio.isPlaying.value).toBe(true)

    ctx.state = 'closed'
    vi.unstubAllGlobals()
  })

  it('cancels current audio and clears playing state', async () => {
    const source = {
      buffer: null as AudioBuffer | null,
      connect: vi.fn(),
      start: vi.fn(),
      stop: vi.fn(),
      onended: null as (() => void) | null,
    }
    const ctx = {
      state: 'running',
      destination: {},
      resume: vi.fn(),
      decodeAudioData: vi.fn(async () => ({ duration: 1 }) as AudioBuffer),
      createBufferSource: vi.fn(() => source),
    }
    class AudioContextMock {
      constructor() {
        return ctx
      }
    }
    vi.stubGlobal('AudioContext', AudioContextMock)
    vi.stubGlobal('atob', vi.fn(() => String.fromCharCode(1, 2, 3)))

    const audio = useAudio()
    await audio.playAudioB64('AQID')
    audio.cancelAll()

    expect(source.stop).toHaveBeenCalled()
    expect(audio.isPlaying.value).toBe(false)

    vi.unstubAllGlobals()
  })
})
