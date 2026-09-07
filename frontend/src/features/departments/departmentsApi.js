import httpClient from '../../services/httpClient.js'

export function listDepartments() {
  return httpClient('/api/departments')
}

export function createDepartment(payload) {
  return httpClient('/api/departments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function updateDepartment(id, payload) {
  return httpClient(`/api/departments/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function deleteDepartment(id) {
  return httpClient(`/api/departments/${id}`, { method: 'DELETE' })
}
