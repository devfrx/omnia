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

import { api, resolveBackendUrl } from '../services/api'
import type {
  ChatMessage,
  ConversationDetail,
  ConversationSummary,
  FileAttachment
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

  /** Thinking tokens accumulated for the in-progress assistant response. */
  const currentThinkingContent = ref('')

  /** Files selected by the user but not yet uploaded. */
  const pendingAttachments = ref<File[]>([])

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
    const remote = await api.getConversations()

    // Merge: keep any locally-created conversations that the backend
    // does not know about yet (created but no message sent).
    const remoteIds = new Set(remote.map((c) => c.id))
    const localOnly = conversations.value.filter(
      (c) => !remoteIds.has(c.id) && c.message_count === 0
    )
    conversations.value = [...localOnly, ...remote]
  }

  /** Load a full conversation (with messages) and set it as active. */
  async function loadConversation(id: string): Promise<void> {
    // If the conversation only exists locally (created but no message sent yet),
    // skip the API call — the backend doesn't know about it and would return 404.
    const summary = conversations.value.find((c) => c.id === id)
    if (summary && summary.message_count === 0) {
      currentConversation.value = {
        id: summary.id,
        title: summary.title,
        created_at: summary.created_at,
        updated_at: summary.updated_at,
        messages: []
      }
      return
    }

    try {
      const detail = await api.getConversation(id)
      // Resolve relative attachment URLs to absolute backend URLs.
      for (const msg of detail.messages) {
        if (msg.attachments) {
          for (const att of msg.attachments) {
            att.url = resolveBackendUrl(att.url)
          }
        }
      }
      currentConversation.value = detail
    } catch (err) {
      // Fallback: if the backend returns 404 (conversation not persisted yet),
      // build a local ConversationDetail so the UI doesn't break.
      if (summary) {
        currentConversation.value = {
          id: summary.id,
          title: summary.title,
          created_at: summary.created_at,
          updated_at: summary.updated_at,
          messages: []
        }
      } else {
        // No local record either — propagate the error.
        throw err
      }
    }
  }

  /**
   * Start a fresh conversation locally.
   * The backend will persist it when the first message is sent via WS.
   */
  function createConversation(): void {
    const now = new Date().toISOString()
    const newId = crypto.randomUUID()

    currentConversation.value = {
      id: newId,
      title: null,
      created_at: now,
      updated_at: now,
      messages: []
    }

    // Add a summary entry so the sidebar shows the new conversation immediately.
    conversations.value.unshift({
      id: newId,
      title: null,
      created_at: now,
      updated_at: now,
      message_count: 0
    })
  }

  /** Delete a conversation on the backend and remove it from local state. */
  async function deleteConversation(id: string): Promise<void> {
    // Only call the backend if the conversation was persisted (has messages).
    const summary = conversations.value.find((c) => c.id === id)
    if (summary && summary.message_count > 0) {
      await api.deleteConversation(id)
    }
    conversations.value = conversations.value.filter((c) => c.id !== id)
    if (currentConversation.value?.id === id) {
      currentConversation.value = null
    }
  }

  /** Rename a conversation on the backend and update local state. */
  async function renameConversation(id: string, title: string): Promise<void> {
    // Only call the backend if the conversation was persisted (has messages).
    const summary = conversations.value.find((c) => c.id === id)
    if (summary && summary.message_count > 0) {
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
    } else {
      // Local-only conversation: update state directly.
      if (summary) {
        summary.title = title
      }
      if (currentConversation.value?.id === id) {
        currentConversation.value.title = title
      }
    }
  }

  // -----------------------------------------------------------------------
  // Message / streaming actions
  // -----------------------------------------------------------------------

  /** Append a user message to the active conversation and start streaming. */
  function addUserMessage(content: string, attachments?: FileAttachment[]): void {
    if (!currentConversation.value) return

    const msg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      tool_calls: null,
      tool_call_id: null,
      created_at: new Date().toISOString(),
      attachments: attachments?.length ? attachments : undefined
    }

    currentConversation.value.messages.push(msg)
    isStreaming.value = true
    currentStreamContent.value = ''
    currentThinkingContent.value = ''
  }

  /** Append a streamed token to the in-progress assistant response. */
  function appendToStream(token: string): void {
    currentStreamContent.value += token
  }

  /** Append a thinking token to the in-progress thinking content. */
  function appendToThinking(token: string): void {
    currentThinkingContent.value += token
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
      created_at: new Date().toISOString(),
      thinking_content: currentThinkingContent.value || null
    }

    currentConversation.value.messages.push(assistantMsg)
    currentStreamContent.value = ''
    currentThinkingContent.value = ''
    isStreaming.value = false

    // Refresh sidebar list asynchronously (fire-and-forget)
    loadConversations().catch(console.error)
  }

  /** Clear streaming state (e.g. on error). */
  function cancelStream(): void {
    currentStreamContent.value = ''
    currentThinkingContent.value = ''
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
    currentThinkingContent,
    pendingAttachments,

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
    appendToThinking,
    finalizeStream,
    cancelStream
  }
})
