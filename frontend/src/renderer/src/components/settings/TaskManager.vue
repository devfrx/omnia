<script setup lang="ts">
/**
 * Task Manager — view and manage autonomous background tasks.
 *
 * Displayed inside the Settings panel alongside MemoryManager,
 * PluginManagement, etc.
 */
import { computed, onMounted, ref } from 'vue'
import { useTasksStore } from '../../stores/tasks'
import { useModal } from '../../composables/useModal'
import type { TaskStatus } from '../../types/tasks'

const store = useTasksStore()
const { confirm: modalConfirm } = useModal()
const filterStatus = ref<TaskStatus | ''>('')
const expandedTask = ref<string | null>(null)

onMounted(() => {
    store.loadTasks()
    store.loadStats()
})

const filteredTasks = computed(() => {
    if (!filterStatus.value) return store.tasks
    return store.tasks.filter((t) => t.status === filterStatus.value)
})

function toggleExpand(id: string): void {
    expandedTask.value = expandedTask.value === id ? null : id
}

async function handleCancel(id: string): Promise<void> {
    const confirmed = await modalConfirm({
        title: 'Cancella task',
        message: 'Cancellare questo task? L\'azione è irreversibile.',
        type: 'danger',
        confirmText: 'Cancella',
    })
    if (confirmed) {
        await store.cancelTask(id)
    }
}

async function handleTrigger(id: string): Promise<void> {
    await store.triggerManual(id)
    await store.loadTasks()
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
    return new Date(iso).toLocaleString()
}

function triggerLabel(type: string): string {
    const map: Record<string, string> = {
        once_at: 'Una Tantum',
        interval: 'Ricorrente',
        daily_at: 'Giornaliero',
        manual: 'Manuale',
    }
    return map[type] || type
}
</script>

<template>
    <div class="task-manager">
        <div class="task-manager__header">
            <h2>Task Autonomi</h2>
            <div v-if="store.stats" class="task-manager__stats">
                <span class="stat stat--pending">{{ store.stats.pending }} in attesa</span>
                <span class="stat stat--running">{{ store.stats.running }} in esecuzione</span>
                <span class="stat stat--completed">{{ store.stats.completed }} completati</span>
                <span class="stat stat--failed">{{ store.stats.failed }} falliti</span>
            </div>
        </div>

        <!-- Filter -->
        <div class="task-manager__filters">
            <select v-model="filterStatus" class="filter-select" @change="store.loadTasks(filterStatus || undefined)">
                <option value="">Tutti</option>
                <option value="pending">In attesa</option>
                <option value="running">In esecuzione</option>
                <option value="completed">Completati</option>
                <option value="failed">Falliti</option>
                <option value="cancelled">Cancellati</option>
            </select>
        </div>

        <!-- Loading -->
        <div v-if="store.loading" class="task-manager__loading">
            Caricamento...
        </div>

        <!-- Empty -->
        <div v-else-if="filteredTasks.length === 0" class="task-manager__empty">
            Nessun task trovato.
        </div>

        <!-- Task list -->
        <div v-else class="task-manager__list">
            <div v-for="task in filteredTasks" :key="task.id" class="task-card" @click="toggleExpand(task.id)">
                <div class="task-card__header">
                    <span :class="['badge', statusBadgeClass(task.status)]">
                        {{ task.status }}
                    </span>
                    <span class="task-card__trigger">{{ triggerLabel(task.trigger_type) }}</span>
                    <span class="task-card__date">{{ formatDate(task.created_at) }}</span>
                </div>

                <p class="task-card__prompt">{{ task.prompt }}</p>

                <div v-if="expandedTask === task.id" class="task-card__details">
                    <div class="detail-row">
                        <span class="detail-label">ID:</span>
                        <span class="detail-value">{{ task.id }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Esecuzioni:</span>
                        <span class="detail-value">{{ task.run_count }}{{ task.max_runs ? ` / ${task.max_runs}` : ''
                            }}</span>
                    </div>
                    <div v-if="task.next_run_at" class="detail-row">
                        <span class="detail-label">Prossima esecuzione:</span>
                        <span class="detail-value">{{ formatDate(task.next_run_at) }}</span>
                    </div>
                    <div v-if="task.interval_seconds" class="detail-row">
                        <span class="detail-label">Intervallo:</span>
                        <span class="detail-value">{{ task.interval_seconds }}s</span>
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
                        <button v-if="task.status === 'pending' || task.status === 'running'" class="btn btn--danger"
                            @click.stop="handleCancel(task.id)">
                            Cancella
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Recent Activity -->
        <div v-if="store.recentActivity.length > 0" class="task-manager__activity">
            <h3>Attività Recente</h3>
            <div v-for="(event, idx) in store.recentActivity.slice(0, 10)" :key="idx" class="activity-item">
                <span class="activity-type">{{ event.type }}</span>
                <span class="activity-time">{{ formatDate(event.timestamp) }}</span>
            </div>
        </div>

        <!-- Error -->
        <div v-if="store.error" class="task-manager__error">
            {{ store.error }}
        </div>
    </div>
</template>

<style scoped>
.task-manager {
    padding: 16px;
    color: var(--text-primary, #e0e0e0);
}

.task-manager__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
}

.task-manager__header h2 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 600;
}

.task-manager__stats {
    display: flex;
    gap: 12px;
    font-size: 0.8rem;
}

.stat {
    opacity: 0.7;
}

.stat--running {
    color: #4fc3f7;
}

.stat--completed {
    color: #81c784;
}

.stat--failed {
    color: #e57373;
}

.task-manager__filters {
    margin-bottom: 12px;
}

.filter-select {
    background: var(--bg-secondary, #2a2a2e);
    color: var(--text-primary, #e0e0e0);
    border: 1px solid var(--border-color, #444);
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 0.85rem;
}

.task-manager__loading,
.task-manager__empty {
    text-align: center;
    padding: 24px;
    opacity: 0.6;
}

.task-card {
    background: var(--bg-secondary, #2a2a2e);
    border: 1px solid var(--border-color, #3a3a3e);
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 8px;
    cursor: pointer;
    transition: border-color 0.2s;
}

.task-card:hover {
    border-color: var(--accent-color, #6366f1);
}

.task-card__header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
}

.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
}

.badge--pending {
    background: #37474f;
    color: #b0bec5;
}

.badge--running {
    background: #0d47a1;
    color: #90caf9;
    animation: pulse 1.5s infinite;
}

.badge--completed {
    background: #1b5e20;
    color: #a5d6a7;
}

.badge--failed {
    background: #b71c1c;
    color: #ef9a9a;
}

.badge--cancelled {
    background: #424242;
    color: #9e9e9e;
}

@keyframes pulse {

    0%,
    100% {
        opacity: 1;
    }

    50% {
        opacity: 0.6;
    }
}

.task-card__trigger {
    font-size: 0.8rem;
    opacity: 0.6;
}

.task-card__date {
    margin-left: auto;
    font-size: 0.75rem;
    opacity: 0.5;
}

.task-card__prompt {
    margin: 0;
    font-size: 0.9rem;
    line-height: 1.4;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.task-card__details {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--border-color, #3a3a3e);
}

.detail-row {
    display: flex;
    gap: 8px;
    margin-bottom: 4px;
    font-size: 0.85rem;
}

.detail-row--full {
    flex-direction: column;
}

.detail-label {
    opacity: 0.6;
    min-width: 140px;
}

.detail-value--result {
    background: var(--bg-tertiary, #1e1e22);
    padding: 8px;
    border-radius: 4px;
    font-size: 0.85rem;
    white-space: pre-wrap;
    margin: 4px 0 0;
}

.detail-value--error {
    color: #e57373;
    background: rgba(183, 28, 28, 0.1);
    padding: 8px;
    border-radius: 4px;
    font-size: 0.85rem;
    margin: 4px 0 0;
}

.task-card__actions {
    display: flex;
    gap: 8px;
    margin-top: 12px;
}

.btn {
    padding: 6px 16px;
    border: none;
    border-radius: 6px;
    font-size: 0.85rem;
    cursor: pointer;
    transition: opacity 0.2s;
}

.btn:hover {
    opacity: 0.85;
}

.btn--primary {
    background: var(--accent-color, #6366f1);
    color: white;
}

.btn--danger {
    background: #c62828;
    color: white;
}

.task-manager__activity {
    margin-top: 24px;
}

.task-manager__activity h3 {
    font-size: 1rem;
    margin-bottom: 8px;
}

.activity-item {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
    font-size: 0.8rem;
    opacity: 0.7;
    border-bottom: 1px solid var(--border-color, #3a3a3e);
}

.task-manager__error {
    margin-top: 12px;
    padding: 8px 12px;
    background: rgba(183, 28, 28, 0.15);
    border: 1px solid rgba(183, 28, 28, 0.3);
    border-radius: 6px;
    color: #e57373;
    font-size: 0.85rem;
}
</style>
