import httpClient from '../../services/httpClient.js'

export function listEmployees(departmentId) {
  const query = departmentId ? `?department_id=${encodeURIComponent(departmentId)}` : ''
  return httpClient(`/api/employees${query}`)
}

export function createEmployee(payload) {
  return httpClient('/api/employees', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function updateEmployee(id, payload) {
  return httpClient(`/api/employees/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function deleteEmployee(id) {
  return httpClient(`/api/employees/${id}`, { method: 'DELETE' })
}
