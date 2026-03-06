<template>
  <div class="settings-view">
    <h2 class="settings-view__title">Impostazioni</h2>
    <div class="settings-view__content">
      <ModelManager />

      <!-- LLM Parameters -->
      <section class="settings-section">
        <h3 class="settings-section__title">Parametri LLM</h3>
        <div class="settings-section__grid">
          <label class="settings-field">
            <span class="settings-field__label">Temperatura</span>
            <input v-model.number="settingsStore.settings.llm.temperature" type="number" class="settings-field__input"
              min="0" max="2" step="0.1" />
          </label>
          <label class="settings-field">
            <span class="settings-field__label">Max Tokens</span>
            <input v-model.number="settingsStore.settings.llm.maxTokens" type="number" class="settings-field__input"
              min="256" max="131072" step="256" />
          </label>
        </div>
      </section>

      <!-- STT Settings -->
      <section class="settings-section">
        <h3 class="settings-section__title">Speech-to-Text</h3>
        <div class="settings-section__grid">
          <label class="settings-field">
            <span class="settings-field__label">Lingua</span>
            <input v-model="settingsStore.settings.stt.language" type="text" class="settings-field__input" />
          </label>
          <label class="settings-field">
            <span class="settings-field__label">Modello</span>
            <input v-model="settingsStore.settings.stt.model" type="text" class="settings-field__input" />
          </label>
        </div>
      </section>

      <!-- TTS Settings -->
      <section class="settings-section">
        <h3 class="settings-section__title">Text-to-Speech</h3>
        <div class="settings-section__grid">
          <label class="settings-field">
            <span class="settings-field__label">Engine</span>
            <input v-model="settingsStore.settings.tts.engine" type="text" class="settings-field__input" />
          </label>
          <label class="settings-field">
            <span class="settings-field__label">Voce</span>
            <input v-model="settingsStore.settings.tts.voice" type="text" class="settings-field__input" />
          </label>
        </div>
      </section>

      <!-- UI Settings -->
      <section class="settings-section">
        <h3 class="settings-section__title">Interfaccia</h3>
        <div class="settings-section__grid">
          <label class="settings-field">
            <span class="settings-field__label">Tema</span>
            <select v-model="settingsStore.settings.ui.theme" class="settings-field__input">
              <option value="dark">Scuro</option>
              <option value="light">Chiaro</option>
            </select>
          </label>
          <label class="settings-field">
            <span class="settings-field__label">Lingua</span>
            <input v-model="settingsStore.settings.ui.language" type="text" class="settings-field__input" />
          </label>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import ModelManager from '../components/settings/ModelManager.vue'
import { useSettingsStore } from '../stores/settings'

const settingsStore = useSettingsStore()
</script>

<style scoped>
.settings-view {
  padding: 2rem;
  color: var(--text-primary);
  max-width: 900px;
  margin: 0 auto;
  height: 100%;
  overflow-y: auto;
}

.settings-view::-webkit-scrollbar {
  width: 4px;
}

.settings-view::-webkit-scrollbar-track {
  background: transparent;
}

.settings-view::-webkit-scrollbar-thumb {
  background: var(--border-hover);
  border-radius: 2px;
}

.settings-view::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

.settings-view__title {
  margin: 0 0 1.5rem 0;
  font-size: 1.3rem;
}

.settings-view__content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.settings-section {
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
}

.settings-section__title {
  margin: 0 0 12px 0;
  font-size: 0.95rem;
  color: var(--text-primary);
}

.settings-section__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.settings-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.settings-field__label {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.settings-field__input {
  padding: 7px 12px;
  background: var(--bg-input, var(--bg-secondary));
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 0.8rem;
  outline: none;
  transition: border-color var(--transition-fast);
}

.settings-field__input:focus {
  border-color: var(--accent-border);
}
</style>
