import httpClient from '../../services/httpClient.js'
import { coordinatedRequest, invalidateResource } from '../../services/requestCoordinator.js'
import { fetchAllOffsetPages } from '../../utils/pagination.js'

export function listTasks({ employeeId = '', status = '', overdueOnly = false } = {}) {
  const params = new URLSearchParams()
  if (employeeId) params.set('employee_id', employeeId)
  if (status) params.set('status', status)
  if (overdueOnly) params.set('overdue_only', 'true')
  params.set('page_size', '100')
  const query = params.toString() ? `?${params.toString()}` : ''
  const requestUrl = `/api/v1/tasks${query}`
  return coordinatedRequest('tasks', requestUrl, async () => {
    const items = []
    let page = 1
    let hasNext = true
    while (hasNext) {
      const pageParams = new URLSearchParams(params)
      if (page > 1) pageParams.set('page', String(page))
      const response = await httpClient(`/api/v1/tasks?${pageParams.toString()}`)
      items.push(...(response.items ?? []))
      hasNext = response.has_next === true
      page += 1
    }
    return items
  })
}

export function createTask(payload) {
  return httpClient('/api/v1/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then((response) => {
    invalidateResource('tasks')
    return response
  })
}

export function updateTask(id, payload) {
  return httpClient(`/api/v1/tasks/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then((response) => {
    invalidateResource('tasks')
    return response
  })
}

export function deleteTask(id) {
  return httpClient(`/api/v1/tasks/${id}`, { method: 'DELETE' }).then((response) => {
    invalidateResource('tasks')
    return response
  })
}

export function getLeadershipTaskOverview(range = '30d') {
  return httpClient(`/api/v1/tasks/leadership-overview?range=${encodeURIComponent(range)}`)
}

export function getDepartmentTaskPortfolio(departmentId, { range = '30d', focus = 'all' } = {}) {
  const params = new URLSearchParams({ range, focus })
  return httpClient(
    `/api/v1/tasks/departments/${encodeURIComponent(departmentId)}/portfolio?${params.toString()}`,
  )
}

export function listDepartmentTaskDirectives(status = '') {
  return fetchAllOffsetPages(({ offset, limit }) => {
    const params = new URLSearchParams({ offset: String(offset), limit: String(limit) })
    if (status) params.set('status', status)
    return httpClient(`/api/v1/tasks/department-directives?${params.toString()}`)
  })
}

export function issueDepartmentTaskDirective(departmentId, payload, idempotencyKey) {
  return httpClient(`/api/v1/tasks/department-directives/${encodeURIComponent(departmentId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    idempotencyKey,
  })
}

export function acknowledgeDepartmentTaskDirective(directiveId, payload, idempotencyKey) {
  return httpClient(
    `/api/v1/tasks/department-directives/${encodeURIComponent(directiveId)}/acknowledgements`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      idempotencyKey,
    },
  )
}

export function submitDepartmentTaskDirective(directiveId, payload = {}, idempotencyKey) {
  return httpClient(
    `/api/v1/tasks/department-directives/${encodeURIComponent(directiveId)}/submissions`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      idempotencyKey,
    },
  )
}

export function acceptDepartmentTaskDirective(directiveId, payload = {}, idempotencyKey) {
  return httpClient(
    `/api/v1/tasks/department-directives/${encodeURIComponent(directiveId)}/acceptances`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      idempotencyKey,
    },
  )
}

export function requestTaskDirectiveRevision(directiveId, payload = {}, idempotencyKey) {
  return httpClient(
    `/api/v1/tasks/department-directives/${encodeURIComponent(directiveId)}/revision-requests`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      idempotencyKey,
    },
  )
}
