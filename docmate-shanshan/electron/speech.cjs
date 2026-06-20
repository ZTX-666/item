const fs = require('fs')
const path = require('path')
const { app } = require('electron')

let transcriberPromise = null
let modelReady = false

function getModelDir() {
  return path.join(app.getPath('userData'), 'whisper-models')
}

async function getTranscriber(onProgress) {
  if (transcriberPromise) return transcriberPromise

  transcriberPromise = (async () => {
    onProgress?.('loading-model')
    fs.mkdirSync(getModelDir(), { recursive: true })

    process.env.TRANSFORMERS_CACHE = getModelDir()
    process.env.HF_HUB_CACHE = getModelDir()

    const { pipeline, env } = await import('@xenova/transformers')
    env.cacheDir = getModelDir()
    env.allowLocalModels = true

    const transcriber = await pipeline(
      'automatic-speech-recognition',
      'Xenova/whisper-tiny',
      { quantized: true },
    )
    modelReady = true
    onProgress?.('ready')
    return transcriber
  })().catch((err) => {
    transcriberPromise = null
    throw err
  })

  return transcriberPromise
}

function decodeAudioBuffer(arrayBuffer) {
  const audioBuffer = toArrayBuffer(arrayBuffer)
  const view = new DataView(audioBuffer)
  const numChannels = view.getUint16(22, true)
  const sampleRate = view.getUint32(24, true)
  const bitsPerSample = view.getUint16(34, true)
  const dataOffset = 44
  const numSamples = (audioBuffer.byteLength - dataOffset) / (bitsPerSample / 8) / numChannels

  const samples = new Float32Array(numSamples)
  if (bitsPerSample === 16) {
    for (let i = 0; i < numSamples; i++) {
      const offset = dataOffset + i * numChannels * 2
      let sample = view.getInt16(offset, true)
      samples[i] = sample / 32768
    }
  }
  return { samples, sampleRate }
}

function toArrayBuffer(input) {
  if (input instanceof ArrayBuffer) return input
  if (ArrayBuffer.isView(input)) {
    return input.buffer.slice(input.byteOffset, input.byteOffset + input.byteLength)
  }
  return Buffer.from(input).buffer
}

async function transcribeAudioBuffer(arrayBuffer, onProgress) {
  const transcriber = await getTranscriber(onProgress)
  const { samples } = decodeAudioBuffer(arrayBuffer)

  const result = await transcriber(samples, {
    language: 'chinese',
    task: 'transcribe',
    chunk_length_s: 30,
    return_timestamps: false,
  })

  const text = (result?.text || '').trim()
  if (!text) throw new Error('未识别到语音内容，请重试')
  return text
}

function resolveSpeechApiUrl(settings) {
  if (settings.speechApiUrl?.trim()) return settings.speechApiUrl.trim()
  const apiUrl = settings.apiUrl || ''
  if (apiUrl.includes('/chat/completions')) {
    return apiUrl.replace('/chat/completions', '/audio/transcriptions')
  }
  return apiUrl.replace(/\/$/, '') + '/audio/transcriptions'
}

async function transcribeOnline(arrayBuffer, settings, onProgress) {
  if (!settings?.useApi || !settings.apiKey) throw new Error('未配置在线语音识别 API Key')
  const url = resolveSpeechApiUrl(settings)
  const form = new FormData()
  form.append('model', settings.speechModel || 'whisper-1')
  form.append('language', 'zh')
  form.append('file', new Blob([toArrayBuffer(arrayBuffer)], { type: 'audio/wav' }), 'speech.wav')
  onProgress?.('online-transcribing')

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${settings.apiKey}`,
    },
    body: form,
    signal: AbortSignal.timeout(60000),
  })

  if (!response.ok) {
    const errText = await response.text().catch(() => '')
    throw new Error(`在线语音识别失败 (${response.status}): ${errText.slice(0, 120)}`)
  }
  const data = await response.json()
  const text = (data.text || data.result || data.transcript || '').trim()
  if (!text) throw new Error('在线语音识别未返回文字')
  return text
}

async function transcribeSmart(arrayBuffer, settings = {}, onProgress) {
  const mode = settings.speechMode || 'online-first'
  if (mode === 'local') return transcribeAudioBuffer(arrayBuffer, onProgress)
  if (mode === 'online') return transcribeOnline(arrayBuffer, settings, onProgress)
  try {
    return await transcribeOnline(arrayBuffer, settings, onProgress)
  } catch (err) {
    onProgress?.('online-fallback')
    console.warn('在线语音识别失败，回退本地识别:', err.message || err)
    return transcribeAudioBuffer(arrayBuffer, onProgress)
  }
}

function isModelReady() {
  return modelReady
}

module.exports = { transcribeAudioBuffer: transcribeSmart, getTranscriber, isModelReady }
