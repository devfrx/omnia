import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface OmniaSettings {
  llm: {
    model: string
    temperature: number
    maxTokens: number
  }
  stt: {
    language: string
    model: string
  }
  tts: {
    voice: string
    engine: string
  }
  ui: {
    theme: 'dark' | 'light'
    language: string
  }
}

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<OmniaSettings>({
    llm: {
      model: 'qwen3.5:9b',
      temperature: 0.7,
      maxTokens: 4096
    },
    stt: {
      language: 'it',
      model: 'large-v3'
    },
    tts: {
      voice: 'it_IT-riccardo-x_low',
      engine: 'piper'
    },
    ui: {
      theme: 'dark',
      language: 'it'
    }
  })

  return { settings }
})
