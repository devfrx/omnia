<script setup lang="ts">
/**
 * ChatInput.vue — Auto-growing textarea with send button.
 *
 * - Enter sends, Shift+Enter inserts a newline.
 * - Textarea grows up to 5 visible lines then scrolls internally.
 * - A small coloured dot indicates WebSocket connection status.
 * - The send button is disabled when the input is empty or streaming.
 */
import { nextTick, ref, watch } from 'vue'

const props = defineProps<{
  /** Disable the input (e.g. while streaming). */
  disabled: boolean
  /** WebSocket connection status. */
  isConnected: boolean
}>()

const emit = defineEmits<{
  /** Fired when the user submits a message. */
  send: [content: string]
}>()

/** Two-way bound text value. */
const text = ref('')

/** Template ref for the textarea DOM element. */
const textareaRef = ref<HTMLTextAreaElement | null>(null)

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

/** Validate and emit the trimmed text. */
function submit(): void {
  const trimmed = text.value.trim()
  if (!trimmed || props.disabled) return
  emit('send', trimmed)
  text.value = ''
  nextTick(autoResize)
}
</script>

<template>
  <div class="chat-input">
    <div class="chat-input__status" :class="isConnected ? 'status--ok' : 'status--err'" />

    <textarea
      ref="textareaRef"
      v-model="text"
      class="chat-input__textarea"
      placeholder="Scrivi un messaggio..."
      rows="1"
      :disabled="disabled"
      @keydown="handleKeydown"
      @input="autoResize"
    />

    <button
      class="chat-input__send"
      :disabled="!text.trim() || disabled"
      aria-label="Invia messaggio"
      @click="submit"
    >
      <!-- Send arrow icon -->
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <line x1="22" y1="2" x2="11" y2="13" />
        <polygon points="22 2 15 22 11 13 2 9 22 2" />
      </svg>
    </button>
  </div>
</template>

<style scoped>
.chat-input {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  background: var(--bg-primary);
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
  background: #3fb950;
  box-shadow: 0 0 6px rgba(63, 185, 80, 0.5);
}

.status--err {
  background: #f85149;
  box-shadow: 0 0 6px rgba(248, 81, 73, 0.5);
}

/* --------------------------------------------------- Textarea */
.chat-input__textarea {
  flex: 1;
  min-height: 38px;
  max-height: 120px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--text-primary);
  font-family: inherit;
  font-size: 0.9rem;
  line-height: 1.5;
  resize: none;
  outline: none;
  transition: border-color 0.2s ease;
}

.chat-input__textarea:focus {
  border-color: var(--accent);
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
  border: 1px solid rgba(88, 166, 255, 0.3);
  border-radius: 10px;
  background: rgba(88, 166, 255, 0.12);
  color: var(--accent);
  cursor: pointer;
  transition: background 0.2s ease, opacity 0.2s ease;
}

.chat-input__send:hover:not(:disabled) {
  background: rgba(88, 166, 255, 0.25);
}

.chat-input__send:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
</style>
