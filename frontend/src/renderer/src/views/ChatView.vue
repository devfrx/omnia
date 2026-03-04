<script setup lang="ts">
/**
 * ChatView.vue — Full chat view with message history, streaming
 * indicator, and an input area.
 *
 * Auto-scrolls on new messages.  Creates a blank conversation on
 * mount when none is active.
 */
import { nextTick, onMounted, ref, watch } from 'vue'

import ChatInput from '../components/chat/ChatInput.vue'
import MessageBubble from '../components/chat/MessageBubble.vue'
import StreamingIndicator from '../components/chat/StreamingIndicator.vue'
import { useChat } from '../composables/useChat'
import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()
const { sendMessage: send, isConnected } = useChat()

/** Template ref for the scrollable message container. */
const messagesContainer = ref<HTMLElement | null>(null)

/** Scroll the message container to the bottom. */
function scrollToBottom(): void {
  nextTick(() => {
    const el = messagesContainer.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

/** Handle a send event from the ChatInput component. */
function handleSend(content: string): void {
  send(content)
  scrollToBottom()
}

// Auto-scroll whenever the message list or streaming content changes.
watch(
  () => [chatStore.messages.length, chatStore.currentStreamContent],
  () => scrollToBottom()
)

// On mount: ensure a conversation exists so the user can start chatting.
onMounted(() => {
  if (!chatStore.currentConversation) {
    chatStore.createConversation()
  }
  scrollToBottom()
})
</script>

<template>
  <div class="chat-view">
    <!-- Messages area -->
    <div ref="messagesContainer" class="chat-view__messages">
      <!-- Empty state -->
      <div v-if="chatStore.messages.length === 0 && !chatStore.isStreaming" class="chat-view__empty">
        <div class="chat-view__empty-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 6v6l4 2" />
          </svg>
        </div>
        <p class="chat-view__empty-title">O.M.N.I.A.</p>
        <p class="chat-view__empty-sub">Scrivi qualcosa per iniziare a parlare con il tuo assistente.</p>
      </div>

      <!-- Message list -->
      <MessageBubble
        v-for="msg in chatStore.messages"
        :key="msg.id"
        :message="msg"
      />

      <!-- Streaming response -->
      <StreamingIndicator
        v-if="chatStore.isStreaming"
        :content="chatStore.currentStreamContent"
      />
    </div>

    <!-- Input -->
    <ChatInput
      :disabled="chatStore.isStreaming"
      :is-connected="isConnected"
      @send="handleSend"
    />
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* ----------------------------------------------- Messages area */
.chat-view__messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  scroll-behavior: smooth;
}

/* Custom dark scrollbar */
.chat-view__messages::-webkit-scrollbar {
  width: 6px;
}

.chat-view__messages::-webkit-scrollbar-track {
  background: transparent;
}

.chat-view__messages::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

.chat-view__messages::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.18);
}

/* ----------------------------------------------- Empty state */
.chat-view__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  opacity: 0.45;
  user-select: none;
}

.chat-view__empty-icon {
  color: var(--accent);
  opacity: 0.6;
}

.chat-view__empty-title {
  font-size: 1.6rem;
  font-weight: 200;
  letter-spacing: 0.2em;
  color: var(--text-primary);
}

.chat-view__empty-sub {
  font-size: 0.85rem;
  color: var(--text-secondary);
}
</style>
