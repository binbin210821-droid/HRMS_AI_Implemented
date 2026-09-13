import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { FadeIn, SlideIn } from '../../components/animations/index.js'
import { Button, Select } from '../../components/ui/index.js'
import {
  REALTIME_COALESCE_DELAY_MS,
  useCoalescedRealtimeUpdates,
} from '../../hooks/useRealtimeUpdates.js'
import { useAuthStore } from '../../stores/authStore.js'
import { listAlerts } from '../alerts/alertsApi.js'
import { listDepartments } from '../departments/departmentsApi.js'
import { listEmployees } from '../employees/employeesApi.js'
import { listOverloadLogs } from '../overload/overloadApi.js'
import { listTasks } from '../tasks/tasksApi.js'
import LeadershipPerformanceCharts from './LeadershipPerformanceCharts.jsx'
import {
  getCompanyPerformanceAnalytics,
  getDepartmentPerformanceAnalytics,
  getEmployeePerformanceAnalytics,
  getDepartmentWeeklyTrend,
} from './performanceApi.js'

const EMPTY_MESSAGE = 'Chưa có dữ liệu hiệu suất trong khoảng thời gian này.'
const BUSINESS_TIME_ZONE = 'Asia/Ho_Chi_Minh'

function formatBusinessDate(date) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: BUSINESS_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day}`
}

function getDateKey(value) {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : formatBusinessDate(date)
}

function getTodayKey() {
  return formatBusinessDate(new Date())
}

function shiftDateKey(dateKey, days) {
  const date = new Date(`${dateKey}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

function formatScore(value) {
  return value == null ? 'Chưa có dữ liệu' : Number(value).toFixed(1)
}

export function buildPerformanceComparison(items = []) {
  const comparableItems = items.filter(
    (item) =>
      item.average_performance_score !== null && item.average_performance_score !== undefined,
  )
  return {
    items: comparableItems.map((item) => ({
      ...item,
      performance: item.average_performance_score,
    })),
    missingCount: items.length - comparableItems.length,
  }
}

function EmptyChart() {
  return (
    <div className="flex h-64 items-center justify-center rounded-xl bg-slate-50 text-sm text-slate-500">
      {EMPTY_MESSAGE}
    </div>
  )
}

function ErrorMessage({ message }) {
  return <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{message}</p>
}

function LoadingMessage({ message = 'Đang tải dữ liệu...' }) {
  return (
    <div className="flex h-64 items-center justify-center rounded-xl bg-slate-50 text-sm text-slate-500">
      {message}
    </div>
  )
}

function ChartCard({ title, description, actions, comparison, className = '', children }) {
  return (
    <section
      className={`w-full min-w-0 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200 sm:p-6 ${className}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h2 className="text-slate-900">{title}</h2>
        {actions}
      </div>
      <p className="mt-2 text-base leading-7 text-ink-600">{description}</p>
      {comparison && <div className="mt-3">{comparison}</div>}
      <div className="mt-5 w-full min-w-0">{children}</div>
    </section>
  )
}

function DashboardSection({ eyebrow, title, description, children }) {
  return (
    <section className="w-full rounded-3xl border border-slate-200/80 bg-slate-50/70 p-4 sm:p-5">
      <div className="mb-4 border-b border-slate-200/80 pb-4">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-700">{eyebrow}</p>
        <h2 className="mt-1 text-xl font-bold text-slate-900">{title}</h2>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">{description}</p>
      </div>
      {children}
    </section>
  )
}

function filterMetricsInRange(metrics, range) {
  return (metrics || []).filter((metric) => {
    const dateKey = getDateKey(metric.date)
    return dateKey && dateKey >= range.startDate && dateKey <= range.endDate
  })
}

function normalizeWeeklyTrend(response) {
  return (response?.weeks || []).map((week) => ({
    weekStart: week.week_start,
    weekLabel: week.week_label,
    performance: week.performance,
  }))
}

function filterByDateRange(items, getDate, range) {
  return (items || []).filter((item) => {
    const dateKey = getDateKey(getDate(item))
    return dateKey && dateKey >= range.startDate && dateKey <= range.endDate
  })
}

function calculateAverageResolution(alerts, range) {
  const durations = filterByDateRange(alerts, (alert) => alert.created_at, range)
    .filter((alert) => alert.status === 'resolved' && alert.resolved_at)
    .map((alert) => {
      const createdAt = new Date(alert.created_at).getTime()
      const resolvedAt = new Date(alert.resolved_at).getTime()
      return (resolvedAt - createdAt) / (1000 * 60 * 60)
    })
    .filter((hours) => Number.isFinite(hours) && hours >= 0)

  if (durations.length < 3) return null
  return {
    count: durations.length,
    hours: durations.reduce((total, hours) => total + hours, 0) / durations.length,
  }
}

function PeriodComparison({ current, previous, type }) {
  if (current == null || previous == null || previous === 0) return null

  const change = ((current - previous) / Math.abs(previous)) * 100
  if (!Number.isFinite(change)) return null

  const displayedChange = Number(change.toFixed(1))
  const direction = change > 0 ? '↑' : change < 0 ? '↓' : '→'
  const colorClass =
    change === 0
      ? 'text-slate-500'
      : type === 'performance'
        ? change > 0
          ? 'text-emerald-700'
          : 'text-red-700'
        : change > 0
          ? 'text-red-700'
          : 'text-emerald-700'

  return (
    <p className={`text-xl font-semibold ${colorClass}`}>
      <span aria-hidden="true" className="mr-1">
        {direction}
      </span>
      {change > 0 ? '+' : ''}
      {displayedChange}% so với kỳ trước
    </p>
  )
}

function PerformanceDashboard({ onCompanyAnalyticsChange }) {
  const role = useAuthStore((state) => state.role)
  const claims = useAuthStore((state) => state.claims)
  const [employees, setEmployees] = useState([])
  const [departments, setDepartments] = useState([])
  const [selectedEmployeeId, setSelectedEmployeeId] = useState('')
  const [selectedDepartmentId, setSelectedDepartmentId] = useState('')
  const [employeeAnalytics, setEmployeeAnalytics] = useState(null)
  const [departmentAnalytics, setDepartmentAnalytics] = useState(null)
  const [companyAnalytics, setCompanyAnalytics] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const employeeSelectionInitializedRef = useRef(false)

  const [weeklyMetrics, setWeeklyMetrics] = useState([])
  const [weeklyAverage, setWeeklyAverage] = useState(null)
  const [previousWeeklyAverage, setPreviousWeeklyAverage] = useState(null)
  const [weeklyLoading, setWeeklyLoading] = useState(false)
  const [weeklyError, setWeeklyError] = useState('')
  const [overloadLogs, setOverloadLogs] = useState([])
  const [overloadLoading, setOverloadLoading] = useState(false)
  const [overloadError, setOverloadError] = useState('')
  const [overloadGroupBy, setOverloadGroupBy] = useState('employee')
  const [alerts, setAlerts] = useState([])
  const [alertsLoading, setAlertsLoading] = useState(false)
  const [alertsError, setAlertsError] = useState('')
  const [dateRangePreset, setDateRangePreset] = useState('30d')
  const [leadershipWeeklyResponses, setLeadershipWeeklyResponses] = useState([])
  const [leadershipWeeklyLoading, setLeadershipWeeklyLoading] = useState(false)
  const [leadershipWeeklyError, setLeadershipWeeklyError] = useState('')
  const [leadershipDepartmentResponses, setLeadershipDepartmentResponses] = useState([])
  const [leadershipDepartmentLoading, setLeadershipDepartmentLoading] = useState(false)
  const [leadershipDepartmentError, setLeadershipDepartmentError] = useState('')
  const [leadershipTasks, setLeadershipTasks] = useState([])
  const [leadershipTasksLoading, setLeadershipTasksLoading] = useState(false)
  const [leadershipTasksError, setLeadershipTasksError] = useState('')

  const todayKey = getTodayKey()
  const dateRange = useMemo(() => {
    const days = dateRangePreset === '7d' ? 7 : dateRangePreset === 'quarter' ? 90 : 30
    const currentStartOffset = -(days - 1)
    return {
      startDate: shiftDateKey(todayKey, currentStartOffset),
      endDate: todayKey,
      previousStartDate: shiftDateKey(todayKey, -(days * 2 - 1)),
      previousEndDate: shiftDateKey(todayKey, -days),
    }
  }, [dateRangePreset, todayKey])
  const currentPeriod = useMemo(
    () => ({ startDate: dateRange.startDate, endDate: dateRange.endDate }),
    [dateRange.endDate, dateRange.startDate],
  )
  const previousPeriod = useMemo(
    () => ({ startDate: dateRange.previousStartDate, endDate: dateRange.previousEndDate }),
    [dateRange.previousEndDate, dateRange.previousStartDate],
  )

  useCoalescedRealtimeUpdates(
    ['performance_metrics'],
    () => setRefreshKey((current) => current + 1),
    { delay: REALTIME_COALESCE_DELAY_MS },
  )

  useEffect(() => {
    let active = true
    async function loadOptions() {
      try {
        const [employeeData, departmentData] = await Promise.all([
          listEmployees(),
          listDepartments(),
        ])
        if (!active) return
        setEmployees(employeeData || [])
        setDepartments(departmentData || [])
        setSelectedDepartmentId(
          (current) => current || claims?.department_id || departmentData?.[0]?.id || '',
        )
      } catch {
        if (active) setError('Không thể tải danh sách dữ liệu cho biểu đồ.')
      } finally {
        if (active) setIsLoading(false)
      }
    }
    loadOptions()
    return () => {
      active = false
    }
  }, [claims?.department_id])

  useEffect(() => {
    if (employeeSelectionInitializedRef.current || selectedEmployeeId) return
    const defaultEmployee = departmentAnalytics?.employees?.find(
      (employee) => employee.metric_days > 0,
    )
    const defaultEmployeeId =
      defaultEmployee?.employee_id || departmentAnalytics?.employees?.[0]?.employee_id
    if (!defaultEmployeeId) return

    employeeSelectionInitializedRef.current = true
    setSelectedEmployeeId(defaultEmployeeId)
  }, [departmentAnalytics, selectedEmployeeId])

  useEffect(() => {
    if (!selectedEmployeeId) return undefined
    let active = true
    getEmployeePerformanceAnalytics(selectedEmployeeId, currentPeriod)
      .then((data) => active && setEmployeeAnalytics(data || null))
      .catch(() => active && setError('Không thể tải xu hướng hiệu suất nhân viên.'))
    return () => {
      active = false
    }
  }, [currentPeriod, refreshKey, selectedEmployeeId])

  useEffect(() => {
    if (!selectedDepartmentId) return undefined
    let active = true
    getDepartmentPerformanceAnalytics(selectedDepartmentId, currentPeriod)
      .then((data) => active && setDepartmentAnalytics(data || null))
      .catch(() => active && setError('Không thể tải so sánh hiệu suất phòng ban.'))
    return () => {
      active = false
    }
  }, [currentPeriod, refreshKey, selectedDepartmentId])

  useEffect(() => {
    if (role !== 'leadership') {
      onCompanyAnalyticsChange?.(null)
      return undefined
    }
    let active = true
    getCompanyPerformanceAnalytics(currentPeriod)
      .then((data) => {
        if (!active) return
        const nextCompanyAnalytics = data || null
        setCompanyAnalytics(nextCompanyAnalytics)
        onCompanyAnalyticsChange?.(nextCompanyAnalytics)
      })
      .catch(() => active && setError('Không thể tải tổng hợp hiệu suất toàn công ty.'))
    return () => {
      active = false
    }
  }, [currentPeriod, onCompanyAnalyticsChange, refreshKey, role])

  useEffect(() => {
    if (role !== 'leadership') {
      setLeadershipWeeklyResponses([])
      setLeadershipWeeklyError('')
      return undefined
    }
    if (!departments.length) {
      setLeadershipWeeklyResponses([])
      return undefined
    }

    let active = true
    setLeadershipWeeklyLoading(true)
    setLeadershipWeeklyError('')
    Promise.allSettled(
      departments.map((department) => getDepartmentWeeklyTrend(department.id, currentPeriod)),
    )
      .then((results) => {
        if (!active) return
        const hasRejected = results.some((result) => result.status === 'rejected')
        setLeadershipWeeklyResponses(
          results.map((result) => (result.status === 'fulfilled' ? result.value : null)),
        )
        if (hasRejected) setLeadershipWeeklyError('Không thể tải đầy đủ xu hướng các phòng ban.')
      })
      .finally(() => active && setLeadershipWeeklyLoading(false))

    return () => {
      active = false
    }
  }, [currentPeriod, departments, refreshKey, role])

  useEffect(() => {
    if (role !== 'leadership') {
      setLeadershipDepartmentResponses([])
      setLeadershipDepartmentError('')
      return undefined
    }
    if (!departments.length) {
      setLeadershipDepartmentResponses([])
      return undefined
    }

    let active = true
    setLeadershipDepartmentLoading(true)
    setLeadershipDepartmentError('')
    Promise.allSettled(
      departments.map((department) =>
        getDepartmentPerformanceAnalytics(department.id, currentPeriod),
      ),
    )
      .then((results) => {
        if (!active) return
        const hasRejected = results.some((result) => result.status === 'rejected')
        setLeadershipDepartmentResponses(
          results.map((result) => (result.status === 'fulfilled' ? result.value : null)),
        )
        if (hasRejected) setLeadershipDepartmentError('Không thể tải đầy đủ dữ liệu khen thưởng.')
      })
      .finally(() => active && setLeadershipDepartmentLoading(false))

    return () => {
      active = false
    }
  }, [currentPeriod, departments, refreshKey, role])

  useEffect(() => {
    if (role !== 'leadership') {
      setLeadershipTasks([])
      setLeadershipTasksError('')
      return undefined
    }

    let active = true
    setLeadershipTasksLoading(true)
    setLeadershipTasksError('')
    listTasks()
      .then((data) => active && setLeadershipTasks(data || []))
      .catch(() => active && setLeadershipTasksError('Không thể tải tiến độ công việc.'))
      .finally(() => active && setLeadershipTasksLoading(false))

    return () => {
      active = false
    }
  }, [refreshKey, role])

  useEffect(() => {
    if (!selectedDepartmentId) {
      setWeeklyMetrics([])
      setWeeklyAverage(null)
      setPreviousWeeklyAverage(null)
      return undefined
    }

    let active = true
    setWeeklyLoading(true)
    setWeeklyError('')
    Promise.allSettled([
      getDepartmentWeeklyTrend(selectedDepartmentId, currentPeriod),
      getDepartmentWeeklyTrend(selectedDepartmentId, previousPeriod),
    ])
      .then(([currentResult, previousResult]) => {
        if (!active) return
        if (currentResult.status === 'fulfilled') {
          const currentTrend = currentResult.value || {}
          setWeeklyMetrics(normalizeWeeklyTrend(currentTrend))
          setWeeklyAverage(currentTrend.overall_average ?? null)
        } else {
          setWeeklyMetrics([])
          setWeeklyAverage(null)
          setWeeklyError('Không thể tải xu hướng hiệu suất theo tuần.')
        }
        if (previousResult.status === 'fulfilled') {
          const previousTrend = previousResult.value || {}
          setPreviousWeeklyAverage(previousTrend.overall_average ?? null)
        } else {
          setPreviousWeeklyAverage(null)
        }
      })
      .finally(() => active && setWeeklyLoading(false))

    return () => {
      active = false
    }
  }, [currentPeriod, previousPeriod, refreshKey, selectedDepartmentId])

  useEffect(() => {
    let active = true
    setOverloadLoading(true)
    setOverloadError('')
    listOverloadLogs({ startDate: previousPeriod.startDate, endDate: currentPeriod.endDate })
      .then((data) => active && setOverloadLogs(data || []))
      .catch(() => active && setOverloadError('Không thể tải tần suất quá tải.'))
      .finally(() => active && setOverloadLoading(false))

    return () => {
      active = false
    }
  }, [currentPeriod.endDate, previousPeriod.startDate, refreshKey])

  useEffect(() => {
    let active = true
    setAlertsLoading(true)
    setAlertsError('')
    // API mặc định chỉ trả early_warning; truyền all để tính đủ mọi loại cảnh báo.
    listAlerts(undefined, 'all', {
      startDate: previousPeriod.startDate,
      endDate: currentPeriod.endDate,
    })
      .then((data) => active && setAlerts(data || []))
      .catch(() => active && setAlertsError('Không thể tải thời gian xử lý cảnh báo.'))
      .finally(() => active && setAlertsLoading(false))

    return () => {
      active = false
    }
  }, [currentPeriod.endDate, previousPeriod.startDate, refreshKey])

  const trendData = useMemo(
    () => filterMetricsInRange(employeeAnalytics?.metrics, currentPeriod),
    [currentPeriod, employeeAnalytics],
  )
  const weeklyPerformance = weeklyMetrics
  const currentAveragePerformance = weeklyAverage
  const previousAveragePerformance = previousWeeklyAverage
  const employeeComparisonData = useMemo(
    () => buildPerformanceComparison(departmentAnalytics?.employees || []),
    [departmentAnalytics],
  )
  const employeeComparison = employeeComparisonData.items
  const employeeWithoutDataCount = employeeComparisonData.missingCount
  const topFiveEmployees = useMemo(
    () =>
      [...employeeComparison]
        .sort((first, second) => second.performance - first.performance)
        .slice(0, 5),
    [employeeComparison],
  )
  const bottomFiveEmployees = useMemo(
    () =>
      [...employeeComparison]
        .sort((first, second) => first.performance - second.performance)
        .slice(0, 5),
    [employeeComparison],
  )
  const currentOverloadLogs = useMemo(
    () => filterByDateRange(overloadLogs, (log) => log.date, currentPeriod),
    [currentPeriod, overloadLogs],
  )
  const previousOverloadLogs = useMemo(
    () => filterByDateRange(overloadLogs, (log) => log.date, previousPeriod),
    [overloadLogs, previousPeriod],
  )
  const currentOverloadCount = currentOverloadLogs.length
  const previousOverloadCount = previousOverloadLogs.length
  const overloadByEmployee = useMemo(() => {
    const groups = new Map()
    currentOverloadLogs.forEach((log) => {
      const employeeId = log.employee_id
      const existing = groups.get(employeeId) || {
        employee_id: employeeId,
        employee_name:
          log.employee_name ||
          employees.find((employee) => employee.id === employeeId)?.full_name ||
          'Nhân viên chưa xác định',
        count: 0,
      }
      existing.count += 1
      groups.set(employeeId, existing)
    })
    return [...groups.values()].sort((first, second) => second.count - first.count)
  }, [currentOverloadLogs, employees])
  const overloadByDepartment = useMemo(() => {
    const departmentNames = new Map(
      departments.map((department) => [String(department.id), department.name]),
    )
    const groups = new Map()

    currentOverloadLogs.forEach((log) => {
      const departmentId = log.department_id || ''
      const departmentKey = String(departmentId || 'unknown')
      const employee = employees.find((item) => item.id === log.employee_id)
      const departmentName =
        log.department_name ||
        departmentNames.get(String(departmentId)) ||
        departmentNames.get(String(employee?.department_id)) ||
        'Phòng ban chưa xác định'
      const existing = groups.get(departmentKey) || {
        department_id: departmentId,
        department_name: departmentName,
        count: 0,
      }
      existing.count += 1
      groups.set(departmentKey, existing)
    })

    return [...groups.values()].sort((first, second) => second.count - first.count)
  }, [currentOverloadLogs, departments, employees])
  const activeOverloadGroupBy = role === 'leadership' ? overloadGroupBy : 'employee'
  const overloadChartData =
    activeOverloadGroupBy === 'department' ? overloadByDepartment : overloadByEmployee
  const departmentComparisonData = useMemo(
    () => buildPerformanceComparison(companyAnalytics?.departments || []),
    [companyAnalytics],
  )
  const departmentComparison = departmentComparisonData.items
  const departmentWithoutDataCount = departmentComparisonData.missingCount
  const averageResolutionHours = useMemo(
    () => calculateAverageResolution(alerts, currentPeriod),
    [alerts, currentPeriod],
  )
  const previousAverageResolutionHours = useMemo(
    () => calculateAverageResolution(alerts, previousPeriod),
    [alerts, previousPeriod],
  )

  return (
    <div className="mt-8 space-y-6">
      <div className="flex flex-col gap-4 rounded-2xl bg-slate-50 p-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="!text-caption !font-semibold !uppercase !tracking-wider !text-brand-600">
            Phân tích dữ liệu
          </p>
          <h2 className="mt-1 text-slate-900">Bảng tổng quan hiệu suất</h2>
        </div>
        <div className="grid w-full gap-3 sm:max-w-3xl sm:grid-cols-3">
          {role !== 'leadership' && (
            <>
              <label className="text-sm font-medium text-slate-700">
                Nhân viên
                <Select
                  className="mt-1 min-w-0"
                  value={selectedEmployeeId}
                  onChange={(event) => setSelectedEmployeeId(event.target.value)}
                  disabled={isLoading}
                >
                  <option value="">Chọn nhân viên</option>
                  {employees.map((employee) => (
                    <option key={employee.id} value={employee.id}>
                      {employee.full_name}
                    </option>
                  ))}
                </Select>
              </label>
              <label className="text-sm font-medium text-slate-700">
                Phòng ban
                <Select
                  className="mt-1 min-w-0"
                  value={selectedDepartmentId}
                  onChange={(event) => setSelectedDepartmentId(event.target.value)}
                  disabled={isLoading}
                >
                  <option value="">Chọn phòng ban</option>
                  {departments.map((department) => (
                    <option key={department.id} value={department.id}>
                      {department.name}
                    </option>
                  ))}
                </Select>
              </label>
            </>
          )}
          <label className="text-sm font-medium text-slate-700">
            Khoảng thời gian
            <Select
              className="mt-1 min-w-0"
              value={dateRangePreset}
              onChange={(event) => setDateRangePreset(event.target.value)}
              disabled={isLoading}
            >
              <option value="7d">7 ngày gần nhất</option>
              <option value="30d">30 ngày gần nhất</option>
              <option value="quarter">Theo quý (90 ngày)</option>
            </Select>
          </label>
        </div>
      </div>

      {error && <ErrorMessage message={error} />}

      <FadeIn className="space-y-6">
        <DashboardSection
          eyebrow="Phân tích hiệu suất"
          title={role === 'leadership' ? 'Tổng quan theo phòng ban' : 'Hiệu suất nhân viên'}
          description={
            role === 'leadership'
              ? 'Theo dõi đồng thời xu hướng hiệu suất, chất lượng, rủi ro và tiến độ của các phòng ban.'
              : 'Theo dõi xu hướng, mức độ chênh lệch và nhóm nhân viên cần được hỗ trợ trong phòng ban.'
          }
        >
          <div className="grid w-full min-w-0 gap-6 lg:grid-cols-2">
            {role === 'leadership' && (
              <LeadershipPerformanceCharts
                departments={departments}
                weeklyResponses={leadershipWeeklyResponses}
                weeklyLoading={leadershipWeeklyLoading}
                weeklyError={leadershipWeeklyError}
                departmentResponses={leadershipDepartmentResponses}
                departmentLoading={leadershipDepartmentLoading}
                departmentError={leadershipDepartmentError}
                overloadLogs={currentOverloadLogs}
                tasks={leadershipTasks}
                tasksLoading={leadershipTasksLoading}
                tasksError={leadershipTasksError}
              />
            )}
            {role !== 'leadership' && (
              <>
                <ChartCard
                  title={`Xu hướng của ${employeeAnalytics?.full_name || 'nhân viên'}`}
                  description="Biểu đồ cho biết điểm hiệu suất, chất lượng và số công việc của nhân viên thay đổi theo từng ngày."
                >
                  {trendData.length ? (
                    <ResponsiveContainer width="100%" height={300}>
                      <LineChart
                        data={trendData}
                        margin={{ top: 8, right: 12, left: 0, bottom: 8 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis dataKey="date" tick={{ fontSize: 12 }} minTickGap={28} />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                        <Tooltip />
                        <Legend />
                        <Line
                          type="monotone"
                          dataKey="performance_score"
                          name="Điểm hiệu suất"
                          stroke="#2563eb"
                          strokeWidth={3}
                          dot={false}
                        />
                        <Line
                          type="monotone"
                          dataKey="quality_score"
                          name="Điểm chất lượng"
                          stroke="#10b981"
                          strokeWidth={2}
                          dot={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <EmptyChart />
                  )}
                </ChartCard>

                <ChartCard
                  title={`So sánh nhân viên — ${departmentAnalytics?.department_name || 'phòng ban'}`}
                  description="Biểu đồ cho biết điểm hiệu suất trung bình của từng nhân viên trong phòng ban đang được xem."
                >
                  {employeeComparison.length ? (
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart
                        data={employeeComparison}
                        margin={{ top: 8, right: 12, left: 0, bottom: 42 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis
                          dataKey="full_name"
                          angle={-25}
                          textAnchor="end"
                          interval={0}
                          tick={{ fontSize: 10 }}
                        />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                        <Tooltip
                          formatter={(value) => [Number(value).toFixed(1), 'Điểm hiệu suất']}
                        />
                        <Bar
                          dataKey="performance"
                          name="Điểm hiệu suất"
                          fill="#7c3aed"
                          radius={[6, 6, 0, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <EmptyChart />
                  )}
                  {employeeWithoutDataCount > 0 && (
                    <p className="mt-3 text-xs text-slate-500">
                      {employeeWithoutDataCount} nhân viên chưa có dữ liệu trong khoảng thời gian
                      này.
                    </p>
                  )}
                </ChartCard>

                <ChartCard
                  title="Xu hướng hiệu suất theo tuần"
                  description="Biểu đồ cho biết điểm hiệu suất trung bình theo từng tuần trong phạm vi bạn đang xem."
                  comparison={
                    <PeriodComparison
                      current={currentAveragePerformance}
                      previous={previousAveragePerformance}
                      type="performance"
                    />
                  }
                >
                  {weeklyError ? (
                    <ErrorMessage message={weeklyError} />
                  ) : weeklyLoading ? (
                    <LoadingMessage message="Đang tải xu hướng theo tuần..." />
                  ) : weeklyPerformance.length ? (
                    <ResponsiveContainer width="100%" height={300}>
                      <LineChart
                        data={weeklyPerformance}
                        margin={{ top: 8, right: 12, left: 0, bottom: 8 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis dataKey="weekLabel" tick={{ fontSize: 12 }} />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                        <Tooltip
                          formatter={(value) => [
                            Number(value).toFixed(1),
                            'Điểm hiệu suất trung bình',
                          ]}
                          labelFormatter={(label) => `Tuần bắt đầu từ ${label}`}
                        />
                        <Line
                          type="monotone"
                          dataKey="performance"
                          name="Điểm hiệu suất trung bình"
                          stroke="#0f766e"
                          strokeWidth={3}
                          dot={{ r: 4 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <EmptyChart />
                  )}
                </ChartCard>

                <ChartCard
                  title="Nhóm hiệu suất cần ưu tiên"
                  description="Hai biểu đồ giúp nhận diện nhanh nhân viên có kết quả nổi bật và nhân viên cần được hỗ trợ thêm trong phạm vi đang xem."
                >
                  {employeeComparison.length ? (
                    <div className="grid gap-6 sm:grid-cols-2">
                      <div>
                        <h3 className="mb-3 text-base font-bold text-slate-800">
                          Top 5 hiệu suất cao
                        </h3>
                        <ResponsiveContainer width="100%" height={280}>
                          <BarChart
                            layout="vertical"
                            data={topFiveEmployees}
                            margin={{ left: 4, right: 12 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                            <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} />
                            <YAxis
                              type="category"
                              dataKey="full_name"
                              width={105}
                              tick={{ fontSize: 10 }}
                            />
                            <Tooltip
                              formatter={(value) => [Number(value).toFixed(1), 'Điểm hiệu suất']}
                            />
                            <Bar
                              dataKey="performance"
                              name="Điểm hiệu suất"
                              fill="#16a34a"
                              radius={[0, 6, 6, 0]}
                            />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                      <div>
                        <h3 className="mb-3 text-base font-bold text-slate-800">
                          5 nhân viên cần hỗ trợ
                        </h3>
                        <ResponsiveContainer width="100%" height={280}>
                          <BarChart
                            layout="vertical"
                            data={bottomFiveEmployees}
                            margin={{ left: 4, right: 12 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                            <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} />
                            <YAxis
                              type="category"
                              dataKey="full_name"
                              width={105}
                              tick={{ fontSize: 10 }}
                            />
                            <Tooltip
                              formatter={(value) => [Number(value).toFixed(1), 'Điểm hiệu suất']}
                            />
                            <Bar
                              dataKey="performance"
                              name="Điểm hiệu suất"
                              fill="#f97316"
                              radius={[0, 6, 6, 0]}
                            />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  ) : (
                    <EmptyChart />
                  )}
                  {employeeWithoutDataCount > 0 && (
                    <p className="mt-3 text-xs text-slate-500">
                      {employeeWithoutDataCount} nhân viên chưa có dữ liệu trong khoảng thời gian
                      này.
                    </p>
                  )}
                </ChartCard>
              </>
            )}
          </div>
        </DashboardSection>

        <DashboardSection
          eyebrow="Theo dõi cảnh báo"
          title="Cảnh báo và thời gian xử lý"
          description="Đặt cạnh nhau tần suất quá tải và thời gian xử lý cảnh báo để nhận diện nhanh khu vực cần ưu tiên."
        >
          <div className="grid w-full min-w-0 gap-6 lg:grid-cols-2">
            <ChartCard
              title={
                activeOverloadGroupBy === 'department'
                  ? 'Tần suất quá tải theo phòng ban'
                  : 'Tần suất quá tải theo nhân viên'
              }
              description={
                activeOverloadGroupBy === 'department'
                  ? 'Biểu đồ đếm số lần hệ thống ghi nhận dấu hiệu quá tải theo từng phòng ban trong phạm vi bạn được xem.'
                  : 'Biểu đồ đếm số lần hệ thống ghi nhận dấu hiệu quá tải của từng nhân viên trong phạm vi bạn được xem.'
              }
              comparison={
                <PeriodComparison
                  current={currentOverloadCount}
                  previous={previousOverloadCount}
                  type="overload"
                />
              }
              actions={
                role === 'leadership' && (
                  <div
                    className="inline-flex rounded-xl bg-slate-100 p-1"
                    role="group"
                    aria-label="Cách nhóm dữ liệu quá tải"
                  >
                    {[
                      ['employee', 'Theo nhân viên'],
                      ['department', 'Theo phòng ban'],
                    ].map(([value, label]) => (
                      <Button
                        key={value}
                        type="button"
                        variant="ghost"
                        size="sm"
                        className={`rounded-lg px-3 py-1.5 text-xs font-semibold shadow-none ${
                          activeOverloadGroupBy === value
                            ? 'bg-white text-brand-700 shadow-sm hover:bg-white'
                            : 'text-slate-600 hover:text-slate-900'
                        }`}
                        aria-pressed={activeOverloadGroupBy === value}
                        onClick={() => setOverloadGroupBy(value)}
                      >
                        {label}
                      </Button>
                    ))}
                  </div>
                )
              }
            >
              {overloadError ? (
                <ErrorMessage message={overloadError} />
              ) : overloadLoading ? (
                <LoadingMessage message="Đang tải dữ liệu quá tải..." />
              ) : overloadChartData.length ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart
                    data={overloadChartData}
                    margin={{ top: 8, right: 12, left: 0, bottom: 42 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis
                      dataKey={
                        activeOverloadGroupBy === 'department' ? 'department_name' : 'employee_name'
                      }
                      angle={-25}
                      textAnchor="end"
                      interval={0}
                      tick={{ fontSize: 10 }}
                    />
                    <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                    <Tooltip formatter={(value) => [value, 'Số lần quá tải']} />
                    <Bar
                      dataKey="count"
                      name="Số lần quá tải"
                      fill="#dc2626"
                      radius={[6, 6, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="flex h-64 items-center justify-center rounded-xl bg-emerald-50 px-4 text-center text-sm font-medium text-emerald-700">
                  Không có dấu hiệu quá tải trong phạm vi này.
                </p>
              )}
            </ChartCard>

            <ChartCard
              className="h-fit lg:self-start"
              title="Thời gian xử lý cảnh báo trung bình"
              description="Chỉ số cho biết trung bình cần bao lâu để hoàn tất xử lý một cảnh báo đã phát sinh trong phạm vi đang xem."
              comparison={
                <PeriodComparison
                  current={averageResolutionHours?.hours}
                  previous={previousAverageResolutionHours?.hours}
                  type="resolution"
                />
              }
            >
              {alertsError ? (
                <ErrorMessage message={alertsError} />
              ) : alertsLoading ? (
                <LoadingMessage message="Đang tải thời gian xử lý..." />
              ) : averageResolutionHours ? (
                <div className="rounded-xl bg-slate-50 p-6 text-center ring-1 ring-slate-100">
                  <p className="text-4xl font-bold text-brand-700">
                    {averageResolutionHours.hours.toFixed(1)} giờ
                  </p>
                  <p className="mt-2 text-sm text-slate-600">
                    Tính từ {averageResolutionHours.count} cảnh báo đã xử lý.
                  </p>
                </div>
              ) : (
                <p className="flex h-32 items-center justify-center rounded-xl bg-slate-50 px-4 text-center text-sm text-slate-500">
                  Chưa đủ dữ liệu để tính trung bình.
                </p>
              )}
            </ChartCard>
          </div>
        </DashboardSection>

        {role === 'leadership' && (
          <DashboardSection
            eyebrow="Góc nhìn lãnh đạo"
            title="So sánh tổng hợp giữa các phòng ban"
            description="Biểu đồ tổng hợp giúp nhìn nhanh phòng ban nào đang có điểm hiệu suất trung bình cao hoặc thấp hơn."
          >
            <SlideIn direction="up" className="w-full">
              <ChartCard
                title="So sánh hiệu suất giữa các phòng ban"
                description="Biểu đồ dành cho Lãnh đạo, giúp nhìn nhanh phòng ban nào đang có điểm hiệu suất trung bình cao hoặc thấp hơn."
              >
                {departmentComparison.length ? (
                  <ResponsiveContainer width="100%" height={320}>
                    <BarChart
                      data={departmentComparison}
                      margin={{ top: 8, right: 12, left: 0, bottom: 30 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="department_name" tick={{ fontSize: 12 }} />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                      <Tooltip
                        formatter={(value) => [Number(value).toFixed(1), 'Điểm hiệu suất']}
                      />
                      <Bar
                        dataKey="performance"
                        name="Điểm hiệu suất trung bình"
                        fill="#ea580c"
                        radius={[6, 6, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyChart />
                )}
                {departmentWithoutDataCount > 0 && (
                  <p className="mt-3 text-xs text-slate-500">
                    {departmentWithoutDataCount} phòng ban chưa có dữ liệu trong khoảng thời gian
                    này.
                  </p>
                )}
              </ChartCard>
            </SlideIn>
          </DashboardSection>
        )}
      </FadeIn>

      <p className="text-xs text-slate-500">
        {employeeAnalytics
          ? `Đang hiển thị ${trendData.length} ngày dữ liệu của ${employeeAnalytics.full_name}.`
          : formatScore(null)}
      </p>
    </div>
  )
}

export default PerformanceDashboard
