<script setup lang="ts">
/**
 * MessageBubble.vue — Renders a single chat message.
 *
 * User messages are right-aligned with an accent background.
 * Assistant messages are left-aligned with a secondary background
 * and a subtle glow border.  Markdown is rendered via `useMarkdown`.
 * Supports collapsible thinking content and image attachments.
 */
import { computed, ref } from 'vue'

import { renderMarkdown } from '../../composables/useMarkdown'
import { useCodeBlocks } from '../../composables/useCodeBlocks'
import type { ChatMessage } from '../../types/chat'

const props = defineProps<{
  /** The message to render. */
  message: ChatMessage
}>()

/** Pre-rendered HTML from the message's markdown content. */
const htmlContent = computed(() => renderMarkdown(props.message.content))

/** Pre-rendered HTML from the message's thinking content (if any). */
const thinkingHtml = computed(() =>
  props.message.thinking_content ? renderMarkdown(props.message.thinking_content) : ''
)

/** Whether the thinking section is collapsed. Defaults to collapsed for stored messages. */
const thinkingCollapsed = ref(true)

/** URL of the image shown in the full-size overlay. */
const overlayImageUrl = ref<string | null>(null)

/** Alt text for the overlay image. */
const overlayImageAlt = ref('')

/** Human-readable time string derived from `created_at`. */
const formattedTime = computed(() => {
  try {
    const date = new Date(props.message.created_at)
    return date.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return ''
  }
})

/** CSS modifier class based on the message role. */
const bubbleClass = computed(() => `bubble--${props.message.role}`)

const { handleCodeBlockClick } = useCodeBlocks()

/** Open full-size image overlay. */
function openOverlay(url: string, alt: string): void {
  overlayImageUrl.value = url
  overlayImageAlt.value = alt
}

/** Close the full-size image overlay. */
function closeOverlay(): void {
  overlayImageUrl.value = null
  overlayImageAlt.value = ''
}
</script>

<template>
  <div class="bubble-row" :class="`row--${message.role}`">
    <div class="bubble" :class="bubbleClass">
      <!-- Image attachments -->
      <div v-if="message.attachments?.length" class="bubble__attachments">
        <div v-for="att in message.attachments" :key="att.file_id" class="bubble__attachment" :title="att.filename"
          @click="openOverlay(att.url, att.filename)">
          <img :src="att.url" :alt="att.filename" loading="lazy" />
        </div>
      </div>

      <!-- Thinking section (assistant only) -->
      <div v-if="message.thinking_content" class="thinking-section">
        <button class="thinking-section__toggle" @click="thinkingCollapsed = !thinkingCollapsed">
          <svg class="thinking-section__icon" width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path
              d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z" />
            <line x1="9" y1="21" x2="15" y2="21" />
            <line x1="10" y1="24" x2="14" y2="24" />
          </svg>
          <span class="thinking-section__label">Ragionamento</span>
          <svg class="thinking-section__chevron" :class="{ 'thinking-section__chevron--collapsed': thinkingCollapsed }"
            width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>
        <div v-show="!thinkingCollapsed" class="thinking-section__body">
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div class="thinking-section__content" v-html="thinkingHtml" @click="handleCodeBlockClick" />
        </div>
      </div>

      <!-- Message content -->
      <!-- eslint-disable-next-line vue/no-v-html — content is sanitised by markdown-it -->
      <div class="bubble__content" v-html="htmlContent" @click="handleCodeBlockClick" />
      <span class="bubble__time">{{ formattedTime }}</span>
    </div>

    <!-- Full-size image overlay -->
    <Teleport to="body">
      <div v-if="overlayImageUrl" class="image-overlay" @click.self="closeOverlay">
        <button class="image-overlay__close" aria-label="Chiudi" @click="closeOverlay">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
        <img :src="overlayImageUrl" :alt="overlayImageAlt" class="image-overlay__img" />
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
/* ------------------------------------------------------------------ Row */
.bubble-row {
  display: flex;
  margin-bottom: 12px;
  animation: slideIn 0.25s ease-out both;
}

.row--user {
  justify-content: flex-end;
}

.row--assistant,
.row--tool {
  justify-content: flex-start;
}

/* ------------------------------------------------------------- Bubble */
.bubble {
  max-width: 75%;
  padding: 10px 14px;
  border-radius: var(--radius-lg);
  line-height: 1.55;
  font-size: 0.9rem;
  position: relative;
  word-break: break-word;
}

.bubble--user {
  background: var(--accent-dim);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-lg);
  color: var(--text-primary);
}

.bubble--assistant {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-lg) var(--radius-sm);
  box-shadow: var(--shadow-glow);
  color: var(--text-primary);
}

.bubble--tool {
  background: rgba(55, 65, 81, 0.5);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-family: var(--font-mono);
  font-size: 0.82rem;
  color: var(--text-secondary);
}

/* -------------------------------------------------------- Attachments */
.bubble__attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.bubble__attachment {
  width: 140px;
  height: 100px;
  border-radius: var(--radius-md);
  overflow: hidden;
  cursor: pointer;
  border: 1px solid var(--border);
  transition: border-color 0.2s ease;
}

.bubble__attachment:hover {
  border-color: var(--accent);
}

.bubble__attachment img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* ----- Thinking section */
.thinking-section {
  margin-bottom: 8px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.02);
  overflow: hidden;
}

.thinking-section__toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 6px 10px;
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 0.78rem;
  cursor: pointer;
  transition: color var(--transition-normal);
}

.thinking-section__toggle:hover {
  color: var(--text-primary);
}

.thinking-section__icon {
  flex-shrink: 0;
  opacity: 0.7;
}

.thinking-section__label {
  font-style: italic;
  flex: 1;
  text-align: left;
}

.thinking-section__chevron {
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.thinking-section__chevron--collapsed {
  transform: rotate(-90deg);
}

.thinking-section__body {
  padding: 4px 10px 8px;
  font-style: italic;
  color: var(--text-secondary);
  font-size: 0.84rem;
  line-height: 1.5;
  opacity: 0.8;
}

.thinking-section__content :deep(p) {
  margin: 0 0 0.4em;
}

.thinking-section__content :deep(p:last-child) {
  margin-bottom: 0;
}

/* --------------------------------------------------------- Content */
.bubble__content {
  overflow-wrap: break-word;
}

.bubble__content :deep(p) {
  margin: 0 0 0.4em;
}

.bubble__content :deep(p:last-child) {
  margin-bottom: 0;
}

.bubble__content :deep(a) {
  color: var(--accent);
  text-decoration: underline;
}

/* ----- Inline code */
.bubble__content :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.85em;
  background: rgba(255, 255, 255, 0.06);
  padding: 1px 5px;
  border-radius: 3px;
}

/* ----- Code block wrapper */
.bubble__content :deep(.code-block-wrapper) {
  margin: 8px 0;
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

/* ----- Code block header (language label + copy button) */
.bubble__content :deep(.code-block-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 12px;
  background: rgba(0, 0, 0, 0.45);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  min-height: 32px;
}

.bubble__content :deep(.code-block-lang) {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  user-select: none;
}

.bubble__content :deep(.code-block-copy) {
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-family: var(--font-sans);
  font-size: 0.72rem;
  padding: 2px 8px;
  cursor: pointer;
  transition: all var(--transition-fast);
  user-select: none;
}

.bubble__content :deep(.code-block-copy:hover) {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.1);
}

.bubble__content :deep(.code-block-copy--copied) {
  color: var(--success) !important;
  border-color: rgba(92, 154, 110, 0.3) !important;
}

.bubble__content :deep(.code-block-copy__label) {
  pointer-events: none;
}

.bubble__content :deep(.code-block-copy svg) {
  pointer-events: none;
  flex-shrink: 0;
}

/* ----- Code block body */
.bubble__content :deep(.code-block) {
  background: rgba(0, 0, 0, 0.35);
  padding: 12px 14px;
  overflow-x: auto;
  margin: 0;
  font-family: var(--font-mono);
  font-size: 0.84rem;
  line-height: 1.55;
  border-radius: 0;
}

.bubble__content :deep(.code-block code) {
  background: none;
  padding: 0;
  font-size: inherit;
  border-radius: 0;
}

/* ----- highlight.js token colors (warm dark theme matching OMNIA gold aesthetic) */
.bubble__content :deep(.hljs) {
  color: #e0dcd4;
}

.bubble__content :deep(.hljs-keyword),
.bubble__content :deep(.hljs-selector-tag),
.bubble__content :deep(.hljs-built_in),
.bubble__content :deep(.hljs-name) {
  color: #c9a84c;
}

.bubble__content :deep(.hljs-string),
.bubble__content :deep(.hljs-addition) {
  color: #8fbc6a;
}

.bubble__content :deep(.hljs-comment),
.bubble__content :deep(.hljs-quote) {
  color: #6a6458;
  font-style: italic;
}

.bubble__content :deep(.hljs-number),
.bubble__content :deep(.hljs-literal) {
  color: #d4956a;
}

.bubble__content :deep(.hljs-type),
.bubble__content :deep(.hljs-class .hljs-title),
.bubble__content :deep(.hljs-title) {
  color: #e0c080;
}

.bubble__content :deep(.hljs-attr),
.bubble__content :deep(.hljs-variable),
.bubble__content :deep(.hljs-template-variable) {
  color: #d4b896;
}

.bubble__content :deep(.hljs-function) {
  color: #d4c49c;
}

.bubble__content :deep(.hljs-params) {
  color: #c0b89c;
}

.bubble__content :deep(.hljs-regexp),
.bubble__content :deep(.hljs-link) {
  color: #c49060;
}

.bubble__content :deep(.hljs-meta) {
  color: #8a8578;
}

.bubble__content :deep(.hljs-deletion) {
  color: #c45c5c;
}

.bubble__content :deep(.hljs-symbol),
.bubble__content :deep(.hljs-bullet) {
  color: #c9a84c;
}

.bubble__content :deep(.hljs-subst) {
  color: #e0dcd4;
}

.bubble__content :deep(.hljs-section) {
  color: #c9a84c;
  font-weight: bold;
}

.bubble__content :deep(.hljs-emphasis) {
  font-style: italic;
}

.bubble__content :deep(.hljs-strong) {
  font-weight: bold;
}

.bubble__content :deep(ul),
.bubble__content :deep(ol) {
  padding-left: 1.4em;
  margin: 0.3em 0;
}

.bubble__content :deep(blockquote) {
  border-left: 3px solid var(--accent);
  margin: 0.5em 0;
  padding: 0.25em 0.8em;
  color: var(--text-secondary);
}

/* --------------------------------------------------------- Timestamp */
.bubble__time {
  display: block;
  font-size: 0.7rem;
  color: var(--text-secondary);
  opacity: 0.6;
  margin-top: 4px;
  text-align: right;
}

/* ------------------------------------------------- Image overlay */
.image-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(4px);
  animation: fadeIn 0.2s ease;
}

.image-overlay__close {
  position: absolute;
  top: 16px;
  right: 16px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 50%;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-primary);
  transition: background var(--transition-normal);
}

.image-overlay__close:hover {
  background: rgba(255, 255, 255, 0.2);
}

.image-overlay__img {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
  border-radius: var(--radius-md);
}

/* --------------------------------------------------------- Animation */
@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }

  to {
    opacity: 1;
  }
}
</style>
