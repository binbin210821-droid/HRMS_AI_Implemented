import httpClient from '../../services/httpClient.js'

export function listAlerts(status, alertType) {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (alertType) params.set('alert_type', alertType)
  const query = params.toString()
  return httpClient(`/api/alerts${query ? `?${query}` : ''}`)
}

export function scanAlerts() {
  return httpClient('/api/alerts/scan', { method: 'POST' })
}

export function listDepartmentAlertSummaries() {
  return httpClient('/api/alerts/department-summary')
}

export function resolveAlert(alertId, resolutionNote) {
  return httpClient(`/api/alerts/${encodeURIComponent(alertId)}/resolve`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resolution_note: resolutionNote || null }),
  })
}
