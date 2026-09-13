import { csrfHeaders } from '../../services/csrf.js'
import httpClient from '../../services/httpClient.js'
import { useAuthStore } from '../../stores/authStore.js'

function parseSseBlock(block) {
  const dataLine = block.split('\n').find((line) => line.startsWith('data:'))
  if (!dataLine) return null

  try {
    return JSON.parse(dataLine.slice(5).trim())
  } catch {
    return null
  }
}

export async function streamAiChat(
  message,
  {
    onToken,
    onStatus,
    onConversation,
    onComplete,
    signal,
    mode = 'chat',
    forceRefresh = false,
    conversationId,
  } = {},
) {
  const response = await fetch('/api/v1/ai/chat/stream', {
    method: 'POST',
    headers: {
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
      ...csrfHeaders('POST'),
    },
    credentials: 'include',
    body: JSON.stringify(
      mode === 'summary'
        ? { message, mode, refresh: forceRefresh }
        : { message, ...(conversationId ? { conversation_id: conversationId } : {}) },
    ),
    signal,
  })

  if (response.status === 401) useAuthStore.getState().clearSession()

  if (!response.ok) {
    let payload = null
    try {
      payload = await response.json()
    } catch {
      // Giữ thông báo an toàn khi provider/proxy không trả JSON.
    }
    const error = new Error(payload?.message || 'Không thể kết nối với Trợ lý AI')
    error.status = response.status
    error.code = payload?.code
    error.details = payload?.details
    error.requestId = payload?.request_id || response.headers.get('X-Request-ID') || undefined
    throw error
  }
  if (!response.body) throw new Error('Trợ lý AI chưa thể mở luồng trả lời')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  function consumeBlocks(flush = false) {
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''
    if (flush && buffer) {
      blocks.push(buffer)
      buffer = ''
    }
    blocks.forEach((block) => {
      const payload = parseSseBlock(block)
      if (payload?.type === 'token' && payload.content) onToken?.(payload.content)
      if (payload?.type === 'status' && payload.content) onStatus?.(payload.content)
      if (payload?.type === 'conversation' && payload.conversation_id) {
        onConversation?.(payload.conversation_id)
      }
      if (payload?.type === 'error') throw new Error(payload.content)
      if (payload?.type === 'done') onComplete?.()
    })
  }

  try {
    let done = false
    while (!done) {
      const result = await reader.read()
      done = result.done
      const { value } = result
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
      consumeBlocks(done)
      if (done) break
    }
  } finally {
    reader.releaseLock()
  }
}

export function streamAiSummary(message, options = {}) {
  return streamAiChat(message, { ...options, mode: 'summary' })
}

export function getAlertActionProposal(alertId) {
  return httpClient(`/api/v1/alerts/${encodeURIComponent(alertId)}/ai-proposal`, {
    method: 'POST',
  })
}

export function getOverdueTaskActionProposal(taskId) {
  return httpClient(`/api/v1/tasks/${encodeURIComponent(taskId)}/ai-proposal`, {
    method: 'POST',
  })
}

export function getLeadershipActionProposal() {
  return httpClient('/api/v1/ai/leadership-proposal', {
    method: 'POST',
  })
}
