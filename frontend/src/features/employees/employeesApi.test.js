import { beforeEach, describe, expect, it, vi } from 'vitest'

const httpClientMock = vi.hoisted(() => vi.fn())

vi.mock('../../services/httpClient.js', () => ({ default: httpClientMock }))

import { createEmployee, deleteEmployee, listEmployees, updateEmployee } from './employeesApi.js'

describe('employeesApi', () => {
  beforeEach(() => {
    httpClientMock.mockReset()
    vi.restoreAllMocks()
  })

  it('unwraps the first v1 page and preserves the department filter', async () => {
    httpClientMock.mockResolvedValue({ items: [{ id: 'employee-1' }], has_next: false })

    await expect(listEmployees('department-1')).resolves.toEqual([{ id: 'employee-1' }])
    expect(httpClientMock).toHaveBeenCalledWith(
      '/api/v1/employees?page=1&page_size=20&department_id=department-1',
    )
  })

  it('uses v1 paths for employee CRUD', async () => {
    httpClientMock.mockResolvedValue({ items: [], has_next: false })

    await createEmployee({ full_name: 'Nguyễn Văn A' })
    await updateEmployee('employee-1', { full_name: 'Nguyễn Văn B' })
    await deleteEmployee('employee-1')

    expect(httpClientMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/v1/employees',
      '/api/v1/employees/employee-1',
      '/api/v1/employees/employee-1',
    ])
  })
})
