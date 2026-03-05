import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useVoiceStore = defineStore('voice', () => {
  const isListening = ref(false)
  const isProcessing = ref(false)
  const isSpeaking = ref(false)
  const transcript = ref('')
  const audioLevel = ref(0)

  return {
    isListening,
    isProcessing,
    isSpeaking,
    transcript,
    audioLevel
  }
})
