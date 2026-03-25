<script setup lang="ts">
/**
 * TitleBar.vue — Custom frameless window title bar for AL\CE.
 *
 * Provides a draggable region with app title and native-style
 * window control buttons (minimize, maximize/restore, close).
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useSettingsStore } from '../stores/settings'
import { useVoiceStore } from '../stores/voice'
import { useUIStore } from '../stores/ui'
import { usePluginsStore } from '../stores/plugins'
import WeatherWidget from './plugins/WeatherWidget.vue'
import AliceSpinner from './ui/AliceSpinner.vue'
import AppIcon from './ui/AppIcon.vue'

/** Tracks whether the window is currently maximized */
const isMaximized = ref(false)

const settingsStore = useSettingsStore()
const voiceStore = useVoiceStore()
const uiStore = useUIStore()
const pluginsStore = usePluginsStore()

/** Whether the weather plugin is enabled. */
const weatherEnabled = computed(() =>
  pluginsStore.plugins.some((p) => p.name === 'weather' && p.enabled)
)

/** Display name of the active LLM model, truncated at 30 chars */
const modelDisplayName = computed(() => {
  const model = settingsStore.activeModel
  if (!model) return settingsStore.settings?.llm?.model || 'Nessun modello'
  const name = model.display_name || model.name
  return name.length > 30 ? name.slice(0, 30) + '\u2026' : name
})

/** Whether a model is active (for styling "Nessun modello" differently) */
const hasActiveModel = computed(() => {
  return !!settingsStore.activeModel || !!settingsStore.settings?.llm?.model
})

/** LM Studio connection status */
const connectionStatus = computed<'connected' | 'loading' | 'disconnected'>(() => {
  if (settingsStore.isAnyOperationInProgress) return 'loading'
  if (settingsStore.lmStudioConnected) return 'connected'
  return 'disconnected'
})

/** Human-readable TTS voice name from the voice store (set by voice_ready). */
const ttsVoice = computed(() => voiceStore.ttsVoice)

const windowControls = window.electron?.windowControls

/** Minimize the application window */
const handleMinimize = (): void => {
  windowControls?.minimize()
}

/** Toggle maximize / restore */
const handleMaximize = (): void => {
  windowControls?.maximize()
  isMaximized.value = !isMaximized.value
}

/** Close the application window */
const handleClose = (): void => {
  windowControls?.close()
}

/**
 * Sync `isMaximized` when the user double-clicks the drag region
 * or the OS triggers a maximize/unmaximize via snap layouts, etc.
 */
const syncMaximizedState = (): void => {
  // matchMedia trick: maximized windows fill the screen
  isMaximized.value = window.outerWidth >= screen.availWidth && window.outerHeight >= screen.availHeight
}

onMounted(() => {
  window.addEventListener('resize', syncMaximizedState)
  syncMaximizedState()
})

onUnmounted(() => {
  window.removeEventListener('resize', syncMaximizedState)
})
</script>

<template>
  <header class="titlebar">
    <!-- Sidebar toggle (hamburger) — no-drag so it's clickable -->
    <button class="titlebar__menu-btn" aria-label="Apri sidebar" @click="uiStore.toggleSidebar">
      <AppIcon name="menu" :size="14" />
    </button>

    <!-- Draggable region -->
    <div class="titlebar__drag-region">
      <span class="titlebar__title">AL\CE</span>

      <span class="titlebar__separator">&middot;</span>

      <div class="titlebar__model-info">
        <span class="titlebar__status-dot" :class="`titlebar__status-dot--${connectionStatus}`" />
        <span class="titlebar__model-name" :class="{ 'titlebar__model-name--empty': !hasActiveModel }"
          :title="modelDisplayName">
          {{ modelDisplayName }}
        </span>
        <AliceSpinner v-if="connectionStatus === 'loading'" size="xs" />
      </div>

      <template v-if="voiceStore.sttAvailable || voiceStore.ttsAvailable">
        <span class="titlebar__separator">&middot;</span>
        <div class="titlebar__voice">
          <!-- STT -->
          <div v-if="voiceStore.sttAvailable && voiceStore.sttEngine" class="titlebar__voice-item">
            <AppIcon name="stt-indicator" :size="9" class="titlebar__voice-icon" />
            <span class="titlebar__voice-engine">{{ voiceStore.sttEngine }}</span>
            <span v-if="voiceStore.sttModel" class="titlebar__voice-model">{{ voiceStore.sttModel }}</span>
          </div>
          <!-- STT / TTS divider -->
          <span
            v-if="voiceStore.sttAvailable && voiceStore.sttEngine && voiceStore.ttsAvailable && voiceStore.ttsEngine"
            class="titlebar__voice-sep">/</span>
          <!-- TTS -->
          <div v-if="voiceStore.ttsAvailable && voiceStore.ttsEngine" class="titlebar__voice-item">
            <AppIcon name="tts-indicator" :size="9" class="titlebar__voice-icon" />
            <span class="titlebar__voice-engine">{{ voiceStore.ttsEngine }}</span>
            <span v-if="ttsVoice" class="titlebar__voice-model">{{ ttsVoice }}</span>
          </div>
        </div>
      </template>
    </div>

    <!-- Weather widget — right side of drag region -->
    <div v-if="weatherEnabled" class="titlebar__weather">
      <WeatherWidget />
    </div>

    <!-- Window controls (no-drag so buttons are clickable) -->
    <div class="titlebar__controls">
      <button class="titlebar__btn titlebar__btn--minimize" aria-label="Minimize" @click="handleMinimize">
        <AppIcon name="win-minimize" :size="10" />
      </button>

      <button class="titlebar__btn titlebar__btn--maximize" :aria-label="isMaximized ? 'Restore' : 'Maximize'"
        @click="handleMaximize">
        <AppIcon v-if="!isMaximized" name="win-maximize" :size="10" />
        <AppIcon v-else name="win-restore" :size="10" />
      </button>

      <button class="titlebar__btn titlebar__btn--close" aria-label="Close" @click="handleClose">
        <AppIcon name="win-close" :size="10" />
      </button>
    </div>
  </header>
</template>

<style scoped>
.titlebar {
  display: flex;
  align-items: center;
  height: var(--titlebar-height, 38px);
  min-height: var(--titlebar-height, 38px);
  background: var(--surface-1);
  border-bottom: 1px solid var(--border);
  z-index: var(--z-sticky);
  user-select: none;
}

/* Sidebar toggle button (hamburger) */
.titlebar__menu-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 100%;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  flex-shrink: 0;
  -webkit-app-region: no-drag;
  transition:
    color 100ms ease,
    background 100ms ease;
}

.titlebar__menu-btn:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.titlebar__menu-btn:active {
  background: var(--surface-active);
}

/* Draggable region fills all available space */
.titlebar__drag-region {
  flex: 1;
  display: flex;
  align-items: center;
  height: 100%;
  padding-left: var(--space-3);
  -webkit-app-region: drag;
}

.titlebar__title {
  font-family: var(--font-display);
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
  letter-spacing: 2px;
  color: var(--text-secondary);
}

/* Separator between title and model info */
.titlebar__separator {
  color: var(--text-muted);
  opacity: 0.3;
  margin: 0 8px;
  font-size: 14px;
}

/* Model info container */
.titlebar__model-info {
  display: flex;
  align-items: center;
  gap: 6px;
  -webkit-app-region: no-drag;
  transition: opacity var(--transition-fast);
}

/* Connection status dot */
.titlebar__status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  flex-shrink: 0;
}

.titlebar__status-dot--connected {
  background: var(--success);
}

.titlebar__status-dot--loading {
  background: var(--accent);
}

.titlebar__status-dot--disconnected {
  background: var(--danger);
}

/* Model name */
.titlebar__model-name {
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 0.5px;
  color: var(--text-secondary);
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.titlebar__model-name--empty {
  color: var(--text-muted);
  font-style: italic;
}

/* Voice info: STT + TTS */
.titlebar__voice {
  display: flex;
  align-items: center;
  gap: 5px;
}

.titlebar__voice-item {
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}

.titlebar__voice-icon {
  color: var(--text-muted);
  opacity: 0.55;
  flex-shrink: 0;
  margin-top: 0.5px;
}

.titlebar__voice-engine {
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 0.3px;
  color: var(--text-muted);
  opacity: 0.75;
}

.titlebar__voice-model {
  font-size: 10px;
  color: var(--text-muted);
  opacity: 0.5;
  letter-spacing: 0.2px;
}

.titlebar__voice-sep {
  font-size: 10px;
  color: var(--text-muted);
  opacity: 0.3;
  margin: 0 1px;
}

/* Weather widget in titlebar */
.titlebar__weather {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  padding: 0 var(--space-2);
  -webkit-app-region: no-drag;
}

/* Control button group */
.titlebar__controls {
  display: flex;
  height: 100%;
  -webkit-app-region: no-drag;
}

.titlebar__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 100%;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition:
    background 100ms ease,
    color 100ms ease;
}

.titlebar__btn:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.titlebar__btn:active {
  background: var(--surface-active);
}

.titlebar__btn--close:hover {
  background: rgba(232, 17, 35, 0.85);
  color: #ffffff;
  transition: background 0.2s ease, color 0.15s ease;
}

.titlebar__btn--close:active {
  background: rgba(232, 17, 35, 0.7);
  color: #ffffff;
}
</style>
