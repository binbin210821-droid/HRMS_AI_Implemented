import { CounterNumber, FadeIn } from '../components/animations/index.js'
import HealthStatus from '../components/HealthStatus.jsx'
import MainLayout from '../components/layout/MainLayout.jsx'
import RealtimeAlertNotice from '../components/RealtimeAlertNotice.jsx'
import AiSummaryCard from '../features/dashboard/AiSummaryCard.jsx'
import AttentionPanel from '../features/dashboard/AttentionPanel.jsx'
import CoordinationSuggestionsCard from '../features/dashboard/CoordinationSuggestionsCard.jsx'
import DirectiveSummaryCard from '../features/dashboard/DirectiveSummaryCard.jsx'
import { getAttentionSummary } from '../features/dashboard/dashboardApi.js'
import PerformanceDashboard from '../features/performance/PerformanceDashboard.jsx'
import { useCallback, useEffect, useState } from 'react'

import { listEmployees } from '../features/employees/employeesApi.js'
import { useRealtimeUpdates } from '../hooks/useRealtimeUpdates.js'
import { useAuthStore } from '../stores/authStore.js'

function DashboardPage({ title }) {
  const claims = useAuthStore((state) => state.claims)
  const [summary, setSummary] = useState({ total: null, active: null, attention: null })
  const [attention, setAttention] = useState(null)
  const [attentionError, setAttentionError] = useState('')
  const [attentionLoading, setAttentionLoading] = useState(true)

  const loadSummary = useCallback(async () => {
    setAttentionLoading(true)
    try {
      const [employees, attentionData] = await Promise.all([listEmployees(), getAttentionSummary()])
      const employeeList = employees || []
      setSummary({
        total: employeeList.length,
        active: employeeList.filter((employee) => employee.is_active).length,
        attention: attentionData?.total ?? 0,
      })
      setAttention(attentionData)
      setAttentionError('')
    } catch {
      setAttentionError('Chưa thể tải danh sách việc cần ưu tiên.')
    } finally {
      setAttentionLoading(false)
    }
  }, [])

  useEffect(() => {
    loadSummary()
  }, [loadSummary])

  useRealtimeUpdates('alerts', loadSummary)
  useRealtimeUpdates('tasks', loadSummary)
  useRealtimeUpdates('department_directives', loadSummary)
  useRealtimeUpdates('task_directives', loadSummary)

  return (
    <MainLayout>
      <FadeIn className="mx-auto max-w-6xl">
        <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200 sm:p-8">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="!text-caption !font-semibold !uppercase !tracking-wider !text-brand-600">
                WorkMind
              </p>
              <h1 className="mt-2 text-slate-900">{title}</h1>
              <p className="mt-2 text-ink-600">Xin chào {claims?.full_name || 'bạn'}.</p>
            </div>
            <div className="w-full sm:max-w-xs [&>div]:mt-0 [&>div]:p-4 [&>div>h2]:text-base [&>div>p]:mt-1 [&>div>p:first-of-type]:hidden">
              <HealthStatus />
            </div>
          </div>

          <FadeIn className="mt-6">
            <AiSummaryCard />
          </FadeIn>

          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            <div className="rounded-xl bg-brand-50 p-5">
              <p className="!text-caption !text-brand-700">Nhân sự trong phạm vi</p>
              <p className="mt-2 text-2xl font-bold text-brand-800">
                {summary.total === null ? '—' : <CounterNumber value={summary.total} />}
              </p>
              {summary.total === null && (
                <p className="mt-1 text-xs font-medium text-brand-700">Không tải được</p>
              )}
            </div>
            <div className="rounded-xl bg-emerald-50 p-5">
              <p className="!text-caption !text-emerald-700">Đang hoạt động</p>
              <p className="mt-2 text-2xl font-bold text-emerald-800">
                {summary.active === null ? '—' : <CounterNumber value={summary.active} />}
              </p>
              {summary.active === null && (
                <p className="mt-1 text-xs font-medium text-emerald-700">Không tải được</p>
              )}
            </div>
            <AttentionCard
              summary={attention}
              role={claims?.role}
              error={attentionError}
              isLoading={attentionLoading}
            />
          </div>

          <DirectiveSummaryCard role={claims?.role} />

          <CoordinationSuggestionsCard role={claims?.role} />

          <RealtimeAlertNotice />
          <PerformanceDashboard />
        </section>
      </FadeIn>
    </MainLayout>
  )
}

export function AttentionCard({ summary, role, error, isLoading }) {
  const [isOpen, setIsOpen] = useState(false)
  const attentionValueUnavailable = summary?.total === null || summary?.total === undefined
  const earlyWarningMetric =
    role === 'leadership'
      ? (summary?.early_warning_department_count ?? summary?.early_warning_count)
      : summary?.early_warning_count
  const overloadMetric =
    role === 'leadership'
      ? (summary?.overloaded_department_count ?? summary?.overload_count)
      : summary?.overload_count
  const overdueTaskMetric = role === 'manager' ? summary?.overdue_task_count : undefined

  function handleBlur(event) {
    if (!event.currentTarget.contains(event.relatedTarget)) setIsOpen(false)
  }

  return (
    <div
      className="relative"
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
      onFocusCapture={() => setIsOpen(true)}
      onBlurCapture={handleBlur}
    >
      <button
        type="button"
        className="w-full rounded-xl bg-amber-50 p-5 text-left transition hover:-translate-y-0.5 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-amber-400 focus:ring-offset-2"
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        onClick={() => setIsOpen(true)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') setIsOpen(false)
        }}
      >
        <div className="flex items-start justify-between gap-3">
          <p className="!text-caption !text-amber-700">Tổng việc cần xử lý</p>
          <span className="text-xs font-semibold text-amber-700">Xem chi tiết</span>
        </div>
        <p className="mt-2 text-3xl font-bold text-amber-800">
          {attentionValueUnavailable ? '—' : <CounterNumber value={summary.total} />}
        </p>
        {attentionValueUnavailable && (
          <p className="mt-1 text-xs font-medium text-amber-700">Không tải được</p>
        )}
        {!attentionValueUnavailable &&
          earlyWarningMetric !== undefined &&
          overloadMetric !== undefined &&
          (role !== 'manager' || overdueTaskMetric !== undefined) && (
            <div
              className={`mt-3 grid gap-2 text-xs font-semibold ${role === 'manager' ? 'grid-cols-3' : 'grid-cols-2'}`}
            >
              <span className="rounded-lg bg-amber-100/80 px-2 py-1.5 text-amber-900">
                Dấu hiệu sớm: {earlyWarningMetric}
              </span>
              <span className="rounded-lg bg-red-100/80 px-2 py-1.5 text-red-900">
                Quá tải: {overloadMetric}
              </span>
              {role === 'manager' && (
                <span className="rounded-lg bg-rose-100/80 px-2 py-1.5 text-rose-900">
                  Quá hạn: {overdueTaskMetric}
                </span>
              )}
            </div>
          )}
        {!attentionValueUnavailable && role === 'leadership' && (
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs font-semibold">
            {summary?.overdue_department_count !== undefined && (
              <span className="rounded-lg bg-rose-100/80 px-2 py-1.5 text-rose-900">
                Phòng ban có việc quá hạn: {summary.overdue_department_count}
              </span>
            )}
            {summary?.overloaded_department_count !== undefined && (
              <span className="rounded-lg bg-red-100/80 px-2 py-1.5 text-red-900">
                Phòng ban quá tải: {summary.overloaded_department_count}
              </span>
            )}
          </div>
        )}
        <p className="mt-2 text-xs font-medium text-amber-800/80">
          Di chuột hoặc chọn thẻ để xem các việc cần ưu tiên.
        </p>
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full z-50 mt-3 w-[min(56rem,calc(100vw-2rem))]">
          <AttentionPanel
            summary={summary}
            role={role}
            error={error}
            isLoading={isLoading}
            variant="popover"
          />
        </div>
      )}
    </div>
  )
}

export default DashboardPage
