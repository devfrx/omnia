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
  letter-spacing: 0.35em;
  font-weight: 200;
  text-shadow: 0 0 40px rgba(201, 168, 76, 0.15);
}

.subtitle {
  font-size: 0.9rem;
  color: var(--text-secondary);
  opacity: 0.6;
  margin-top: 0.5rem;
}

.start-btn {
  margin-top: 2rem;
  padding: 0.8rem 2rem;
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  text-decoration: none;
  transition: all var(--transition-normal);
}

.start-btn:hover {
  background: var(--accent-dim);
  border-color: var(--accent-border);
  color: var(--accent);
}
</style>
