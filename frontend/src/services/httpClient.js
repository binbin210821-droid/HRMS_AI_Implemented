import { useAuthStore } from '../stores/authStore.js'

export default async function httpClient(url, options = {}) {
  const token = useAuthStore.getState().token
  const { headers: optionHeaders, ...requestOptions } = options
  const response = await fetch(url, {
    ...requestOptions,
    headers: {
      Accept: 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...optionHeaders,
    },
  })

  if (!response.ok) {
    let detail = ''
    try {
      const payload = await response.json()
      detail = typeof payload?.detail === 'string' ? payload.detail : ''
    } catch {
      // Một số lỗi hạ tầng không trả về JSON; giữ thông báo mặc định bên dưới.
    }
    const error = new Error(detail || `Yêu cầu thất bại: ${response.status}`)
    error.status = response.status
    error.detail = detail
    throw error
  }

  if (response.status === 204) return null

  return response.json()
}
