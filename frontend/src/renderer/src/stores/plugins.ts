import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '../services/api'
import type { PluginInfo } from '../types/plugin'

export const usePluginsStore = defineStore('plugins', () => {
  const plugins = ref<PluginInfo[]>([])
  const loading = ref(false)

  async function loadPlugins(): Promise<void> {
    loading.value = true
    try {
      plugins.value = await api.getPlugins()
    } catch (err) {
      console.error('[plugins store] loadPlugins failed:', err)
    } finally {
      loading.value = false
    }
  }

  async function togglePlugin(name: string, enabled: boolean): Promise<void> {
    try {
      await api.togglePlugin(name, enabled)
      const target = plugins.value.find((p) => p.name === name)
      if (target) {
        target.enabled = enabled
      }
    } catch (err) {
      console.error('[plugins store] togglePlugin failed:', err)
    }
  }

  return { plugins, loading, loadPlugins, togglePlugin }
})
