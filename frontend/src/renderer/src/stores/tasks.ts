/**
 * Pinia store for OMNIA autonomous task management.
 *
 * Provides CRUD operations and real-time status updates for
 * background tasks managed by the TaskScheduler.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../services/api'
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
      tasks.value.unshift(task)
      total.value += 1
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
        tasks.value[idx].status = 'cancelled'
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    }
  }

  /** Trigger a manual task run. */
  async function triggerManual(id: string): Promise<void> {
    error.value = null
    try {
      const updated = await api.triggerTaskRun(id)
      const idx = tasks.value.findIndex((t) => t.id === id)
      if (idx !== -1) {
        tasks.value[idx] = updated
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    }
  }

  /** Handle an incoming real-time task event from /ws/events. */
  function onTaskEvent(event: TaskActivityEvent): void {
    recentActivity.value.unshift(event)
    if (recentActivity.value.length > 50) {
      recentActivity.value = recentActivity.value.slice(0, 50)
    }

    // Update task status in local state
    const idx = tasks.value.findIndex((t) => t.id === event.task_id)
    if (idx !== -1 && event.status) {
      tasks.value[idx].status = event.status
      if (event.result_summary) {
        tasks.value[idx].result_summary = event.result_summary
      }
      if (event.error_message) {
        tasks.value[idx].error_message = event.error_message
      }
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
