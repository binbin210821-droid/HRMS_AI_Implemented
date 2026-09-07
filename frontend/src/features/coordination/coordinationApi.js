import httpClient from '../../services/httpClient.js'

export function listCoordinationSuggestions() {
  return httpClient('/api/coordination/suggestions')
}

export function applyCoordination(alertId, payload = {}) {
  return httpClient(`/api/coordination/alerts/${encodeURIComponent(alertId)}/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function listDirectiveTargets(alertId) {
  return httpClient(`/api/coordination/alerts/${encodeURIComponent(alertId)}/directive-targets`)
}

export function issueDirective(alertId, payload = {}) {
  return httpClient(`/api/coordination/alerts/${encodeURIComponent(alertId)}/direct`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function listDirectives(status) {
  const query = status ? `?status=${encodeURIComponent(status)}` : ''
  return httpClient(`/api/coordination/directives${query}`)
}

export function getDirectiveCandidates(directiveId) {
  return httpClient(`/api/coordination/directives/${encodeURIComponent(directiveId)}/candidates`)
}

export function fulfillDirective(directiveId, payload = {}) {
  return httpClient(`/api/coordination/directives/${encodeURIComponent(directiveId)}/fulfill`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function listDepartmentDirectives(status) {
  const query = status ? `?status=${encodeURIComponent(status)}` : ''
  return httpClient(`/api/coordination/department-directives${query}`)
}

export function issueDepartmentDirective(departmentId, payload = {}) {
  return httpClient(`/api/coordination/department-directives/${encodeURIComponent(departmentId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function acknowledgeDepartmentDirective(directiveId, payload = {}) {
  return httpClient(
    `/api/coordination/department-directives/${encodeURIComponent(directiveId)}/acknowledge`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}

export function submitDepartmentDirective(directiveId, payload = {}) {
  return httpClient(
    `/api/coordination/department-directives/${encodeURIComponent(directiveId)}/submit`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}

export function acceptDepartmentDirective(directiveId, payload = {}) {
  return httpClient(
    `/api/coordination/department-directives/${encodeURIComponent(directiveId)}/accept`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}

export function requestDepartmentDirectiveRevision(directiveId, payload = {}) {
  return httpClient(
    `/api/coordination/department-directives/${encodeURIComponent(directiveId)}/request-revision`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}
