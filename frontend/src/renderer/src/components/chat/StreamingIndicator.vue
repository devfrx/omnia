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
import ThinkingSection from './ThinkingSection.vue'

const props = defineProps<{
  /** Accumulated tokens so far (`currentStreamContent` from the store). */
  content: string
  /** Accumulated thinking tokens (`currentThinkingContent` from the store). */
  thinkingContent: string
}>()

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
      <ThinkingSection v-if="thinkingContent" :thinking-html="thinkingHtml" :initial-collapsed="false"
        :auto-expand="true" :content-length="thinkingContent.length">
        <span v-if="!content" class="streaming-bubble__cursor" />
      </ThinkingSection>

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

/* ----- Thinking section — now rendered by ThinkingSection.vue */

/* ----- markdown content */
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

/* ----- Code block styles are in assets/styles/code-blocks.css */

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
