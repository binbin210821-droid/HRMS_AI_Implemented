import { beforeEach, describe, expect, it, vi } from 'vitest'

const httpClientMock = vi.hoisted(() => vi.fn())

vi.mock('../../services/httpClient.js', () => ({ default: httpClientMock }))

import { completeUploadSession, createUploadSession } from './attachmentsApi.js'

describe('attachmentsApi idempotency', () => {
  beforeEach(() => {
    httpClientMock.mockReset()
    httpClientMock.mockResolvedValue({})
  })

  it('passes independent keys for upload creation and completion', async () => {
    await createUploadSession({ file_name: 'evidence.pdf' }, 'upload-create-key')
    await completeUploadSession('session-1', 'upload-complete-key')

    expect(httpClientMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/upload-sessions',
      expect.objectContaining({ idempotencyKey: 'upload-create-key' }),
    )
    expect(httpClientMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/upload-sessions/session-1/completions',
      expect.objectContaining({ idempotencyKey: 'upload-complete-key' }),
    )
  })
})
