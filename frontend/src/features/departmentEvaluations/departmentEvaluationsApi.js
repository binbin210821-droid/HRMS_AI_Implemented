import httpClient from '../../services/httpClient.js'

export function getWeeklyDepartmentReview(departmentId, weekStart) {
  const params = new URLSearchParams({ department_id: departmentId, week_start: weekStart })
  return httpClient(`/api/department-evaluations/weekly-review?${params.toString()}`)
}

export function listDepartmentEvaluations(departmentId = '', page = 1, pageSize = 12) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (departmentId) params.set('department_id', departmentId)
  const query = `?${params.toString()}`
  return httpClient(`/api/department-evaluations${query}`)
}

export function getDepartmentEvaluation(evaluationId) {
  return httpClient(`/api/department-evaluations/${encodeURIComponent(evaluationId)}`)
}

export function getDepartmentEvaluationAttachmentUrl(evaluationId, attachmentId) {
  return httpClient(
    `/api/department-evaluations/${encodeURIComponent(evaluationId)}/attachments/${encodeURIComponent(attachmentId)}/download-url`,
  )
}

function evaluationFormData(payload, files = []) {
  const formData = new FormData()
  formData.append('payload', JSON.stringify(payload))
  files.forEach((file) => formData.append('files', file))
  return formData
}

export function createDepartmentEvaluation(payload, files) {
  return httpClient('/api/department-evaluations/weekly-review', {
    method: 'POST',
    body: evaluationFormData(payload, files),
  })
}

export function updateDepartmentEvaluation(evaluationId, payload, files = []) {
  return httpClient(`/api/department-evaluations/${encodeURIComponent(evaluationId)}`, {
    method: 'PATCH',
    body: evaluationFormData(payload, files),
  })
}
