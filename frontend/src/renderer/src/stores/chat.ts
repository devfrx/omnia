/**
 * Pinia store managing chat state for the OMNIA assistant.
 *
 * Responsibilities:
 * - Maintain the sidebar conversation list (`conversations`)
 * - Track the active conversation (`currentConversation`)
 * - Accumulate streaming tokens from the WebSocket
 * - Dispatch REST calls via `services/api.ts`
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api } from '../services/api'
import type {
  ChatMessage,
  ConversationDetail,
  ConversationSummary
} from '../types/chat'

export const useChatStore = defineStore('chat', () => {
  // -----------------------------------------------------------------------
  // State
  // -----------------------------------------------------------------------

  /** All conversations for the sidebar (summary only, no messages). */
  const conversations = ref<ConversationSummary[]>([])

  /** The currently open conversation (includes messages). */
  const currentConversation = ref<ConversationDetail | null>(null)

  /** Whether the LLM is currently streaming a response. */
  const isStreaming = ref(false)

  /** Tokens accumulated so far for the in-progress assistant response. */
  const currentStreamContent = ref('')

  // -----------------------------------------------------------------------
  // Computed
  // -----------------------------------------------------------------------

  /** Messages of the active conversation (empty array when none). */
  const messages = computed<ChatMessage[]>(
    () => currentConversation.value?.messages ?? []
  )

  // -----------------------------------------------------------------------
  // REST actions
  // -----------------------------------------------------------------------

  /** Fetch the conversation list from the backend. */
  async function loadConversations(): Promise<void> {
    conversations.value = await api.getConversations()
  }

  /** Load a full conversation (with messages) and set it as active. */
  async function loadConversation(id: string): Promise<void> {
    currentConversation.value = await api.getConversation(id)
  }

  /**
   * Start a fresh conversation locally.
   * The backend will persist it when the first message is sent via WS.
   */
  function createConversation(): void {
    currentConversation.value = {
      id: crypto.randomUUID(),
      title: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      messages: []
    }
  }

  /** Delete a conversation on the backend and remove it from local state. */
  async function deleteConversation(id: string): Promise<void> {
    await api.deleteConversation(id)
    conversations.value = conversations.value.filter((c) => c.id !== id)
    if (currentConversation.value?.id === id) {
      currentConversation.value = null
    }
  }

  /** Rename a conversation on the backend and update local state. */
  async function renameConversation(id: string, title: string): Promise<void> {
    const result = await api.renameConversation(id, title)

    // Update sidebar entry
    const entry = conversations.value.find((c) => c.id === id)
    if (entry) {
      entry.title = result.title
      entry.updated_at = result.updated_at
    }

    // Update active conversation if it matches
    if (currentConversation.value?.id === id) {
      currentConversation.value.title = result.title
      currentConversation.value.updated_at = result.updated_at
    }
  }

  // -----------------------------------------------------------------------
  // Message / streaming actions
  // -----------------------------------------------------------------------

  /** Append a user message to the active conversation and start streaming. */
  function addUserMessage(content: string): void {
    if (!currentConversation.value) return

    const msg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      tool_calls: null,
      tool_call_id: null,
      created_at: new Date().toISOString()
    }

    currentConversation.value.messages.push(msg)
    isStreaming.value = true
    currentStreamContent.value = ''
  }

  /** Append a streamed token to the in-progress assistant response. */
  function appendToStream(token: string): void {
    currentStreamContent.value += token
  }

  /**
   * Finalise the streamed response: create the assistant message,
   * reset streaming state, and refresh the sidebar.
   */
  function finalizeStream(conversationId: string, messageId: string): void {
    if (!currentConversation.value) return

    // Ensure the active conversation id matches the one from the server
    if (currentConversation.value.id !== conversationId) {
      currentConversation.value.id = conversationId
    }

    const assistantMsg: ChatMessage = {
      id: messageId,
      role: 'assistant',
      content: currentStreamContent.value,
      tool_calls: null,
      tool_call_id: null,
      created_at: new Date().toISOString()
    }

    currentConversation.value.messages.push(assistantMsg)
    currentStreamContent.value = ''
    isStreaming.value = false

    // Refresh sidebar list asynchronously (fire-and-forget)
    loadConversations().catch(console.error)
  }

  /** Clear streaming state (e.g. on error). */
  function cancelStream(): void {
    currentStreamContent.value = ''
    isStreaming.value = false
  }

  // -----------------------------------------------------------------------
  // Public surface
  // -----------------------------------------------------------------------

  return {
    // state
    conversations,
    currentConversation,
    isStreaming,
    currentStreamContent,

    // computed
    messages,

    // REST actions
    loadConversations,
    loadConversation,
    createConversation,
    deleteConversation,
    renameConversation,

    // message / streaming actions
    addUserMessage,
    appendToStream,
    finalizeStream,
    cancelStream
  }
})
