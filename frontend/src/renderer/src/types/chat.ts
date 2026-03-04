/** Chat-related types */

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  toolCalls?: ToolCall[]
}

export interface ToolCall {
  name: string
  args: Record<string, unknown>
  result?: string
  status: 'pending' | 'running' | 'success' | 'error'
}

export interface Conversation {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: number
  updatedAt: number
}

/** WebSocket message types */
export interface WsMessage {
  type: 'token' | 'done' | 'error' | 'tool_call' | 'tool_result' | 'status'
  content?: string
  toolCall?: ToolCall
  error?: string
}
