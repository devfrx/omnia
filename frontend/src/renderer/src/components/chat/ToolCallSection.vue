<script setup lang="ts">
/**
 * ToolCallSection.vue — Collapsible display of tool calls on a message.
 *
 * Follows the same collapsible pattern as ThinkingSection.vue.
 * Shows tool function names and their JSON arguments.
 */
import { computed, ref } from 'vue'

import type { ToolCall } from '../../types/chat'

const props = defineProps<{
    /** The tool_calls array from the assistant message. */
    toolCalls: ToolCall[]
}>()

const collapsed = ref(true)

const badgeText = computed(() => {
    const n = props.toolCalls.length
    return n === 1 ? '1 tool call' : `${n} tool calls`
})

/** Parse arguments JSON safely. */
function formatArgs(args: string): string {
    try {
        return JSON.stringify(JSON.parse(args), null, 2)
    } catch {
        return args
    }
}
</script>

<template>
    <div class="tool-section" role="region" aria-label="Tool calls">
        <!-- Header row -->
        <button class="tool-section__toggle" :aria-expanded="!collapsed" @click="collapsed = !collapsed">
            <svg class="tool-section__icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path
                    d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
            </svg>
            <span class="tool-section__label">Strumenti usati</span>
            <span class="tool-section__count">{{ badgeText }}</span>
            <svg class="tool-section__chevron" :class="{ 'tool-section__chevron--open': !collapsed }" width="12"
                height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <polyline points="6 9 12 15 18 9" />
            </svg>
        </button>

        <!-- Collapsed chips strip: one chip per tool call, horizontally scrollable -->
        <div class="tool-section__chips" :class="{ 'tool-section__chips--hidden': !collapsed }">
            <div class="tool-section__chips-inner">
                <div v-for="(tc, index) in toolCalls" :key="tc.id ?? index" class="tool-section__chip">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                        stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <path
                            d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
                    </svg>
                    <span>{{ tc.function.name }}</span>
                </div>
            </div>
        </div>

        <!-- Expanded cards: full detail per tool call -->
        <div class="tool-section__body" :class="{ 'tool-section__body--collapsed': collapsed }">
            <div class="tool-section__inner">
                <div v-for="(tc, index) in toolCalls" :key="tc.id ?? index" class="tool-section__card">
                    <div class="tool-section__card-header">
                        <span class="tool-section__fn-name">{{ tc.function.name }}</span>
                        <span class="tool-section__call-id">#{{ (tc.id ?? '').slice(0, 8) || '?' }}</span>
                    </div>
                    <pre class="tool-section__args"><code>{{ formatArgs(tc.function.arguments) }}</code></pre>
                </div>
            </div>
        </div>

        <div class="tool-section__separator" />
    </div>
</template>

<style scoped>
.tool-section {
    margin-bottom: 10px;
}

/* --------------------------------------------------------- Header / toggle */
.tool-section__toggle {
    display: flex;
    align-items: center;
    gap: 7px;
    width: 100%;
    padding: 5px 0;
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 0.75rem;
    cursor: pointer;
    text-align: left;
    border-radius: var(--radius-sm);
    transition: color var(--transition-fast);
    user-select: none;
}

.tool-section__toggle:hover {
    color: var(--text-secondary);
}

.tool-section__icon {
    flex-shrink: 0;
    opacity: 0.55;
    color: var(--accent);
}

.tool-section__label {
    font-family: var(--font-mono);
    font-size: 0.68rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    flex: 1;
    text-align: left;
}

.tool-section__count {
    font-family: var(--font-mono);
    font-size: 0.62rem;
    color: var(--accent);
    background: var(--accent-dim);
    border: 1px solid var(--accent-border);
    padding: 1px 8px;
    border-radius: 10px;
    letter-spacing: 0;
    line-height: 1.6;
}

.tool-section__chevron {
    flex-shrink: 0;
    opacity: 0.5;
    transition: transform var(--transition-fast);
}

.tool-section__chevron--open {
    transform: rotate(180deg);
}

/* --------------------------------------------------------- Chips strip */
.tool-section__chips {
    display: grid;
    grid-template-rows: 1fr;
    opacity: 1;
    transition:
        grid-template-rows 0.3s cubic-bezier(0.4, 0, 0.2, 1),
        opacity 0.25s ease;
}

.tool-section__chips--hidden {
    grid-template-rows: 0fr;
    opacity: 0;
    pointer-events: none;
}

.tool-section__chips-inner {
    overflow: hidden;
    min-height: 0;
    display: flex;
    gap: 6px;
    padding: 3px 0 8px;
    overflow-x: auto;
    scrollbar-width: none;
}

.tool-section__chips-inner::-webkit-scrollbar {
    display: none;
}

.tool-section__chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 10px 3px 7px;
    background: rgba(201, 168, 76, 0.05);
    border: 1px solid var(--accent-border);
    border-radius: 20px;
    font-family: var(--font-mono);
    font-size: 0.68rem;
    color: var(--text-secondary);
    white-space: nowrap;
    flex-shrink: 0;
    line-height: 1.4;
}

.tool-section__chip svg {
    flex-shrink: 0;
    opacity: 0.45;
    color: var(--accent);
}

/* --------------------------------------------------------- Expanded body */
.tool-section__body {
    display: grid;
    grid-template-rows: 1fr;
    opacity: 1;
    transition:
        grid-template-rows 0.35s cubic-bezier(0.4, 0, 0.2, 1),
        opacity 0.3s ease;
}

.tool-section__body--collapsed {
    grid-template-rows: 0fr;
    opacity: 0;
    pointer-events: none;
}

.tool-section__inner {
    overflow: hidden;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 3px 0 8px;
}

/* --------------------------------------------------------- Tool call card */
.tool-section__card {
    background: rgba(0, 0, 0, 0.22);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-left: 2px solid var(--accent-border);
    border-radius: var(--radius-sm);
    overflow: hidden;
}

.tool-section__card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 10px 5px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    background: rgba(201, 168, 76, 0.03);
}

.tool-section__fn-name {
    font-family: var(--font-mono);
    font-size: 0.74rem;
    color: var(--accent);
    font-weight: 500;
    letter-spacing: 0.02em;
}

.tool-section__call-id {
    font-family: var(--font-mono);
    font-size: 0.6rem;
    color: var(--text-muted);
    letter-spacing: 0.06em;
    opacity: 0.65;
}

.tool-section__args {
    margin: 0;
    padding: 8px 12px;
    font-family: var(--font-mono);
    font-size: 0.7rem;
    line-height: 1.65;
    color: var(--text-secondary);
    background: transparent;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-word;
    user-select: text;
    cursor: text;
}

.tool-section__args code {
    font-family: inherit;
    font-size: inherit;
    color: inherit;
    background: none;
}

/* --------------------------------------------------------- Separator */
.tool-section__separator {
    height: 1px;
    background: var(--border);
    margin: 2px 0 6px;
}

/* ------------------------------------------------- Reduced motion */
@media (prefers-reduced-motion: reduce) {

    .tool-section__chips,
    .tool-section__body,
    .tool-section__chevron,
    .tool-section__toggle {
        transition: none;
    }
}
</style>
