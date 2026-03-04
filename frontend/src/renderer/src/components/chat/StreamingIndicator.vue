<script setup lang="ts">
/**
 * StreamingIndicator.vue — Shows the in-progress assistant response.
 *
 * Renders partial markdown as it streams in, styled identically to an
 * assistant {@link MessageBubble} but with a blinking cursor appended.
 * The parent controls visibility (`v-if="isStreaming"` outside).
 */
import { computed } from 'vue'

import { renderMarkdown } from '../../composables/useMarkdown'

const props = defineProps<{
  /** Accumulated tokens so far (`currentStreamContent` from the store). */
  content: string
}>()

/** Rendered HTML of the partial markdown content. */
const htmlContent = computed(() => renderMarkdown(props.content))
</script>

<template>
  <div class="bubble-row row--assistant">
    <div class="streaming-bubble">
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div v-if="content" class="streaming-bubble__content" v-html="htmlContent" />
      <span class="streaming-bubble__cursor" />
    </div>
  </div>
</template>

<style scoped>
.bubble-row {
  display: flex;
  justify-content: flex-start;
  margin-bottom: 12px;
}

.streaming-bubble {
  max-width: 75%;
  padding: 10px 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px 12px 12px 4px;
  box-shadow: 0 0 16px rgba(88, 166, 255, 0.1);
  color: var(--text-primary);
  line-height: 1.55;
  font-size: 0.9rem;
  word-break: break-word;
  position: relative;
}

/* ----- markdown content (re-uses same deep selectors as MessageBubble) */
.streaming-bubble__content :deep(p) {
  margin: 0 0 0.4em;
}

.streaming-bubble__content :deep(p:last-child) {
  margin-bottom: 0;
}

.streaming-bubble__content :deep(a) {
  color: var(--accent);
  text-decoration: underline;
}

.streaming-bubble__content :deep(.code-block) {
  background: rgba(0, 0, 0, 0.35);
  border-radius: 6px;
  padding: 10px 12px;
  overflow-x: auto;
  margin: 6px 0;
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 0.84rem;
  line-height: 1.5;
}

.streaming-bubble__content :deep(code) {
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 0.85em;
  background: rgba(255, 255, 255, 0.06);
  padding: 1px 5px;
  border-radius: 3px;
}

.streaming-bubble__content :deep(.code-block code) {
  background: none;
  padding: 0;
}

/* ------------------------------------------------------ Blinking cursor */
.streaming-bubble__cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background: var(--accent);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink 0.8s step-end infinite;
}

@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}
</style>
