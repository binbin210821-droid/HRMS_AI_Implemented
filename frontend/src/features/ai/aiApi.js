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

export async function streamAiChat(message, { onToken, onComplete, signal } = {}) {
  const token = useAuthStore.getState().token
  const response = await fetch('/api/ai/chat/stream', {
    method: 'POST',
    headers: {
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message }),
    signal,
  })

  if (!response.ok) throw new Error('Không thể kết nối với Trợ lý AI')
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
