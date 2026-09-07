import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AttentionPanel from './AttentionPanel.jsx'

const navigateMock = vi.hoisted(() => vi.fn())

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigateMock,
}))

beforeEach(() => {
  navigateMock.mockReset()
})

describe('AttentionPanel', () => {
  it('shows the three attention categories and opens the exact task', () => {
    render(
      <AttentionPanel
        role="manager"
        summary={{
          total: 3,
          early_warning_count: 1,
          overload_count: 1,
          overdue_task_count: 1,
          generated_at: '2026-09-03T10:00:00Z',
          items: [
            {
              id: 'alert-1',
              source: 'alert',
              category: 'overload',
              title: 'Nhân viên có dấu hiệu quá tải',
              message: 'Cần xử lý.',
              employee_name: 'Nguyễn Văn A',
              department_id: 'department-1',
              department_name: 'Kinh doanh',
              severity: 'high',
              created_at: '2026-09-03T09:00:00Z',
            },
            {
              id: 'task-1',
              source: 'task',
              category: 'overdue_task',
              title: 'Hoàn tất báo cáo tháng',
              message: 'Đã quá hạn 3 ngày.',
              employee_id: 'employee-2',
              employee_name: 'Nguyễn Văn B',
              department_id: 'department-1',
              department_name: 'Kinh doanh',
              created_at: '2026-09-01T09:00:00Z',
              due_date: '2026-08-31',
              days_overdue: 3,
            },
            {
              id: 'alert-2',
              source: 'alert',
              category: 'early_warning',
              title: 'Theo dõi chất lượng công việc',
              message: 'Chất lượng có dấu hiệu giảm.',
              employee_name: 'Nguyễn Văn C',
              department_id: 'department-1',
              department_name: 'Kinh doanh',
              severity: 'medium',
              created_at: '2026-09-02T09:00:00Z',
            },
          ],
        }}
      />,
    )

    expect(screen.getByText('Dấu hiệu sớm')).toBeInTheDocument()
    expect(screen.getByText('Quá tải')).toBeInTheDocument()
    expect(screen.getByText('Công việc quá hạn')).toBeInTheDocument()
    expect(screen.getByText('Nhân viên có dấu hiệu quá tải')).toBeInTheDocument()
    expect(screen.getByText('Hoàn tất báo cáo tháng')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Xem và xử lý Hoàn tất báo cáo tháng' }))

    expect(navigateMock).toHaveBeenCalledWith(
      '/manager/tasks?task=task-1&deadline=overdue&employee_id=employee-2',
    )
  })

  it('shows a friendly empty state when there is nothing to follow up', () => {
    render(<AttentionPanel role="leadership" summary={{ total: 0, items: [] }} error="" />)

    expect(screen.getByText('Hiện không có việc nào cần theo dõi.')).toBeInTheDocument()
  })

  it('passes exact alert filters when opening an alert', () => {
    render(
      <AttentionPanel
        role="manager"
        summary={{
          total: 1,
          items: [
            {
              id: 'alert-1',
              source: 'alert',
              category: 'overload',
              severity: 'high',
              title: 'Cảnh báo quá tải',
              message: 'Cần xử lý.',
              employee_id: 'employee-1',
              employee_name: 'Nguyễn Văn A',
              department_id: 'department-1',
              department_name: 'Kinh doanh',
              created_at: '2026-09-03T09:00:00Z',
            },
          ],
        }}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Xem và xử lý Cảnh báo quá tải' }))

    expect(navigateMock).toHaveBeenCalledWith(
      '/manager/alerts?alert=alert-1&status=open&alert_type=overload&severity=high&employee_id=employee-1&department_id=department-1',
    )
  })

  it('filters leadership overdue tasks by department instead of employee', () => {
    render(
      <AttentionPanel
        role="leadership"
        summary={{
          total: 1,
          items: [
            {
              id: 'task-1',
              source: 'task',
              category: 'overdue_task',
              title: 'Công việc quá hạn',
              message: 'Cần xử lý.',
              employee_id: 'employee-1',
              employee_name: 'Nguyễn Văn A',
              department_id: 'department-1',
              department_name: 'Kinh doanh',
            },
          ],
        }}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Xem và xử lý Công việc quá hạn' }))

    expect(navigateMock).toHaveBeenCalledWith(
      '/leadership/tasks?task=task-1&deadline=overdue&department_id=department-1',
    )
  })
})
