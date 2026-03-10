<script setup lang="ts">
/**
 * AssistantResponse.vue — Rich markdown response display for OMNIA.
 *
 * Renders the assistant's streamed/final response with full markdown support,
 * thinking/reasoning collapse section, streaming cursor, and phase-aware styling.
 */
import { computed, ref, watch, nextTick, onMounted } from 'vue'
import { renderMarkdown } from '../../utils/markdownRenderer'

const props = defineProps<{
    content: string
    isStreaming: boolean
    thinkingContent: string
}>()

const thinkingExpanded = ref(false)
const scrollContainer = ref<HTMLElement | null>(null)

/** Whether the assistant is currently in the thinking phase (no content yet). */
const isThinkingPhase = computed(
    () => !!props.thinkingContent && !props.content && props.isStreaming
)

/** Whether we're actively generating response content. */
const isGenerating = computed(() => props.isStreaming && !!props.content)

/** Rendered HTML for the main response content. */
const renderedContent = computed(() => renderMarkdown(props.content))

/** Rendered HTML for the thinking content. */
const renderedThinking = computed(() => renderMarkdown(props.thinkingContent))

/** Truncated thinking preview (first ~2 lines). */
const thinkingPreview = computed(() => {
    if (!props.thinkingContent) return ''
    const lines = props.thinkingContent.split('\n').filter((l) => l.trim())
    const preview = lines.slice(0, 2).join(' ')
    return preview.length > 120 ? preview.slice(0, 120) + '…' : preview
})

/** Auto-scroll to bottom during streaming. */
watch(
    () => props.content + props.thinkingContent,
    async () => {
        if (!props.isStreaming) return
        await nextTick()
        if (scrollContainer.value) {
            scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
        }
    }
)

/** Expand thinking section automatically during thinking phase. */
watch(isThinkingPhase, (thinking) => {
    if (thinking) thinkingExpanded.value = true
})

onMounted(() => {
    if (isThinkingPhase.value) thinkingExpanded.value = true
})
</script>

<template>
    <div ref="scrollContainer" class="assistant-response" :class="{
        'assistant-response--thinking': isThinkingPhase,
        'assistant-response--generating': isGenerating,
        'assistant-response--complete': !isStreaming && !!content
    }">
        <!-- Thinking section -->
        <div v-if="thinkingContent" class="thinking-section" :class="{ 'thinking-section--active': isThinkingPhase }">
            <button class="thinking-toggle" @click="thinkingExpanded = !thinkingExpanded">
                <span class="thinking-toggle__icon">✦</span>
                <span class="thinking-toggle__label">Ragionamento</span>
                <span v-if="isThinkingPhase" class="thinking-toggle__indicator" />
                <span class="thinking-toggle__chevron"
                    :class="{ 'thinking-toggle__chevron--open': thinkingExpanded }">›</span>
            </button>

            <!-- Collapsed preview -->
            <p v-if="!thinkingExpanded" class="thinking-preview">
                {{ thinkingPreview }}
            </p>

            <!-- Expanded content -->
            <Transition name="thinking-expand">
                <div v-if="thinkingExpanded" class="thinking-body" v-html="renderedThinking" />
            </Transition>
        </div>

        <!-- Main response content -->
        <div v-if="content" class="response-body" v-html="renderedContent" />

        <!-- Streaming cursor -->
        <span v-if="isStreaming && content" class="streaming-cursor" />

        <!-- Thinking phase placeholder (no content yet) -->
        <div v-if="isThinkingPhase && !content" class="thinking-placeholder">
            <span class="thinking-placeholder__dot" />
            <span class="thinking-placeholder__dot" />
            <span class="thinking-placeholder__dot" />
        </div>
    </div>
</template>

<style scoped>
/* ── Container ── */
.assistant-response {
    max-width: 620px;
    width: 100%;
    max-height: 70vh;
    overflow-y: auto;
    padding: var(--space-5, 20px) var(--space-6, 24px);
    background: var(--surface-1, #13161e);
    border: 1px solid var(--border, rgba(255, 255, 255, 0.06));
    border-radius: var(--radius-xl, 16px);
    color: var(--text-primary, #e8e4de);
    font-size: var(--text-sm, 0.8125rem);
    line-height: var(--leading-relaxed, 1.7);
    transition: border-color 0.3s var(--ease-out-expo), box-shadow 0.3s var(--ease-out-expo);
}

/* Custom scrollbar */
.assistant-response::-webkit-scrollbar {
    width: 4px;
}

.assistant-response::-webkit-scrollbar-track {
    background: transparent;
}

.assistant-response::-webkit-scrollbar-thumb {
    background: rgba(201, 168, 76, 0.2);
    border-radius: 4px;
}

.assistant-response::-webkit-scrollbar-thumb:hover {
    background: rgba(201, 168, 76, 0.4);
}

/* ── Phase states ── */
.assistant-response--thinking {
    border-color: rgba(201, 168, 76, 0.3);
    box-shadow: 0 0 30px rgba(201, 168, 76, 0.06), inset 0 0 30px rgba(201, 168, 76, 0.03);
    animation: thinking-pulse 3s ease-in-out infinite;
}

.assistant-response--generating {
    border-color: rgba(201, 168, 76, 0.2);
    box-shadow: 0 0 20px rgba(201, 168, 76, 0.04);
}

.assistant-response--complete {
    border-color: var(--border, rgba(255, 255, 255, 0.06));
    box-shadow: none;
}

@keyframes thinking-pulse {

    0%,
    100% {
        border-color: rgba(201, 168, 76, 0.2);
    }

    50% {
        border-color: rgba(201, 168, 76, 0.4);
    }
}

/* ── Thinking section ── */
.thinking-section {
    margin-bottom: var(--space-4, 16px);
    padding-bottom: var(--space-3, 12px);
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.thinking-section--active {
    border-bottom-color: rgba(201, 168, 76, 0.15);
}

.thinking-toggle {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    background: none;
    border: none;
    color: var(--accent, #c9a84c);
    font-size: var(--text-sm, 0.8125rem);
    cursor: pointer;
    padding: var(--space-1, 4px) 0;
    font-family: inherit;
    transition: opacity 0.2s ease;
}

.thinking-toggle:hover {
    opacity: 0.8;
}

.thinking-toggle__icon {
    font-size: 1rem;
}

.thinking-toggle__label {
    font-weight: 500;
    letter-spacing: 0.02em;
}

.thinking-toggle__indicator {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent, #c9a84c);
    animation: blink 1.2s ease-in-out infinite;
}

.thinking-toggle__chevron {
    font-size: 1rem;
    transition: transform 0.25s ease;
    margin-left: auto;
}

.thinking-toggle__chevron--open {
    transform: rotate(90deg);
}

.thinking-preview {
    margin: var(--space-2, 8px) 0 0;
    color: var(--text-secondary, #8a8578);
    font-size: var(--text-sm, 0.8125rem);
    line-height: 1.5;
    opacity: 0.7;
}

.thinking-body {
    margin-top: var(--space-2, 8px);
    padding: var(--space-3, 12px);
    background: rgba(201, 168, 76, 0.04);
    border-left: 2px solid var(--accent, #c9a84c);
    border-radius: 0 var(--radius-md, 8px) var(--radius-md, 8px) 0;
    color: var(--text-secondary, #8a8578);
    font-family: var(--font-mono, ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace);
    font-size: var(--text-sm, 0.8125rem);
    line-height: 1.6;
    overflow-wrap: break-word;
}

/* Thinking expand transition */
.thinking-expand-enter-active,
.thinking-expand-leave-active {
    transition: all 0.3s ease;
    overflow: hidden;
}

.thinking-expand-enter-from,
.thinking-expand-leave-to {
    opacity: 0;
    max-height: 0;
    padding-top: 0;
    padding-bottom: 0;
    margin-top: 0;
}

/* ── Response body (markdown content) ── */
.response-body {
    overflow-wrap: break-word;
}

.response-body :deep(p) {
    margin: 0 0 0.75em;
}

.response-body :deep(p:last-child) {
    margin-bottom: 0;
}

.response-body :deep(h1),
.response-body :deep(h2),
.response-body :deep(h3) {
    color: var(--text-primary, #e8e4de);
    margin: 1.2em 0 0.5em;
    line-height: 1.3;
}

.response-body :deep(h1) {
    font-size: 1.35em;
}

.response-body :deep(h2) {
    font-size: 1.15em;
}

.response-body :deep(h3) {
    font-size: 1.05em;
}

.response-body :deep(h1:first-child),
.response-body :deep(h2:first-child),
.response-body :deep(h3:first-child) {
    margin-top: 0;
}

.response-body :deep(strong) {
    color: var(--text-primary, #e8e4de);
    font-weight: 600;
}

.response-body :deep(em) {
    font-style: italic;
    color: var(--text-secondary, #8a8578);
}

.response-body :deep(.inline-code) {
    background: rgba(201, 168, 76, 0.1);
    border: 1px solid rgba(201, 168, 76, 0.15);
    border-radius: 4px;
    padding: 0.1em 0.35em;
    font-family: var(--font-mono, ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace);
    font-size: 0.88em;
    color: var(--accent, #c9a84c);
}

.response-body :deep(.code-block) {
    position: relative;
    background: var(--bg-primary, #0c0e12);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: var(--radius-md, 8px);
    padding: var(--space-4, 16px);
    margin: 0.75em 0;
    overflow-x: auto;
    font-family: var(--font-mono, ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace);
    font-size: 0.85em;
    line-height: 1.55;
    color: var(--text-primary, #e8e4de);
}

.response-body :deep(.code-block code) {
    background: none;
    border: none;
    padding: 0;
    font-size: inherit;
    color: inherit;
}

.response-body :deep(.code-block__lang) {
    display: block;
    margin-bottom: var(--space-2, 8px);
    font-size: 0.75em;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--accent, #c9a84c);
    opacity: 0.6;
}

.response-body :deep(ul),
.response-body :deep(ol) {
    margin: 0.5em 0;
    padding-left: 1.5em;
}

.response-body :deep(li) {
    margin-bottom: 0.3em;
}

.response-body :deep(blockquote) {
    margin: 0.75em 0;
    padding: var(--space-2, 8px) var(--space-3, 12px);
    border-left: 3px solid var(--accent-border, rgba(201, 168, 76, 0.25));
    background: rgba(201, 168, 76, 0.04);
    color: var(--text-secondary, #8a8578);
    border-radius: 0 var(--radius-sm, 4px) var(--radius-sm, 4px) 0;
}

.response-body :deep(a) {
    color: var(--accent, #c9a84c);
    text-decoration: none;
    border-bottom: 1px solid rgba(201, 168, 76, 0.3);
    transition: border-color 0.2s ease;
}

.response-body :deep(a:hover) {
    border-bottom-color: var(--accent, #c9a84c);
}

/* ── Streaming cursor ── */
.streaming-cursor {
    display: inline-block;
    width: 2px;
    height: 1.1em;
    background: var(--accent, #c9a84c);
    margin-left: 2px;
    vertical-align: text-bottom;
    animation: cursor-blink 0.8s ease-in-out infinite;
}

@keyframes cursor-blink {

    0%,
    100% {
        opacity: 1;
    }

    50% {
        opacity: 0;
    }
}

/* ── Thinking placeholder dots ── */
.thinking-placeholder {
    display: flex;
    gap: 6px;
    justify-content: center;
    padding: var(--space-3, 12px) 0;
}

.thinking-placeholder__dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent, #c9a84c);
    animation: dot-pulse 1.4s ease-in-out infinite;
}

.thinking-placeholder__dot:nth-child(2) {
    animation-delay: 0.2s;
}

.thinking-placeholder__dot:nth-child(3) {
    animation-delay: 0.4s;
}

@keyframes dot-pulse {

    0%,
    80%,
    100% {
        opacity: 0.2;
        transform: scale(0.8);
    }

    40% {
        opacity: 1;
        transform: scale(1);
    }
}

@keyframes blink {

    0%,
    100% {
        opacity: 1;
    }

    50% {
        opacity: 0.3;
    }
}
</style>
