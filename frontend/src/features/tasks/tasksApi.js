import httpClient from '../../services/httpClient.js'

export function listTasks({ employeeId = '', status = '', overdueOnly = false } = {}) {
  const params = new URLSearchParams()
  if (employeeId) params.set('employee_id', employeeId)
  if (status) params.set('status', status)
  if (overdueOnly) params.set('overdue_only', 'true')
  const query = params.toString() ? `?${params.toString()}` : ''
  return httpClient(`/api/tasks${query}`)
}

export function createTask(payload) {
  return httpClient('/api/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function updateTask(id, payload) {
  return httpClient(`/api/tasks/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function deleteTask(id) {
  return httpClient(`/api/tasks/${id}`, { method: 'DELETE' })
}

export function getLeadershipTaskOverview(range = '30d') {
  return httpClient(`/api/tasks/leadership-overview?range=${encodeURIComponent(range)}`)
}

export function getDepartmentTaskPortfolio(departmentId, { range = '30d', focus = 'all' } = {}) {
  const params = new URLSearchParams({ range, focus })
  return httpClient(
    `/api/tasks/departments/${encodeURIComponent(departmentId)}/portfolio?${params.toString()}`,
  )
}

export function listDepartmentTaskDirectives(status = '') {
  const query = status ? `?status=${encodeURIComponent(status)}` : ''
  return httpClient(`/api/tasks/department-directives${query}`)
}

export function issueDepartmentTaskDirective(departmentId, payload) {
  return httpClient(`/api/tasks/department-directives/${encodeURIComponent(departmentId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function acknowledgeDepartmentTaskDirective(directiveId, payload) {
  return httpClient(
    `/api/tasks/department-directives/${encodeURIComponent(directiveId)}/acknowledge`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}

export function submitDepartmentTaskDirective(directiveId, payload = {}) {
  return httpClient(`/api/tasks/department-directives/${encodeURIComponent(directiveId)}/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function acceptDepartmentTaskDirective(directiveId, payload = {}) {
  return httpClient(`/api/tasks/department-directives/${encodeURIComponent(directiveId)}/accept`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function requestTaskDirectiveRevision(directiveId, payload = {}) {
  return httpClient(
    `/api/tasks/department-directives/${encodeURIComponent(directiveId)}/request-revision`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}
