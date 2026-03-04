import { defineStore } from 'pinia'
import { ref } from 'vue'

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
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  const currentStreamContent = ref('')

  function addMessage(message: ChatMessage) {
    messages.value.push(message)
  }

  function clearMessages() {
    messages.value = []
  }

  function appendToStream(token: string) {
    currentStreamContent.value += token
  }

  function finalizeStream() {
    if (currentStreamContent.value) {
      addMessage({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: currentStreamContent.value,
        timestamp: Date.now()
      })
      currentStreamContent.value = ''
    }
    isStreaming.value = false
  }

  return {
    messages,
    isStreaming,
    currentStreamContent,
    addMessage,
    clearMessages,
    appendToStream,
    finalizeStream
  }
})
