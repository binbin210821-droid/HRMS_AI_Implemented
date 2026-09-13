import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useEffect, useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { AttentionCard } from './DashboardPage.jsx'

const navigateMock = vi.hoisted(() => vi.fn())
const listEmployeesMock = vi.hoisted(() => vi.fn())
const getAttentionSummaryMock = vi.hoisted(() => vi.fn())
const getCompanyPerformanceAnalyticsMock = vi.hoisted(() => vi.fn())

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigateMock,
}))

vi.mock('../features/employees/employeesApi.js', () => ({
  listEmployees: listEmployeesMock,
}))

vi.mock('../features/dashboard/dashboardApi.js', () => ({
  getAttentionSummary: getAttentionSummaryMock,
}))

vi.mock('../stores/authStore.js', () => ({
  useAuthStore: (selector) =>
    selector({
      claims: { role: 'leadership', full_name: 'Lãnh đạo kiểm thử' },
    }),
}))

vi.mock('../hooks/useRealtimeUpdates.js', () => ({
  REALTIME_COALESCE_DELAY_MS: 0,
  useCoalescedRealtimeUpdates: () => undefined,
}))

vi.mock('../components/layout/MainLayout.jsx', () => ({
  default: ({ children }) => <>{children}</>,
}))

vi.mock('../components/HealthStatus.jsx', () => ({ default: () => null }))
vi.mock('../components/RealtimeAlertNotice.jsx', () => ({ default: () => null }))
vi.mock('../components/ui/Card.jsx', () => ({
  default: ({ as: Component = 'div', children }) => <Component>{children}</Component>,
}))
vi.mock('../components/animations/index.js', () => ({
  CounterNumber: ({ value }) => <>{value}</>,
  FadeIn: ({ children }) => <>{children}</>,
  StaggerList: ({ children }) => <>{children}</>,
}))
vi.mock('../features/dashboard/AiSummaryCard.jsx', () => ({ default: () => null }))
vi.mock('../features/dashboard/CoordinationSuggestionsCard.jsx', () => ({ default: () => null }))
vi.mock('../features/dashboard/DirectiveSummaryCard.jsx', () => ({ default: () => null }))
vi.mock('../features/dashboard/LeadershipAiOverviewCard.jsx', () => ({ default: () => null }))
vi.mock('../features/dashboard/LeadershipAiProposalCard.jsx', () => ({ default: () => null }))

vi.mock('../features/performance/PerformanceDashboard.jsx', () => ({
  default: function MockPerformanceDashboard({ onCompanyAnalyticsChange }) {
    const [period, setPeriod] = useState('30d')
    const [analytics, setAnalytics] = useState(null)
    useEffect(() => {
      const range =
        period === '30d'
          ? { startDate: '2026-09-01', endDate: '2026-09-30' }
          : { startDate: '2026-08-01', endDate: '2026-08-31' }
      getCompanyPerformanceAnalyticsMock(range).then((data) => {
        setAnalytics(data)
        onCompanyAnalyticsChange(data)
      })
    }, [onCompanyAnalyticsChange, period])
    const department = analytics?.departments?.[0]
    return (
      <div>
        <button type="button" onClick={() => setPeriod('previous')}>
          Đổi kỳ công ty
        </button>
        <span data-testid="company-chart-score">
          {department
            ? `${department.department_name}: ${Number(department.average_performance_score).toFixed(1)} điểm`
            : ''}
        </span>
      </div>
    )
  },
}))

describe('AttentionCard', () => {
  it('keeps details hidden until the card is hovered and closes on leave', async () => {
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
    await waitFor(() => expect(screen.queryByText('Việc cần ưu tiên')).not.toBeInTheDocument())
  })

  it('groups leadership attention details by department in the popover', () => {
    const summary = {
      total: 3,
      early_warning_count: 1,
      overload_count: 1,
      overdue_task_count: 1,
      overdue_task_total: 1,
      overdue_department_count: 1,
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
    expect(screen.getByText('Công việc quá hạn: 1')).toBeInTheDocument()
    expect(screen.queryByText('Nhân viên Kinh doanh 1')).not.toBeInTheDocument()
    expect(screen.queryByText('Nhân viên Kinh doanh 2')).not.toBeInTheDocument()
  })
})

describe('DashboardPage company analytics source', () => {
  it('fetches company analytics once per range and shares the same score with the insight card', async () => {
    const companyAnalytics = {
      departments: [
        {
          department_id: 'department-1',
          department_name: 'Kinh doanh',
          average_performance_score: 86.5,
          average_quality_score: 88,
          metric_days: 3,
        },
      ],
    }
    listEmployeesMock.mockResolvedValue([{ id: 'employee-1', is_active: true }])
    getAttentionSummaryMock.mockResolvedValue({ total: 0, items: [] })
    getCompanyPerformanceAnalyticsMock.mockResolvedValue(companyAnalytics)

    const { default: DashboardPage } = await import('./DashboardPage.jsx')
    render(<DashboardPage title="Dashboard Lãnh đạo" />)

    await waitFor(() => {
      expect(getCompanyPerformanceAnalyticsMock).toHaveBeenCalledTimes(1)
      expect(screen.getByText('86.5 điểm')).toBeInTheDocument()
      expect(screen.getByTestId('company-chart-score')).toHaveTextContent('Kinh doanh: 86.5 điểm')
    })

    fireEvent.click(screen.getByRole('button', { name: 'Đổi kỳ công ty' }))

    await waitFor(() => {
      expect(getCompanyPerformanceAnalyticsMock).toHaveBeenCalledTimes(2)
      expect(getCompanyPerformanceAnalyticsMock).toHaveBeenLastCalledWith({
        startDate: '2026-08-01',
        endDate: '2026-08-31',
      })
      expect(screen.getByText('86.5 điểm')).toBeInTheDocument()
    })
  })
})
