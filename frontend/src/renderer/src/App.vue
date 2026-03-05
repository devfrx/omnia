<script setup lang="ts">
// O.M.N.I.A. — Root App Component
import { provide } from 'vue'

import TitleBar from './components/TitleBar.vue'
import AppSidebar from './components/sidebar/AppSidebar.vue'
import { useChat, ChatApiKey } from './composables/useChat'

// Initialise the WebSocket connection at the app level so it survives
// route changes (e.g. navigating to Settings while streaming).
const chatApi = useChat()
provide(ChatApiKey, chatApi)
</script>

<template>
  <div id="omnia-app">
    <TitleBar />
    <div class="app-body">
      <AppSidebar />
      <main class="app-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style>
/* Theme tokens & global reset are loaded via main.css → styles/theme.css */

#omnia-app {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.app-content {
  flex: 1;
  overflow: hidden;
}
</style>
