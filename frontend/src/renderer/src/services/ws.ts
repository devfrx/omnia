/**
 * WebSocket connection manager for OMNIA backend.
 * Handles connection, reconnection, and message dispatching.
 */

type MessageHandler = (data: unknown) => void

export class WebSocketManager {
  private ws: WebSocket | null = null
  private url: string
  private handlers: Map<string, MessageHandler[]> = new Map()
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private reconnectDelay = 1000

  constructor(url: string = 'ws://localhost:8000/ws/chat') {
    this.url = url
  }

  connect(): void {
    this.ws = new WebSocket(this.url)

    this.ws.onopen = () => {
      console.log('[OMNIA WS] Connected to', this.url)
      this.reconnectAttempts = 0
      this.emit('connected', null)
    }

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)
        this.emit(data.type || 'message', data)
      } catch {
        // Binary data (audio frames) — pass raw
        this.emit('binary', event.data)
      }
    }

    this.ws.onclose = () => {
      console.log('[OMNIA WS] Disconnected')
      this.emit('disconnected', null)
      this.attemptReconnect()
    }

    this.ws.onerror = (error) => {
      console.error('[OMNIA WS] Error:', error)
      this.emit('error', error)
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[OMNIA WS] Max reconnect attempts reached')
      return
    }
    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
    console.log(`[OMNIA WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)
    setTimeout(() => this.connect(), delay)
  }

  send(data: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }

  sendBinary(data: ArrayBuffer | Blob): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(data)
    }
  }

  on(event: string, handler: MessageHandler): void {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, [])
    }
    this.handlers.get(event)!.push(handler)
  }

  off(event: string, handler: MessageHandler): void {
    const handlers = this.handlers.get(event)
    if (handlers) {
      const idx = handlers.indexOf(handler)
      if (idx !== -1) handlers.splice(idx, 1)
    }
  }

  private emit(event: string, data: unknown): void {
    this.handlers.get(event)?.forEach((handler) => handler(data))
  }

  disconnect(): void {
    this.maxReconnectAttempts = 0 // prevent reconnect
    this.ws?.close()
    this.ws = null
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

// Singleton instance
export const wsManager = new WebSocketManager()
