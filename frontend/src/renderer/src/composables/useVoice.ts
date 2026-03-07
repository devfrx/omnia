/**
 * useVoice — composable for voice interaction (STT + TTS).
 *
 * Manages microphone capture, binary PCM streaming to the backend,
 * and TTS playback from backend responses.
 *
 * Audio capture uses toggle-to-talk: the client sends `voice_start`,
 * streams raw PCM-16 binary frames, then sends `voice_stop` to
 * trigger server-side STT transcription.
 */

import { computed, onScopeDispose, ref, shallowRef, watch, type ComputedRef, type Ref, type ShallowRef } from 'vue'

import { WebSocketManager } from '../services/ws'
import { useVoiceStore } from '../stores/voice'

// ---------------------------------------------------------------------------
// AudioWorklet processor source (inlined as JS to avoid TS loading issues).
// Converts Float32 input → PCM-16 Int16 and posts via MessagePort.
// ---------------------------------------------------------------------------
const PCM_WORKLET_SRC = /* js */ `
class PCMProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0] && inputs[0][0];
    if (!input || input.length === 0) return true;
    const pcm = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) {
      const s = Math.max(-1, Math.min(1, input[i]));
      pcm[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    this.port.postMessage(pcm.buffer, [pcm.buffer]);
    return true;
  }
}
registerProcessor('pcm-processor', PCMProcessor);
`

/** Create a blob URL from the inline worklet source. */
function createWorkletUrl(): string {
  const blob = new Blob([PCM_WORKLET_SRC], { type: 'application/javascript' })
  return URL.createObjectURL(blob)
}

// ---------------------------------------------------------------------------
// Dedicated WebSocket for voice (separate from the chat WS)
// ---------------------------------------------------------------------------

function getVoiceWsUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.hostname || 'localhost'
  const port = '8000'
  return `${protocol}//${host}:${port}/api/voice/ws/voice`
}

const voiceWs = new WebSocketManager(getVoiceWsUrl())
let handlersRegistered = false

// ---------------------------------------------------------------------------
// Public interface
// ---------------------------------------------------------------------------

export interface AudioDevice {
  deviceId: string
  label: string
}

export interface UseVoiceReturn {
  isListening: ComputedRef<boolean>
  isProcessing: ComputedRef<boolean>
  isSpeaking: ComputedRef<boolean>
  transcript: ComputedRef<string>
  audioLevel: ComputedRef<number>
  voiceAvailable: ComputedRef<boolean>
  micPermission: ComputedRef<'granted' | 'denied' | 'prompt'>
  isConnected: ComputedRef<boolean>
  /** List of available audio input devices. */
  audioDevices: ShallowRef<AudioDevice[]>
  /** Currently selected device ID (empty = system default). */
  selectedDeviceId: Ref<string>
  startListening: () => Promise<void>
  stopListening: () => void
  /** Cancel a stuck STT processing state (user-initiated). */
  cancelProcessing: () => void
  speak: (text: string) => void
  cancelSpeak: () => void
  connect: () => void
  disconnect: () => void
  /** Refresh the list of available audio input devices. */
  refreshDevices: () => Promise<void>
}

// ---------------------------------------------------------------------------
// Composable
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'omnia_selected_mic_id'

export function useVoice(): UseVoiceReturn {
  const store = useVoiceStore()

  // -- Local state --
  const isConnected = ref(false)
  const voiceAvailable = ref(false)
  const micPermission = ref<'granted' | 'denied' | 'prompt'>('prompt')

  // -- Device selection --
  const audioDevices = shallowRef<AudioDevice[]>([])
  const savedDeviceId = localStorage.getItem(STORAGE_KEY) ?? ''
  const selectedDeviceId = ref(savedDeviceId)

  // Persist mic selection
  watch(selectedDeviceId, (newId) => {
    if (newId) {
      localStorage.setItem(STORAGE_KEY, newId)
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  })

  // -- Audio capture resources --
  let mediaStream: MediaStream | null = null
  let audioContext: AudioContext | null = null
  let analyserNode: AnalyserNode | null = null
  let workletNode: AudioWorkletNode | null = null
  let levelTimer: ReturnType<typeof setInterval> | null = null
  let workletBlobUrl: string | null = null

  // -- STT processing timeout --
  let sttTimeoutTimer: ReturnType<typeof setTimeout> | null = null
  const STT_TIMEOUT_MS = 135_000 // slightly above backend's 120s limit

  // -- TTS playback resources --
  let playbackCtx: AudioContext | null = null
  let ttsSampleRate = 22050
  const audioQueue: ArrayBuffer[] = []
  let isPlayingQueue = false

  // -----------------------------------------------------------------------
  // WS event handlers
  // -----------------------------------------------------------------------

  const onConnected = (): void => {
    console.log('[OMNIA Voice] WS connected')
    isConnected.value = true
    store.connected = true
  }
  const onDisconnected = (): void => {
    console.log('[OMNIA Voice] WS disconnected')
    isConnected.value = false
    store.connected = false
    if (store.isListening) stopListening()
  }
  const onVoiceReady = (data: unknown): void => {
    const d = data as { stt_available: boolean; tts_available: boolean; sample_rate?: number; stt_model?: string; stt_engine?: string; tts_engine?: string }
    console.log('[OMNIA Voice] voice_ready:', d)
    voiceAvailable.value = d.stt_available || d.tts_available
    store.sttAvailable = d.stt_available
    store.ttsAvailable = d.tts_available
    store.enabled = d.stt_available || d.tts_available
    if (d.sample_rate) ttsSampleRate = d.sample_rate
    store.sttModel = d.stt_model ?? ''
    store.sttEngine = d.stt_engine ?? ''
    store.ttsEngine = d.tts_engine ?? ''
  }
  const onTranscript = (data: unknown): void => {
    const d = data as { text: string }
    console.log('[OMNIA Voice] Transcript received:', d.text)
    clearSttTimeout()
    store.transcript = d.text
    store.isProcessing = false
  }
  const onSttProcessing = (): void => {
    console.log('[OMNIA Voice] STT processing...')
    store.isProcessing = true
    startSttTimeout()
  }
  const onTtsStart = (): void => { store.isSpeaking = true }
  const onTtsDone = (): void => { store.isSpeaking = false }
  const onBinaryAudio = (data: unknown): void => {
    audioQueue.push(data as ArrayBuffer)
    if (!isPlayingQueue) playNextChunk()
  }
  const onVoiceError = (data: unknown): void => {
    const d = data as { message: string }
    console.error('[OMNIA Voice] Error:', d.message)
    clearSttTimeout()
    cleanupAudioResources()
    store.isListening = false
    store.isProcessing = false
    store.audioLevel = 0
    store.stopRecordingTimer()
  }
  const onRecordingStopped = (data: unknown): void => {
    const d = data as { empty?: boolean }
    if (d.empty) {
      clearSttTimeout()
      store.isProcessing = false
    }
  }
  const onTtsCancelled = (): void => {
    store.isSpeaking = false
    audioQueue.length = 0
    isPlayingQueue = false
  }

  // Register handlers (guarded to prevent duplicate registration on singleton)
  if (!handlersRegistered) {
    voiceWs.on('connected', onConnected)
    voiceWs.on('disconnected', onDisconnected)
    voiceWs.on('voice_ready', onVoiceReady)
    voiceWs.on('transcript', onTranscript)
    voiceWs.on('stt_processing', onSttProcessing)
    voiceWs.on('tts_start', onTtsStart)
    voiceWs.on('tts_done', onTtsDone)
    voiceWs.on('binary', onBinaryAudio)
    voiceWs.on('voice_error', onVoiceError)
    voiceWs.on('recording_stopped', onRecordingStopped)
    voiceWs.on('tts_cancelled', onTtsCancelled)
    handlersRegistered = true
  }

  // -----------------------------------------------------------------------
  // STT processing timeout
  // -----------------------------------------------------------------------

  function startSttTimeout(): void {
    clearSttTimeout()
    sttTimeoutTimer = setTimeout(() => {
      console.warn(`[OMNIA Voice] STT processing timed out after ${STT_TIMEOUT_MS / 1000}s`)
      cleanupAudioResources()
      store.isListening = false
      store.isProcessing = false
      store.audioLevel = 0
      store.stopRecordingTimer()
    }, STT_TIMEOUT_MS)
  }

  function clearSttTimeout(): void {
    if (sttTimeoutTimer) {
      clearTimeout(sttTimeoutTimer)
      sttTimeoutTimer = null
    }
  }

  // -----------------------------------------------------------------------
  // Audio resource cleanup (idempotent — safe to call multiple times)
  // -----------------------------------------------------------------------

  function cleanupAudioResources(): void {
    if (levelTimer) { clearInterval(levelTimer); levelTimer = null }
    if (workletNode) { workletNode.disconnect(); workletNode = null }
    if (analyserNode) { analyserNode.disconnect(); analyserNode = null }
    if (audioContext) { audioContext.close(); audioContext = null }
    if (mediaStream) { mediaStream.getTracks().forEach((t) => t.stop()); mediaStream = null }
    if (playbackCtx) { playbackCtx.close(); playbackCtx = null }
    audioQueue.length = 0
    isPlayingQueue = false
  }

  // -----------------------------------------------------------------------
  // Cancel a stuck processing state (user-initiated)
  // -----------------------------------------------------------------------

  function cancelProcessing(): void {
    console.log('[OMNIA Voice] Cancelling stuck processing state')
    clearSttTimeout()
    cleanupAudioResources()
    store.isListening = false
    store.isProcessing = false
    store.audioLevel = 0
    store.stopRecordingTimer()
  }

  // -----------------------------------------------------------------------
  // Microphone capture
  // -----------------------------------------------------------------------

  async function startListening(): Promise<void> {
    if (store.isListening) return
    if (!voiceWs.isConnected) {
      console.warn('[OMNIA Voice] Voice WS not connected, cannot start listening')
      return
    }

    console.log('[OMNIA Voice] Starting mic capture...')

    // Refresh devices to validate saved device (fallback handled inside refreshDevices)
    await refreshDevices()

    // Build audio constraints with optional device selection
    const audioConstraints: MediaTrackConstraints = {
      sampleRate: 16000,
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
    }
    if (selectedDeviceId.value) {
      audioConstraints.deviceId = { exact: selectedDeviceId.value }
    }

    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints })
      micPermission.value = 'granted'
      store.micPermission = 'granted'
    } catch (err) {
      console.error('[OMNIA Voice] Mic permission denied or error:', err)
      micPermission.value = 'denied'
      store.micPermission = 'denied'
      return
    }

    // Log which device is actually being used
    const track = mediaStream.getAudioTracks()[0]
    const settings = track.getSettings()
    console.log('[OMNIA Voice] Using mic:', track.label, '| deviceId:', settings.deviceId)

    // Refresh device list now that we have permission (labels become available)
    await refreshDevices()

    audioContext = new AudioContext({ sampleRate: 16000 })
    const actualSampleRate = audioContext.sampleRate
    console.log(`[OMNIA Voice] AudioContext sampleRate: requested=16000, actual=${actualSampleRate}`)
    const source = audioContext.createMediaStreamSource(mediaStream)

    // Level analyser
    analyserNode = audioContext.createAnalyser()
    analyserNode.fftSize = 256
    source.connect(analyserNode)
    levelTimer = setInterval(() => {
      if (!analyserNode) return
      const buf = new Uint8Array(analyserNode.frequencyBinCount)
      analyserNode.getByteFrequencyData(buf)
      store.audioLevel = buf.reduce((a, b) => a + b, 0) / buf.length / 255
    }, 100)

    // PCM capture via AudioWorklet (loaded from inline blob URL)
    try {
      if (!workletBlobUrl) workletBlobUrl = createWorkletUrl()
      await audioContext.audioWorklet.addModule(workletBlobUrl)
    } catch (err) {
      console.error('[OMNIA Voice] AudioWorklet addModule failed:', err)
      // Cleanup on failure
      if (levelTimer) { clearInterval(levelTimer); levelTimer = null }
      analyserNode?.disconnect(); analyserNode = null
      audioContext.close(); audioContext = null
      mediaStream.getTracks().forEach((t) => t.stop()); mediaStream = null
      return
    }

    workletNode = new AudioWorkletNode(audioContext, 'pcm-processor')
    workletNode.port.onmessage = (e: MessageEvent<ArrayBuffer>): void => {
      // Backpressure handling is managed in ws.ts via bufferedAmount checks
      voiceWs.sendBinary(e.data)
    }
    source.connect(workletNode)
    workletNode.connect(audioContext.destination)

    // Tell backend to start recording (include actual sample rate)
    voiceWs.send({ type: 'voice_start', sample_rate: actualSampleRate })
    store.isListening = true
    store.startRecordingTimer()
    console.log('[OMNIA Voice] Recording started, streaming PCM to backend')
  }

  function stopListening(): void {
    if (!store.isListening) return
    store.isListening = false
    store.stopRecordingTimer()
    store.audioLevel = 0
    console.log('[OMNIA Voice] Stopping recording, sending voice_stop')

    // Tell backend to stop recording and process STT
    voiceWs.send({ type: 'voice_stop' })

    // Release audio resources
    cleanupAudioResources()
  }

  // -----------------------------------------------------------------------
  // Device enumeration
  // -----------------------------------------------------------------------

  async function refreshDevices(): Promise<void> {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices()
      audioDevices.value = devices
        .filter((d) => d.kind === 'audioinput')
        .map((d) => ({ deviceId: d.deviceId, label: d.label || `Microfono (${d.deviceId.slice(0, 8)})` }))
      console.log('[OMNIA Voice] Available audio devices:', audioDevices.value)
      if (selectedDeviceId.value && !audioDevices.value.some(d => d.deviceId === selectedDeviceId.value)) {
        console.warn('[OMNIA Voice] Selected mic device disappeared from device list, resetting to default')
        selectedDeviceId.value = ''
      }
    } catch (err) {
      console.error('[OMNIA Voice] Failed to enumerate devices:', err)
    }
  }

  // -----------------------------------------------------------------------
  // TTS playback
  // -----------------------------------------------------------------------

  function speak(text: string): void {
    voiceWs.send({ type: 'tts_speak', text })
  }

  function cancelSpeak(): void {
    voiceWs.send({ type: 'tts_cancel' })
    audioQueue.length = 0
    store.isSpeaking = false
  }

  async function playNextChunk(): Promise<void> {
    if (audioQueue.length === 0) { isPlayingQueue = false; return }
    isPlayingQueue = true
    if (!playbackCtx) playbackCtx = new AudioContext({ sampleRate: ttsSampleRate })
    const chunk = audioQueue.shift()!
    try {
      const buf = await playbackCtx.decodeAudioData(chunk.slice(0))
      const src = playbackCtx.createBufferSource()
      src.buffer = buf
      src.connect(playbackCtx.destination)
      src.onended = () => playNextChunk()
      src.start()
    } catch (err) {
      console.warn('[OMNIA Voice] Failed to decode audio chunk:', err)
      setTimeout(() => playNextChunk(), 0)
    }
  }

  // -----------------------------------------------------------------------
  // Connection helpers
  // -----------------------------------------------------------------------

  function connect(): void {
    voiceWs.connect()
    // Enumerate devices on connect (may need mic permission first for labels)
    void refreshDevices()
  }
  function disconnect(): void {
    clearSttTimeout()
    stopListening()
    cancelSpeak()
    voiceWs.disconnect()
    cleanupAudioResources()
    if (playbackCtx) { playbackCtx.close(); playbackCtx = null }
    audioQueue.length = 0
    isPlayingQueue = false
    if (workletBlobUrl) { URL.revokeObjectURL(workletBlobUrl); workletBlobUrl = null }
  }

  // -----------------------------------------------------------------------
  // Cleanup
  // -----------------------------------------------------------------------

  onScopeDispose(() => {
    disconnect()
    voiceWs.off('connected', onConnected)
    voiceWs.off('disconnected', onDisconnected)
    voiceWs.off('voice_ready', onVoiceReady)
    voiceWs.off('transcript', onTranscript)
    voiceWs.off('stt_processing', onSttProcessing)
    voiceWs.off('tts_start', onTtsStart)
    voiceWs.off('tts_done', onTtsDone)
    voiceWs.off('binary', onBinaryAudio)
    voiceWs.off('voice_error', onVoiceError)
    voiceWs.off('recording_stopped', onRecordingStopped)
    voiceWs.off('tts_cancelled', onTtsCancelled)
    handlersRegistered = false
  })

  return {
    isListening: computed(() => store.isListening),
    isProcessing: computed(() => store.isProcessing),
    isSpeaking: computed(() => store.isSpeaking),
    transcript: computed(() => store.transcript),
    audioLevel: computed(() => store.audioLevel),
    voiceAvailable: computed(() => voiceAvailable.value),
    micPermission: computed(() => micPermission.value),
    isConnected: computed(() => isConnected.value),
    audioDevices,
    selectedDeviceId,
    startListening,
    stopListening,
    cancelProcessing,
    speak,
    cancelSpeak,
    connect,
    disconnect,
    refreshDevices,
  }
}
