<script setup lang="ts">
/**
 * TasksView — Full-page autonomous task management view.
 *
 * Displays task list with real-time status, filters, stats,
 * task detail expansion, and recent activity log.
 */
import { computed, onMounted, ref, onUnmounted } from 'vue'
import { useTasksStore } from '../../stores/tasks'
import type { TaskStatus } from '../../types/tasks'

const store = useTasksStore()
const filterStatus = ref<TaskStatus | ''>('')
const expandedTask = ref<string | null>(null)

/** Countdown interval handle. */
let countdownTimer: ReturnType<typeof setInterval> | null = null
const now = ref(Date.now())

onMounted(() => {
    store.loadTasks()
    store.loadStats()
    countdownTimer = setInterval(() => {
        now.value = Date.now()
    }, 1000)
})

onUnmounted(() => {
    if (countdownTimer) clearInterval(countdownTimer)
})

const filteredTasks = computed(() => {
    if (!filterStatus.value) return store.tasks
    return store.tasks.filter((t) => t.status === filterStatus.value)
})

function toggleExpand(id: string): void {
    expandedTask.value = expandedTask.value === id ? null : id
}

async function handleCancel(id: string): Promise<void> {
    if (confirm('Cancellare questo task?')) {
        await store.cancelTask(id)
    }
}

async function handleTrigger(id: string): Promise<void> {
    await store.triggerManual(id)
    await store.loadTasks()
}

function statusLabel(status: string): string {
    const map: Record<string, string> = {
        pending: 'In attesa',
        running: 'In esecuzione',
        completed: 'Completato',
        failed: 'Fallito',
        cancelled: 'Cancellato',
    }
    return map[status] || status
}

function statusBadgeClass(status: string): string {
    const map: Record<string, string> = {
        pending: 'badge--pending',
        running: 'badge--running',
        completed: 'badge--completed',
        failed: 'badge--failed',
        cancelled: 'badge--cancelled',
    }
    return map[status] || ''
}

function formatDate(iso: string | null): string {
    if (!iso) return '—'
    return new Date(iso).toLocaleString('it-IT')
}

function triggerLabel(type: string): string {
    const map: Record<string, string> = {
        once_at: 'Una Tantum',
        interval: 'Ricorrente',
        manual: 'Manuale',
    }
    return map[type] || type
}

/** Format interval seconds into human-readable Italian string. */
function formatInterval(seconds: number): string {
    if (seconds < 60) return `ogni ${seconds}s`
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    if (mins < 60) {
        return secs > 0 ? `ogni ${mins}min ${secs}s` : `ogni ${mins} minut${mins === 1 ? 'o' : 'i'}`
    }
    const hours = Math.floor(mins / 60)
    const remMins = mins % 60
    if (remMins > 0) return `ogni ${hours}h ${remMins}min`
    return `ogni ${hours} or${hours === 1 ? 'a' : 'e'}`
}

/** Format next run countdown as relative time. */
function nextRunCountdown(iso: string | null): string {
    if (!iso) return '—'
    const diff = new Date(iso).getTime() - now.value
    if (diff <= 0) return 'imminente'
    const totalSecs = Math.floor(diff / 1000)
    const mins = Math.floor(totalSecs / 60)
    const secs = totalSecs % 60
    if (mins < 1) return `tra ${secs}s`
    if (mins < 60) return secs > 0 ? `tra ${mins}min ${secs}s` : `tra ${mins}min`
    const hours = Math.floor(mins / 60)
    const remMins = mins % 60
    return remMins > 0 ? `tra ${hours}h ${remMins}min` : `tra ${hours}h`
}

/** Map event type to Italian label. */
function eventTypeLabel(type: string): string {
    const map: Record<string, string> = {
        task_scheduled: 'Programmato',
        task_started: 'Avviato',
        task_completed: 'Completato',
        task_failed: 'Fallito',
        task_cancelled: 'Cancellato',
    }
    return map[type] || type
}

/** CSS class for event type. */
function eventTypeClass(type: string): string {
    const map: Record<string, string> = {
        task_scheduled: 'event-type--scheduled',
        task_started: 'event-type--started',
        task_completed: 'event-type--completed',
        task_failed: 'event-type--failed',
        task_cancelled: 'event-type--cancelled',
    }
    return map[type] || ''
}
</script>

<template>
    <div class="tasks-view">
        <!-- Page header -->
        <header class="tasks-view__header">
            <div class="tasks-view__title-row">
                <svg class="tasks-view__title-icon" width="24" height="24" viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                </svg>
                <h1 class="tasks-view__title">Task Autonomi</h1>
            </div>

            <!-- Stats bar -->
            <div v-if="store.stats" class="tasks-view__stats">
                <div class="stat-chip stat-chip--pending">
                    <span class="stat-chip__count">{{ store.stats.pending }}</span>
                    <span class="stat-chip__label">In attesa</span>
                </div>
                <div class="stat-chip stat-chip--running">
                    <span class="stat-chip__dot stat-chip__dot--pulse" />
                    <span class="stat-chip__count">{{ store.stats.running }}</span>
                    <span class="stat-chip__label">In esecuzione</span>
                </div>
                <div class="stat-chip stat-chip--completed">
                    <span class="stat-chip__count">{{ store.stats.completed }}</span>
                    <span class="stat-chip__label">Completati</span>
                </div>
                <div class="stat-chip stat-chip--failed">
                    <span class="stat-chip__count">{{ store.stats.failed }}</span>
                    <span class="stat-chip__label">Falliti</span>
                </div>
            </div>
        </header>

        <!-- Filter bar -->
        <div class="tasks-view__filters">
            <select v-model="filterStatus" class="tasks-view__select"
                @change="store.loadTasks(filterStatus || undefined)">
                <option value="">Tutti</option>
                <option value="pending">In attesa</option>
                <option value="running">In esecuzione</option>
                <option value="completed">Completati</option>
                <option value="failed">Falliti</option>
                <option value="cancelled">Cancellati</option>
            </select>
        </div>

        <!-- Content area -->
        <div class="tasks-view__content">
            <!-- Loading -->
            <div v-if="store.loading" class="tasks-view__loading">
                <span class="tasks-view__spinner" />
                Caricamento task…
            </div>

            <!-- Empty -->
            <div v-else-if="filteredTasks.length === 0" class="tasks-view__empty">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"
                    opacity="0.3">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                </svg>
                <p>Nessun task trovato.</p>
            </div>

            <!-- Task list -->
            <div v-else class="tasks-view__list">
                <div v-for="task in filteredTasks" :key="task.id" class="task-card"
                    :class="{ 'task-card--expanded': expandedTask === task.id }" @click="toggleExpand(task.id)">
                    <div class="task-card__header">
                        <span :class="['task-card__badge', statusBadgeClass(task.status)]">
                            <span v-if="task.status === 'running'" class="task-card__pulse-dot" />
                            {{ statusLabel(task.status) }}
                        </span>
                        <span class="task-card__trigger">{{ triggerLabel(task.trigger_type) }}</span>
                        <span v-if="task.status === 'running'" class="task-card__running-label">
                            In esecuzione<span class="task-card__dots" />
                        </span>
                        <span class="task-card__date">{{ formatDate(task.created_at) }}</span>
                    </div>

                    <p class="task-card__prompt">{{ task.prompt }}</p>

                    <!-- Expanded details -->
                    <transition name="detail-expand">
                        <div v-if="expandedTask === task.id" class="task-card__details">
                            <div class="detail-row">
                                <span class="detail-label">ID:</span>
                                <span class="detail-value detail-value--mono">{{ task.id }}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Esecuzioni:</span>
                                <span class="detail-value">
                                    {{ task.run_count }}{{ task.max_runs ? ` / ${task.max_runs}` : '' }}
                                </span>
                            </div>
                            <div v-if="task.next_run_at" class="detail-row">
                                <span class="detail-label">Prossima esecuzione:</span>
                                <span class="detail-value">
                                    {{ formatDate(task.next_run_at) }}
                                    <span class="detail-countdown">{{ nextRunCountdown(task.next_run_at) }}</span>
                                </span>
                            </div>
                            <div v-if="task.interval_seconds" class="detail-row">
                                <span class="detail-label">Intervallo:</span>
                                <span class="detail-value">{{ formatInterval(task.interval_seconds) }}</span>
                            </div>
                            <div v-if="task.last_run_at" class="detail-row">
                                <span class="detail-label">Ultima esecuzione:</span>
                                <span class="detail-value">{{ formatDate(task.last_run_at) }}</span>
                            </div>
                            <div v-if="task.result_summary" class="detail-row detail-row--full">
                                <span class="detail-label">Risultato:</span>
                                <p class="detail-value detail-value--result">{{ task.result_summary }}</p>
                            </div>
                            <div v-if="task.error_message" class="detail-row detail-row--full">
                                <span class="detail-label">Errore:</span>
                                <p class="detail-value detail-value--error">{{ task.error_message }}</p>
                            </div>

                            <!-- Actions -->
                            <div class="task-card__actions">
                                <button v-if="task.trigger_type === 'manual' && task.status === 'pending'"
                                    class="btn btn--primary" @click.stop="handleTrigger(task.id)">
                                    Esegui ora
                                </button>
                                <button v-if="task.status === 'pending' || task.status === 'running'"
                                    class="btn btn--danger" @click.stop="handleCancel(task.id)">
                                    Cancella
                                </button>
                            </div>
                        </div>
                    </transition>
                </div>
            </div>

            <!-- Recent Activity -->
            <div v-if="store.recentActivity.length > 0" class="tasks-view__activity">
                <h3 class="tasks-view__activity-title">Attività Recente</h3>
                <div v-for="(event, idx) in store.recentActivity.slice(0, 10)" :key="idx" class="activity-row">
                    <span :class="['activity-row__type', eventTypeClass(event.type)]">
                        {{ eventTypeLabel(event.type) }}
                    </span>
                    <span class="activity-row__time">{{ formatDate(event.timestamp) }}</span>
                </div>
            </div>

            <!-- Error -->
            <div v-if="store.error" class="tasks-view__error">
                {{ store.error }}
            </div>
        </div>
    </div>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════
   TasksView — Full-page task management
   ═══════════════════════════════════════════════════════════ */

/* ------------------------------------------------- Root */
.tasks-view {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
    color: var(--text-primary);
    background: var(--surface-1);
}

/* ------------------------------------------------- Header */
.tasks-view__header {
    flex-shrink: 0;
    padding: var(--space-6) var(--space-6) var(--space-4);
    border-bottom: 1px solid var(--border);
}

.tasks-view__title-row {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
}

.tasks-view__title-icon {
    color: var(--accent);
    flex-shrink: 0;
}

.tasks-view__title {
    margin: 0;
    font-size: var(--text-xl);
    font-weight: var(--weight-bold);
    color: var(--text-primary);
}

/* ------------------------------------------------- Stats */
.tasks-view__stats {
    display: flex;
    gap: var(--space-3);
    flex-wrap: wrap;
}

.stat-chip {
    display: flex;
    align-items: center;
    gap: var(--space-1-5);
    padding: var(--space-1-5) var(--space-3);
    border-radius: var(--radius-md);
    background: var(--surface-inset);
    border: 1px solid var(--border);
    font-size: var(--text-sm);
}

.stat-chip__count {
    font-weight: var(--weight-bold);
    font-variant-numeric: tabular-nums;
}

.stat-chip__label {
    color: var(--text-muted);
    font-size: var(--text-xs);
}

.stat-chip__dot {
    width: 6px;
    height: 6px;
    border-radius: var(--radius-full, 9999px);
    flex-shrink: 0;
}

.stat-chip__dot--pulse {
    background: #4fc3f7;
    animation: dot-pulse 1.5s ease-in-out infinite;
}

.stat-chip--pending .stat-chip__count {
    color: var(--text-secondary);
}

.stat-chip--running .stat-chip__count {
    color: #4fc3f7;
}

.stat-chip--completed .stat-chip__count {
    color: #81c784;
}

.stat-chip--failed .stat-chip__count {
    color: #e57373;
}

@keyframes dot-pulse {

    0%,
    100% {
        opacity: 1;
        transform: scale(1);
    }

    50% {
        opacity: 0.4;
        transform: scale(0.7);
    }
}

/* ------------------------------------------------- Filters */
.tasks-view__filters {
    flex-shrink: 0;
    padding: var(--space-3) var(--space-6);
    border-bottom: 1px solid var(--border);
}

.tasks-view__select {
    background: var(--surface-inset);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: var(--space-1-5) var(--space-3);
    font-size: var(--text-sm);
    cursor: pointer;
    transition: border-color var(--transition-fast);
}

.tasks-view__select:focus {
    outline: none;
    border-color: var(--accent);
}

/* ------------------------------------------------- Content (scrollable) */
.tasks-view__content {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-4) var(--space-6) var(--space-6);
}

.tasks-view__content::-webkit-scrollbar {
    width: 5px;
}

.tasks-view__content::-webkit-scrollbar-track {
    background: transparent;
}

.tasks-view__content::-webkit-scrollbar-thumb {
    background: var(--glass-border);
    border-radius: var(--radius-full, 9999px);
}

/* ------------------------------------------------- Loading */
.tasks-view__loading {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    padding: var(--space-8);
    color: var(--text-muted);
    font-size: var(--text-sm);
}

.tasks-view__spinner {
    width: 16px;
    height: 16px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: var(--radius-full, 9999px);
    animation: spin 0.8s linear infinite;
}

@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}

/* ------------------------------------------------- Empty */
.tasks-view__empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-10);
    color: var(--text-muted);
    font-size: var(--text-sm);
}

/* ------------------------------------------------- Task list */
.tasks-view__list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
}

/* ------------------------------------------------- Task card */
.task-card {
    background: var(--surface-inset);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: var(--space-3) var(--space-4);
    cursor: pointer;
    transition:
        border-color var(--transition-fast),
        box-shadow var(--transition-fast);
}

.task-card:hover {
    border-color: var(--accent);
}

.task-card--expanded {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.1);
}

.task-card__header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-1-5);
}

.task-card__badge {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: 2px 8px;
    border-radius: var(--radius-sm);
    font-size: var(--text-2xs);
    font-weight: var(--weight-bold);
    text-transform: uppercase;
    letter-spacing: 0.03em;
    white-space: nowrap;
}

.badge--pending {
    background: rgba(176, 190, 197, 0.12);
    color: #b0bec5;
}

.badge--running {
    background: rgba(79, 195, 247, 0.15);
    color: #4fc3f7;
}

.badge--completed {
    background: rgba(129, 199, 132, 0.15);
    color: #81c784;
}

.badge--failed {
    background: rgba(229, 115, 115, 0.15);
    color: #e57373;
}

.badge--cancelled {
    background: rgba(158, 158, 158, 0.12);
    color: #9e9e9e;
}

.task-card__pulse-dot {
    width: 6px;
    height: 6px;
    border-radius: var(--radius-full, 9999px);
    background: #4fc3f7;
    animation: dot-pulse 1.5s ease-in-out infinite;
}

.task-card__trigger {
    font-size: var(--text-xs);
    color: var(--text-muted);
}

.task-card__running-label {
    font-size: var(--text-xs);
    color: #4fc3f7;
    margin-left: auto;
    white-space: nowrap;
}

.task-card__dots::after {
    content: '';
    animation: dots-anim 1.5s steps(4, end) infinite;
}

@keyframes dots-anim {
    0% {
        content: '';
    }

    25% {
        content: '.';
    }

    50% {
        content: '..';
    }

    75% {
        content: '...';
    }
}

.task-card__date {
    margin-left: auto;
    font-size: var(--text-2xs);
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
}

.task-card__prompt {
    margin: 0;
    font-size: var(--text-sm);
    line-height: 1.5;
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* ------------------------------------------------- Expanded details */
.task-card__details {
    margin-top: var(--space-3);
    padding-top: var(--space-3);
    border-top: 1px solid var(--border);
}

.detail-row {
    display: flex;
    gap: var(--space-2);
    margin-bottom: var(--space-1);
    font-size: var(--text-sm);
    align-items: baseline;
}

.detail-row--full {
    flex-direction: column;
}

.detail-label {
    color: var(--text-muted);
    min-width: 150px;
    flex-shrink: 0;
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: var(--weight-medium);
}

.detail-value {
    color: var(--text-secondary);
}

.detail-value--mono {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: var(--text-xs);
    opacity: 0.7;
}

.detail-countdown {
    margin-left: var(--space-2);
    color: var(--accent);
    font-weight: var(--weight-medium);
    font-size: var(--text-xs);
}

.detail-value--result {
    background: var(--surface-1);
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-sm);
    font-size: var(--text-sm);
    white-space: pre-wrap;
    margin: var(--space-1) 0 0;
    border: 1px solid var(--border);
    line-height: 1.5;
}

.detail-value--error {
    color: #e57373;
    background: rgba(183, 28, 28, 0.08);
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-sm);
    font-size: var(--text-sm);
    margin: var(--space-1) 0 0;
    border: 1px solid rgba(183, 28, 28, 0.2);
}

/* Detail expand transition */
.detail-expand-enter-active,
.detail-expand-leave-active {
    transition: all 0.2s ease;
    overflow: hidden;
}

.detail-expand-enter-from,
.detail-expand-leave-to {
    opacity: 0;
    max-height: 0;
}

.detail-expand-enter-to,
.detail-expand-leave-from {
    opacity: 1;
    max-height: 600px;
}

/* ------------------------------------------------- Actions */
.task-card__actions {
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-3);
}

.btn {
    padding: var(--space-1-5) var(--space-4);
    border: none;
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
    font-weight: var(--weight-medium);
    cursor: pointer;
    transition:
        opacity var(--transition-fast),
        transform var(--transition-fast);
}

.btn:hover {
    opacity: 0.85;
}

.btn:active {
    transform: scale(0.97);
}

.btn--primary {
    background: var(--accent);
    color: #1a1a2e;
}

.btn--danger {
    background: rgba(198, 40, 40, 0.8);
    color: #fafafa;
}

/* ------------------------------------------------- Activity */
.tasks-view__activity {
    margin-top: var(--space-6);
    padding-top: var(--space-4);
    border-top: 1px solid var(--border);
}

.tasks-view__activity-title {
    font-size: var(--text-base);
    font-weight: var(--weight-bold);
    color: var(--text-primary);
    margin: 0 0 var(--space-3);
}

.activity-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-1-5) 0;
    font-size: var(--text-sm);
    border-bottom: 1px solid var(--border);
}

.activity-row:last-child {
    border-bottom: none;
}

.activity-row__type {
    font-weight: var(--weight-medium);
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 2px 8px;
    border-radius: var(--radius-sm);
}

.event-type--scheduled {
    background: rgba(176, 190, 197, 0.1);
    color: #b0bec5;
}

.event-type--started {
    background: rgba(79, 195, 247, 0.12);
    color: #4fc3f7;
}

.event-type--completed {
    background: rgba(129, 199, 132, 0.12);
    color: #81c784;
}

.event-type--failed {
    background: rgba(229, 115, 115, 0.12);
    color: #e57373;
}

.event-type--cancelled {
    background: rgba(158, 158, 158, 0.1);
    color: #9e9e9e;
}

.activity-row__time {
    color: var(--text-muted);
    font-size: var(--text-xs);
    font-variant-numeric: tabular-nums;
}

/* ------------------------------------------------- Error */
.tasks-view__error {
    margin-top: var(--space-4);
    padding: var(--space-2) var(--space-3);
    background: rgba(183, 28, 28, 0.1);
    border: 1px solid rgba(183, 28, 28, 0.25);
    border-radius: var(--radius-md);
    color: #e57373;
    font-size: var(--text-sm);
}

/* ------------------------------------------------- Reduced motion */
@media (prefers-reduced-motion: reduce) {

    .task-card__pulse-dot,
    .stat-chip__dot--pulse,
    .tasks-view__spinner {
        animation: none;
    }

    .task-card,
    .btn,
    .detail-expand-enter-active,
    .detail-expand-leave-active {
        transition: none;
    }
}
</style>
