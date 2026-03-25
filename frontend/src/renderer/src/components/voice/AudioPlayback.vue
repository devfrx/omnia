<script setup lang="ts">
/**
 * AudioPlayback.vue — TTS audio playback manager.
 *
 * Receives audio chunks from WebSocket, queues them,
 * and plays them sequentially using the Web Audio API.
 * Shows a minimal playback control when audio is playing.
 */
import { onBeforeUnmount, ref } from 'vue'
import { useVoiceStore } from '../../stores/voice'
import AppIcon from '../ui/AppIcon.vue'

const store = useVoiceStore()

const props = defineProps<{
  /** Sample rate of incoming audio (from backend TTS config). */
  sampleRate: number
}>()

const emit = defineEmits<{
  /** Fired when user cancels playback. */
  cancel: []
}>()

// -- Audio state --
let audioContext: AudioContext | null = null
let currentSource: AudioBufferSourceNode | null = null
const isPlaying = ref(false)
const audioQueue = ref<ArrayBuffer[]>([])

/** Enqueue an audio chunk for playback. */
function enqueueChunk(chunk: ArrayBuffer): void {
  audioQueue.value.push(chunk)
  if (!isPlaying.value) {
    playNext()
  }
}

/** Play the next chunk from the queue. */
async function playNext(): Promise<void> {
  if (audioQueue.value.length === 0) {
    isPlaying.value = false
    store.isSpeaking = false
    return
  }

  if (!audioContext) {
    audioContext = new AudioContext({ sampleRate: props.sampleRate })
  }

  if (audioContext.state === 'suspended') {
    await audioContext.resume()
  }

  isPlaying.value = true
  store.isSpeaking = true
  const chunk = audioQueue.value.shift()!

  try {
    const buffer = await audioContext.decodeAudioData(chunk.slice(0))
    currentSource = audioContext.createBufferSource()
    currentSource.buffer = buffer
    currentSource.connect(audioContext.destination)
    currentSource.onended = () => {
      currentSource = null
      playNext()
    }
    currentSource.start()
  } catch (err) {
    console.error('[AudioPlayback] decode error:', err)
    playNext()
  }
}

/** Stop all playback and clear the queue. */
function cancelPlayback(): void {
  audioQueue.value = []
  if (currentSource) {
    currentSource.stop()
    currentSource = null
  }
  isPlaying.value = false
  store.isSpeaking = false
  emit('cancel')
}

/** Cleanup on unmount. */
onBeforeUnmount(() => {
  cancelPlayback()
  if (audioContext) {
    audioContext.close()
    audioContext = null
  }
})

// Expose for parent
defineExpose({ enqueueChunk, cancelPlayback })
</script>

<template>
  <Transition name="fade">
    <div v-if="isPlaying" class="ap" role="status" aria-label="Riproduzione audio TTS">
      <!-- Speaking icon -->
      <AppIcon name="volume" :size="14" class="ap__icon" />
      <span class="ap__label">TTS</span>
      <!-- Cancel button -->
      <button class="ap__cancel" aria-label="Interrompi audio" @click="cancelPlayback">
        <AppIcon name="x" :size="12" :stroke-width="2.5" />
      </button>
    </div>
  </Transition>
</template>

<style scoped>
.ap {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1-5);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-pill);
  background: var(--speaking-dim);
  color: var(--speaking);
  font-size: var(--text-xs);
  font-weight: var(--weight-medium);
}

.ap__icon {
  flex-shrink: 0;
}

.ap__label {
  letter-spacing: 0.02em;
}

.ap__cancel {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: none;
  border-radius: var(--radius-full);
  background: var(--surface-hover);
  color: inherit;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.ap__cancel:hover {
  background: var(--surface-active);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--transition-fast);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
