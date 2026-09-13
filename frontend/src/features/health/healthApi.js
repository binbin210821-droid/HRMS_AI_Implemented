import httpClient from '../../services/httpClient.js'

export function getHealth() {
  return httpClient('/api/v1/health')
}
