/**
 * REST API client for the OMNIA backend.
 *
 * Every method is strongly typed against the shapes defined in
 * `types/chat.ts` which mirror the backend JSON responses exactly.
 */

import type {
  ConversationDetail,
  ConversationSummary,
  DeleteConversationResponse,
  RenameConversationResponse
} from '../types/chat'

/** Base URL for all REST calls. */
const BASE_URL = 'http://localhost:8000/api'

/**
 * Generic fetch wrapper with JSON parsing and error handling.
 *
 * @typeParam T - Expected response body type.
 * @param endpoint - Path appended to {@link BASE_URL} (must start with `/`).
 * @param options  - Standard `RequestInit` overrides.
 * @returns Parsed JSON body cast to `T`.
 * @throws {Error} On non-2xx status codes.
 */
async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers
    },
    ...options
  })

  if (!response.ok) {
    const body = await response.text().catch(() => '')
    throw new Error(`API Error ${response.status}: ${response.statusText} — ${body}`)
  }

  return response.json()
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export const api = {
  // -- Chat conversations ---------------------------------------------------

  /** List all conversations (most recent first). */
  getConversations: (): Promise<ConversationSummary[]> =>
    request<ConversationSummary[]>('/chat/conversations'),

  /** Fetch a single conversation with its full message list. */
  getConversation: (id: string): Promise<ConversationDetail> =>
    request<ConversationDetail>(`/chat/conversations/${id}`),

  /** Delete a conversation and all its messages. */
  deleteConversation: (id: string): Promise<DeleteConversationResponse> =>
    request<DeleteConversationResponse>(`/chat/conversations/${id}`, { method: 'DELETE' }),

  /** Rename a conversation. */
  renameConversation: (id: string, title: string): Promise<RenameConversationResponse> =>
    request<RenameConversationResponse>(`/chat/conversations/${id}/title`, {
      method: 'POST',
      body: JSON.stringify({ title })
    }),

  // -- Config ---------------------------------------------------------------

  /** Retrieve the current server configuration. */
  getConfig: (): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>('/config'),

  /** Update the server configuration. */
  updateConfig: (config: Record<string, unknown>): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>('/config', {
      method: 'PUT',
      body: JSON.stringify(config)
    }),

  // -- Plugins --------------------------------------------------------------

  /** List installed plugins. */
  getPlugins: (): Promise<unknown[]> => request<unknown[]>('/plugins'),

  /** Enable or disable a plugin by name. */
  togglePlugin: (name: string, enabled: boolean): Promise<unknown> =>
    request<unknown>(`/plugins/${name}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled })
    })
}
