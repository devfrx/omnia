/** Voice-related types */

export interface VoiceState {
  isListening: boolean
  isProcessing: boolean
  isSpeaking: boolean
  transcript: string
  audioLevel: number
}

export interface AudioChunk {
  data: ArrayBuffer
  sampleRate: number
  timestamp: number
}
