import httpClient from '../../services/httpClient.js'

export function createUploadSession(payload) {
  return httpClient('/api/attachments/upload-sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function completeUploadSession(sessionId) {
  return httpClient(`/api/attachments/upload-sessions/${encodeURIComponent(sessionId)}/complete`, {
    method: 'POST',
  })
}

export function cancelUploadSession(sessionId) {
  return httpClient(`/api/attachments/upload-sessions/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
  })
}
