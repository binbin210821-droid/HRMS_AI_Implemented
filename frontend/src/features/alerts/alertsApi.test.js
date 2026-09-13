import { beforeEach, describe, expect, it, vi } from 'vitest'

const httpClientMock = vi.hoisted(() => vi.fn())

vi.mock('../../services/httpClient.js', () => ({ default: httpClientMock }))

import { listAlerts, resolveAlert } from './alertsApi.js'
import { clearRequestCoordinator } from '../../services/requestCoordinator.js'

describe('alertsApi', () => {
  beforeEach(() => {
    httpClientMock.mockReset()
    clearRequestCoordinator()
    vi.restoreAllMocks()
  })

  it('requests 100 alerts without warning when the page is complete', async () => {
    httpClientMock.mockResolvedValue({ items: [{ id: 'alert-1' }], has_next: false })

    await expect(listAlerts('open', 'all')).resolves.toEqual([{ id: 'alert-1' }])
    expect(httpClientMock).toHaveBeenCalledWith(
      '/api/v1/alerts?status=open&alert_type=all&page_size=100',
    )
  })

  it('passes the selected date range and loads every alert page', async () => {
    httpClientMock
      .mockResolvedValueOnce({ items: [{ id: 'alert-1' }], has_next: true })
      .mockResolvedValueOnce({ items: [{ id: 'alert-2' }], has_next: false })

    await expect(
      listAlerts(undefined, 'all', { startDate: '2026-09-01', endDate: '2026-09-30' }),
    ).resolves.toEqual([{ id: 'alert-1' }, { id: 'alert-2' }])
    expect(httpClientMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/alerts?alert_type=all&from=2026-09-01&to=2026-09-30&page_size=100',
    )
    expect(httpClientMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/alerts?alert_type=all&from=2026-09-01&to=2026-09-30&page_size=100&page=2',
    )
  })

  it('sends the v1 resolved status when resolving an alert', async () => {
    httpClientMock.mockResolvedValue({ id: 'alert-1', status: 'resolved' })

    await expect(resolveAlert('alert-1', 'Đã xử lý')).resolves.toEqual({
      id: 'alert-1',
      status: 'resolved',
    })

    expect(httpClientMock).toHaveBeenCalledWith('/api/v1/alerts/alert-1', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'resolved', resolution_note: 'Đã xử lý' }),
    })
  })
})
