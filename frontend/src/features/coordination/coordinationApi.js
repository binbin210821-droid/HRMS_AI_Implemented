import httpClient from '../../services/httpClient.js'
import { fetchAllOffsetPages } from '../../utils/pagination.js'

function buildDirectiveUrl(path, status, offset, limit) {
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) })
  if (status) params.set('status', status)
  return `${path}?${params.toString()}`
}

function fetchAllDirectives(path, status) {
  return fetchAllOffsetPages(({ offset, limit }) =>
    httpClient(buildDirectiveUrl(path, status, offset, limit)),
  )
}

export function listCoordinationSuggestions() {
  return httpClient('/api/v1/coordination/suggestions')
}

export function applyCoordination(alertId, payload = {}, idempotencyKey) {
  return httpClient(`/api/v1/coordination/alerts/${encodeURIComponent(alertId)}/plans`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    idempotencyKey,
  })
}

export function listDirectives(status) {
  return fetchAllDirectives('/api/v1/coordination/directives', status)
}

export function getDirectiveCandidates(directiveId) {
  return httpClient(`/api/v1/coordination/directives/${encodeURIComponent(directiveId)}/candidates`)
}

export function fulfillDirective(directiveId, payload = {}, idempotencyKey) {
  return httpClient(
    `/api/v1/coordination/directives/${encodeURIComponent(directiveId)}/fulfillment`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      idempotencyKey,
    },
  )
}

export function listDepartmentDirectives(status) {
  return fetchAllDirectives('/api/v1/coordination/department-directives', status)
}

export function issueDepartmentDirective(departmentId, payload = {}, idempotencyKey) {
  return httpClient(
    `/api/v1/coordination/department-directives/${encodeURIComponent(departmentId)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      idempotencyKey,
    },
  )
}

export function acknowledgeDepartmentDirective(directiveId, payload = {}, idempotencyKey) {
  return httpClient(
    `/api/v1/alerts/department-directives/${encodeURIComponent(directiveId)}/acknowledgements`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      idempotencyKey,
    },
  )
}

export function submitDepartmentDirective(directiveId, payload = {}, idempotencyKey) {
  return httpClient(
    `/api/v1/alerts/department-directives/${encodeURIComponent(directiveId)}/submissions`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      idempotencyKey,
    },
  )
}

export function acceptDepartmentDirective(directiveId, payload = {}, idempotencyKey) {
  return httpClient(
    `/api/v1/alerts/department-directives/${encodeURIComponent(directiveId)}/acceptances`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      idempotencyKey,
    },
  )
}

export function requestDepartmentDirectiveRevision(directiveId, payload = {}, idempotencyKey) {
  return httpClient(
    `/api/v1/alerts/department-directives/${encodeURIComponent(directiveId)}/revision-requests`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      idempotencyKey,
    },
  )
}
