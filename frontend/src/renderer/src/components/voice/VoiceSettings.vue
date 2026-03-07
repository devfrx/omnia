<script setup lang="ts">
/**
 * VoiceSettings.vue — Voice configuration panel.
 *
 * Allows the user to enable/disable STT and TTS,
 * select voice, adjust speed, and choose activation mode.
 */
import { ref } from 'vue'

const props = defineProps<{
  /** Current voice configuration from backend. */
  config: {
    stt: { enabled: boolean; model: string; language: string }
    tts: { enabled: boolean; engine: string; voice: string; speed: number }
    voice: { activation_mode: string; wake_word: string; auto_tts_response: boolean }
  }
}>()

const emit = defineEmits<{
  /** Emitted when configuration changes. */
  update: [config: Record<string, unknown>]
}>()

// Local state mirrors config for two-way binding
const sttEnabled = ref(props.config.stt.enabled)
const ttsEnabled = ref(props.config.tts.enabled)
const ttsEngine = ref(props.config.tts.engine)
const ttsVoice = ref(props.config.tts.voice)
const ttsSpeed = ref(props.config.tts.speed)
const activationMode = ref(props.config.voice.activation_mode)
const autoTtsResponse = ref(props.config.voice.auto_tts_response)

const activationModes = [
  { value: 'push_to_talk', label: 'Premi per parlare' },
  { value: 'wake_word', label: 'Parola di attivazione' },
  { value: 'always_on', label: 'Sempre attivo' },
]

const ttsEngines = [
  { value: 'piper', label: 'Piper (CPU, veloce)' },
  { value: 'xtts', label: 'XTTS v2 (GPU, clonazione voce)' },
]

function save(): void {
  emit('update', {
    stt: { enabled: sttEnabled.value },
    tts: {
      enabled: ttsEnabled.value,
      engine: ttsEngine.value,
      voice: ttsVoice.value,
      speed: ttsSpeed.value,
    },
    voice: {
      activation_mode: activationMode.value,
      auto_tts_response: autoTtsResponse.value,
    },
  })
}
</script>

<template>
  <div class="vs" role="region" aria-label="Impostazioni voce">
    <h3 class="vs__title">Impostazioni Voce</h3>

    <!-- STT Section -->
    <section class="vs__section" aria-labelledby="stt-heading">
      <h4 id="stt-heading" class="vs__subtitle">Riconoscimento Vocale (STT)</h4>
      <label class="vs__toggle">
        <input
          v-model="sttEnabled"
          type="checkbox"
          aria-label="Abilita riconoscimento vocale"
          @change="save"
        />
        <span>Abilita STT</span>
      </label>
      <div v-if="sttEnabled" class="vs__detail">
        <span class="vs__info">Modello: {{ props.config.stt.model }}</span>
        <span class="vs__info">Lingua: {{ props.config.stt.language }}</span>
      </div>
    </section>

    <!-- TTS Section -->
    <section class="vs__section" aria-labelledby="tts-heading">
      <h4 id="tts-heading" class="vs__subtitle">Sintesi Vocale (TTS)</h4>
      <label class="vs__toggle">
        <input
          v-model="ttsEnabled"
          type="checkbox"
          aria-label="Abilita sintesi vocale"
          @change="save"
        />
        <span>Abilita TTS</span>
      </label>
      <div v-if="ttsEnabled" class="vs__fields">
        <label class="vs__field">
          <span class="vs__field-label">Motore</span>
          <select
            v-model="ttsEngine"
            class="vs__select"
            aria-label="Seleziona motore TTS"
            @change="save"
          >
            <option v-for="e in ttsEngines" :key="e.value" :value="e.value">
              {{ e.label }}
            </option>
          </select>
        </label>
        <label class="vs__field">
          <span class="vs__field-label">Velocità</span>
          <input
            v-model.number="ttsSpeed"
            type="range"
            min="0.5"
            max="2.0"
            step="0.1"
            class="vs__range"
            aria-label="Velocità sintesi vocale"
            @change="save"
          />
          <span class="vs__range-value">{{ ttsSpeed.toFixed(1) }}x</span>
        </label>
        <label class="vs__toggle">
          <input
            v-model="autoTtsResponse"
            type="checkbox"
            aria-label="Rispondi automaticamente a voce"
            @change="save"
          />
          <span>Rispondi automaticamente a voce</span>
        </label>
      </div>
    </section>

    <!-- Activation Mode -->
    <section class="vs__section" aria-labelledby="activation-heading">
      <h4 id="activation-heading" class="vs__subtitle">Modalità Attivazione</h4>
      <div class="vs__radio-group" role="radiogroup" aria-label="Modalità di attivazione vocale">
        <label v-for="mode in activationModes" :key="mode.value" class="vs__radio">
          <input
            v-model="activationMode"
            type="radio"
            :value="mode.value"
            name="activation-mode"
            :aria-label="mode.label"
            @change="save"
          />
          <span>{{ mode.label }}</span>
        </label>
      </div>
    </section>
  </div>
</template>

<style scoped>
.vs {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  color: var(--text-primary, #e0e0e0);
}

.vs__title {
  font-size: 1rem;
  font-weight: 600;
  margin: 0;
  color: var(--accent, #c8a23c);
}

.vs__section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
}

.vs__subtitle {
  font-size: 0.85rem;
  font-weight: 600;
  margin: 0;
}

.vs__toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.82rem;
  cursor: pointer;
}

.vs__toggle input[type="checkbox"] {
  accent-color: var(--accent, #c8a23c);
}

.vs__detail {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-left: 24px;
}

.vs__info {
  font-size: 0.75rem;
  color: var(--text-secondary, #a0a0a0);
}

.vs__fields {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 4px;
}

.vs__field {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.82rem;
}

.vs__field-label {
  min-width: 60px;
  color: var(--text-secondary, #a0a0a0);
}

.vs__select {
  flex: 1;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(0, 0, 0, 0.2);
  color: var(--text-primary, #e0e0e0);
  font-size: 0.8rem;
}

.vs__range {
  flex: 1;
  accent-color: var(--accent, #c8a23c);
}

.vs__range-value {
  min-width: 36px;
  text-align: right;
  font-size: 0.78rem;
  color: var(--text-secondary, #a0a0a0);
}

.vs__radio-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.vs__radio {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.82rem;
  cursor: pointer;
}

.vs__radio input[type="radio"] {
  accent-color: var(--accent, #c8a23c);
}
</style>
