const DEFAULT_CSRF_COOKIE_NAME = 'hrms_csrf_token'

function getCookie(name) {
  if (typeof document === 'undefined') return ''
  const prefix = `${encodeURIComponent(name)}=`
  const item = document.cookie.split('; ').find((entry) => entry.startsWith(prefix))
  return item ? decodeURIComponent(item.slice(prefix.length)) : ''
}

export function getCsrfToken() {
  const cookieName = import.meta.env.VITE_AUTH_CSRF_COOKIE_NAME || DEFAULT_CSRF_COOKIE_NAME
  return getCookie(cookieName)
}

export function csrfHeaders(method = 'GET') {
  if (['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method.toUpperCase())) return {}
  const token = getCsrfToken()
  return token ? { 'X-CSRF-Token': token } : {}
}
