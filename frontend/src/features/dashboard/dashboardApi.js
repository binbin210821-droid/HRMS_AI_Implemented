import httpClient from '../../services/httpClient.js'

export function getAttentionSummary() {
  return httpClient('/api/dashboard/attention-summary')
}
