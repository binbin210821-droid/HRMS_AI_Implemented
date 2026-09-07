import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useRealtimeUpdates } from './useRealtimeUpdates.js'
import { useAuthStore } from '../stores/authStore.js'

class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSED = 3
  static instances = []

  constructor(url) {
    this.url = url
    this.readyState = MockWebSocket.CONNECTING
    this.closeCalls = []
    MockWebSocket.instances.push(this)
  }

  close(code, reason) {
    this.closeCalls.push({ code, reason })
    this.readyState = MockWebSocket.CLOSED
  }

  emitMessage(message) {
    this.onmessage({ data: JSON.stringify(message) })
  }

  emitClose() {
    this.onclose()
  }
}

function setAuthenticated() {
  useAuthStore.setState({
    token: 'header.payload.signature',
    role: 'manager',
    isAuthenticated: true,
  })
}

describe('useRealtimeUpdates', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    MockWebSocket.instances = []
    vi.stubGlobal('WebSocket', MockWebSocket)
    act(() => useAuthStore.getState().logout())
    setAuthenticated()
  })

  afterEach(() => {
    useAuthStore.getState().logout()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('delivers only events matching the subscribed topic', () => {
    const callback = vi.fn()
    const { unmount } = renderHook(() => useRealtimeUpdates('alerts', callback))
    const socket = MockWebSocket.instances[0]

    socket.emitMessage({ topic: 'employees', data: {} })
    socket.emitMessage({ topic: 'alerts', operation: 'insert', data: { id: 'a1' } })

    expect(callback).toHaveBeenCalledTimes(1)
    expect(callback).toHaveBeenCalledWith({
      topic: 'alerts',
      operation: 'insert',
      data: { id: 'a1' },
    })
    unmount()
  })

  it('reconnects with a timer after an unexpected close', () => {
    const { unmount } = renderHook(() =>
      useRealtimeUpdates('alerts', vi.fn(), { reconnectDelay: 25 }),
    )
    MockWebSocket.instances[0].emitClose()

    vi.advanceTimersByTime(24)
    expect(MockWebSocket.instances).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(MockWebSocket.instances).toHaveLength(2)
    unmount()
  })

  it('closes the socket when the component unmounts or the user logs out', () => {
    const { unmount } = renderHook(() => useRealtimeUpdates('alerts', vi.fn()))
    const socket = MockWebSocket.instances[0]

    act(() => useAuthStore.getState().logout())
    expect(socket.closeCalls).toHaveLength(1)
    expect(socket.closeCalls[0].code).toBe(1000)
    unmount()
  })
})
