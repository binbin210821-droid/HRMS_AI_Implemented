import httpClient from '../../services/httpClient.js'
import { unwrapPageItems } from '../../utils/pagination.js'

export async function listDepartments() {
  const response = await httpClient('/api/v1/departments?page=1&page_size=20')
  return unwrapPageItems(response, 'departments')
}

export function createDepartment(payload) {
  return httpClient('/api/v1/departments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function updateDepartment(id, payload) {
  return httpClient(`/api/v1/departments/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function deleteDepartment(id) {
  return httpClient(`/api/v1/departments/${id}`, { method: 'DELETE' })
}
