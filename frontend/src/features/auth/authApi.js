import httpClient from '../../services/httpClient.js'

export function login(credentials) {
  return httpClient('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  })
}
