import httpClient from '../../services/httpClient.js'

export function getWeeklyDepartmentReview(departmentId, weekStart) {
  return httpClient(
    `/api/v1/department-evaluations/weekly-reviews/${encodeURIComponent(departmentId)}/${encodeURIComponent(weekStart)}`,
  )
}

export function listDepartmentEvaluations(departmentId = '', page = 1, pageSize = 12) {
  const params = new URLSearchParams({
    offset: String(Math.max(0, page - 1) * pageSize),
    limit: String(pageSize),
  })
  if (departmentId) params.set('department_id', departmentId)
  const query = `?${params.toString()}`
  return httpClient(`/api/v1/department-evaluations${query}`)
}

export function getDepartmentEvaluation(evaluationId) {
  return httpClient(`/api/v1/department-evaluations/${encodeURIComponent(evaluationId)}`)
}

export function getDepartmentEvaluationAttachmentUrl(evaluationId, attachmentId) {
  return httpClient(
    `/api/v1/department-evaluations/${encodeURIComponent(evaluationId)}/attachments/${encodeURIComponent(attachmentId)}/download-url`,
  )
}

function evaluationFormData(payload, files = []) {
  const formData = new FormData()
  formData.append('payload', JSON.stringify(payload))
  files.forEach((file) => formData.append('files', file))
  return formData
}

export function createDepartmentEvaluation(payload, files, idempotencyKey) {
  return httpClient('/api/v1/department-evaluations/weekly-review', {
    method: 'POST',
    body: evaluationFormData(payload, files),
    idempotencyKey,
  })
}

export function updateDepartmentEvaluation(evaluationId, payload, files = [], idempotencyKey) {
  return httpClient(`/api/v1/department-evaluations/${encodeURIComponent(evaluationId)}`, {
    method: 'PATCH',
    body: evaluationFormData(payload, files),
    idempotencyKey,
  })
}
