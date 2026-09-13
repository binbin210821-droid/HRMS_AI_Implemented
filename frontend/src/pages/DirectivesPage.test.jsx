import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

import DirectivesPage from './DirectivesPage.jsx'
import {
  listDepartmentDirectives,
  listDirectives,
} from '../features/coordination/coordinationApi.js'
import { listAlerts } from '../features/alerts/alertsApi.js'
import { listDepartmentTaskDirectives, listTasks } from '../features/tasks/tasksApi.js'
import {
  getDepartmentEvaluationAttachmentUrl,
  listDepartmentEvaluations,
} from '../features/departmentEvaluations/departmentEvaluationsApi.js'
import { useAuthStore } from '../stores/authStore.js'

vi.mock('../components/layout/MainLayout.jsx', () => ({
  default: ({ children }) => <main>{children}</main>,
}))

vi.mock('../hooks/useRealtimeUpdates.js', () => ({
  REALTIME_COALESCE_DELAY: 250,
  useRealtimeUpdates: vi.fn(),
}))

vi.mock('../features/coordination/coordinationApi.js', () => ({
  listDepartmentDirectives: vi.fn(),
  listDirectives: vi.fn(),
}))

vi.mock('../features/alerts/alertsApi.js', () => ({
  listAlerts: vi.fn(),
}))

vi.mock('../features/tasks/tasksApi.js', () => ({
  listDepartmentTaskDirectives: vi.fn(),
  listTasks: vi.fn(),
}))

vi.mock('../features/departmentEvaluations/departmentEvaluationsApi.js', () => ({
  getDepartmentEvaluationAttachmentUrl: vi.fn(),
  listDepartmentEvaluations: vi.fn(),
}))

const alertDirective = {
  id: 'alert-directive-1',
  department_id: 'department-1',
  department_name: 'Kinh doanh',
  alert_ids: ['alert-1', 'alert-2'],
  selected_alert_type: 'overload',
  selected_severity: 'high',
  selected_alert_count: 2,
  status: 'pending',
  issued_at: '2026-09-05T08:00:00Z',
  note: 'Rà soát cảnh báo quá tải.',
}

const taskDirective = {
  id: 'task-directive-1',
  target_department_id: 'department-2',
  target_department_name: 'Kỹ thuật',
  task_ids: ['task-1'],
  focus: 'overdue',
  selected_task_count: 1,
  status: 'pending',
  issued_at: '2026-09-05T09:00:00Z',
}

const coordinationDirective = {
  id: 'coordination-directive-1',
  alert_id: 'alert-3',
  target_department_id: 'department-3',
  target_department_name: 'Chăm sóc khách hàng',
  source_department_name: 'Kinh doanh',
  alert_title: 'Điều phối khối lượng công việc',
  tasks_to_transfer: 2,
  status: 'pending',
  issued_at: '2026-09-05T10:00:00Z',
}

const weeklyEvaluation = {
  id: 'weekly-evaluation-1',
  department_id: 'department-4',
  department_name: 'Tài chính',
  week_start: '2026-08-31',
  week_end: '2026-09-04',
  directive_execution_score: 85,
  stability_score: 90,
  timeliness_score: 95,
  overall_score: 89,
  assessment_note: 'Duy trì tiến độ xử lý trong tuần tiếp theo.',
  attachments: [
    {
      attachment_id: 'attachment-1',
      file_name: 'dinh-huong-tuan.pdf',
      content_type: 'application/pdf',
      file_size: 123,
    },
  ],
}

function LocationProbe() {
  const location = useLocation()
  return <p>{`${location.pathname}${location.search}`}</p>
}

function renderPage(role = 'manager') {
  useAuthStore.setState({ isAuthenticated: true, role })
  return render(
    <MemoryRouter initialEntries={[`/${role}/directives`]}>
      <Routes>
        <Route path="/:role/directives" element={<DirectivesPage />} />
        <Route path="*" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('DirectivesPage', () => {
  afterEach(cleanup)

  beforeEach(() => {
    vi.spyOn(window, 'open').mockImplementation(() => ({ location: {}, close: vi.fn() }))
    listDepartmentDirectives.mockResolvedValue([alertDirective])
    listDepartmentTaskDirectives.mockResolvedValue([taskDirective])
    listTasks.mockResolvedValue([])
    listAlerts.mockResolvedValue([])
    listDirectives.mockResolvedValue([coordinationDirective])
    listDepartmentEvaluations.mockResolvedValue({
      items: [weeklyEvaluation],
      page: 1,
      page_size: 12,
      total: 1,
      has_next: false,
    })
    getDepartmentEvaluationAttachmentUrl.mockResolvedValue({
      url: 'https://storage.test/dinh-huong-tuan.pdf',
    })
  })

  it('gom đủ ba loại yêu cầu và điều phối vào một trang', async () => {
    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'Yêu cầu xử lý cảnh báo' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Giao việc quá hạn' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Điều phối liên phòng ban' })).toBeInTheDocument()
    expect(screen.getAllByText('3', { selector: 'p.text-3xl' })).toHaveLength(2)
    expect(screen.getByText('Kinh doanh')).toBeInTheDocument()
    expect(screen.getByText('Kỹ thuật')).toBeInTheDocument()
    expect(screen.getByText('Chăm sóc khách hàng')).toBeInTheDocument()
    expect(screen.getByText('Tài chính')).toBeInTheDocument()
    const attachment = await screen.findByRole('button', { name: 'dinh-huong-tuan.pdf' })
    fireEvent.click(attachment)
    expect(getDepartmentEvaluationAttachmentUrl).toHaveBeenCalledWith(
      'weekly-evaluation-1',
      'attachment-1',
    )
  })

  it('đưa Manager đến đúng trang xử lý và giữ mã chỉ thị trong query', async () => {
    renderPage()

    const buttons = await screen.findAllByRole('button', {
      name: 'Xử lý yêu cầu cảnh báo →',
    })
    fireEvent.click(buttons[0])

    expect(
      screen.getByText(
        '/manager/alerts?department_id=department-1&alert_directive=alert-directive-1&alert=alert-1',
      ),
    ).toBeInTheDocument()
  })

  it('vẫn hiển thị chỉ thị của Manager sau khi đã tiếp nhận', async () => {
    listDepartmentDirectives.mockResolvedValue([
      { ...alertDirective, status: 'acknowledged', commitment_date: '2026-09-12' },
    ])
    listDepartmentTaskDirectives.mockResolvedValue([])
    listDirectives.mockResolvedValue([])

    renderPage()

    expect(await screen.findByText('Đã tiếp nhận yêu cầu cảnh báo')).toBeInTheDocument()
    expect(screen.getByText('1 đang thực hiện')).toBeInTheDocument()
  })

  it('chỉ mở bối cảnh cho Leadership, không truyền query thao tác', async () => {
    renderPage('leadership')

    fireEvent.click(await screen.findByRole('button', { name: '3 yêu cầu và điều phối' }))
    const buttons = await screen.findAllByRole('button', {
      name: 'Xem yêu cầu xử lý cảnh báo →',
    })
    fireEvent.click(buttons[0])

    expect(
      screen.getByText('/leadership/alerts?department_id=department-1&alert=alert-1'),
    ).toBeInTheDocument()
  })

  it('hiển thị chỉ thị đang chờ tiếp nhận của phòng ban ngay ở bộ lọc mặc định Leadership', async () => {
    listDepartmentDirectives.mockResolvedValue([])
    listDepartmentTaskDirectives.mockResolvedValue([
      {
        ...taskDirective,
        target_department_name: 'Chăm sóc khách hàng',
        status: 'pending',
      },
    ])
    listDirectives.mockResolvedValue([])

    renderPage('leadership')

    expect(await screen.findByText('Chăm sóc khách hàng')).toBeInTheDocument()
    expect(screen.getByText('Đang chờ nhận việc quá hạn')).toBeInTheDocument()
  })

  it('mở popup đọc lại chỉ thị đã nghiệm thu và không điều hướng sang nghiệp vụ', async () => {
    listDepartmentDirectives.mockResolvedValue([])
    listDepartmentTaskDirectives.mockResolvedValue([
      {
        ...taskDirective,
        status: 'accepted',
        accepted_at: '2026-09-06T10:00:00Z',
        completion_note: 'Đã xử lý toàn bộ công việc được giao.',
        acceptance_note: 'Đã kiểm tra và nghiệm thu.',
      },
    ])
    listTasks.mockResolvedValue([
      {
        id: 'task-1',
        title: 'Khắc phục ngay',
        employee_name: 'Nguyễn Văn A',
        status: 'done',
        due_date: '2026-09-01',
        completed_at: '2026-09-03T10:00:00Z',
      },
    ])
    listDirectives.mockResolvedValue([])

    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: '1 đã nghiệm thu' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Xem lại kết quả nghiệm thu →' }))

    expect(
      screen.getByRole('heading', { name: 'Xem lại chỉ thị đã nghiệm thu' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Nhân viên: Nguyễn Văn A')).toBeInTheDocument()
    expect(screen.getByText('Đã quá hạn 2 ngày khi hoàn tất')).toBeInTheDocument()
    expect(screen.getByText('Đã xử lý toàn bộ công việc được giao.')).toBeInTheDocument()
    expect(screen.queryByText('/manager/alerts')).not.toBeInTheDocument()
  })

  it('hiển thị chi tiết cảnh báo trong popup nghiệm thu', async () => {
    listDepartmentDirectives.mockResolvedValue([
      {
        ...alertDirective,
        status: 'accepted',
        accepted_at: '2026-09-06T10:00:00Z',
      },
    ])
    listDepartmentTaskDirectives.mockResolvedValue([])
    listAlerts.mockResolvedValue([
      {
        id: 'alert-1',
        alert_type: 'overload',
        severity: 'high',
        status: 'resolved',
        employee_name: 'Trần Thị B',
        title: 'Nhân viên có dấu hiệu quá tải',
        created_at: '2026-09-04T08:00:00Z',
        detected_dates: ['2026-09-03'],
        resolution_note: 'Đã điều phối lại công việc.',
      },
    ])
    listDirectives.mockResolvedValue([])

    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: '1 đã nghiệm thu' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Xem lại kết quả nghiệm thu →' }))

    expect(screen.getByText('Cảnh báo trong chỉ thị')).toBeInTheDocument()
    expect(screen.getByText('Nhân viên: Trần Thị B')).toBeInTheDocument()
    expect(screen.getByText('Đã xử lý')).toBeInTheDocument()
    expect(screen.getByText('Ghi chú xử lý: Đã điều phối lại công việc.')).toBeInTheDocument()
  })
})
