import { create } from 'zustand'

const TOKEN_KEY = 'hrms_auth_token'

function readToken() {
  if (typeof localStorage === 'undefined') return null
  return localStorage.getItem(TOKEN_KEY)
}

function decodeToken(token) {
  if (!token) return null

  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(payload))
  } catch {
    return null
  }
}

function getSession(token) {
  const claims = decodeToken(token)
  if (!claims?.sub || !claims?.role) return { token: null, role: null, claims: null }
  if (claims.exp && claims.exp * 1000 <= Date.now())
    return { token: null, role: null, claims: null }
  return { token, role: claims.role, claims }
}

const initialSession = getSession(readToken())

export const useAuthStore = create((set) => ({
  token: initialSession.token,
  role: initialSession.role,
  claims: initialSession.claims,
  isAuthenticated: Boolean(initialSession.token),
  login: (authResponse) => {
    const session = getSession(authResponse.access_token)
    if (typeof localStorage !== 'undefined' && session.token) {
      localStorage.setItem(TOKEN_KEY, session.token)
    }
    set({ ...session, isAuthenticated: Boolean(session.token) })
  },
  logout: () => {
    if (typeof localStorage !== 'undefined') localStorage.removeItem(TOKEN_KEY)
    set({ token: null, role: null, claims: null, isAuthenticated: false })
  },
}))

export { TOKEN_KEY }
