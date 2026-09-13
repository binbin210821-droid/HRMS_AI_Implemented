import httpClient from '../../services/httpClient.js'

export function getAttentionSummary() {
  return httpClient('/api/v1/dashboard/attention-summary')
}
