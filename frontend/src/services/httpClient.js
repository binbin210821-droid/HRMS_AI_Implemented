import { useAuthStore } from '../stores/authStore.js'
import { csrfHeaders } from './csrf.js'

export default async function httpClient(url, options = {}) {
  const { headers: optionHeaders, idempotencyKey, ...requestOptions } = options
  const method = requestOptions.method || 'GET'
  const idempotencyHeaders =
    idempotencyKey && !['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase())
      ? { 'Idempotency-Key': idempotencyKey }
      : {}
  const response = await fetch(url, {
    ...requestOptions,
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      ...csrfHeaders(method),
      ...idempotencyHeaders,
      ...optionHeaders,
    },
  })

  if (response.status === 401) useAuthStore.getState().clearSession()

  if (!response.ok) {
    let detail = ''
    let payload = null
    try {
      payload = await response.json()
      detail =
        typeof payload?.message === 'string'
          ? payload.message
          : typeof payload?.detail === 'string'
            ? payload.detail
            : ''
    } catch {
      // Một số lỗi hạ tầng không trả về JSON; giữ thông báo mặc định bên dưới.
    }
    const error = new Error(detail || `Yêu cầu thất bại: ${response.status}`)
    error.status = response.status
    error.detail = detail
    error.code = typeof payload?.code === 'string' ? payload.code : undefined
    error.details = payload?.details ?? undefined
    error.requestId =
      typeof payload?.request_id === 'string'
        ? payload.request_id
        : response.headers.get('X-Request-ID') || undefined
    throw error
  }

  if (response.status === 204) return null

  return response.json()
}
