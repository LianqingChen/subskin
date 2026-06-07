import { ref, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

export function useWebSocket() {
  const ws = ref<WebSocket | null>(null)
  const connected = ref(false)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 5
  const messageHandlers = new Map<string, Set<(data: any) => void>>()

  function connect() {
    const authStore = useAuthStore()
    const token = authStore.token
    if (!token) return

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${location.host}/ws/chat?token=${token}`

    const socket = new WebSocket(url)
    ws.value = socket

    socket.onopen = () => {
      connected.value = true
      reconnectAttempts.value = 0
      const ping = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN)
          socket.send(JSON.stringify({ type: 'ping' }))
        else clearInterval(ping)
      }, 30000)
    }

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        const handlers = messageHandlers.get(data.type)
        if (handlers) handlers.forEach((h) => h(data))
        const allHandlers = messageHandlers.get('*')
        if (allHandlers) allHandlers.forEach((h) => h(data))
      } catch {
        /* ignore malformed messages */
      }
    }

    socket.onclose = () => {
      connected.value = false
      if (reconnectAttempts.value < maxReconnectAttempts) {
        reconnectAttempts.value++
        setTimeout(connect, 1000 * Math.min(reconnectAttempts.value, 5))
      }
    }

    socket.onerror = () => socket.close()
  }

  function on(event: string, handler: (data: any) => void) {
    if (!messageHandlers.has(event)) messageHandlers.set(event, new Set())
    messageHandlers.get(event)!.add(handler)
  }

  function off(event: string, handler: (data: any) => void) {
    messageHandlers.get(event)?.delete(handler)
  }

  function send(data: any) {
    if (ws.value?.readyState === WebSocket.OPEN)
      ws.value.send(JSON.stringify(data))
  }

  onUnmounted(() => {
    ws.value?.close()
  })

  return { connect, on, off, send, connected }
}
