import httpClient from '../../services/httpClient.js'

export function listOverloadLogs() {
  return httpClient('/api/overload')
}

export function scanOverloadLogs() {
  return httpClient('/api/overload/scan', { method: 'POST' })
}
