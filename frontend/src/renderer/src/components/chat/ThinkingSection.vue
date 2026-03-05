<script setup lang="ts">
/**
 * ThinkingSection.vue — Collapsible "Ragionamento" section.
 *
 * Reusable component that renders a collapsible thinking/reasoning
 * section with rendered markdown content. Used by both MessageBubble
 * and StreamingIndicator.
 */
import { ref, watch } from 'vue'

import { useCodeBlocks } from '../../composables/useCodeBlocks'

const props = defineProps<{
    /** Pre-rendered HTML of thinking content. */
    thinkingHtml: string
    /** Whether the section starts collapsed. */
    initialCollapsed?: boolean
    /** Whether to auto-expand when content grows (for streaming). */
    autoExpand?: boolean
    /** Raw thinking content length, used for auto-expand detection. */
    contentLength?: number
}>()

const collapsed = ref(props.initialCollapsed ?? true)

const { handleCodeBlockClick } = useCodeBlocks()

// Auto-expand while thinking tokens are arriving
if (props.autoExpand) {
    watch(
        () => props.contentLength,
        (val, old) => {
            if ((val ?? 0) > (old ?? 0)) {
                collapsed.value = false
            }
        }
    )
}
</script>

<template>
    <div class="thinking-section" role="region" aria-label="Ragionamento del modello">
        <button class="thinking-section__toggle" :aria-expanded="!collapsed" aria-label="Mostra/nascondi ragionamento"
            @click="collapsed = !collapsed">
            <svg class="thinking-section__icon" width="14" height="14" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path
                    d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z" />
                <line x1="9" y1="21" x2="15" y2="21" />
                <line x1="10" y1="24" x2="14" y2="24" />
            </svg>
            <span class="thinking-section__label">Ragionamento</span>
            <svg class="thinking-section__chevron" :class="{ 'thinking-section__chevron--collapsed': collapsed }"
                width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                stroke-linecap="round" stroke-linejoin="round">
                <polyline points="6 9 12 15 18 9" />
            </svg>
        </button>
        <div v-show="!collapsed" class="thinking-section__body">
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div class="thinking-section__content" v-html="thinkingHtml" @click="handleCodeBlockClick" />
            <slot />
        </div>
    </div>
</template>

<style scoped>
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
</style>
