import { beforeEach, describe, expect, it, vi } from 'vitest'

const httpClientMock = vi.hoisted(() => vi.fn())

vi.mock('../../services/httpClient.js', () => ({ default: httpClientMock }))

import {
  acceptDepartmentDirective,
  acknowledgeDepartmentDirective,
  applyCoordination,
  fulfillDirective,
  issueDepartmentDirective,
  listDepartmentDirectives,
  listDirectives,
  requestDepartmentDirectiveRevision,
  submitDepartmentDirective,
} from './coordinationApi.js'

describe('coordinationApi idempotency', () => {
  beforeEach(() => {
    httpClientMock.mockReset()
    httpClientMock.mockResolvedValue({})
  })

  it('passes the caller-owned key to every mutating coordination action', async () => {
    const key = 'coordination-key'
    await applyCoordination('alert-1', { note: 'Điều phối' }, key)
    await fulfillDirective('directive-1', { target_employee_id: 'employee-1' }, key)
    await issueDepartmentDirective('department-1', { note: 'Theo dõi' }, key)
    await acknowledgeDepartmentDirective('directive-1', { note: 'Đã nhận' }, key)
    await submitDepartmentDirective('directive-1', { completion_note: 'Đã xong' }, key)
    await acceptDepartmentDirective('directive-1', { note: 'Đạt' }, key)
    await requestDepartmentDirectiveRevision('directive-1', { note: 'Bổ sung' }, key)

    expect(httpClientMock.mock.calls).toHaveLength(7)
    for (const [, options] of httpClientMock.mock.calls) {
      expect(options).toEqual(expect.objectContaining({ idempotencyKey: key }))
    }
  })

  it('uses the v1 alert directive POST action routes', async () => {
    await acknowledgeDepartmentDirective('directive/1', { note: 'Đã nhận' }, 'key-1')
    await submitDepartmentDirective('directive/1', { completion_note: 'Đã xong' }, 'key-2')
    await acceptDepartmentDirective('directive/1', { note: 'Đạt' }, 'key-3')
    await requestDepartmentDirectiveRevision('directive/1', { note: 'Bổ sung' }, 'key-4')

    expect(
      httpClientMock.mock.calls.slice(0, 4).map(([url, options]) => [url, options.method]),
    ).toEqual([
      ['/api/v1/alerts/department-directives/directive%2F1/acknowledgements', 'POST'],
      ['/api/v1/alerts/department-directives/directive%2F1/submissions', 'POST'],
      ['/api/v1/alerts/department-directives/directive%2F1/acceptances', 'POST'],
      ['/api/v1/alerts/department-directives/directive%2F1/revision-requests', 'POST'],
    ])
  })

  it('loads every page for coordination and alert directives', async () => {
    const firstPage = Array.from({ length: 100 }, (_, index) => ({ id: `directive-${index}` }))
    httpClientMock
      .mockResolvedValueOnce(firstPage)
      .mockResolvedValueOnce([{ id: 'directive-100' }])
      .mockResolvedValueOnce(firstPage)
      .mockResolvedValueOnce([{ id: 'alert-directive-100' }])

    await expect(listDirectives('pending')).resolves.toHaveLength(101)
    await expect(listDepartmentDirectives('acknowledged')).resolves.toHaveLength(101)

    expect(httpClientMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/coordination/directives?offset=0&limit=100&status=pending',
    )
    expect(httpClientMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/coordination/directives?offset=100&limit=100&status=pending',
    )
    expect(httpClientMock).toHaveBeenNthCalledWith(
      3,
      '/api/v1/coordination/department-directives?offset=0&limit=100&status=acknowledged',
    )
    expect(httpClientMock).toHaveBeenNthCalledWith(
      4,
      '/api/v1/coordination/department-directives?offset=100&limit=100&status=acknowledged',
    )
  })
})
