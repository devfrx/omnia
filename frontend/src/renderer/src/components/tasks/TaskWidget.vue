<script setup lang="ts">
/**
 * TaskWidget — Sidebar widget showing active autonomous tasks.
 *
 * Expanded mode: section label, header with task count, preview/list.
 * Collapsed mode: task icon with active count badge (34x34 circle).
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTasksStore } from '../../stores/tasks'

const props = defineProps<{
    collapsed: boolean
}>()

const store = useTasksStore()
const router = useRouter()
const expanded = ref(false)

let refreshInterval: ReturnType<typeof setInterval> | null = null

/** Count of active tasks (pending + running). */
const activeCount = computed((): number => {
    if (!store.stats) return 0
    return store.stats.pending + store.stats.running
})

/** Tasks currently pending or running. */
const activeTasks = computed(() =>
    store.tasks.filter((t) => t.status === 'pending' || t.status === 'running')
)

/** Next running or pending task for preview. */
const nextTask = computed(() => activeTasks.value[0] ?? null)

/** Tooltip for collapsed mode. */
const tooltipText = computed((): string => {
    const count = activeCount.value
    if (count === 0) return 'Nessun task attivo'
    return count === 1 ? '1 task attivo' : `${count} task attivi`
})

/** Truncate text to a max length. */
function truncate(text: string, max: number): string {
    if (text.length <= max) return text
    return text.slice(0, max) + '…'
}

function toggleExpanded(): void {
    expanded.value = !expanded.value
}

function openTasks(): void {
    router.push('/tasks')
}

onMounted(() => {
    store.loadTasks()
    store.loadStats()
    refreshInterval = setInterval(() => {
        store.loadTasks()
        store.loadStats()
    }, 30_000)
})

onUnmounted(() => {
    if (refreshInterval) {
        clearInterval(refreshInterval)
        refreshInterval = null
    }
})
</script>

<template>
    <!-- Collapsed sidebar mode — icon + badge only -->
    <div v-if="props.collapsed" class="task-widget task-widget--collapsed" :title="tooltipText">
        <div class="task-widget__icon-btn" @click="openTasks">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
            </svg>
            <span v-if="activeCount > 0" class="task-widget__mini-badge">
                {{ activeCount }}
            </span>
        </div>
    </div>

    <!-- Expanded sidebar mode — full widget -->
    <div v-else class="task-widget">
        <!-- Section label (same style as CalendarWidget / "Conversazioni") -->
        <div class="task-widget__section-label">
            <span>Task Autonomi</span>
        </div>

        <!-- Header: icon + count + badge + open-page button + chevron -->
        <div class="task-widget__header" @click="toggleExpanded">
            <span class="task-widget__icon" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                    stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                </svg>
            </span>
            <span class="task-widget__label">
                {{ activeCount }} task attiv{{ activeCount === 1 ? 'o' : 'i' }}
            </span>
            <span v-if="activeCount > 0" class="task-widget__badge"
                :class="{ 'task-widget__badge--running': store.stats && store.stats.running > 0 }">
                {{ activeCount }}
            </span>
            <button class="task-widget__open-btn" title="Apri pagina task" @click.stop="openTasks">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                    <polyline points="15 3 21 3 21 9" />
                    <line x1="10" y1="14" x2="21" y2="3" />
                </svg>
            </button>
            <span class="task-widget__chevron" :class="{ 'task-widget__chevron--open': expanded }" aria-hidden="true">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
                    stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="6 9 12 15 18 9" />
                </svg>
            </span>
        </div>

        <!-- Next task preview (when list is collapsed) -->
        <div v-if="!expanded && nextTask" class="task-widget__next">
            <span class="task-widget__next-status" :class="{
                'task-widget__next-status--running': nextTask.status === 'running',
                'task-widget__next-status--pending': nextTask.status === 'pending'
            }">
                {{ nextTask.status === 'running' ? '●' : '○' }}
            </span>
            <span class="task-widget__next-prompt">{{ truncate(nextTask.prompt, 40) }}</span>
        </div>

        <!-- Expanded task list -->
        <transition name="task-expand">
            <div v-if="expanded" class="task-widget__list">
                <div v-if="activeTasks.length === 0" class="task-widget__empty">
                    Nessun task attivo
                </div>
                <div v-for="task in activeTasks" :key="task.id" class="task-widget__item">
                    <span class="task-widget__item-badge" :class="{
                        'task-widget__item-badge--running': task.status === 'running',
                        'task-widget__item-badge--pending': task.status === 'pending'
                    }">
                        {{ task.status === 'running' ? 'In esecuzione' : 'In attesa' }}
                    </span>
                    <span class="task-widget__item-prompt">{{ truncate(task.prompt, 36) }}</span>
                </div>
            </div>
        </transition>
    </div>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════
   TaskWidget — Sidebar task widget
   ═══════════════════════════════════════════════════════════ */

/* ------------------------------------------------- Root */
.task-widget {
    position: relative;
    z-index: 1;
    flex-shrink: 0;
}

/* ------------------------------------------------- Section label */
.task-widget__section-label {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) 14px var(--space-1);
    font-size: var(--text-2xs);
    font-weight: var(--weight-bold);
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-muted);
}

.task-widget__section-label::after {
    content: '';
    flex: 1;
    height: var(--space-px);
    background: linear-gradient(90deg, var(--border) 0%, transparent 100%);
}

/* ------------------------------------------------- Header */
.task-widget__header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1-5) 14px;
    cursor: pointer;
    border-radius: var(--radius-md);
    margin: 0 var(--space-1);
    transition:
        background var(--transition-fast),
        color var(--transition-fast);
}

.task-widget__header:hover {
    background: rgba(255, 255, 255, 0.04);
}

.task-widget__header:active {
    transform: scale(0.98);
}

/* ------------------------------------------------- Icon */
.task-widget__icon {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    color: var(--text-muted);
    opacity: var(--opacity-soft);
    transition: opacity var(--transition-fast);
}

.task-widget__header:hover .task-widget__icon {
    opacity: 1;
}

/* ------------------------------------------------- Label */
.task-widget__label {
    font-size: var(--text-sm);
    font-weight: var(--weight-medium);
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
    min-width: 0;
}

/* ------------------------------------------------- Badge (active task count) */
.task-widget__badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 18px;
    height: 18px;
    padding: 0 5px;
    border-radius: var(--radius-full, 9999px);
    background: var(--accent);
    color: #1a1a2e;
    font-size: var(--text-2xs);
    font-weight: var(--weight-bold);
    line-height: 1;
    flex-shrink: 0;
}

.task-widget__badge--running {
    animation: task-pulse 1.5s ease-in-out infinite;
}

@keyframes task-pulse {

    0%,
    100% {
        opacity: 1;
    }

    50% {
        opacity: 0.55;
    }
}

/* ------------------------------------------------- Open page button */
.task-widget__open-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: var(--radius-sm);
    border: none;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    flex-shrink: 0;
    transition: color var(--transition-fast), background var(--transition-fast);
}

.task-widget__open-btn:hover {
    color: var(--accent);
    background: rgba(255, 255, 255, 0.05);
}

/* ------------------------------------------------- Chevron */
.task-widget__chevron {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    color: var(--text-muted);
    transition: transform var(--transition-fast);
}

.task-widget__chevron--open {
    transform: rotate(180deg);
}

/* ------------------------------------------------- Next task preview */
.task-widget__next {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) 14px var(--space-1-5);
    margin: 0 var(--space-1);
}

.task-widget__next-status {
    flex-shrink: 0;
    font-size: var(--text-xs);
    color: var(--text-muted);
}

.task-widget__next-status--running {
    color: #4fc3f7;
    animation: task-pulse 1.5s ease-in-out infinite;
}

.task-widget__next-status--pending {
    color: var(--text-muted);
}

.task-widget__next-prompt {
    font-size: var(--text-xs);
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
    flex: 1;
}

/* ------------------------------------------------- Expanded task list */
.task-widget__list {
    max-height: 150px;
    overflow-y: auto;
    padding: var(--space-1) 0 var(--space-2);
    margin: 0 var(--space-1);
}

.task-widget__list::-webkit-scrollbar {
    width: 3px;
}

.task-widget__list::-webkit-scrollbar-track {
    background: transparent;
}

.task-widget__list::-webkit-scrollbar-thumb {
    background: var(--glass-border);
    border-radius: var(--radius-full, 9999px);
}

/* ------------------------------------------------- Task item row */
.task-widget__item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) 14px;
    border-radius: var(--radius-sm);
    transition: background var(--transition-fast);
}

.task-widget__item:hover {
    background: rgba(255, 255, 255, 0.03);
}

.task-widget__item-badge {
    font-size: 9px;
    font-weight: var(--weight-bold);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 1px 5px;
    border-radius: var(--radius-sm);
    flex-shrink: 0;
    white-space: nowrap;
}

.task-widget__item-badge--running {
    background: rgba(79, 195, 247, 0.15);
    color: #4fc3f7;
    animation: task-pulse 1.5s ease-in-out infinite;
}

.task-widget__item-badge--pending {
    background: rgba(176, 190, 197, 0.1);
    color: var(--text-muted);
}

.task-widget__item-prompt {
    font-size: var(--text-xs);
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
}

/* ------------------------------------------------- Empty state */
.task-widget__empty {
    padding: var(--space-2) 14px;
    font-size: var(--text-xs);
    color: var(--text-muted);
    font-style: italic;
}

/* ------------------------------------------------- Expand/collapse transition */
.task-expand-enter-active,
.task-expand-leave-active {
    transition:
        max-height 0.25s cubic-bezier(0.4, 0, 0.2, 1),
        opacity 0.2s ease;
    overflow: hidden;
}

.task-expand-enter-from,
.task-expand-leave-to {
    max-height: 0;
    opacity: 0;
}

.task-expand-enter-to,
.task-expand-leave-from {
    max-height: 150px;
    opacity: 1;
}

/* ═══════════════════════════════════════════════════════════
   Collapsed mode — icon-only circular button
   ═══════════════════════════════════════════════════════════ */
.task-widget--collapsed {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--space-1) 0;
    cursor: pointer;
}

.task-widget__icon-btn {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    border-radius: var(--radius-full, 9999px);
    color: var(--text-secondary);
    cursor: pointer;
    transition:
        background var(--transition-fast),
        color var(--transition-fast);
}

.task-widget__icon-btn:hover {
    background: rgba(255, 255, 255, 0.04);
    color: var(--text-primary);
}

.task-widget__mini-badge {
    position: absolute;
    top: 1px;
    right: 1px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 14px;
    height: 14px;
    padding: 0 3px;
    border-radius: var(--radius-full, 9999px);
    background: var(--accent);
    color: #1a1a2e;
    font-size: 9px;
    font-weight: var(--weight-bold);
    line-height: 1;
    pointer-events: none;
}

/* ------------------------------------------------- Reduced motion */
@media (prefers-reduced-motion: reduce) {

    .task-widget__header,
    .task-widget__icon,
    .task-widget__chevron,
    .task-widget__item,
    .task-widget__icon-btn,
    .task-widget__badge--running,
    .task-widget__item-badge--running,
    .task-widget__next-status--running,
    .task-expand-enter-active,
    .task-expand-leave-active {
        transition: none;
        animation: none;
    }
}
</style>
