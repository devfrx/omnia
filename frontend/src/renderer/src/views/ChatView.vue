<template>
  <div class="chat-view">
    <div class="messages" ref="messagesContainer">
      <!-- Messages will render here -->
      <p v-if="chatStore.messages.length === 0" class="empty-state">
        Scrivi qualcosa per iniziare a parlare con OMNIA...
      </p>
    </div>
    <div class="input-area">
      <textarea
        v-model="inputText"
        @keydown.enter.exact.prevent="sendMessage"
        placeholder="Scrivi un messaggio..."
        rows="1"
      />
      <button @click="sendMessage" :disabled="!inputText.trim() || chatStore.isStreaming">
        Invia
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()
const inputText = ref('')

function sendMessage() {
  const text = inputText.value.trim()
  if (!text || chatStore.isStreaming) return

  chatStore.addMessage({
    id: crypto.randomUUID(),
    role: 'user',
    content: text,
    timestamp: Date.now()
  })

  inputText.value = ''
  // TODO: send to backend via WebSocket
}
</script>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.empty-state {
  text-align: center;
  opacity: 0.5;
  margin-top: 40vh;
}

.input-area {
  display: flex;
  padding: 1rem;
  gap: 0.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

textarea {
  flex: 1;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  padding: 0.6rem 1rem;
  color: #e0e0e0;
  resize: none;
  font-family: inherit;
  font-size: 0.9rem;
}

button {
  padding: 0.6rem 1.5rem;
  background: rgba(100, 180, 255, 0.2);
  border: 1px solid rgba(100, 180, 255, 0.3);
  border-radius: 8px;
  color: #e0e0e0;
  cursor: pointer;
  transition: all 0.2s;
}

button:hover:not(:disabled) {
  background: rgba(100, 180, 255, 0.3);
}

button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
