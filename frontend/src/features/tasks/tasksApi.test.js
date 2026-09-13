import { beforeEach, describe, expect, it, vi } from 'vitest'

const httpClientMock = vi.hoisted(() => vi.fn())

vi.mock('../../services/httpClient.js', () => ({ default: httpClientMock }))

import {
  acceptDepartmentTaskDirective,
  acknowledgeDepartmentTaskDirective,
  listDepartmentTaskDirectives,
  listTasks,
  requestTaskDirectiveRevision,
  submitDepartmentTaskDirective,
} from './tasksApi.js'
import { clearRequestCoordinator } from '../../services/requestCoordinator.js'

describe('tasksApi', () => {
  beforeEach(() => {
    httpClientMock.mockReset()
    clearRequestCoordinator()
    vi.restoreAllMocks()
  })

  it('loads all task pages when the first page is full', async () => {
    httpClientMock
      .mockResolvedValueOnce({ items: [{ id: 'task-1' }], has_next: true })
      .mockResolvedValueOnce({ items: [{ id: 'task-2' }], has_next: false })

    await expect(
      listTasks({ employeeId: 'employee-1', status: 'todo', overdueOnly: true }),
    ).resolves.toEqual([{ id: 'task-1' }, { id: 'task-2' }])
    expect(httpClientMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/tasks?employee_id=employee-1&status=todo&overdue_only=true&page_size=100',
    )
    expect(httpClientMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/tasks?employee_id=employee-1&status=todo&overdue_only=true&page_size=100&page=2',
    )
  })

  it('requests the leadership-wide task list without a department filter', async () => {
    httpClientMock.mockResolvedValue({
      items: [{ id: 'task-1', department_id: 'department-1' }],
      has_next: false,
    })

    await expect(listTasks()).resolves.toEqual([{ id: 'task-1', department_id: 'department-1' }])
    expect(httpClientMock).toHaveBeenCalledWith('/api/v1/tasks?page_size=100')
  })

  it('uses the v1 POST action routes for task directives', async () => {
    await acknowledgeDepartmentTaskDirective('directive/1', { note: 'Đã nhận' }, 'key-1')
    await submitDepartmentTaskDirective('directive/1', { completion_note: 'Đã xong' }, 'key-2')
    await acceptDepartmentTaskDirective('directive/1', { note: 'Đạt' }, 'key-3')
    await requestTaskDirectiveRevision('directive/1', { note: 'Bổ sung' }, 'key-4')

    expect(httpClientMock.mock.calls.map(([url, options]) => [url, options.method])).toEqual([
      ['/api/v1/tasks/department-directives/directive%2F1/acknowledgements', 'POST'],
      ['/api/v1/tasks/department-directives/directive%2F1/submissions', 'POST'],
      ['/api/v1/tasks/department-directives/directive%2F1/acceptances', 'POST'],
      ['/api/v1/tasks/department-directives/directive%2F1/revision-requests', 'POST'],
    ])
  })

  it('loads every page for task directives', async () => {
    const firstPage = Array.from({ length: 100 }, (_, index) => ({ id: `directive-${index}` }))
    httpClientMock.mockResolvedValueOnce(firstPage).mockResolvedValueOnce([{ id: 'directive-100' }])

    await expect(listDepartmentTaskDirectives('pending')).resolves.toHaveLength(101)
    expect(httpClientMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/tasks/department-directives?offset=0&limit=100&status=pending',
    )
    expect(httpClientMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/tasks/department-directives?offset=100&limit=100&status=pending',
    )
  })
})
