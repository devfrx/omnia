import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface PluginInfo {
  name: string
  version: string
  description: string
  enabled: boolean
  tools: string[]
}

export const usePluginsStore = defineStore('plugins', () => {
  const plugins = ref<PluginInfo[]>([])
  const loading = ref(false)

  return { plugins, loading }
})
