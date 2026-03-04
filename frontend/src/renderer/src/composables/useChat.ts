/**
 * Composable that wires the WebSocket connection to the Pinia chat store.
 *
 * Usage (typically in a top-level layout or ChatView):
 *
 * ```vue
 * <script setup lang="ts">
 * const { sendMessage, isConnected, connectionStatus } = useChat()
 * </script>
 * ```
 *
 * The composable:
 * - Connects on setup AND disconnects when the calling scope is disposed.
 * - Listens for `token`, `done`, and `error` WS events, forwarding them
 *   into the chat store so the UI stays reactive.
 * - Exposes a `sendMessage` helper that optimistically adds the user
 *   message to the store then sends it over the socket.
 */

import { onScopeDispose, ref, type Ref } from 'vue'

import { wsManager } from '../services/ws'
import { useChatStore } from '../stores/chat'
import type { WsDoneMessage, WsErrorMessage, WsSendPayload, WsTokenMessage } from '../types/chat'

/** Connection status reported by the composable. */
export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

export interface UseChatReturn {
  /** Send a user message (and optionally target an existing conversation). */
  sendMessage: (content: string, conversationId?: string) => void
  /** Reactive flag — `true` while the socket is open. */
  isConnected: Ref<boolean>
  /** Reactive connection status string. */
  connectionStatus: Ref<ConnectionStatus>
}

/**
 * Wire up WebSocket events to the chat store.
 *
 * @returns Reactive helpers for the chat UI.
 */
export function useChat(): UseChatReturn {
  const store = useChatStore()

  const isConnected = ref(false)
  const connectionStatus = ref<ConnectionStatus>('disconnected')

  // -----------------------------------------------------------------------
  // WS event handlers (named so they can be removed in cleanup)
  // -----------------------------------------------------------------------

  const onConnected = (): void => {
    isConnected.value = true
    connectionStatus.value = 'connected'
  }

  const onDisconnected = (): void => {
    isConnected.value = false
    connectionStatus.value = 'disconnected'
  }

  const onError = (): void => {
    connectionStatus.value = 'error'
  }

  const onReconnectFailed = (): void => {
    connectionStatus.value = 'error'
  }

  const onToken = (data: unknown): void => {
    const msg = data as WsTokenMessage
    store.appendToStream(msg.content)
  }

  const onDone = (data: unknown): void => {
    const msg = data as WsDoneMessage
    store.finalizeStream(msg.conversation_id, msg.message_id)
  }

  const onWsError = (data: unknown): void => {
    const msg = data as WsErrorMessage
    console.error('[useChat] Server error:', msg.content)
    store.cancelStream()
  }

  // -----------------------------------------------------------------------
  // Register handlers & connect
  // -----------------------------------------------------------------------

  wsManager.on('connected', onConnected)
  wsManager.on('disconnected', onDisconnected)
  wsManager.on('error', onError)
  wsManager.on('reconnect_failed', onReconnectFailed)
  wsManager.on('token', onToken)
  wsManager.on('done', onDone)
  wsManager.on('error', onWsError) // also catches server-side error frames

  connectionStatus.value = 'connecting'
  wsManager.connect()

  // Sync initial state (connect may have already opened)
  if (wsManager.isConnected) {
    isConnected.value = true
    connectionStatus.value = 'connected'
  }

  // -----------------------------------------------------------------------
  // Cleanup on scope dispose
  // -----------------------------------------------------------------------

  onScopeDispose(() => {
    wsManager.off('connected', onConnected)
    wsManager.off('disconnected', onDisconnected)
    wsManager.off('error', onError)
    wsManager.off('reconnect_failed', onReconnectFailed)
    wsManager.off('token', onToken)
    wsManager.off('done', onDone)
    wsManager.off('error', onWsError)
    wsManager.disconnect()
  })

  // -----------------------------------------------------------------------
  // Public API
  // -----------------------------------------------------------------------

  /**
   * Send a user message via WebSocket.
   *
   * Optimistically adds the message to the store so the UI updates
   * instantly, then dispatches the payload over the socket.
   */
  function sendMessage(content: string, conversationId?: string): void {
    const trimmed = content.trim()
    if (!trimmed) return

    // Optimistic UI update
    store.addUserMessage(trimmed)

    const payload: WsSendPayload = {
      content: trimmed,
      conversation_id: conversationId ?? store.currentConversation?.id
    }

    wsManager.send(payload)
  }

  return {
    sendMessage,
    isConnected,
    connectionStatus
  }
}
