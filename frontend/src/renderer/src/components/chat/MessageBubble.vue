<script setup lang="ts">
/**
 * MessageBubble.vue — Renders a single chat message.
 *
 * User messages are right-aligned with an accent background.
 * Assistant messages are left-aligned with a secondary background
 * and a subtle glow border.  Markdown is rendered via `useMarkdown`.
 */
import { computed } from 'vue'

import { renderMarkdown } from '../../composables/useMarkdown'
import type { ChatMessage } from '../../types/chat'

const props = defineProps<{
  /** The message to render. */
  message: ChatMessage
}>()

/** Pre-rendered HTML from the message's markdown content. */
const htmlContent = computed(() => renderMarkdown(props.message.content))

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
</script>

<template>
  <div class="bubble-row" :class="`row--${message.role}`">
    <div class="bubble" :class="bubbleClass">
      <!-- eslint-disable-next-line vue/no-v-html — content is sanitised by markdown-it -->
      <div class="bubble__content" v-html="htmlContent" />
      <span class="bubble__time">{{ formattedTime }}</span>
    </div>
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
  border-radius: 12px;
  line-height: 1.55;
  font-size: 0.9rem;
  position: relative;
  word-break: break-word;
}

.bubble--user {
  background: rgba(88, 166, 255, 0.18);
  border: 1px solid rgba(88, 166, 255, 0.3);
  border-radius: 12px 12px 4px 12px;
  color: var(--text-primary);
}

.bubble--assistant {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px 12px 12px 4px;
  box-shadow: 0 0 12px rgba(88, 166, 255, 0.06);
  color: var(--text-primary);
}

.bubble--tool {
  background: rgba(55, 65, 81, 0.5);
  border: 1px solid var(--border);
  border-radius: 8px;
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 0.82rem;
  color: var(--text-secondary);
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

.bubble__content :deep(.code-block) {
  background: rgba(0, 0, 0, 0.35);
  border-radius: 6px;
  padding: 10px 12px;
  overflow-x: auto;
  margin: 6px 0;
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 0.84rem;
  line-height: 1.5;
}

.bubble__content :deep(code) {
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 0.85em;
  background: rgba(255, 255, 255, 0.06);
  padding: 1px 5px;
  border-radius: 3px;
}

.bubble__content :deep(.code-block code) {
  background: none;
  padding: 0;
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
</style>
