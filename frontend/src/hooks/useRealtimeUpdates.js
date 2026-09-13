import { useEffect, useRef } from 'react'

import { useAuthStore } from '../stores/authStore.js'

const DEFAULT_RECONNECT_DELAY = 1000
const DEFAULT_MAX_RECONNECT_DELAY = 10000
export const REALTIME_COALESCE_DELAY_MS = 800
// Giữ tên export cũ để các caller chưa nằm trong phạm vi Phase 12.1 không bị break.
export const REALTIME_COALESCE_DELAY = REALTIME_COALESCE_DELAY_MS
const DEFAULT_COALESCE_DELAY = 0

function getWebSocketUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws/realtime`
}

export function useRealtimeUpdates(
  topic,
  callback,
  {
    reconnectDelay = DEFAULT_RECONNECT_DELAY,
    maxReconnectDelay = DEFAULT_MAX_RECONNECT_DELAY,
    coalesceDelay = DEFAULT_COALESCE_DELAY,
  } = {},
) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const callbackRef = useRef(callback)
  const topics = Array.isArray(topic) ? topic : [topic]
  const topicsKey = topics.join('\u0000')

  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  useEffect(() => {
    const subscribedTopics = topicsKey ? topicsKey.split('\u0000') : []

    if (!isAuthenticated || typeof WebSocket === 'undefined') return undefined

    let socket
    let reconnectTimer
    let coalesceTimer
    let pendingMessage
    let reconnectAttempt = 0
    let disposed = false

    function connect() {
      if (disposed) return
      socket = new WebSocket(getWebSocketUrl())

      socket.onopen = () => {
        reconnectAttempt = 0
      }

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          if (!subscribedTopics.includes(message.topic)) return
          if (coalesceDelay <= 0) {
            callbackRef.current(message)
            return
          }
          pendingMessage = message
          if (coalesceTimer) window.clearTimeout(coalesceTimer)
          coalesceTimer = window.setTimeout(() => {
            coalesceTimer = undefined
            const latestMessage = pendingMessage
            pendingMessage = undefined
            if (!disposed && latestMessage) callbackRef.current(latestMessage)
          }, coalesceDelay)
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
      if (coalesceTimer) window.clearTimeout(coalesceTimer)
      coalesceTimer = undefined
      pendingMessage = undefined
    }
  }, [coalesceDelay, isAuthenticated, maxReconnectDelay, reconnectDelay, topicsKey])
}

export function useCoalescedRealtimeUpdates(
  topics,
  callback,
  { delay = REALTIME_COALESCE_DELAY_MS } = {},
) {
  const callbackRef = useRef(callback)
  const schedulerRef = useRef(null)

  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  useEffect(() => {
    let disposed = false
    let timer
    let running = false
    let queued = false

    async function invoke() {
      if (disposed) return
      if (running) {
        queued = true
        return
      }

      running = true
      try {
        await callbackRef.current()
      } finally {
        running = false
        if (queued && !disposed) {
          queued = false
          void invoke()
        }
      }
    }

    function schedule() {
      if (disposed) return
      if (timer) window.clearTimeout(timer)
      timer = window.setTimeout(
        () => {
          timer = undefined
          void invoke()
        },
        Math.max(0, delay),
      )
    }

    schedulerRef.current = schedule
    return () => {
      disposed = true
      queued = false
      schedulerRef.current = null
      if (timer) window.clearTimeout(timer)
    }
  }, [delay])

  useRealtimeUpdates(
    topics,
    () => {
      schedulerRef.current?.()
    },
    { coalesceDelay: 0 },
  )
}
