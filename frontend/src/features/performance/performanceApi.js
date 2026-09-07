import httpClient from '../../services/httpClient.js'

export function listPerformance({ employeeId, departmentId, startDate, endDate } = {}) {
  const params = new URLSearchParams()
  if (employeeId) params.set('employee_id', employeeId)
  if (departmentId) params.set('department_id', departmentId)
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  const query = params.toString()
  return httpClient(`/api/performance${query ? `?${query}` : ''}`)
}

export function createDailyPerformance(payload) {
  return httpClient('/api/performance/daily', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function getDailyPerformanceReview(employeeId, date) {
  const params = new URLSearchParams({ employee_id: employeeId, date })
  return httpClient(`/api/performance/daily-review?${params.toString()}`)
}

export function getDailyReviewAttachmentUrl(employeeId, date, attachmentId) {
  return httpClient(
    `/api/performance/daily-review/${encodeURIComponent(employeeId)}/${encodeURIComponent(date)}/attachments/${encodeURIComponent(attachmentId)}/download-url`,
  )
}

export function saveDailyPerformanceReview(payload) {
  return httpClient('/api/performance/daily-review', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function updateDailyPerformanceReview(payload) {
  return httpClient('/api/performance/daily-review', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
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
    `/api/performance/analytics/employee/${encodeURIComponent(employeeId)}${analyticsQuery(options)}`,
  )
}

export function getDepartmentPerformanceAnalytics(departmentId, options) {
  return httpClient(
    `/api/performance/analytics/department/${encodeURIComponent(departmentId)}${analyticsQuery(options)}`,
  )
}

export function getCompanyPerformanceAnalytics(options) {
  return httpClient(`/api/performance/analytics/company${analyticsQuery(options)}`)
}
