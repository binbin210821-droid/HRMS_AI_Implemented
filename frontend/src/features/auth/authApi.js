import httpClient from '../../services/httpClient.js'

export function login(credentials) {
  return httpClient('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  })
}

export function getCurrentUser() {
  return httpClient('/api/v1/auth/me')
}

export function logout() {
  return httpClient('/api/v1/auth/logout', { method: 'POST' })
}
