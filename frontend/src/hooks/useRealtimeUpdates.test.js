import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useCoalescedRealtimeUpdates, useRealtimeUpdates } from './useRealtimeUpdates.js'
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
  act(() => {
    useAuthStore.setState({
      role: 'manager',
      isAuthenticated: true,
      isInitializing: false,
    })
  })
}

describe('useRealtimeUpdates', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    MockWebSocket.instances = []
    vi.stubGlobal('WebSocket', MockWebSocket)
    act(() => useAuthStore.getState().clearSession())
    setAuthenticated()
  })

  afterEach(() => {
    useAuthStore.getState().clearSession()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('delivers only events matching the subscribed topic', async () => {
    const callback = vi.fn()
    let hook
    await act(async () => {
      hook = renderHook(() => useRealtimeUpdates('alerts', callback))
    })
    const { unmount } = hook
    const socket = MockWebSocket.instances[0]

    expect(socket.url).toBe(`ws://${window.location.host}/ws/realtime`)

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

  it('coalesces a burst of matching events and delivers the latest one', async () => {
    const callback = vi.fn()
    let hook
    await act(async () => {
      hook = renderHook(() => useRealtimeUpdates('alerts', callback, { coalesceDelay: 100 }))
    })
    const { unmount } = hook
    const socket = MockWebSocket.instances[0]

    socket.emitMessage({ topic: 'alerts', data: { id: 'a1' } })
    socket.emitMessage({ topic: 'alerts', data: { id: 'a2' } })
    socket.emitMessage({ topic: 'alerts', data: { id: 'a3' } })
    socket.emitMessage({ topic: 'alerts', data: { id: 'a4' } })
    socket.emitMessage({ topic: 'alerts', data: { id: 'a5' } })
    expect(callback).not.toHaveBeenCalled()

    act(() => vi.advanceTimersByTime(99))
    expect(callback).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(1))

    expect(callback).toHaveBeenCalledTimes(1)
    expect(callback).toHaveBeenCalledWith({ topic: 'alerts', data: { id: 'a5' } })
    unmount()
  })

  it('coalesces events from multiple topics into one callback', async () => {
    const callback = vi.fn()
    let hook
    await act(async () => {
      hook = renderHook(() =>
        useCoalescedRealtimeUpdates(['alerts', 'tasks'], callback, { delay: 100 }),
      )
    })
    const { unmount } = hook
    const socket = MockWebSocket.instances[0]

    socket.emitMessage({ topic: 'alerts', data: { id: 'a1' } })
    socket.emitMessage({ topic: 'tasks', data: { id: 't1' } })
    socket.emitMessage({ topic: 'alerts', data: { id: 'a2' } })

    act(() => vi.advanceTimersByTime(99))
    expect(callback).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(1))
    expect(callback).toHaveBeenCalledTimes(1)
    unmount()
  })

  it('queues one follow-up callback when the async callback is still running', async () => {
    let resolveFirst
    const firstCall = new Promise((resolve) => {
      resolveFirst = resolve
    })
    const callback = vi
      .fn()
      .mockImplementationOnce(() => firstCall)
      .mockImplementation(() => undefined)
    let hook
    await act(async () => {
      hook = renderHook(() => useCoalescedRealtimeUpdates(['alerts'], callback, { delay: 100 }))
    })
    const { unmount } = hook
    const socket = MockWebSocket.instances[0]

    socket.emitMessage({ topic: 'alerts', data: { id: 'a1' } })
    act(() => vi.advanceTimersByTime(100))
    expect(callback).toHaveBeenCalledTimes(1)

    socket.emitMessage({ topic: 'alerts', data: { id: 'a2' } })
    socket.emitMessage({ topic: 'alerts', data: { id: 'a3' } })
    act(() => vi.advanceTimersByTime(100))
    expect(callback).toHaveBeenCalledTimes(1)

    await act(async () => {
      resolveFirst()
      await firstCall
    })
    expect(callback).toHaveBeenCalledTimes(2)
    unmount()
  })

  it('reconnects with a timer after an unexpected close', async () => {
    let hook
    await act(async () => {
      hook = renderHook(() => useRealtimeUpdates('alerts', vi.fn(), { reconnectDelay: 25 }))
    })
    const { unmount } = hook
    MockWebSocket.instances[0].emitClose()

    vi.runOnlyPendingTimers()
    expect(MockWebSocket.instances).toHaveLength(2)
    unmount()
  })

  it('closes the socket when the component unmounts or the user logs out', async () => {
    let hook
    await act(async () => {
      hook = renderHook(() => useRealtimeUpdates('alerts', vi.fn()))
    })
    const { unmount } = hook
    const socket = MockWebSocket.instances[0]

    act(() => useAuthStore.getState().clearSession())
    expect(socket.closeCalls).toHaveLength(1)
    expect(socket.closeCalls[0].code).toBe(1000)
    unmount()
  })
})
