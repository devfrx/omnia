/**
 * Composable for the persistent events WebSocket connection.
 *
 * Connects to `/api/events/ws` on setup and dispatches incoming
 * task events to the tasks Pinia store. Handles reconnection
 * with exponential back-off.
 */

import { onScopeDispose, ref } from 'vue'
import { useTasksStore } from '../stores/tasks'
import { useCalendarStore } from '../stores/calendar'
import { BACKEND_HOST } from '../services/api'
import type { TaskActivityEvent } from '../types/tasks'

const WS_URL = `${BACKEND_HOST.replace(/^http/, 'ws')}/api/events/ws`

export function useEventsWebSocket() {
  const isConnected = ref(false)
  const tasksStore = useTasksStore()
  const calendarStore = useCalendarStore()

  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectAttempts = 0
  let intentionalClose = false
  let pingInterval: ReturnType<typeof setInterval> | null = null

  function connect(): void {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    intentionalClose = false
    ws = new WebSocket(WS_URL)

    ws.onopen = (): void => {
      console.log('[OMNIA Events WS] Connected')
      isConnected.value = true
      reconnectAttempts = 0

      // Send ping every 30s to keep connection alive
      pingInterval = setInterval(() => {
        if (ws?.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, 30_000)
    }

    ws.onmessage = (event: MessageEvent): void => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'pong' || data.type === 'heartbeat') {
          return // Keep-alive, ignore
        }

        // Forward task events to the store
        if (
          data.type === 'task_scheduled' ||
          data.type === 'task_started' ||
          data.type === 'task_completed' ||
          data.type === 'task_failed' ||
          data.type === 'task_cancelled'
        ) {
          const taskEvent: TaskActivityEvent = {
            type: data.type,
            task_id: data.task_id,
            status: data.status,
            result_summary: data.result_summary,
            error_message: data.error_message,
            timestamp: new Date().toISOString(),
          }
          tasksStore.onTaskEvent(taskEvent)
        }

        // Forward calendar change events to the store
        if (data.type === 'calendar_changed') {
          void calendarStore.refresh()
        }
      } catch {
        console.warn('[OMNIA Events WS] Failed to parse message')
      }
    }

    ws.onclose = (): void => {
      isConnected.value = false
      clearPing()
      if (!intentionalClose) {
        scheduleReconnect()
      }
    }

    ws.onerror = (): void => {
      isConnected.value = false
    }
  }

  function disconnect(): void {
    intentionalClose = true
    clearPing()
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.close()
      ws = null
    }
    isConnected.value = false
  }

  function clearPing(): void {
    if (pingInterval) {
      clearInterval(pingInterval)
      pingInterval = null
    }
  }

  function scheduleReconnect(): void {
    if (reconnectAttempts >= 10) return
    const delay = Math.min(1000 * 2 ** reconnectAttempts, 30_000)
    reconnectAttempts += 1
    reconnectTimer = setTimeout(() => {
      connect()
    }, delay)
  }

  // Auto-connect and cleanup
  connect()
  onScopeDispose(() => disconnect())

  return { isConnected, connect, disconnect }
}
