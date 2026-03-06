<script setup lang="ts">
/**
 * ChatInput.vue — Auto-growing textarea with send button and image attachments.
 *
 * - Enter sends, Shift+Enter inserts a newline.
 * - Textarea grows up to 5 visible lines then scrolls internally.
 * - A small coloured dot indicates WebSocket connection status.
 * - A paperclip button allows selecting image attachments.
 * - Supports drag-and-drop and clipboard paste (Ctrl+V) for images.
 * - Thumbnails of pending images appear above the input area.
 * - The send button is disabled when the input is empty (and no files) or streaming.
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import ModelSelector from '../settings/ModelSelector.vue'
import { useSettingsStore } from '../../stores/settings'

const settingsStore = useSettingsStore()

const supportsVision = computed(() => settingsStore.activeModel?.capabilities.vision ?? false)
const supportsToolUse = computed(() => settingsStore.activeModel?.capabilities.trained_for_tool_use ?? false)
const supportsThinking = computed(() => settingsStore.activeModel?.capabilities.thinking ?? false)

const props = defineProps<{
  /** Disable the input (e.g. while streaming). */
  disabled: boolean
  /** WebSocket connection status. */
  isConnected: boolean
  /** Whether the LLM is currently streaming a response. */
  isStreaming: boolean
}>()

const emit = defineEmits<{
  /** Fired when the user submits a message (with any pending attachments). */
  send: [content: string, attachments: File[]]
  /** Fired when the user clicks the stop button during streaming. */
  stop: []
}>()

/** Two-way bound text value. */
const text = ref('')

/** Template ref for the textarea DOM element. */
const textareaRef = ref<HTMLTextAreaElement | null>(null)

/** Template ref for the hidden file input element. */
const fileInputRef = ref<HTMLInputElement | null>(null)

/** Files selected by the user but not yet sent. */
const pendingFiles = ref<File[]>([])

/** Whether the user is dragging files over the input area. */
const isDragOver = ref(false)

/** Counter to handle drag enter/leave on child elements without flicker. */
const dragCounter = ref(0)

/** Thumbnail blob-URLs keyed by their File reference. */
const thumbnailUrls = ref<Map<File, string>>(new Map())

// -----------------------------------------------------------------------
// Auto-resize
// -----------------------------------------------------------------------

/**
 * Resize the textarea to fit its content (up to ~5 lines ≈ 120px).
 * Called after every input and explicit resets.
 */
function autoResize(): void {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 120)}px`
}

/** Watch for external clears (parent resets v-model). */
watch(text, () => nextTick(autoResize))

// -----------------------------------------------------------------------
// Keyboard
// -----------------------------------------------------------------------

/**
 * Handle the Enter key: send the message unless Shift is held.
 * Shift+Enter falls through to the default behaviour (new line).
 */
function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}

// -----------------------------------------------------------------------
// Submit
// -----------------------------------------------------------------------

/** Validate and emit the trimmed text together with pending attachments. */
function submit(): void {
  const trimmed = text.value.trim()
  if ((!trimmed && pendingFiles.value.length === 0) || props.disabled) return
  emit('send', trimmed, [...pendingFiles.value])
  text.value = ''
  clearAllFiles()
  nextTick(autoResize)
}

// -----------------------------------------------------------------------
// File attachment helpers
// -----------------------------------------------------------------------

/** Open the native file picker. */
function openFilePicker(): void {
  fileInputRef.value?.click()
}

/** Handle files selected via the hidden `<input type="file">`. */
function handleFileSelect(event: Event): void {
  const input = event.target as HTMLInputElement
  if (input.files) {
    addFiles(Array.from(input.files))
  }
  // Reset so the same file can be selected again
  input.value = ''
}

/** Add image files to the pending list and generate thumbnails. */
function addFiles(files: File[]): void {
  const imageFiles = files.filter((f) => f.type.startsWith('image/'))
  if (!supportsVision.value && imageFiles.length > 0) return
  for (const file of imageFiles) {
    pendingFiles.value.push(file)
    const url = URL.createObjectURL(file)
    thumbnailUrls.value.set(file, url)
  }
}

/** Remove a single pending file and revoke its thumbnail URL. */
function removeFile(file: File): void {
  const url = thumbnailUrls.value.get(file)
  if (url) URL.revokeObjectURL(url)
  thumbnailUrls.value.delete(file)
  pendingFiles.value = pendingFiles.value.filter((f) => f !== file)
}

/** Clear all pending files and revoke every thumbnail URL. */
function clearAllFiles(): void {
  for (const url of thumbnailUrls.value.values()) {
    URL.revokeObjectURL(url)
  }
  thumbnailUrls.value.clear()
  pendingFiles.value = []
}

/** Get the blob thumbnail URL for a given file. */
function getThumbnail(file: File): string {
  return thumbnailUrls.value.get(file) ?? ''
}

// -----------------------------------------------------------------------
// Drag-and-drop
// -----------------------------------------------------------------------

/** @internal */
function handleDragEnter(event: DragEvent): void {
  event.preventDefault()
  dragCounter.value++
  isDragOver.value = true
}

/** @internal */
function handleDragOver(event: DragEvent): void {
  event.preventDefault()
}

/** @internal */
function handleDragLeave(): void {
  dragCounter.value--
  if (dragCounter.value === 0) isDragOver.value = false
}

/** @internal */
function handleDrop(event: DragEvent): void {
  event.preventDefault()
  dragCounter.value = 0
  isDragOver.value = false
  if (event.dataTransfer?.files) {
    addFiles(Array.from(event.dataTransfer.files))
  }
}

// -----------------------------------------------------------------------
// Lifecycle — revoke blob URLs on unmount
// -----------------------------------------------------------------------

onBeforeUnmount(() => clearAllFiles())

// -----------------------------------------------------------------------
// Clipboard paste
// -----------------------------------------------------------------------

/** Intercept paste events and extract image data from the clipboard. */
function handlePaste(event: ClipboardEvent): void {
  const items = event.clipboardData?.items
  if (!items) return
  const imageFiles: File[] = []
  for (let i = 0; i < items.length; i++) {
    const item = items[i]
    if (item.type.startsWith('image/')) {
      const file = item.getAsFile()
      if (file) imageFiles.push(file)
    }
  }
  if (imageFiles.length > 0) {
    event.preventDefault()
    addFiles(imageFiles)
  }
}
</script>

<template>
  <div class="chat-input" :class="{ 'chat-input--drag-over': isDragOver }" @dragenter="handleDragEnter"
    @dragover="handleDragOver" @dragleave="handleDragLeave" @drop="handleDrop">
    <!-- Thumbnail preview strip -->
    <div v-if="pendingFiles.length > 0" class="chat-input__attachments">
      <div v-for="file in pendingFiles" :key="file.name + file.size + file.lastModified" class="chat-input__thumb">
        <img :src="getThumbnail(file)" :alt="file.name" :title="file.name" />
        <button class="chat-input__thumb-remove" aria-label="Rimuovi allegato" @click="removeFile(file)">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
            stroke-linecap="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Input row -->
    <div class="chat-input__row">
      <div class="chat-input__status" :class="isConnected ? 'status--ok' : 'status--err'" />

      <!-- Attachment (paperclip) button -->
      <button class="chat-input__attach" :disabled="disabled || !supportsVision"
        :aria-label="supportsVision ? 'Allega immagine' : 'Il modello attivo non supporta immagini'"
        :title="supportsVision ? 'Allega immagine' : 'Il modello attivo non supporta immagini'" @click="openFilePicker">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round">
          <path
            d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
        </svg>
      </button>

      <!-- Hidden file input -->
      <input ref="fileInputRef" type="file" accept="image/*" multiple class="chat-input__file-input"
        @change="handleFileSelect" />

      <textarea ref="textareaRef" v-model="text" class="chat-input__textarea" placeholder="Scrivi un messaggio..."
        rows="1" :disabled="disabled" aria-label="Scrivi un messaggio" @keydown="handleKeydown" @input="autoResize"
        @paste="handlePaste" />

      <!-- Model capability badges -->
      <div v-if="settingsStore.activeModel" class="chat-input__caps">
        <span v-if="supportsVision" class="chat-input__cap" title="Vision">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
            stroke-linejoin="round">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        </span>
        <span v-if="supportsThinking" class="chat-input__cap" title="Thinking">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
            stroke-linejoin="round">
            <path d="M12 2a7 7 0 0 0-4.6 12.3c.6.5 1 1.2 1.1 2h7c.1-.8.5-1.5 1.1-2A7 7 0 0 0 12 2z" />
            <line x1="10" y1="20" x2="14" y2="20" />
            <line x1="10" y1="22" x2="14" y2="22" />
          </svg>
        </span>
        <span v-if="supportsToolUse" class="chat-input__cap" title="Tool Use">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
            stroke-linejoin="round">
            <path
              d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
          </svg>
        </span>
      </div>

      <ModelSelector />

      <!-- Stop / Send button with smooth transition -->
      <Transition name="btn-swap" mode="out-in">
        <button v-if="isStreaming" key="stop" class="chat-input__stop" aria-label="Interrompi generazione"
          @click="emit('stop')">
          <!-- Stop icon: square inside a circle -->
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10" />
            <rect x="9" y="9" width="6" height="6" rx="1" fill="currentColor" stroke="none" />
          </svg>
        </button>
        <button v-else key="send" class="chat-input__send"
          :disabled="(!text.trim() && pendingFiles.length === 0) || disabled" aria-label="Invia messaggio"
          @click="submit">
          <!-- Send arrow icon -->
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.chat-input {
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--border);
  background: var(--bg-primary);
  transition: box-shadow 0.2s ease;
}

.chat-input--drag-over {
  box-shadow: inset 0 0 0 2px var(--accent-border);
}

/* ----------------------------------------------- Attachment thumbnails */
.chat-input__attachments {
  display: flex;
  gap: 8px;
  padding: 10px 16px 0;
  flex-wrap: wrap;
}

.chat-input__thumb {
  position: relative;
  width: 56px;
  height: 56px;
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border);
  flex-shrink: 0;
}

.chat-input__thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.chat-input__thumb-remove {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.65);
  border: none;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
  transition: background 0.15s ease;
}

.chat-input__thumb-remove:hover {
  background: rgba(196, 92, 92, 0.8);
}

/* ----------------------------------------------- Input row */
.chat-input__row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px 16px;
}

/* ----------------------------------------------- Hidden file input */
.chat-input__file-input {
  display: none;
}

/* ------------------------------------------------ Connection dot */
.chat-input__status {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-bottom: 10px;
  transition: background 0.3s ease;
}

.status--ok {
  background: var(--success);
  box-shadow: 0 0 6px var(--success-glow);
  animation: chatStatusPulse 3s ease-in-out infinite;
}

@keyframes chatStatusPulse {

  0%,
  100% {
    box-shadow: 0 0 6px var(--success-glow);
  }

  50% {
    box-shadow: 0 0 10px var(--success-glow), 0 0 3px var(--success);
  }
}

.status--err {
  background: var(--danger);
  box-shadow: 0 0 6px rgba(196, 92, 92, 0.5);
  animation: chatDisconnectBlink 2s ease-in-out infinite;
}

@keyframes chatDisconnectBlink {

  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0.4;
  }
}

/* ------------------------------------------------ Attach button */
.chat-input__attach {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-input);
  color: var(--text-secondary);
  cursor: pointer;
  transition: background var(--transition-normal), color var(--transition-normal);
}

.chat-input__attach:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  color: var(--accent);
}

.chat-input__attach:disabled {
  opacity: 0.25;
  cursor: not-allowed;
  filter: grayscale(100%);
}

/* --------------------------------------------------- Textarea */
.chat-input__textarea {
  flex: 1;
  min-height: 38px;
  max-height: 120px;
  padding: 8px 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 0.9rem;
  line-height: 1.5;
  resize: none;
  outline: none;
  transition: border-color var(--transition-normal);
}

.chat-input__textarea:focus {
  border-color: var(--accent-border);
}

.chat-input__textarea::placeholder {
  color: var(--text-secondary);
  opacity: 0.6;
}

.chat-input__textarea:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* -------------------------------------------------- Send button */
.chat-input__send {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-md);
  background: var(--accent-dim);
  color: var(--accent);
  cursor: pointer;
  transition: background var(--transition-normal), opacity var(--transition-normal);
}

.chat-input__send:hover:not(:disabled) {
  background: rgba(201, 168, 76, 0.22);
}

.chat-input__send:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

/* -------------------------------------------------- Stop button */
.chat-input__stop {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border: 1px solid var(--danger, #c45c5c);
  border-radius: var(--radius-md);
  background: rgba(196, 92, 92, 0.12);
  color: var(--danger, #c45c5c);
  cursor: pointer;
  transition: background var(--transition-normal), opacity var(--transition-normal);
}

.chat-input__stop:hover {
  background: rgba(196, 92, 92, 0.25);
}

/* ----------------------------------------------- Button swap transition */
.btn-swap-enter-active,
.btn-swap-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.btn-swap-enter-from {
  opacity: 0;
  transform: scale(0.85);
}

.btn-swap-leave-to {
  opacity: 0;
  transform: scale(0.85);
}

/* ----------------------------------------- Capability badges */
.chat-input__caps {
  display: flex;
  align-items: center;
  gap: 3px;
  margin-bottom: 8px;
  animation: capsEntrance 0.3s ease-out;
}

@keyframes capsEntrance {
  from {
    opacity: 0;
    transform: scale(0.9);
  }

  to {
    opacity: 1;
    transform: scale(1);
  }
}

.chat-input__cap {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: var(--radius-sm);
  background: var(--bg-tertiary);
  color: var(--text-muted);
  border: 1px solid var(--border);
}

.chat-input__cap svg {
  width: 12px;
  height: 12px;
}
</style>
