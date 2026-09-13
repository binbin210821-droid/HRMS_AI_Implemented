import httpClient from '../../services/httpClient.js'
import { coordinatedRequest, invalidateResource } from '../../services/requestCoordinator.js'

export function listAlerts(status, alertType, { startDate, endDate } = {}) {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (alertType) params.set('alert_type', alertType)
  if (startDate) params.set('from', startDate)
  if (endDate) params.set('to', endDate)
  params.set('page_size', '100')
  const query = params.toString()
  const requestUrl = `/api/v1/alerts${query ? `?${query}` : ''}`
  return coordinatedRequest('alerts', requestUrl, () => fetchAllAlertPages(params))
}

async function fetchAllAlertPages(params) {
  const items = []
  let page = 1
  let hasNext = true
  while (hasNext) {
    const pageParams = new URLSearchParams(params)
    if (page > 1) pageParams.set('page', String(page))
    const response = await httpClient(`/api/v1/alerts?${pageParams.toString()}`)
    items.push(...(response.items ?? []))
    hasNext = response.has_next === true
    page += 1
  }
  return items
}

export function scanAlerts() {
  return httpClient('/api/v1/alert-scans', { method: 'POST' }).then((response) => {
    invalidateResource('alerts')
    return response
  })
}

export function listDepartmentAlertSummaries() {
  return httpClient('/api/v1/alerts/department-summary')
}

export function resolveAlert(alertId, resolutionNote) {
  return httpClient(`/api/v1/alerts/${encodeURIComponent(alertId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'resolved', resolution_note: resolutionNote || null }),
  }).then((response) => {
    invalidateResource('alerts')
    return response
  })
}
