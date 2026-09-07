import { useEffect, useRef } from 'react'

import { useAuthStore } from '../stores/authStore.js'

const DEFAULT_RECONNECT_DELAY = 1000
const DEFAULT_MAX_RECONNECT_DELAY = 10000

function getWebSocketUrl(token) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws/realtime?token=${encodeURIComponent(token)}`
}

export function useRealtimeUpdates(
  topic,
  callback,
  {
    reconnectDelay = DEFAULT_RECONNECT_DELAY,
    maxReconnectDelay = DEFAULT_MAX_RECONNECT_DELAY,
  } = {},
) {
  const token = useAuthStore((state) => state.token)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const callbackRef = useRef(callback)

  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  useEffect(() => {
    if (!isAuthenticated || !token || typeof WebSocket === 'undefined') return undefined

    let socket
    let reconnectTimer
    let reconnectAttempt = 0
    let disposed = false

    function connect() {
      if (disposed) return
      socket = new WebSocket(getWebSocketUrl(token))

      socket.onopen = () => {
        reconnectAttempt = 0
      }

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          if (message.topic === topic) callbackRef.current(message)
        } catch {
          // Bỏ qua frame không phải JSON để một event lỗi không làm hỏng hook.
        }
      }

      socket.onclose = () => {
        if (disposed) return
        const delay = Math.min(reconnectDelay * 2 ** reconnectAttempt, maxReconnectDelay)
        reconnectAttempt += 1
        reconnectTimer = window.setTimeout(connect, delay)
      }

      socket.onerror = () => {
        socket.close()
      }
    }

    connect()

    return () => {
      disposed = true
      if (reconnectTimer) window.clearTimeout(reconnectTimer)
      if (socket && socket.readyState !== WebSocket.CLOSED) socket.close(1000, 'Rời trang')
    }
  }, [isAuthenticated, maxReconnectDelay, reconnectDelay, token, topic])
}
