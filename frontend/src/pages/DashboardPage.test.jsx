import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { AttentionCard } from './DashboardPage.jsx'

const navigateMock = vi.hoisted(() => vi.fn())

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigateMock,
}))

describe('AttentionCard', () => {
  it('keeps details hidden until the card is hovered and closes on leave', () => {
    const summary = {
      total: 1,
      early_warning_count: 0,
      overload_count: 0,
      overdue_task_count: 1,
      items: [
        {
          id: 'task-1',
          source: 'task',
          category: 'overdue_task',
          title: 'Công việc quá hạn',
          message: 'Đã quá hạn 2 ngày.',
          employee_name: 'Nguyễn Văn A',
          department_id: 'department-1',
          department_name: 'Kinh doanh',
          days_overdue: 2,
          created_at: '2026-09-01T09:00:00Z',
        },
      ],
    }

    render(<AttentionCard summary={summary} role="manager" error="" isLoading={false} />)

    expect(screen.queryByText('Việc cần ưu tiên')).not.toBeInTheDocument()

    const card = screen.getAllByRole('button', { name: /Tổng việc cần xử lý/ }).at(-1).parentElement
    fireEvent.mouseEnter(card)
    expect(screen.getByText('Việc cần ưu tiên')).toBeInTheDocument()
    expect(screen.getByText('Quá hạn: 1')).toBeInTheDocument()

    fireEvent.mouseLeave(card)
    expect(screen.queryByText('Việc cần ưu tiên')).not.toBeInTheDocument()
  })

  it('groups leadership attention details by department in the popover', () => {
    const summary = {
      total: 3,
      early_warning_count: 1,
      overload_count: 1,
      overdue_task_count: 1,
      items: [
        {
          id: 'alert-1',
          source: 'alert',
          category: 'overload',
          title: 'Cảnh báo quá tải',
          message: 'Cần rà soát.',
          employee_name: 'Nhân viên Kinh doanh 1',
          department_id: 'department-1',
          department_name: 'Kinh doanh',
          created_at: '2026-09-03T09:00:00Z',
        },
        {
          id: 'alert-2',
          source: 'alert',
          category: 'early_warning',
          title: 'Dấu hiệu sớm',
          message: 'Cần theo dõi.',
          employee_name: 'Nhân viên Kinh doanh 2',
          department_id: 'department-1',
          department_name: 'Kinh doanh',
          created_at: '2026-09-03T10:00:00Z',
        },
        {
          id: 'task-1',
          source: 'task',
          category: 'overdue_task',
          title: 'Công việc quá hạn',
          message: 'Đã quá hạn.',
          employee_name: 'Nhân viên Kỹ thuật 1',
          department_id: 'department-2',
          department_name: 'Kỹ thuật',
          created_at: '2026-09-01T09:00:00Z',
          days_overdue: 2,
        },
      ],
    }

    render(<AttentionCard summary={summary} role="leadership" error="" isLoading={false} />)

    const card = screen.getAllByRole('button', { name: /Tổng việc cần xử lý/ }).at(-1).parentElement
    fireEvent.mouseEnter(card)

    expect(screen.getByText('Kinh doanh', { selector: 'span' })).toBeInTheDocument()
    expect(screen.getByText('Kỹ thuật')).toBeInTheDocument()
    expect(screen.getByText('Sớm: 1')).toBeInTheDocument()
    expect(screen.getAllByText('Quá tải: 1')).toHaveLength(2)
    expect(screen.getByText('Quá hạn: 1 việc')).toBeInTheDocument()
    expect(screen.queryByText('Nhân viên Kinh doanh 1')).not.toBeInTheDocument()
    expect(screen.queryByText('Nhân viên Kinh doanh 2')).not.toBeInTheDocument()
  })
})
