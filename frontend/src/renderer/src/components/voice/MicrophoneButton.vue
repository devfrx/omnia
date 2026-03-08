<script setup lang="ts">
/**
 * MicrophoneButton.vue — Toggle microphone control.
 *
 * Click to start recording, click again to stop and send for transcription.
 * Right-click to select a different audio input device.
 * Shows multi-ring audio visualization while recording,
 * conic gradient + bouncing dots when processing STT.
 */
import { ref, computed, onBeforeUnmount } from 'vue'
import type { AudioDevice } from '../../composables/useVoice'
import { useVoiceStore } from '../../stores/voice'

const store = useVoiceStore()

const props = defineProps<{
  /** Whether voice services are available. */
  available: boolean
  /** Whether the voice WS is connected. */
  connected: boolean
  /** Available audio input devices. */
  audioDevices: AudioDevice[]
  /** Currently selected device ID (empty = default). */
  selectedDeviceId: string
}>()

const emit = defineEmits<{
  /** Start recording audio. */
  'start-recording': []
  /** Stop recording audio. */
  'stop-recording': []
  /** Cancel a stuck processing state. */
  'cancel-processing': []
  /** Refresh the device list. */
  'refresh-devices': []
  /** Select an audio input device. */
  'select-device': [deviceId: string]
}>()

const isActive = computed(() => store.isListening)
const isProcessing = computed(() => store.isProcessing)
const level = computed(() => store.audioLevel)

/** Whether the device dropdown is visible. */
const showDeviceMenu = ref(false)

/** Ripple animation trigger. */
const clicking = ref(false)

function onClick(): void {
  if (!props.available || !props.connected) return

  /* ripple feedback */
  clicking.value = true
  requestAnimationFrame(() => {
    setTimeout(() => { clicking.value = false }, 200)
  })

  if (isProcessing.value) {
    emit('cancel-processing')
    return
  }
  if (isActive.value) {
    emit('stop-recording')
  } else {
    emit('start-recording')
  }
}

/** Close the menu if clicking outside the wrapper. */
function onClickOutside(e: MouseEvent): void {
  const wrapper = (e.target as HTMLElement)?.closest('.mic-wrapper')
  if (!wrapper) showDeviceMenu.value = false
}

function onContextMenu(e: MouseEvent): void {
  e.preventDefault()
  emit('refresh-devices')
  if (!showDeviceMenu.value) {
    showDeviceMenu.value = true
    document.addEventListener('click', onClickOutside, { once: true })
  } else {
    showDeviceMenu.value = false
  }
}

/** Cleanup on unmount: remove stale document listener if menu is still open. */
onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside)
})

function selectDevice(deviceId: string): void {
  emit('select-device', deviceId)
  showDeviceMenu.value = false
}

/* --- Computed inline styles for the 3 concentric rings --- */
const ringInnerStyle = computed(() => ({
  opacity: 0.6 + level.value * 0.4,
  transform: `scale(${1 + level.value * 0.15})`,
}))
const ringMidStyle = computed(() => ({
  opacity: level.value * 0.8,
  transform: `scale(${1 + level.value * 0.35})`,
}))
const ringOuterStyle = computed(() => ({
  opacity: level.value * 0.5,
  transform: `scale(${1 + level.value * 0.55})`,
}))
</script>

<template>
  <div class="mic-wrapper">
    <button class="mic-btn" :class="{
      'mic-btn--active': isActive,
      'mic-btn--processing': isProcessing,
      'mic-btn--disabled': !available || !connected,
      'mic-btn--click': clicking,
    }" :disabled="!available || !connected"
      :aria-label="isActive ? 'Clicca per inviare' : isProcessing ? 'Clicca per annullare' : 'Clicca per parlare'"
      :title="!available ? 'Servizio vocale non disponibile' : !connected ? 'Non connesso' : isActive ? 'Clicca per fermare' : isProcessing ? 'Clicca per annullare' : 'Clicca per parlare (tasto destro: microfono)'"
      @click.prevent="onClick" @contextmenu="onContextMenu">
      <!-- Multi-ring audio visualization (recording) -->
      <span v-if="isActive" class="mic-ring mic-ring--inner" :style="ringInnerStyle" />
      <span v-if="isActive && level > 0.15" class="mic-ring mic-ring--mid" :style="ringMidStyle" />
      <span v-if="isActive && level > 0.3" class="mic-ring mic-ring--outer" :style="ringOuterStyle" />

      <!-- Processing conic gradient border -->
      <span v-if="isProcessing" class="mic-btn__conic" />

      <!-- Icon: mic or processing dots -->
      <Transition name="icon-morph" mode="out-in">
        <svg v-if="!isProcessing" key="mic" class="mic-btn__icon" :class="{ 'mic-btn__icon--rec': isActive }" width="20"
          height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
          stroke-linejoin="round">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="23" />
          <line x1="8" y1="23" x2="16" y2="23" />
        </svg>
        <span v-else key="dots" class="mic-btn__dots">
          <span /><span /><span />
        </span>
      </Transition>
    </button>

    <!-- Device selection dropdown (right-click) -->
    <Transition name="menu-fade">
      <div v-if="showDeviceMenu" class="mic-menu">
        <div class="mic-menu__title">Microfono</div>
        <div v-if="audioDevices.length === 0" class="mic-menu__empty">
          Nessun dispositivo trovato
        </div>
        <button v-for="device in audioDevices" :key="device.deviceId" class="mic-menu__item"
          :class="{ 'mic-menu__item--active': device.deviceId === selectedDeviceId }"
          @click="selectDevice(device.deviceId)">
          <span class="mic-menu__check">{{ device.deviceId === selectedDeviceId ? '✓' : '' }}</span>
          {{ device.label }}
        </button>
        <button class="mic-menu__item mic-menu__item--default" @click="selectDevice('')">
          <span class="mic-menu__check">{{ !selectedDeviceId ? '✓' : '' }}</span>
          Predefinito di sistema
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* ============================================================
   Mic wrapper — positions pills relative to the button
   ============================================================ */
.mic-wrapper {
  position: relative;
  display: inline-flex;
  overflow: visible;
}

/* ============================================================
   Base button — Premium glass effect
   ============================================================ */
.mic-btn {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  color: var(--text-secondary);
  cursor: pointer;
  transition: color 0.2s, background 0.25s, transform 0.15s ease, border-color 0.2s, box-shadow 0.2s;
  outline: none;
  -webkit-app-region: no-drag;
}

.mic-btn:hover:not(:disabled) {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.1);
}

.mic-btn:focus-visible {
  box-shadow: 0 0 0 2px var(--accent), 0 0 12px rgba(201, 168, 76, 0.2);
}

/* ---- Recording state — Dramatic crimson glow ---- */
.mic-btn--active {
  color: #e74c3c;
  background: rgba(231, 76, 60, 0.12);
  border-color: rgba(231, 76, 60, 0.25);
  box-shadow: 0 0 20px rgba(231, 76, 60, 0.15);
  animation: rec-bg-pulse 2s ease-in-out infinite;
}

@keyframes rec-bg-pulse {

  0%,
  100% {
    background: rgba(231, 76, 60, 0.1);
    box-shadow: 0 0 16px rgba(231, 76, 60, 0.12);
  }

  50% {
    background: rgba(231, 76, 60, 0.2);
    box-shadow: 0 0 28px rgba(231, 76, 60, 0.22);
  }
}

/* ---- Processing state — Visually distinct ---- */
.mic-btn--processing {
  color: var(--accent);
  background: rgba(201, 168, 76, 0.1);
  border-color: rgba(201, 168, 76, 0.18);
  box-shadow: 0 0 12px rgba(201, 168, 76, 0.1);
  cursor: pointer;
}

/* ---- Disabled ---- */
.mic-btn--disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* ---- Click ripple ---- */
.mic-btn--click {
  animation: mic-click 0.2s ease;
}

@keyframes mic-click {
  0% {
    transform: scale(1);
  }

  50% {
    transform: scale(0.88);
  }

  100% {
    transform: scale(1);
  }
}

/* ============================================================
   Multi-ring audio visualization — Smoother, layered
   ============================================================ */
.mic-ring {
  position: absolute;
  border-radius: var(--radius-md);
  pointer-events: none;
  transition: transform 0.1s ease-out, opacity 0.1s ease-out;
}

.mic-ring--inner {
  inset: -4px;
  border: 2px solid rgba(231, 76, 60, 0.35);
  box-shadow: 0 0 8px rgba(231, 76, 60, 0.15);
}

.mic-ring--mid {
  inset: -10px;
  border: 1.5px solid rgba(231, 76, 60, 0.25);
  box-shadow: 0 0 12px rgba(231, 76, 60, 0.1);
}

.mic-ring--outer {
  inset: -16px;
  border: 1px solid rgba(231, 76, 60, 0.15);
  box-shadow: 0 0 16px rgba(231, 76, 60, 0.08);
}

/* ============================================================
   Processing — conic gradient spinner border
   ============================================================ */
.mic-btn__conic {
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  background: conic-gradient(from 0deg, transparent 50%, var(--accent) 80%, transparent 100%);
  mask: radial-gradient(farthest-side, transparent calc(100% - 2px), black calc(100% - 2px));
  -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 2px), black calc(100% - 2px));
  animation: conic-spin 1s linear infinite;
  pointer-events: none;
  opacity: 0.8;
}

@keyframes conic-spin {
  to {
    transform: rotate(360deg);
  }
}

/* ============================================================
   Mic icon
   ============================================================ */
.mic-btn__icon {
  position: relative;
  z-index: 1;
  transition: filter 0.2s ease, transform 0.15s ease, opacity 0.15s ease;
}

.mic-btn__icon--rec {
  filter: drop-shadow(0 0 6px rgba(231, 76, 60, 0.6));
}

/* ============================================================
   Processing dots (thinking animation)
   ============================================================ */
.mic-btn__dots {
  display: flex;
  gap: 3px;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;
}

.mic-btn__dots span {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 4px rgba(201, 168, 76, 0.3);
  animation: dot-bounce 1.2s ease-in-out infinite;
}

.mic-btn__dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.mic-btn__dots span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes dot-bounce {

  0%,
  80%,
  100% {
    transform: translateY(0);
    opacity: 0.5;
  }

  40% {
    transform: translateY(-5px);
    opacity: 1;
  }
}

/* ============================================================
   Icon morph transition
   ============================================================ */
.icon-morph-enter-active,
.icon-morph-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.icon-morph-enter-from {
  opacity: 0;
  transform: scale(0.7);
}

.icon-morph-leave-to {
  opacity: 0;
  transform: scale(0.7);
}

/* ============================================================
   Device selection dropdown — Glass-morphism
   ============================================================ */
.mic-menu {
  position: absolute;
  bottom: calc(100% + 10px);
  right: 0;
  min-width: 240px;
  max-width: 340px;
  background: rgba(19, 22, 28, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-md);
  padding: var(--space-1) 0;
  box-shadow:
    0 12px 32px rgba(0, 0, 0, 0.45),
    0 0 0 1px rgba(255, 255, 255, 0.03),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  z-index: 100;
}

.mic-menu__title {
  padding: 8px 14px 6px;
  font-size: var(--text-2xs);
  font-weight: var(--weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.mic-menu__empty {
  padding: 10px 14px;
  font-size: var(--text-sm);
  color: var(--text-muted);
  font-style: italic;
}

.mic-menu__item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 14px;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: var(--text-sm);
  cursor: pointer;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: background 0.15s;
}

.mic-menu__item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.mic-menu__item--active {
  color: var(--accent);
}

.mic-menu__item--default {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  margin-top: 2px;
  padding-top: 10px;
}

.mic-menu__check {
  width: 14px;
  text-align: center;
  flex-shrink: 0;
  font-size: var(--text-xs);
}

.menu-fade-enter-active,
.menu-fade-leave-active {
  transition: opacity 0.2s cubic-bezier(0.16, 1, 0.3, 1), transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.97);
}
</style>
