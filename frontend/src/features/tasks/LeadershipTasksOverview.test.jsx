import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import LeadershipTasksOverview from './LeadershipTasksOverview.jsx'
import {
  getDepartmentTaskPortfolio,
  getLeadershipTaskOverview,
  issueDepartmentTaskDirective,
  listDepartmentTaskDirectives,
} from './tasksApi.js'

vi.mock('../../components/layout/MainLayout.jsx', () => ({
  default: ({ children }) => <main>{children}</main>,
}))

vi.mock('../../hooks/useRealtimeUpdates.js', () => ({
  REALTIME_COALESCE_DELAY: 250,
  useRealtimeUpdates: vi.fn(),
}))

vi.mock('./tasksApi.js', () => ({
  getDepartmentTaskPortfolio: vi.fn(),
  getLeadershipTaskOverview: vi.fn(),
  issueDepartmentTaskDirective: vi.fn(),
  listDepartmentTaskDirectives: vi.fn(),
}))

const overview = {
  range: '30d',
  period_start: '2026-08-07',
  period_end: '2026-09-05',
  departments_with_tasks: 2,
  departments_need_attention: 1,
  departments_overdue: 1,
  departments_due_soon: 1,
  completion_trend: [{ week_start: '2026-09-01', label: '01/09', completed_count: 3 }],
  departments: [
    {
      department_id: 'department-kd',
      department_name: 'Kinh doanh',
      department_code: 'KD',
      manager_name: 'Quản lý Kinh doanh',
      total_count: 8,
      open_count: 4,
      overdue_count: 2,
      due_soon_count: 1,
      high_priority_open_count: 1,
      completed_in_period_count: 4,
      oldest_overdue_date: '2026-09-01',
      undirected_at_risk_count: 2,
      undirected_overdue_count: 2,
    },
  ],
}

describe('LeadershipTasksOverview', () => {
  beforeEach(() => {
    getLeadershipTaskOverview.mockResolvedValue(overview)
    listDepartmentTaskDirectives.mockResolvedValue([])
    issueDepartmentTaskDirective.mockReset()
  })

  it('hiển thị số liệu theo phòng ban và không có thao tác quản lý nhân viên', async () => {
    render(
      <MemoryRouter>
        <LeadershipTasksOverview />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Tình hình công việc theo phòng ban')).toBeInTheDocument()
    expect(screen.getByText('Kinh doanh')).toBeInTheDocument()
    expect(screen.getByText('2 công việc quá hạn chưa gửi chỉ thị')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Xem chi tiết' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ra chỉ thị cho Quản lý' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Thêm công việc/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Sửa' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Xóa' })).not.toBeInTheDocument()
    expect(screen.queryByText('Người phụ trách')).not.toBeInTheDocument()
  })

  it('đóng được modal khi mở từ deep-link trên notification belt', async () => {
    getDepartmentTaskPortfolio.mockResolvedValue({
      range: '30d',
      overdue: [],
      due_soon: [],
      high_priority: [],
      on_track: [],
      completed_in_period: [],
    })

    render(
      <MemoryRouter
        initialEntries={[
          '/leadership/tasks?task=task-1&deadline=overdue&department_id=department-kd',
        ]}
      >
        <LeadershipTasksOverview />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Đóng cửa sổ' }))

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('lọc được việc đã ra chỉ thị và cho phép chọn việc quá hạn chưa ra chỉ thị', async () => {
    getDepartmentTaskPortfolio.mockResolvedValue({
      range: '30d',
      overdue: [
        {
          id: 'task-unsent',
          title: 'Công việc chưa gửi',
          priority: 'high',
          status: 'in_progress',
          due_date: '2026-09-01',
          is_overdue: true,
          subtask_count: 0,
          directive_id: null,
          directive_status: null,
        },
        {
          id: 'task-sent',
          title: 'Công việc đã gửi',
          priority: 'high',
          status: 'in_progress',
          due_date: '2026-09-01',
          is_overdue: true,
          subtask_count: 0,
          directive_id: 'directive-1',
          directive_status: 'pending',
        },
      ],
      due_soon: [],
      high_priority: [],
      on_track: [],
      completed_in_period: [],
    })

    render(
      <MemoryRouter>
        <LeadershipTasksOverview />
      </MemoryRouter>,
    )

    const directiveButtons = await screen.findAllByRole('button', {
      name: 'Ra chỉ thị cho Quản lý',
    })
    fireEvent.click(directiveButtons.at(-1))
    const filter = await screen.findByLabelText('Lọc trạng thái chỉ thị')
    expect(filter).toHaveValue('not_directed')

    expect(screen.getByText('Đang quá hạn (1)')).toBeInTheDocument()
    expect(screen.getByText('Công việc chưa gửi')).toBeInTheDocument()
    expect(screen.getAllByText('Chưa ra chỉ thị').length).toBeGreaterThanOrEqual(2)
    expect(screen.queryByText('Công việc đã gửi')).not.toBeInTheDocument()
    fireEvent.change(filter, { target: { value: 'all' } })
    expect(screen.getByText('Đã ra chỉ thị · Chờ tiếp nhận')).toBeInTheDocument()
    fireEvent.change(filter, { target: { value: 'not_directed' } })
    fireEvent.click(screen.getByRole('button', { name: 'Thêm vào chỉ thị' }))
    expect(screen.getByText('Đã chọn 1 công việc quá hạn chưa ra chỉ thị.')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Ra chỉ thị cho 1 việc đã chọn' }))
    expect(
      await screen.findByText('Đã chọn 1 công việc quá hạn để đưa vào chỉ thị.'),
    ).toBeInTheDocument()
    issueDepartmentTaskDirective.mockResolvedValue({})
    fireEvent.click(screen.getByRole('button', { name: 'Gửi chỉ thị cho 1 việc' }))
    await waitFor(() => {
      expect(issueDepartmentTaskDirective).toHaveBeenCalledWith(
        'department-kd',
        {
          focus: 'overdue',
          note: '',
          task_ids: ['task-unsent'],
        },
        expect.any(String),
      )
    })
  })

  it('đưa việc đã nghiệm thu trước đó trở lại nhóm có thể ra chỉ thị mới', async () => {
    getDepartmentTaskPortfolio.mockResolvedValue({
      range: '30d',
      overdue: [
        {
          id: 'task-reopened',
          title: 'Công việc đã mở lại',
          priority: 'high',
          status: 'todo',
          due_date: '2026-09-01',
          is_overdue: true,
          subtask_count: 0,
          directive_id: 'directive-accepted',
          directive_status: 'accepted',
          has_active_directive: false,
        },
        {
          id: 'task-active',
          title: 'Công việc đang có chỉ thị',
          priority: 'high',
          status: 'in_progress',
          due_date: '2026-09-01',
          is_overdue: true,
          subtask_count: 0,
          directive_id: 'directive-pending',
          directive_status: 'pending',
          has_active_directive: true,
        },
      ],
      due_soon: [],
      high_priority: [],
      on_track: [],
      completed_in_period: [],
    })

    render(
      <MemoryRouter>
        <LeadershipTasksOverview />
      </MemoryRouter>,
    )

    const directiveButtons = await screen.findAllByRole('button', {
      name: 'Ra chỉ thị cho Quản lý',
    })
    fireEvent.click(directiveButtons.at(-1))

    expect(await screen.findByText('Đang quá hạn (1)')).toBeInTheDocument()
    expect(await screen.findByText('Công việc đã mở lại')).toBeInTheDocument()
    expect(screen.queryByText('Công việc đang có chỉ thị')).not.toBeInTheDocument()
    expect(screen.getByText('Đã nghiệm thu trước đó · Có thể ra chỉ thị mới')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Thêm vào chỉ thị' }))
    expect(screen.getByText('Đã chọn 1 công việc quá hạn chưa ra chỉ thị.')).toBeInTheDocument()
  })
})
