import httpClient from '../../services/httpClient.js'
import { unwrapPageItems } from '../../utils/pagination.js'

export function listEmployees(departmentId) {
  const params = new URLSearchParams({ page: '1', page_size: '20' })
  if (departmentId) params.set('department_id', departmentId)

  return httpClient(`/api/v1/employees?${params.toString()}`).then((response) =>
    unwrapPageItems(response, 'employees'),
  )
}

export function createEmployee(payload) {
  return httpClient('/api/v1/employees', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function updateEmployee(id, payload) {
  return httpClient(`/api/v1/employees/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function deleteEmployee(id) {
  return httpClient(`/api/v1/employees/${id}`, { method: 'DELETE' })
}
