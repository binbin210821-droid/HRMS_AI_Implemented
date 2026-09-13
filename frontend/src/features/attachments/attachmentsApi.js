import httpClient from '../../services/httpClient.js'

export function createUploadSession(payload, idempotencyKey) {
  return httpClient('/api/v1/upload-sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    idempotencyKey,
  })
}

export function completeUploadSession(sessionId, idempotencyKey) {
  return httpClient(`/api/v1/upload-sessions/${encodeURIComponent(sessionId)}/completions`, {
    method: 'POST',
    idempotencyKey,
  })
}

export function cancelUploadSession(sessionId) {
  return httpClient(`/api/v1/upload-sessions/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
  })
}
