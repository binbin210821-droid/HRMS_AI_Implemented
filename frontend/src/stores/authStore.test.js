import { act } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from './authStore.js'

const manager = {
  user_id: 'user-1',
  username: 'demo.manager',
  full_name: 'Quản lý Demo',
  role: 'manager',
  department_id: 'dept-1',
}

describe('authStore', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    useAuthStore.getState().clearSession()
  })

  it('stores server-provided user data without persisting an access token', () => {
    useAuthStore.getState().setUser(manager)

    expect(useAuthStore.getState()).toMatchObject({
      currentUser: manager,
      claims: manager,
      role: 'manager',
      isAuthenticated: true,
      isInitializing: false,
    })
    expect(localStorage.length).toBe(0)
  })

  it('restores a session from /me through the HttpOnly cookie', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => manager }))

    await act(async () => {
      await useAuthStore.getState().initializeSession()
    })

    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/auth/me',
      expect.objectContaining({ credentials: 'include' }),
    )
    expect(useAuthStore.getState()).toMatchObject({ role: 'manager', isAuthenticated: true })
  })

  it('clears the session when /me is unauthorized', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401 }))

    await act(async () => {
      await useAuthStore.getState().initializeSession()
    })

    expect(useAuthStore.getState()).toMatchObject({
      currentUser: null,
      role: null,
      isAuthenticated: false,
      isInitializing: false,
    })
  })

  it('clears the local session immediately and calls logout with credentials', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
    useAuthStore.getState().setUser(manager)

    await act(async () => {
      await useAuthStore.getState().logout()
    })

    expect(useAuthStore.getState().isAuthenticated).toBe(false)
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/auth/logout',
      expect.objectContaining({ method: 'POST', credentials: 'include' }),
    )
  })
})
