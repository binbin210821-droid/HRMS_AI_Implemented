const STORAGE_PREFIX = 'workmind:ai-suggestion:'

export function makeAiSuggestionKey(scope, identity = 'default') {
  return `${STORAGE_PREFIX}${scope}:${identity}`
}

export function readAiSuggestion(key) {
  if (typeof window === 'undefined') return null

  try {
    const value = window.sessionStorage.getItem(key)
    return value ? JSON.parse(value) : null
  } catch {
    return null
  }
}

export function writeAiSuggestion(key, value) {
  if (typeof window === 'undefined') return

  try {
    window.sessionStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Bộ nhớ phiên có thể bị tắt hoặc đầy; giao diện vẫn hoạt động bình thường.
  }
}

export function removeAiSuggestion(key) {
  if (typeof window === 'undefined') return

  try {
    window.sessionStorage.removeItem(key)
  } catch {
    // Không để lỗi bộ nhớ ảnh hưởng tới luồng nghiệp vụ chính.
  }
}
