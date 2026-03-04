<template>
  <div class="home-view">
    <h1>O.M.N.I.A.</h1>
    <p class="subtitle">Orchestrated Modular Network for Intelligent Automation</p>
    <router-link to="/chat" class="start-btn">Avvia Chat</router-link>
  </div>
</template>

<script setup lang="ts">
// HomeView — landing page placeholder
</script>

<style scoped>
.home-view {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-primary);
}

h1 {
  font-size: 3rem;
  letter-spacing: 0.3em;
  font-weight: 200;
}

.subtitle {
  font-size: 0.9rem;
  opacity: 0.6;
  margin-top: 0.5rem;
}

.start-btn {
  margin-top: 2rem;
  padding: 0.8rem 2rem;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: #e0e0e0;
  text-decoration: none;
  transition: all 0.2s;
}

.start-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.4);
}
</style>
