/**
 * Pinia store for OMNIA autonomous task management.
 *
 * Provides CRUD operations and real-time status updates for
 * background tasks managed by the TaskScheduler.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../services/api'
import { useToast } from '../composables/useToast'
import type {
  AgentTask,
  TaskActivityEvent,
  TaskCreateRequest,
  TaskStatsResponse,
  TaskStatus
} from '../types/tasks'

export const useTasksStore = defineStore('tasks', () => {
  // -----------------------------------------------------------------------
  // State
  // -----------------------------------------------------------------------

  const tasks = ref<AgentTask[]>([])
  const total = ref(0)
  const stats = ref<TaskStatsResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const recentActivity = ref<TaskActivityEvent[]>([])
  // -----------------------------------------------------------------------
  // Actions
  // -----------------------------------------------------------------------

  /** Fetch tasks with optional filters. */
  async function loadTasks(
    status?: TaskStatus,
    triggerType?: string,
    limit = 20,
    offset = 0,
  ): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams()
      if (status) params.set('status', status)
      if (triggerType) params.set('trigger_type', triggerType)
      params.set('limit', String(limit))
      params.set('offset', String(offset))

      const data = await api.getTasks(params)
      tasks.value = data.tasks
      total.value = data.total
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      loading.value = false
    }
  }

  /** Fetch task statistics. */
  async function loadStats(): Promise<void> {
    try {
      stats.value = await api.getTaskStats()
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    }
  }

  /** Create a new task via REST. */
  async function createTask(req: TaskCreateRequest): Promise<AgentTask | null> {
    error.value = null
    try {
      const task = await api.createTaskEntry(req)
      tasks.value = [task, ...tasks.value]
      total.value += 1
      void loadStats()
      return task
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      return null
    }
  }

  /** Cancel a task. */
  async function cancelTask(id: string): Promise<void> {
    error.value = null
    try {
      await api.cancelTaskEntry(id)
      const idx = tasks.value.findIndex((t) => t.id === id)
      if (idx !== -1) {
        tasks.value = tasks.value.map((t, i) =>
          i === idx ? { ...t, status: 'cancelled' as const } : t
        )
      }
      void loadStats()
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    }
  }

  /** Trigger a manual task run. */
  async function triggerManual(id: string): Promise<void> {
    error.value = null
    try {
      const updated = await api.triggerTaskRun(id)
      tasks.value = tasks.value.map((t) => (t.id === id ? updated : t))
      void loadStats()
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    }
  }

  /** Handle an incoming real-time task event from /ws/events. */
  function onTaskEvent(event: TaskActivityEvent): void {
    recentActivity.value = [event, ...recentActivity.value].slice(0, 50)

    // Update task status in local state
    const idx = tasks.value.findIndex((t) => t.id === event.task_id)
    if (idx !== -1 && event.status) {
      tasks.value = tasks.value.map((t, i) => {
        if (i !== idx) return t
        return {
          ...t,
          status: event.status!,
          ...(event.result_summary ? { result_summary: event.result_summary } : {}),
          ...(event.error_message ? { error_message: event.error_message } : {}),
        }
      })
    } else if (idx === -1) {
      // New task not in local array — re-fetch from server
      void loadTasks()
    }

    // Always refresh stats to keep counts in sync
    void loadStats()

    // Show global toast notification for key events.
    const toast = useToast()
    if (event.type === 'task_started') {
      toast.info('Task in esecuzione…')
    } else if (event.type === 'task_completed') {
      const msg = event.result_summary
        ? `Task completato: ${event.result_summary.slice(0, 100)}`
        : 'Task completato'
      toast.success(msg)
    } else if (event.type === 'task_failed') {
      const msg = event.error_message
        ? `Task fallito: ${event.error_message.slice(0, 100)}`
        : 'Task fallito'
      toast.error(msg)
    }
  }

  return {
    tasks,
    total,
    stats,
    loading,
    error,
    recentActivity,
    loadTasks,
    loadStats,
    createTask,
    cancelTask,
    triggerManual,
    onTaskEvent,
  }
})
