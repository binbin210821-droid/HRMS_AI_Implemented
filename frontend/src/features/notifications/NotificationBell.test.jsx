import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import NotificationBell from './NotificationBell.jsx'
import { listAlerts } from '../alerts/alertsApi.js'
import { listDepartmentDirectives } from '../coordination/coordinationApi.js'
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
    listDepartments.mockResolvedValue([{ id: 'department-1', name: 'Phòng Kinh doanh' }])
    listDepartmentDirectives.mockResolvedValue([])
  })

  it('loads open alerts and shows a realtime-ready unread badge/dropdown', async () => {
    render(<NotificationBell />)

    await waitFor(() => expect(listAlerts).toHaveBeenCalledWith('open', 'all'))
    expect(listTasks).toHaveBeenCalledWith({ overdueOnly: true })
    expect(screen.getByRole('button', { name: 'Thông báo, 1 cần theo dõi' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Thông báo, 1 cần theo dõi' }))
    expect(screen.getByRole('heading', { name: 'Yêu cầu xử lý cảnh báo' })).toBeInTheDocument()
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

  it('ẩn cả cảnh báo và công việc quá hạn đã nằm trong chỉ thị của Leadership', async () => {
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

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Thông báo' })).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Thông báo' }))

    expect(screen.getByText('Bạn không có thông báo mới.')).toBeInTheDocument()
    expect(screen.queryByText('Công việc đã được chỉ thị')).not.toBeInTheDocument()
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

  it('shows a 10-second reminder every 15 seconds when notifications need attention', async () => {
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
      'Có 1 yêu cầu xử lý cảnh báo và 1 giao việc quá hạn cần xử lý.',
    )

    act(() => {
      vi.advanceTimersByTime(10000)
    })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
