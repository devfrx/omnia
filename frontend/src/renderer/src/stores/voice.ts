import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useVoiceStore = defineStore('voice', () => {
  const isListening = ref(false)
  const isProcessing = ref(false)
  const isSpeaking = ref(false)
  const transcript = ref('')

  return {
    isListening,
    isProcessing,
    isSpeaking,
    transcript
  }
})
