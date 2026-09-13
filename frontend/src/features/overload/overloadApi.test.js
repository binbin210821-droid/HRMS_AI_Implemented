import { beforeEach, describe, expect, it, vi } from 'vitest'

const httpClientMock = vi.hoisted(() => vi.fn())

vi.mock('../../services/httpClient.js', () => ({ default: httpClientMock }))

import { listOverloadLogs } from './overloadApi.js'
import { clearRequestCoordinator } from '../../services/requestCoordinator.js'

describe('overloadApi', () => {
  beforeEach(() => {
    httpClientMock.mockReset()
    clearRequestCoordinator()
    vi.restoreAllMocks()
  })

  it('requests 100 overload logs and unwraps the page', async () => {
    httpClientMock.mockResolvedValue({ items: [{ id: 'overload-1' }], has_next: false })

    await expect(listOverloadLogs()).resolves.toEqual([{ id: 'overload-1' }])
    expect(httpClientMock).toHaveBeenCalledWith('/api/v1/overload?page_size=100')
  })

  it('passes the selected date range and loads every overload page', async () => {
    httpClientMock
      .mockResolvedValueOnce({ items: [{ id: 'overload-1' }], has_next: true })
      .mockResolvedValueOnce({ items: [{ id: 'overload-2' }], has_next: false })

    await expect(
      listOverloadLogs({ startDate: '2026-09-01', endDate: '2026-09-30' }),
    ).resolves.toEqual([{ id: 'overload-1' }, { id: 'overload-2' }])
    expect(httpClientMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/overload?page_size=100&from=2026-09-01&to=2026-09-30',
    )
    expect(httpClientMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/overload?page_size=100&from=2026-09-01&to=2026-09-30&page=2',
    )
  })
})
