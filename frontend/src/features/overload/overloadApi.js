import httpClient from '../../services/httpClient.js'
import { coordinatedRequest } from '../../services/requestCoordinator.js'

export function listOverloadLogs({ startDate, endDate } = {}) {
  const params = new URLSearchParams({ page_size: '100' })
  if (startDate) params.set('from', startDate)
  if (endDate) params.set('to', endDate)
  const requestUrl = `/api/v1/overload?${params.toString()}`
  return coordinatedRequest('overload', requestUrl, () => fetchAllOverloadPages(params))
}

async function fetchAllOverloadPages(params) {
  const items = []
  let page = 1
  let hasNext = true
  while (hasNext) {
    const pageParams = new URLSearchParams(params)
    if (page > 1) pageParams.set('page', String(page))
    const response = await httpClient(`/api/v1/overload?${pageParams.toString()}`)
    items.push(...(response.items ?? []))
    hasNext = response.has_next === true
    page += 1
  }
  return items
}

export function scanOverloadLogs() {
  return httpClient('/api/v1/overload-scans', { method: 'POST' })
}
