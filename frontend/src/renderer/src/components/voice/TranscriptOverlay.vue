<script setup lang="ts">
/**
 * TranscriptOverlay.vue — Live STT transcript display.
 *
 * Shows the current transcript text as a floating overlay
 * when the user is speaking or when STT is processing.
 * Auto-hides after the transcript is consumed.
 */
import { computed } from 'vue'

const props = defineProps<{
  /** The current transcript text from STT. */
  text: string
  /** Whether STT is currently processing. */
  isProcessing: boolean
  /** Whether currently recording. */
  isRecording: boolean
  /** Audio level 0-1 from the microphone. */
  audioLevel: number
  /** Formatted recording duration (e.g. "0:05"). */
  duration: string
  /** If true, transcript is auto-sent (no Invia/Annulla shown). */
  autoSend: boolean
}>()

const emit = defineEmits<{
  /** Fired when user clicks to send the transcript as a message. */
  send: [text: string]
  /** Fired when user dismisses the transcript. */
  dismiss: []
}>()

const barCount = 5
const bars = computed(() => {
  if (!props.isRecording) return Array(barCount).fill('15%')
  return Array.from({ length: barCount }, (_, i) => {
    const threshold = (i + 1) / (barCount + 1)
    const height = Math.max(0.15, Math.min(1, props.audioLevel * 1.5 - threshold + 0.5))
    return `${height * 100}%`
  })
})

const visible = computed(() => {
  return props.isRecording || props.isProcessing || (props.text.length > 0 && !props.autoSend)
})

function handleSend(): void {
  if (props.text.trim()) {
    emit('send', props.text.trim())
  }
}

function handleDismiss(): void {
  emit('dismiss')
}
</script>

<template>
  <Transition name="slide-up">
    <div v-if="visible" class="to" role="status" aria-live="polite">
      <!-- Recording indicator -->
      <div v-if="isRecording && !text" class="to__recording">
        <span class="to__dot" />
        <div class="to__bars">
          <span v-for="(h, i) in bars" :key="i" class="to__bar" :style="{ height: h }" />
        </div>
        <span class="to__label">In ascolto...</span>
        <span class="to__duration">{{ duration }}</span>
      </div>

      <!-- Processing indicator -->
      <div v-else-if="isProcessing && !text" class="to__processing">
        <span class="to__spinner" />
        <span>Trascrizione in corso...</span>
      </div>

      <!-- Transcript text -->
      <div v-else-if="text" class="to__result">
        <p class="to__text">{{ text }}</p>
        <div class="to__actions">
          <button class="to__btn to__btn--send" aria-label="Invia come messaggio" @click="handleSend">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
            Invia
          </button>
          <button class="to__btn to__btn--dismiss" aria-label="Annulla" @click="handleDismiss">
            Annulla
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.to {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  margin-bottom: 8px;
  padding: 10px 14px;
  border-radius: 10px;
  background: var(--bg-secondary, #1e1e22);
  border: 1px solid rgba(255, 255, 255, 0.06);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  z-index: 10;
}

.to__recording,
.to__processing {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.82rem;
  color: var(--text-secondary, #a0a0a0);
}

.to__recording {
  color: #e74c3c;
}

.to__bars {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 16px;
}

.to__bar {
  width: 3px;
  min-height: 2px;
  border-radius: 1.5px;
  background: currentColor;
  transition: height 0.1s ease;
}

.to__label {
  flex: 1;
}

.to__duration {
  font-variant-numeric: tabular-nums;
  font-size: 0.78rem;
  opacity: 0.7;
}

.to__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #e74c3c;
  animation: blink 1s ease-in-out infinite;
}

.to__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid transparent;
  border-top-color: var(--accent, #c8a23c);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.to__result {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.to__text {
  margin: 0;
  font-size: 0.88rem;
  color: var(--text-primary, #e0e0e0);
  line-height: 1.4;
}

.to__actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.to__btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border: none;
  border-radius: 6px;
  font-size: 0.78rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}

.to__btn--send {
  background: var(--accent, #c8a23c);
  color: #000;
}

.to__btn--send:hover {
  background: #d4ae4a;
}

.to__btn--dismiss {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-secondary, #a0a0a0);
}

.to__btn--dismiss:hover {
  background: rgba(255, 255, 255, 0.1);
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.2s ease;
}

.slide-up-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.slide-up-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

@keyframes blink {

  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0.3;
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
