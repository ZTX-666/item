import { ref } from 'vue'

interface VoiceOptions {
  onResult?: (transcript: string) => void
  onEnd?: (finalTranscript: string) => void
  onError?: (error: string) => void
  onStart?: () => void
  onStatus?: (status: string) => void
}

function encodeWav(samples: Float32Array, sampleRate: number): ArrayBuffer {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)

  const writeString = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i))
  }

  writeString(0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  writeString(8, 'WAVE')
  writeString(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(36, 'data')
  view.setUint32(40, samples.length * 2, true)

  let offset = 44
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    offset += 2
  }

  return buffer
}

export function useVoice(options: VoiceOptions = {}) {
  const isRecording = ref(false)
  const isProcessing = ref(false)
  const transcript = ref('')

  let audioContext: AudioContext | null = null
  let mediaStream: MediaStream | null = null
  let processor: ScriptProcessorNode | null = null
  let recorded: Float32Array[] = []
  let statusUnsub: (() => void) | undefined

  const { onResult, onEnd, onError, onStart, onStatus } = options

  async function start() {
    if (!window.electronAPI?.transcribeSpeech) {
      onError?.('not-supported')
      return
    }

    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      audioContext = new AudioContext({ sampleRate: 16000 })
      const source = audioContext.createMediaStreamSource(mediaStream)
      processor = audioContext.createScriptProcessor(4096, 1, 1)
      recorded = []

      statusUnsub = window.electronAPI.onSpeechStatus?.((status) => {
        onStatus?.(status)
        if (status === 'loading-model') isProcessing.value = true
      })

      processor.onaudioprocess = (e) => {
        recorded.push(new Float32Array(e.inputBuffer.getChannelData(0)))
      }

      source.connect(processor)
      processor.connect(audioContext.destination)
      isRecording.value = true
      onStart?.()
    } catch (err: unknown) {
      const name = err instanceof DOMException ? err.name : ''
      if (name === 'NotAllowedError') onError?.('not-allowed')
      else onError?.('not-supported')
    }
  }

  async function stop() {
    if (!isRecording.value) return
    isRecording.value = false

    processor?.disconnect()
    mediaStream?.getTracks().forEach((t) => t.stop())
    await audioContext?.close()
    processor = null
    mediaStream = null
    audioContext = null
    statusUnsub?.()
    statusUnsub = undefined

    if (recorded.length === 0) {
      onEnd?.('')
      return
    }

    const totalLength = recorded.reduce((sum, chunk) => sum + chunk.length, 0)
    const samples = new Float32Array(totalLength)
    let offset = 0
    for (const chunk of recorded) {
      samples.set(chunk, offset)
      offset += chunk.length
    }

    isProcessing.value = true
    try {
      const wavBuffer = encodeWav(samples, 16000)
      const result = await window.electronAPI!.transcribeSpeech(wavBuffer)

      if (!result.ok) {
        onError?.(result.error || 'transcription-failed')
        onEnd?.('')
        return
      }

      transcript.value = result.text || ''
      onResult?.(transcript.value)
      onEnd?.(transcript.value)
    } catch {
      onError?.('transcription-failed')
      onEnd?.('')
    } finally {
      isProcessing.value = false
      recorded = []
    }
  }

  function toggle() {
    if (isRecording.value) stop()
    else start()
  }

  return { isRecording, isProcessing, transcript, start, stop, toggle }
}
