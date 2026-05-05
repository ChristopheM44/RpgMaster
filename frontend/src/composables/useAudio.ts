/**
 * Composable pour la lecture audio TTS.
 *
 * Reçoit un payload base64 WAV depuis le WebSocket et le joue via Web Audio API.
 * Gère une file d'attente simple pour éviter les chevauchements audio.
 */
import { ref } from 'vue'

let _audioCtx: AudioContext | null = null
const MAX_QUEUE_SIZE = 20

function getAudioContext(): AudioContext {
  if (!_audioCtx || _audioCtx.state === 'closed') {
    _audioCtx = new AudioContext()
  }
  return _audioCtx
}

export function useAudio() {
  const isPlaying = ref(false)
  const error = ref<string | null>(null)

  // File d'attente des buffers à jouer
  const _queue: AudioBuffer[] = []
  let _playing = false
  let _currentSource: AudioBufferSourceNode | null = null

  async function _playNext() {
    if (_playing || _queue.length === 0) return
    _playing = true
    isPlaying.value = true

    const buffer = _queue.shift()!
    const ctx = getAudioContext()
    const source = ctx.createBufferSource()
    _currentSource = source
    source.buffer = buffer
    source.connect(ctx.destination)
    source.onended = () => {
      if (_currentSource === source) _currentSource = null
      _playing = false
      isPlaying.value = _queue.length > 0
      _playNext()
    }
    source.start()
  }

  async function playAudioB64(b64: string) {
    error.value = null
    try {
      // Décode le base64 en ArrayBuffer
      const binary = atob(b64)
      const bytes = new Uint8Array(binary.length)
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i)
      }

      const ctx = getAudioContext()
      // Résume le contexte si suspendu (politique autoplay navigateur)
      if (ctx.state === 'suspended') {
        await ctx.resume()
      }

      const audioBuffer = await ctx.decodeAudioData(bytes.buffer)
      if (_queue.length >= MAX_QUEUE_SIZE) {
        _queue.shift()
      }
      _queue.push(audioBuffer)
      _playNext()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur lecture audio'
      _playing = false
      isPlaying.value = false
    }
  }

  function cancelAll() {
    _queue.splice(0)
    if (_currentSource) {
      const source = _currentSource
      _currentSource = null
      source.onended = null
      try {
        source.stop()
      } catch {
        // Already stopped.
      }
    }
    _playing = false
    isPlaying.value = false
  }

  return { isPlaying, error, playAudioB64, cancelAll }
}
