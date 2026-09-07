import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import ManagerTaskDirectives from './ManagerTaskDirectives.jsx'
import { acknowledgeDepartmentTaskDirective, listDepartmentTaskDirectives } from './tasksApi.js'

vi.mock('../../hooks/useRealtimeUpdates.js', () => ({
  useRealtimeUpdates: vi.fn(),
}))

vi.mock('./tasksApi.js', () => ({
  acknowledgeDepartmentTaskDirective: vi.fn(),
  listDepartmentTaskDirectives: vi.fn(),
}))

const pendingDirective = {
  id: 'directive-1',
  focus: 'overdue',
  selected_task_count: 2,
  task_ids: ['task-1', 'task-2'],
  status: 'pending',
  issued_at: '2026-09-05T08:00:00Z',
  note: 'Ưu tiên rà soát các công việc đã quá hạn.',
}

const acknowledgedDirective = {
  ...pendingDirective,
  status: 'acknowledged',
  action_note: 'Đã phân công xử lý và cập nhật tiến độ mỗi ngày.',
  commitment_date: '2026-09-08',
}

const tasks = [
  { id: 'task-1', title: 'Hoàn thiện báo cáo', status: 'done', is_overdue: false },
  { id: 'task-2', title: 'Rà soát hồ sơ', status: 'in_progress', is_overdue: true },
]

describe('ManagerTaskDirectives', () => {
  afterEach(cleanup)

  beforeEach(() => {
    listDepartmentTaskDirectives.mockReset()
    listDepartmentTaskDirectives
      .mockResolvedValueOnce([pendingDirective])
      .mockResolvedValue([acknowledgedDirective])
    acknowledgeDepartmentTaskDirective.mockReset()
    acknowledgeDepartmentTaskDirective.mockResolvedValue(acknowledgedDirective)
  })

  it('hiển thị trực tiếp chỉ thị khi vào trang Công việc không qua Trung tâm', async () => {
    render(
      <MemoryRouter initialEntries={['/manager/tasks']}>
        <ManagerTaskDirectives tasks={tasks} />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Giao việc quá hạn từ Lãnh đạo')).toBeInTheDocument()
    expect(screen.getByText('Tiếp nhận và lập kế hoạch')).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
  })

  it('hiển thị thông tin chỉ thị và tiến độ công việc liên quan', async () => {
    render(
      <MemoryRouter initialEntries={['/manager/tasks?task_directive=directive-1']}>
        <ManagerTaskDirectives tasks={tasks} />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Công việc quá hạn')).toBeInTheDocument()
    expect(
      screen.getByText('Giao việc quá hạn: Ưu tiên rà soát các công việc đã quá hạn.'),
    ).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
    expect(screen.getByText('1/2 công việc đã hoàn thành')).toBeInTheDocument()
    expect(screen.getByText('Hoàn thiện báo cáo')).toBeInTheDocument()
    expect(screen.getByText('Đã xong')).toBeInTheDocument()
    expect(screen.getByText('Quá hạn')).toBeInTheDocument()
  })

  it('hiển thị nhân viên và số ngày đã trễ hạn trong danh sách đầy đủ', async () => {
    const overdueDate = new Date()
    overdueDate.setDate(overdueDate.getDate() - 2)
    const overdueDateValue = [
      overdueDate.getFullYear(),
      String(overdueDate.getMonth() + 1).padStart(2, '0'),
      String(overdueDate.getDate()).padStart(2, '0'),
    ].join('-')

    render(
      <MemoryRouter initialEntries={['/manager/tasks?task_directive=directive-1']}>
        <ManagerTaskDirectives
          tasks={[
            { ...tasks[0], employee_name: 'Nguyễn Văn A' },
            {
              ...tasks[1],
              employee_name: 'Trần Thị B',
              due_date: overdueDateValue,
            },
          ]}
        />
      </MemoryRouter>,
    )

    fireEvent.click(
      await screen.findByRole('button', {
        name: 'Xem đầy đủ công việc trong giao việc quá hạn',
      }),
    )

    expect(screen.getByText('Nhân viên: Trần Thị B')).toBeInTheDocument()
    expect(screen.getByText('Đã trễ hạn 2 ngày')).toBeInTheDocument()
  })

  it('giữ lại kế hoạch và trạng thái sau khi Manager xác nhận', async () => {
    render(
      <MemoryRouter initialEntries={['/manager/tasks?task_directive=directive-1']}>
        <ManagerTaskDirectives tasks={tasks} />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Tiếp nhận và lập kế hoạch' }))
    fireEvent.change(screen.getByLabelText('Hành động dự kiến'), {
      target: { value: 'Đã phân công xử lý và cập nhật tiến độ mỗi ngày.' },
    })
    fireEvent.change(screen.getByLabelText('Ngày cam kết xử lý'), {
      target: { value: '2026-09-08' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận tiếp nhận' }))

    expect(await screen.findByText('Đã tiếp nhận việc quá hạn')).toBeInTheDocument()
    expect(
      await screen.findByText(
        'Kế hoạch của Quản lý: Đã phân công xử lý và cập nhật tiến độ mỗi ngày.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText(/Cam kết xử lý trước/)).toBeInTheDocument()
    expect(acknowledgeDepartmentTaskDirective).toHaveBeenCalledWith('directive-1', {
      action_note: 'Đã phân công xử lý và cập nhật tiến độ mỗi ngày.',
      commitment_date: '2026-09-08',
    })
  })

  it('ẩn card công việc khi chỉ thị đã được nghiệm thu', async () => {
    listDepartmentTaskDirectives.mockReset()
    listDepartmentTaskDirectives.mockResolvedValue([{ ...pendingDirective, status: 'accepted' }])

    render(
      <MemoryRouter initialEntries={['/manager/tasks']}>
        <ManagerTaskDirectives tasks={tasks} />
      </MemoryRouter>,
    )

    expect(
      await screen.findByText('Hiện chưa có giao việc quá hạn nào từ Lãnh đạo trong phòng ban.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Đã nghiệm thu việc quá hạn')).not.toBeInTheDocument()
  })
})
