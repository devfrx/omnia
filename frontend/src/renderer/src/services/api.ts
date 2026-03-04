/**
 * REST API client for OMNIA backend.
 */

const BASE_URL = 'http://localhost:8000/api'

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers
    },
    ...options
  })
  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`)
  }
  return response.json()
}

export const api = {
  // Chat
  getChatHistory: () => request<unknown[]>('/chat/history'),
  deleteConversation: (id: string) => request(`/chat/history/${id}`, { method: 'DELETE' }),

  // Config
  getConfig: () => request<Record<string, unknown>>('/config'),
  updateConfig: (config: Record<string, unknown>) =>
    request('/config', { method: 'PUT', body: JSON.stringify(config) }),

  // Plugins
  getPlugins: () => request<unknown[]>('/plugins'),
  togglePlugin: (name: string, enabled: boolean) =>
    request(`/plugins/${name}`, { method: 'PATCH', body: JSON.stringify({ enabled }) })
}
