import { afterEach, describe, expect, it, vi } from 'vitest'

import httpClient from './httpClient.js'

const originalFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = originalFetch
  vi.restoreAllMocks()
  document.cookie = 'hrms_csrf_token=; Max-Age=0'
})

describe('httpClient', () => {
  it('sends credentials, csrf and optional idempotency key', async () => {
    document.cookie = 'hrms_csrf_token=csrf-123'
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }))

    await httpClient('/api/v1/items', {
      method: 'POST',
      idempotencyKey: 'item-1',
      body: JSON.stringify({ value: 'a' }),
    })

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/items',
      expect.objectContaining({
        credentials: 'include',
        headers: expect.objectContaining({
          'X-CSRF-Token': 'csrf-123',
          'Idempotency-Key': 'item-1',
        }),
      }),
    )
  })

  it('maps the backend error contract and request id', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          code: 'validation_error',
          message: 'Dữ liệu không hợp lệ',
          details: [{ field: 'name' }],
          request_id: 'req-123',
        }),
        { status: 422, headers: { 'X-Request-ID': 'req-123' } },
      ),
    )

    await expect(httpClient('/api/v1/items')).rejects.toMatchObject({
      message: 'Dữ liệu không hợp lệ',
      status: 422,
      code: 'validation_error',
      requestId: 'req-123',
      details: [{ field: 'name' }],
    })
  })
})
