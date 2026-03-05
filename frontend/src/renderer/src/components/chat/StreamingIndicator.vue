<script setup lang="ts">
/**
 * StreamingIndicator.vue — Shows the in-progress assistant response.
 *
 * Renders partial markdown as it streams in, styled identically to an
 * assistant {@link MessageBubble} but with a blinking cursor appended.
 * Includes a collapsible "Ragionamento" section for thinking tokens.
 * The parent controls visibility (`v-if="isStreaming"` outside).
 */
import { computed, ref, watch } from 'vue'

import { renderMarkdown } from '../../composables/useMarkdown'
import { useCodeBlocks } from '../../composables/useCodeBlocks'

const props = defineProps<{
  /** Accumulated tokens so far (`currentStreamContent` from the store). */
  content: string
  /** Accumulated thinking tokens (`currentThinkingContent` from the store). */
  thinkingContent: string
}>()

/** Whether the thinking section is collapsed. */
const thinkingCollapsed = ref(false)

/** Auto-expand while thinking tokens are arriving. */
watch(
  () => props.thinkingContent,
  (val, old) => {
    if (val.length > (old?.length ?? 0)) {
      thinkingCollapsed.value = false
    }
  }
)

/** Rendered HTML of the partial markdown content. */
const htmlContent = computed(() => renderMarkdown(props.content))

/** Rendered HTML of the thinking content. */
const thinkingHtml = computed(() => renderMarkdown(props.thinkingContent))

const { handleCodeBlockClick } = useCodeBlocks()
</script>

<template>
  <div class="bubble-row row--assistant">
    <div class="streaming-bubble">
      <!-- Thinking section -->
      <div v-if="thinkingContent" class="thinking-section">
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
          <span v-if="!content" class="streaming-bubble__cursor" />
        </div>
      </div>

      <!-- Main content -->
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div v-if="content" class="streaming-bubble__content" v-html="htmlContent" @click="handleCodeBlockClick" />
      <span v-if="content || !thinkingContent" class="streaming-bubble__cursor" />
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
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-lg) var(--radius-sm);
  box-shadow: 0 0 16px var(--accent-glow);
  color: var(--text-primary);
  line-height: 1.55;
  font-size: 0.9rem;
  word-break: break-word;
  position: relative;
  animation: pulseGlow 2.5s ease-in-out infinite;
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

/* ----- Inline code */
.streaming-bubble__content :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.85em;
  background: rgba(255, 255, 255, 0.06);
  padding: 1px 5px;
  border-radius: 3px;
}

/* ----- Code block wrapper */
.streaming-bubble__content :deep(.code-block-wrapper) {
  margin: 8px 0;
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.streaming-bubble__content :deep(.code-block-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 12px;
  background: rgba(0, 0, 0, 0.45);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  min-height: 32px;
}

.streaming-bubble__content :deep(.code-block-lang) {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  user-select: none;
}

.streaming-bubble__content :deep(.code-block-copy) {
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

.streaming-bubble__content :deep(.code-block-copy:hover) {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.1);
}

.streaming-bubble__content :deep(.code-block-copy--copied) {
  color: var(--success) !important;
  border-color: rgba(92, 154, 110, 0.3) !important;
}

.streaming-bubble__content :deep(.code-block-copy__label) {
  pointer-events: none;
}

.streaming-bubble__content :deep(.code-block-copy svg) {
  pointer-events: none;
  flex-shrink: 0;
}

.streaming-bubble__content :deep(.code-block) {
  background: rgba(0, 0, 0, 0.35);
  padding: 12px 14px;
  overflow-x: auto;
  margin: 0;
  font-family: var(--font-mono);
  font-size: 0.84rem;
  line-height: 1.55;
  border-radius: 0;
}

.streaming-bubble__content :deep(.code-block code) {
  background: none;
  padding: 0;
  font-size: inherit;
  border-radius: 0;
}

/* ----- highlight.js token colors */
.streaming-bubble__content :deep(.hljs) { color: #e0dcd4; }
.streaming-bubble__content :deep(.hljs-keyword),
.streaming-bubble__content :deep(.hljs-selector-tag),
.streaming-bubble__content :deep(.hljs-built_in),
.streaming-bubble__content :deep(.hljs-name) { color: #c9a84c; }
.streaming-bubble__content :deep(.hljs-string),
.streaming-bubble__content :deep(.hljs-addition) { color: #8fbc6a; }
.streaming-bubble__content :deep(.hljs-comment),
.streaming-bubble__content :deep(.hljs-quote) { color: #6a6458; font-style: italic; }
.streaming-bubble__content :deep(.hljs-number),
.streaming-bubble__content :deep(.hljs-literal) { color: #d4956a; }
.streaming-bubble__content :deep(.hljs-type),
.streaming-bubble__content :deep(.hljs-class .hljs-title),
.streaming-bubble__content :deep(.hljs-title) { color: #e0c080; }
.streaming-bubble__content :deep(.hljs-attr),
.streaming-bubble__content :deep(.hljs-variable),
.streaming-bubble__content :deep(.hljs-template-variable) { color: #d4b896; }
.streaming-bubble__content :deep(.hljs-function) { color: #d4c49c; }
.streaming-bubble__content :deep(.hljs-params) { color: #c0b89c; }
.streaming-bubble__content :deep(.hljs-regexp),
.streaming-bubble__content :deep(.hljs-link) { color: #c49060; }
.streaming-bubble__content :deep(.hljs-meta) { color: #8a8578; }
.streaming-bubble__content :deep(.hljs-deletion) { color: #c45c5c; }
.streaming-bubble__content :deep(.hljs-symbol),
.streaming-bubble__content :deep(.hljs-bullet) { color: #c9a84c; }
.streaming-bubble__content :deep(.hljs-subst) { color: #e0dcd4; }
.streaming-bubble__content :deep(.hljs-section) { color: #c9a84c; font-weight: bold; }
.streaming-bubble__content :deep(.hljs-emphasis) { font-style: italic; }
.streaming-bubble__content :deep(.hljs-strong) { font-weight: bold; }

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

@keyframes pulseGlow {

  0%,
  100% {
    box-shadow: 0 0 16px var(--accent-glow);
  }

  50% {
    box-shadow: 0 0 24px rgba(201, 168, 76, 0.14);
  }
}
</style>
