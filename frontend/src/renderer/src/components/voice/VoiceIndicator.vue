<script setup lang="ts">
/**
 * VoiceIndicator.vue — Audio level visualization (bars or waveform).
 *
 * Shows animated bars that respond to the current audio input level.
 * Used during recording to give visual feedback that the mic is active.
 */
import { computed } from 'vue'

const props = defineProps<{
  /** Audio input level 0-1. */
  level: number
  /** Current voice state. */
  state: 'idle' | 'recording' | 'processing' | 'speaking'
}>()

const barCount = 5
const bars = computed(() => {
  return Array.from({ length: barCount }, (_, i) => {
    const threshold = (i + 1) / (barCount + 1)
    const height = props.state === 'recording'
      ? Math.max(0.15, Math.min(1, props.level * 1.5 - threshold + 0.5))
      : props.state === 'speaking'
        ? 0.3 + 0.1 * ((i + 1) / barCount)
        : 0.15
    return { height: `${height * 100}%` }
  })
})

const stateLabel = computed(() => {
  switch (props.state) {
    case 'recording': return 'In ascolto...'
    case 'processing': return 'Elaborazione...'
    case 'speaking': return 'Parlando...'
    default: return ''
  }
})

const stateClass = computed(() => `vi--${props.state}`)
</script>

<template>
  <div v-if="state !== 'idle'" class="vi" :class="stateClass" role="status" :aria-label="stateLabel">
    <div class="vi__bars">
      <span
        v-for="(bar, index) in bars"
        :key="index"
        class="vi__bar"
        :style="{ height: bar.height }"
      />
    </div>
    <span class="vi__label">{{ stateLabel }}</span>
  </div>
</template>

<style scoped>
.vi {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 0.75rem;
  color: var(--text-secondary, #a0a0a0);
  background: rgba(255, 255, 255, 0.04);
  transition: background 0.2s;
}

.vi--recording {
  background: rgba(231, 76, 60, 0.08);
  color: #e74c3c;
}

.vi--processing {
  background: rgba(200, 162, 60, 0.08);
  color: var(--accent, #c8a23c);
}

.vi--speaking {
  background: rgba(46, 204, 113, 0.08);
  color: #2ecc71;
}

.vi__bars {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 16px;
}

.vi__bar {
  width: 3px;
  min-height: 2px;
  border-radius: 1.5px;
  background: currentColor;
  transition: height 0.1s ease;
}

.vi--speaking .vi__bar {
  animation: speak-pulse 0.6s ease-in-out infinite alternate;
}

.vi--speaking .vi__bar:nth-child(2) { animation-delay: 0.1s; }
.vi--speaking .vi__bar:nth-child(3) { animation-delay: 0.2s; }
.vi--speaking .vi__bar:nth-child(4) { animation-delay: 0.3s; }
.vi--speaking .vi__bar:nth-child(5) { animation-delay: 0.4s; }

@keyframes speak-pulse {
  from { height: 30%; }
  to { height: 70%; }
}

.vi__label {
  white-space: nowrap;
  font-weight: 500;
  letter-spacing: 0.02em;
}
</style>
