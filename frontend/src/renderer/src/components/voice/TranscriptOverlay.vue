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
  margin-bottom: 10px;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  background: rgba(19, 22, 28, 0.8);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.06);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.35),
    0 0 0 1px rgba(255, 255, 255, 0.03),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  z-index: 10;
}

.to__recording,
.to__processing {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: var(--text-base);
  color: var(--text-secondary);
}

.to__recording {
  color: #e74c3c;
}

.to__bars {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 18px;
}

.to__bar {
  width: 3px;
  min-height: 3px;
  border-radius: 1.5px;
  background: currentColor;
  transition: height 0.08s ease;
  box-shadow: 0 0 4px rgba(231, 76, 60, 0.3);
}

.to__label {
  flex: 1;
  letter-spacing: 0.02em;
}

.to__duration {
  font-variant-numeric: tabular-nums;
  font-size: var(--text-sm);
  opacity: 0.6;
  font-weight: var(--weight-medium);
}

.to__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #e74c3c;
  box-shadow: 0 0 8px rgba(231, 76, 60, 0.5);
  animation: dotPulse 1.2s ease-in-out infinite;
}

.to__spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(201, 168, 76, 0.2);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.to__result {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.to__text {
  margin: 0;
  font-size: var(--text-md);
  color: var(--text-primary);
  line-height: var(--leading-relaxed);
  letter-spacing: 0.01em;
  animation: textReveal 0.3s ease both;
}

.to__actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.to__btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  cursor: pointer;
  transition: background 0.2s, box-shadow 0.2s, transform 0.15s;
  letter-spacing: 0.02em;
}

.to__btn--send {
  background: linear-gradient(135deg, var(--accent), rgba(212, 182, 94, 0.9));
  color: #0c0e12;
  box-shadow: 0 2px 8px rgba(201, 168, 76, 0.25);
}

.to__btn--send:hover {
  background: linear-gradient(135deg, #d4b65e, var(--accent));
  box-shadow: 0 4px 16px rgba(201, 168, 76, 0.35);
  transform: translateY(-1px);
}

.to__btn--dismiss {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-secondary);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.to__btn--dismiss:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.1);
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-up-enter-from {
  opacity: 0;
  transform: translateY(12px) scale(0.97);
}

.slide-up-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.97);
}

@keyframes dotPulse {

  0%,
  100% {
    opacity: 1;
    box-shadow: 0 0 8px rgba(231, 76, 60, 0.5);
  }

  50% {
    opacity: 0.3;
    box-shadow: 0 0 16px rgba(231, 76, 60, 0.7);
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes textReveal {
  from {
    opacity: 0;
    transform: translateY(4px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
