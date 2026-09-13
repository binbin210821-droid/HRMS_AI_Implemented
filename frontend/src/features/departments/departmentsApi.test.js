import { beforeEach, describe, expect, it, vi } from 'vitest'

const httpClientMock = vi.hoisted(() => vi.fn())

vi.mock('../../services/httpClient.js', () => ({ default: httpClientMock }))

import {
  createDepartment,
  deleteDepartment,
  listDepartments,
  updateDepartment,
} from './departmentsApi.js'

describe('departmentsApi', () => {
  beforeEach(() => {
    httpClientMock.mockReset()
    vi.restoreAllMocks()
  })

  it('unwraps the first v1 page and warns if more pages exist', async () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => {})
    httpClientMock.mockResolvedValue({ items: [{ id: 'department-1' }], has_next: true })

    await expect(listDepartments()).resolves.toEqual([{ id: 'department-1' }])
    expect(httpClientMock).toHaveBeenCalledWith('/api/v1/departments?page=1&page_size=20')
    expect(warning).toHaveBeenCalledOnce()
  })

  it('uses v1 paths for department CRUD', async () => {
    httpClientMock.mockResolvedValue({ items: [], has_next: false })

    await createDepartment({ name: 'Kinh doanh', code: 'KD' })
    await updateDepartment('department-1', { name: 'Kinh doanh mới' })
    await deleteDepartment('department-1')

    expect(httpClientMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/v1/departments',
      '/api/v1/departments/department-1',
      '/api/v1/departments/department-1',
    ])
  })
})
