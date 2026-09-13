const cache = new Map()
const inFlight = new Map()
let sessionGeneration = 0

const DEFAULT_TTL_MS = 750

function cacheKey(resource, requestKey) {
  return `${sessionGeneration}:${resource}:${requestKey}`
}

/**
 * Dedupe các request đọc giống nhau trong một khoảng rất ngắn.
 *
 * Đây không phải cache nghiệp vụ dài hạn: dữ liệu realtime vẫn được làm mới
 * qua invalidateResource() sau mutation hoặc event liên quan.
 */
export function coordinatedRequest(
  resource,
  requestKey,
  loader,
  { ttlMs = DEFAULT_TTL_MS, force = false } = {},
) {
  const key = cacheKey(resource, requestKey)
  if (force) cache.delete(key)

  const pending = inFlight.get(key)
  if (pending) return pending

  const cached = cache.get(key)
  if (!force && cached && cached.expiresAt > Date.now()) {
    return Promise.resolve(cached.value)
  }

  const request = Promise.resolve()
    .then(loader)
    .then((value) => {
      if (ttlMs > 0) cache.set(key, { value, expiresAt: Date.now() + ttlMs })
      return value
    })
    .finally(() => {
      inFlight.delete(key)
    })

  inFlight.set(key, request)
  return request
}

export function invalidateResource(resource) {
  const prefix = `${sessionGeneration}:${resource}:`
  for (const key of cache.keys()) {
    if (key.startsWith(prefix)) cache.delete(key)
  }
}

export function rotateRequestSession() {
  sessionGeneration += 1
  cache.clear()
  inFlight.clear()
}

export function clearRequestCoordinator() {
  cache.clear()
  inFlight.clear()
}
