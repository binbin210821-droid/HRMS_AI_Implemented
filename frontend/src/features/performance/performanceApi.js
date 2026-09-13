import httpClient from '../../services/httpClient.js'

function unwrapPerformanceItems(response) {
  return Array.isArray(response) ? response : (response?.items ?? [])
}

export function listPerformance({ employeeId, departmentId, startDate, endDate } = {}) {
  const params = new URLSearchParams()
  if (employeeId) params.set('employee_id', employeeId)
  if (departmentId) params.set('department_id', departmentId)
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  const query = params.toString()
  return httpClient(`/api/v1/performance${query ? `?${query}` : ''}`).then(unwrapPerformanceItems)
}

export function getDailyPerformanceReview(employeeId, date) {
  const params = new URLSearchParams({ employee_id: employeeId, date })
  return httpClient(`/api/v1/performance/daily-review?${params.toString()}`)
}

export function getDailyReviewAttachmentUrl(employeeId, date, attachmentId) {
  return httpClient(
    `/api/v1/performance/daily-review/${encodeURIComponent(employeeId)}/${encodeURIComponent(date)}/attachments/${encodeURIComponent(attachmentId)}/download-url`,
  )
}

export function saveDailyPerformanceReview(payload, idempotencyKey) {
  return httpClient('/api/v1/performance/daily-review', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    idempotencyKey,
  })
}

export function updateDailyPerformanceReview(payload, idempotencyKey) {
  return httpClient('/api/v1/performance/daily-review', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    idempotencyKey,
  })
}

function analyticsQuery({ startDate, endDate } = {}) {
  const params = new URLSearchParams()
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  const query = params.toString()
  return query ? `?${query}` : ''
}

export function getEmployeePerformanceAnalytics(employeeId, options) {
  return httpClient(
    `/api/v1/performance/analytics/employee/${encodeURIComponent(employeeId)}${analyticsQuery(options)}`,
  )
}

export function getDepartmentPerformanceAnalytics(departmentId, options) {
  return httpClient(
    `/api/v1/performance/analytics/department/${encodeURIComponent(departmentId)}${analyticsQuery(options)}`,
  )
}

export function getDepartmentWeeklyTrend(departmentId, options) {
  return httpClient(
    `/api/v1/performance/analytics/department/${encodeURIComponent(departmentId)}/weekly-trend${analyticsQuery(options)}`,
  )
}

export function getCompanyPerformanceAnalytics(options) {
  return httpClient(`/api/v1/performance/analytics/company${analyticsQuery(options)}`)
}
