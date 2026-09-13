import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import NotificationBell from './NotificationBell.jsx'
import { listAlerts } from '../alerts/alertsApi.js'
import { listDepartmentDirectives, listDirectives } from '../coordination/coordinationApi.js'
import { listDepartments } from '../departments/departmentsApi.js'
import { listDepartmentTaskDirectives, listTasks } from '../tasks/tasksApi.js'
import { useAuthStore } from '../../stores/authStore.js'

const navigateMock = vi.hoisted(() => vi.fn())

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigateMock,
}))

vi.mock('../alerts/alertsApi.js', () => ({
  listAlerts: vi.fn(),
}))

vi.mock('../coordination/coordinationApi.js', () => ({
  listDepartmentDirectives: vi.fn(),
  listDirectives: vi.fn(),
}))

vi.mock('../departments/departmentsApi.js', () => ({
  listDepartments: vi.fn(),
}))

vi.mock('../tasks/tasksApi.js', () => ({
  listDepartmentTaskDirectives: vi.fn(),
  listTasks: vi.fn(),
}))

describe('NotificationBell', () => {
  afterEach(() => {
    cleanup()
    useAuthStore.setState({ role: null })
    vi.useRealTimers()
  })

  beforeEach(() => {
    navigateMock.mockClear()
    listAlerts.mockResolvedValue([
      {
        id: 'alert-1',
        alert_type: 'early_warning',
        severity: 'medium',
        employee_id: 'employee-1',
        department_id: 'department-1',
        title: 'Cần theo dõi hiệu suất',
        message: 'Chất lượng công việc có dấu hiệu đi xuống.',
        employee_name: 'Nguyễn Văn A',
      },
    ])
    listTasks.mockResolvedValue([])
    listDepartmentTaskDirectives.mockResolvedValue([])
    listDirectives.mockResolvedValue([])
    listDepartments.mockResolvedValue([{ id: 'department-1', name: 'Phòng Kinh doanh' }])
    listDepartmentDirectives.mockResolvedValue([])
  })

  it('loads open alerts and shows a realtime-ready unread badge/dropdown', async () => {
    render(<NotificationBell />)

    await waitFor(() => expect(listAlerts).toHaveBeenCalledWith('open', 'all'))
    expect(listTasks).toHaveBeenCalledWith({ overdueOnly: true })
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Thông báo, 1 cần theo dõi' })).toBeInTheDocument(),
    )

    fireEvent.click(screen.getByRole('button', { name: 'Thông báo, 1 cần theo dõi' }))
    const alertSection = screen
      .getByRole('heading', { name: 'Yêu cầu xử lý cảnh báo' })
      .closest('section')
    const taskSection = screen
      .getByRole('heading', { name: 'Giao việc quá hạn' })
      .closest('section')
    expect(alertSection).toHaveClass('border-amber-200', 'bg-amber-50')
    expect(taskSection).toHaveClass('border-rose-200', 'bg-rose-50')
    expect(screen.getByText('Dấu hiệu sớm: 1')).toBeInTheDocument()
    expect(screen.getByText('Quá tải: 0')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Giao việc quá hạn' })).toBeInTheDocument()
    expect(screen.getByText('Cần theo dõi hiệu suất')).toBeInTheDocument()
    expect(screen.getByText('Nguyễn Văn A')).toBeInTheDocument()
  })

  it('opens the exact alert in the manager alert page', async () => {
    render(<NotificationBell />)

    const notificationButton = await waitFor(() =>
      screen.getByRole('button', { name: 'Thông báo, 1 cần theo dõi' }),
    )
    fireEvent.click(notificationButton)
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Mở cảnh báo/ })).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Mở cảnh báo Cần theo dõi hiệu suất' }))

    expect(navigateMock).toHaveBeenCalledWith(
      '/manager/alerts?alert=alert-1&status=open&alert_type=early_warning&severity=medium&employee_id=employee-1&department_id=department-1',
    )
  })

  it('separates threshold alerts from overdue tasks', async () => {
    listTasks.mockResolvedValue([
      {
        id: 'task-1',
        title: 'Hoàn tất báo cáo tháng',
        due_date: '2026-08-30',
        department_id: 'department-1',
        employee_id: 'employee-1',
        employee_name: 'Nguyễn Văn B',
        employee_code: 'KD-001',
      },
    ])

    render(<NotificationBell />)

    const notificationButton = await waitFor(() =>
      screen.getByRole('button', { name: 'Thông báo, 2 cần theo dõi' }),
    )
    fireEvent.click(notificationButton)

    expect(screen.getByRole('heading', { name: 'Yêu cầu xử lý cảnh báo' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Giao việc quá hạn' })).toBeInTheDocument()
    expect(screen.getByText('Cần theo dõi hiệu suất')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('Phòng Kinh doanh')).toBeInTheDocument())
    expect(screen.getByText('Nguyễn Văn B')).toBeInTheDocument()
    expect(screen.getByText('1 việc quá hạn')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Mở công việc quá hạn của Nguyễn Văn B' }))

    expect(navigateMock).toHaveBeenCalledWith(
      '/manager/tasks?task=task-1&deadline=overdue&employee_id=employee-1',
    )
  })

  it('groups open threshold alerts by department for leadership', async () => {
    useAuthStore.setState({ role: 'leadership' })
    listAlerts.mockResolvedValue([
      {
        id: 'alert-1',
        department_id: 'department-1',
        employee_name: 'Nguyễn Văn A',
        alert_type: 'early_warning',
        title: 'Dấu hiệu sớm',
        message: 'Chất lượng có dấu hiệu đi xuống.',
      },
      {
        id: 'alert-2',
        department_id: 'department-1',
        employee_name: 'Nguyễn Văn B',
        alert_type: 'overload',
        title: 'Quá tải',
        message: 'Khối lượng công việc tăng cao.',
      },
    ])
    listDepartmentDirectives.mockResolvedValue([{ alert_ids: ['alert-2'] }])

    render(<NotificationBell />)

    const notificationButton = await waitFor(() =>
      screen.getByRole('button', { name: 'Thông báo, 1 cần theo dõi' }),
    )
    fireEvent.click(notificationButton)

    expect(screen.getByText('Phòng Kinh doanh')).toBeInTheDocument()
    expect(screen.getByText('1 chưa xử lý')).toBeInTheDocument()
    expect(screen.getAllByText('Dấu hiệu sớm: 1')).toHaveLength(2)
    expect(screen.getAllByText('Quá tải: 0')).toHaveLength(2)
    expect(screen.queryByText('Nguyễn Văn A')).not.toBeInTheDocument()
    expect(screen.queryByText('Nguyễn Văn B')).not.toBeInTheDocument()
  })

  it('vẫn hiển thị công việc quá hạn dù đã nằm trong chỉ thị của Leadership', async () => {
    useAuthStore.setState({ role: 'leadership' })
    listTasks.mockResolvedValue([
      {
        id: 'task-1',
        title: 'Công việc đã được chỉ thị',
        due_date: '2026-08-30',
        department_id: 'department-1',
        employee_id: 'employee-1',
        employee_name: 'Nguyễn Văn B',
      },
    ])
    listDepartmentDirectives.mockResolvedValue([{ alert_ids: ['alert-1'] }])
    listDepartmentTaskDirectives.mockResolvedValue([{ task_ids: ['task-1'] }])

    render(<NotificationBell />)

    const notificationButton = await waitFor(() =>
      screen.getByRole('button', { name: 'Thông báo, 1 cần theo dõi' }),
    )
    fireEvent.click(notificationButton)

    expect(screen.getByText('Nguyễn Văn B')).toBeInTheDocument()
    expect(screen.getByText('1 việc')).toBeInTheDocument()
  })

  it('filters leadership overdue tasks by department', async () => {
    useAuthStore.setState({ role: 'leadership' })
    listTasks.mockResolvedValue([
      {
        id: 'task-1',
        title: 'Hoàn tất báo cáo tháng',
        due_date: '2026-08-30',
        department_id: 'department-1',
        employee_id: 'employee-1',
        employee_name: 'Nguyễn Văn B',
        employee_code: 'KD-001',
      },
    ])

    render(<NotificationBell />)

    const notificationButton = await waitFor(() =>
      screen.getByRole('button', { name: 'Thông báo, 2 cần theo dõi' }),
    )
    fireEvent.click(notificationButton)
    fireEvent.click(screen.getByRole('button', { name: 'Mở công việc quá hạn của Nguyễn Văn B' }))

    expect(navigateMock).toHaveBeenCalledWith(
      '/leadership/tasks?task=task-1&deadline=overdue&department_id=department-1',
    )
  })

  it('shows one 10-second reminder after 15 seconds when notifications need attention', async () => {
    vi.useFakeTimers()
    listTasks.mockResolvedValue([
      {
        id: 'task-1',
        title: 'Hoàn tất báo cáo tháng',
        due_date: '2026-08-30',
        employee_name: 'Nguyễn Văn B',
      },
    ])

    render(<NotificationBell />)
    await act(async () => {})

    expect(screen.queryByRole('status')).not.toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(15000)
    })
    expect(screen.getByRole('status')).toHaveTextContent(
      'Có 1 yêu cầu xử lý cảnh báo, 1 giao việc quá hạn và 0 chỉ thị đang theo dõi.',
    )

    act(() => {
      vi.advanceTimersByTime(10000)
    })
    act(() => {
      vi.advanceTimersByTime(400)
    })
    vi.useRealTimers()
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
  })

  it('đếm chỉ thị đang theo dõi và mở đúng trung tâm chỉ thị cho Manager', async () => {
    useAuthStore.setState({ role: 'manager' })
    listAlerts.mockResolvedValue([])
    listTasks.mockResolvedValue([])
    listDepartmentDirectives.mockResolvedValue([
      { id: 'alert-directive-1', status: 'pending' },
      { id: 'alert-directive-2', status: 'accepted' },
    ])
    listDepartmentTaskDirectives.mockResolvedValue([
      { id: 'task-directive-1', status: 'needs_revision' },
    ])
    listDirectives.mockResolvedValue([{ id: 'coordination-1', status: 'fulfilled' }])

    render(<NotificationBell />)

    const notificationButton = await waitFor(() =>
      screen.getByRole('button', { name: 'Thông báo, 2 cần theo dõi' }),
    )
    fireEvent.click(notificationButton)

    const section = screen
      .getByRole('heading', { name: 'Chỉ thị đang theo dõi' })
      .closest('section')
    expect(section).not.toBeNull()
    expect(section).toHaveClass('border-blue-200', 'bg-blue-50')
    expect(within(section).getByText('2')).toBeInTheDocument()
    expect(
      within(section).getByRole('button', { name: 'Mở trung tâm chỉ thị: Yêu cầu xử lý cảnh báo' }),
    ).toBeInTheDocument()
    expect(
      within(section).getByRole('button', { name: 'Mở trung tâm chỉ thị: Giao việc quá hạn' }),
    ).toBeInTheDocument()
    expect(within(section).queryByText('Đã nghiệm thu xử lý cảnh báo')).not.toBeInTheDocument()

    fireEvent.click(
      within(section).getByRole('button', {
        name: 'Mở trung tâm chỉ thị: Yêu cầu xử lý cảnh báo',
      }),
    )
    expect(navigateMock).toHaveBeenCalledWith('/manager/directives')
  })
})
