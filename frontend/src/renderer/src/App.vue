<script setup lang="ts">
// O.M.N.I.A. — Root App Component
import TitleBar from './components/TitleBar.vue'
import AppSidebar from './components/sidebar/AppSidebar.vue'
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
:root {
  --bg-primary: #0d1117;
  --bg-secondary: #161b22;
  --text-primary: #e6edf3;
  --text-secondary: #8b949e;
  --accent: #58a6ff;
  --border: rgba(255, 255, 255, 0.1);
  --titlebar-height: 34px;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  overflow: hidden;
}

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
