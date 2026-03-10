/**
 * Task-related types aligned with the OMNIA backend API.
 *
 * Every interface here mirrors the JSON shapes returned by
 * `backend/api/routes/tasks.py` so the frontend can consume
 * responses without transformation.
 */

// ---------------------------------------------------------------------------
// Task
// ---------------------------------------------------------------------------

/** Possible trigger types for a task. */
export type TaskTriggerType = 'once_at' | 'interval' | 'manual'

/** Possible task statuses. */
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

/** Task entry returned by the API (matches backend snake_case JSON). */
export interface AgentTask {
  id: string
  prompt: string
  trigger_type: TaskTriggerType
  status: TaskStatus
  run_at: string | null
  interval_seconds: number | null
  next_run_at: string | null
  max_runs: number | null
  run_count: number
  last_run_at: string | null
  result_summary: string | null
  error_message: string | null
  conversation_id: string | null
  created_at: string
  updated_at: string
}

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

/** Real-time task event received from /api/events/ws (snake_case). */
export interface TaskActivityEvent {
  type: 'task_scheduled' | 'task_started' | 'task_completed' | 'task_failed' | 'task_cancelled'
  task_id: string
  status?: TaskStatus
  result_summary?: string
  error_message?: string
  timestamp: string
}

// ---------------------------------------------------------------------------
// REST response helpers
// ---------------------------------------------------------------------------

/** Task list response. */
export interface TaskListResponse {
  tasks: AgentTask[]
  total: number
}

/** Task stats response. */
export interface TaskStatsResponse {
  pending: number
  running: number
  completed: number
  failed: number
  cancelled: number
}

// ---------------------------------------------------------------------------
// Create request
// ---------------------------------------------------------------------------

/** Body for POST /api/tasks. */
export interface TaskCreateRequest {
  prompt: string
  trigger_type: TaskTriggerType
  run_at?: string
  interval_seconds?: number
  max_runs?: number
}
