import { beforeEach, describe, expect, it } from 'vitest'

import { TOKEN_KEY, useAuthStore } from './authStore.js'

function tokenFor(claims) {
  const encode = (value) =>
    btoa(JSON.stringify(value)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode(claims)}.signature`
}

describe('authStore', () => {
  beforeEach(() => {
    useAuthStore.getState().logout()
    localStorage.clear()
  })

  it('stores a valid JWT session and claims', () => {
    const token = tokenFor({ sub: 'user-1', role: 'manager', department_id: 'dept-1' })

    useAuthStore.getState().login({ access_token: token })

    expect(useAuthStore.getState()).toMatchObject({
      token,
      role: 'manager',
      isAuthenticated: true,
      claims: { sub: 'user-1', department_id: 'dept-1' },
    })
    expect(localStorage.getItem(TOKEN_KEY)).toBe(token)
  })

  it('rejects expired or malformed JWT sessions', () => {
    useAuthStore.getState().login({
      access_token: tokenFor({
        sub: 'user-1',
        role: 'manager',
        exp: Math.floor(Date.now() / 1000) - 1,
      }),
    })
    expect(useAuthStore.getState().isAuthenticated).toBe(false)

    useAuthStore.getState().login({ access_token: 'not-a-jwt' })
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('clears local session on logout', () => {
    const token = tokenFor({ sub: 'user-1', role: 'leadership' })
    useAuthStore.getState().login({ access_token: token })
    useAuthStore.getState().logout()

    expect(useAuthStore.getState()).toMatchObject({
      token: null,
      role: null,
      claims: null,
      isAuthenticated: false,
    })
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })
})
