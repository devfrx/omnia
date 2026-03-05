import { defineStore } from 'pinia'
import { ref } from 'vue'

import type { PluginInfo } from '../types/plugin'

export const usePluginsStore = defineStore('plugins', () => {
  const plugins = ref<PluginInfo[]>([])
  const loading = ref(false)

  return { plugins, loading }
})
