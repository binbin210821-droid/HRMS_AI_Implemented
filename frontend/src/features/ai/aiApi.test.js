import { beforeEach, describe, expect, it, vi } from 'vitest'

const httpClientMock = vi.hoisted(() => vi.fn())

vi.mock('../../services/httpClient.js', () => ({ default: httpClientMock }))

import {
  getAlertActionProposal,
  getLeadershipActionProposal,
  streamAiChat,
  streamAiSummary,
} from './aiApi.js'

describe('aiApi', () => {
  beforeEach(() => {
    httpClientMock.mockReset()
    httpClientMock.mockResolvedValue({ alert_id: 'alert-1', summary: 'Đề xuất', actions: [] })
  })

  it('requests an alert proposal with POST and no client payload', async () => {
    await getAlertActionProposal('alert/1')

    expect(httpClientMock).toHaveBeenCalledWith('/api/v1/alerts/alert%2F1/ai-proposal', {
      method: 'POST',
    })
  })

  it('requests a Leadership proposal with POST and no client payload', async () => {
    await getLeadershipActionProposal()

    expect(httpClientMock).toHaveBeenCalledWith('/api/v1/ai/leadership-proposal', {
      method: 'POST',
    })
  })

  it('marks Dashboard requests as summary mode and sends refresh explicitly', async () => {
    const reader = {
      read: vi
        .fn()
        .mockResolvedValueOnce({
          done: false,
          value: new TextEncoder().encode('data: {"type":"done"}\n\n'),
        })
        .mockResolvedValueOnce({ done: true, value: new Uint8Array() }),
      releaseLock: vi.fn(),
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: { getReader: () => reader },
      }),
    )

    await streamAiSummary('Tóm tắt hôm nay', { forceRefresh: true })

    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/ai/chat/stream',
      expect.objectContaining({
        body: JSON.stringify({
          message: 'Tóm tắt hôm nay',
          mode: 'summary',
          refresh: true,
        }),
      }),
    )
    vi.unstubAllGlobals()
  })

  it('persists the server conversation id and sends it on the next turn', async () => {
    const reader = {
      read: vi
        .fn()
        .mockResolvedValueOnce({
          done: false,
          value: new TextEncoder().encode(
            'data: {"type":"conversation","conversation_id":"conv-1"}\n\n',
          ),
        })
        .mockResolvedValueOnce({ done: true, value: new Uint8Array() }),
      releaseLock: vi.fn(),
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: { getReader: () => reader },
      }),
    )

    const onConversation = vi.fn()
    await streamAiChat('Vì sao?', { conversationId: 'conv-1', onConversation })

    expect(onConversation).toHaveBeenCalledWith('conv-1')
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/ai/chat/stream',
      expect.objectContaining({
        body: JSON.stringify({ message: 'Vì sao?', conversation_id: 'conv-1' }),
      }),
    )
    vi.unstubAllGlobals()
  })
})
