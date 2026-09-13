import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
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

import { FadeIn } from '../../components/animations/index.js'
import { useActionFeedback } from '../../components/feedback/index.js'
import MainLayout from '../../components/layout/MainLayout.jsx'
import { Button, Dialog, EmptyState, Select, Textarea } from '../../components/ui/index.js'
import { REALTIME_COALESCE_DELAY, useRealtimeUpdates } from '../../hooks/useRealtimeUpdates.js'
import { generateIdempotencyKey } from '../../utils/idempotency.js'
import {
  getDepartmentTaskPortfolio,
  getLeadershipTaskOverview,
  issueDepartmentTaskDirective,
  listDepartmentTaskDirectives,
} from './tasksApi.js'

const RANGE_LABELS = {
  '7d': '7 ngày',
  '30d': '30 ngày',
  '90d': '90 ngày',
}

const FOCUS_LABELS = {
  overdue: 'Công việc quá hạn',
  due_soon: 'Sắp đến hạn trong 7 ngày',
  high_priority_open: 'Công việc ưu tiên cao',
  at_risk: 'Tất cả công việc cần chú ý',
}

const PRIORITY_LABELS = { low: 'Thấp', medium: 'Trung bình', high: 'Cao' }
const STATUS_LABELS = {
  todo: 'Chưa bắt đầu',
  in_progress: 'Đang thực hiện',
  done: 'Đã hoàn thành',
}
const DIRECTIVE_STATUS_LABELS = {
  pending: 'Đã ra chỉ thị · Chờ tiếp nhận',
  acknowledged: 'Đang thực hiện chỉ thị',
  submitted: 'Chờ nghiệm thu chỉ thị',
  accepted: 'Đã nghiệm thu chỉ thị',
  needs_revision: 'Cần xử lý lại chỉ thị',
}

function getDirectiveStatusLabel(task) {
  if (!task.directive_id) return 'Chưa ra chỉ thị'
  if (task.has_active_directive === false && task.directive_status === 'accepted') {
    return 'Đã nghiệm thu trước đó · Có thể ra chỉ thị mới'
  }
  return DIRECTIVE_STATUS_LABELS[task.directive_status] || 'Đã ra chỉ thị'
}

function hasActiveDirective(task) {
  if (typeof task.has_active_directive === 'boolean') return task.has_active_directive
  return Boolean(task.directive_id && task.directive_status !== 'accepted')
}

function LeadershipTasksOverview() {
  const { confirmAction, notifyActionSuccess, notifyActionError } = useActionFeedback()
  const [searchParams, setSearchParams] = useSearchParams()
  const [range, setRange] = useState('30d')
  const [overview, setOverview] = useState(null)
  const [directives, setDirectives] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [portfolio, setPortfolio] = useState(null)
  const [portfolioDepartment, setPortfolioDepartment] = useState(null)
  const [portfolioInitialDirectiveFilter, setPortfolioInitialDirectiveFilter] = useState('all')
  const [portfolioLoading, setPortfolioLoading] = useState(false)
  const [portfolioError, setPortfolioError] = useState('')
  const [selectedDirectiveTaskIds, setSelectedDirectiveTaskIds] = useState([])
  const [directiveDepartment, setDirectiveDepartment] = useState(null)
  const [directiveForm, setDirectiveForm] = useState({ focus: 'overdue', note: '', taskIds: [] })
  const [directiveSaving, setDirectiveSaving] = useState(false)
  const [directiveError, setDirectiveError] = useState('')
  const directiveIdempotencyKeyRef = useRef(null)
  const dismissedDeepLinkRef = useRef('')

  const loadOverview = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const [overviewData, directiveData] = await Promise.all([
        getLeadershipTaskOverview(range),
        listDepartmentTaskDirectives(),
      ])
      setOverview(overviewData)
      setDirectives(directiveData)
    } catch (requestError) {
      setError(requestError.message || 'Không thể tải tổng quan công việc.')
    } finally {
      setIsLoading(false)
    }
  }, [range])

  useEffect(() => {
    void loadOverview()
  }, [loadOverview])

  useRealtimeUpdates(
    'tasks',
    () => {
      void loadOverview()
    },
    { coalesceDelay: REALTIME_COALESCE_DELAY },
  )
  useRealtimeUpdates(
    'task_directives',
    () => {
      void loadOverview()
    },
    { coalesceDelay: REALTIME_COALESCE_DELAY },
  )

  const openPortfolio = useCallback(
    async (department, highlightedTaskId = '', initialDirectiveFilter = 'all') => {
      setPortfolioDepartment(department)
      setPortfolio(null)
      setPortfolioError('')
      setPortfolioLoading(true)
      try {
        const data = await getDepartmentTaskPortfolio(department.department_id, { range })
        setPortfolio(data)
        setPortfolioInitialDirectiveFilter(initialDirectiveFilter)
        if (highlightedTaskId) {
          window.setTimeout(() => {
            document
              .getElementById(`leadership-task-${highlightedTaskId}`)
              ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
          }, 80)
        }
      } catch (requestError) {
        setPortfolioError(requestError.message || 'Không thể tải danh mục công việc phòng ban.')
      } finally {
        setPortfolioLoading(false)
      }
    },
    [range],
  )

  useEffect(() => {
    const departmentId = searchParams.get('department_id')
    const taskId = searchParams.get('task')
    const deepLinkKey = `${departmentId || ''}:${taskId || ''}`
    if (dismissedDeepLinkRef.current && dismissedDeepLinkRef.current !== deepLinkKey) {
      dismissedDeepLinkRef.current = ''
    }
    if (
      !overview ||
      !departmentId ||
      portfolioDepartment ||
      dismissedDeepLinkRef.current === deepLinkKey
    )
      return
    const department = overview.departments.find((item) => item.department_id === departmentId)
    if (department) void openPortfolio(department, taskId || '')
  }, [openPortfolio, overview, portfolioDepartment, searchParams])

  const pendingByDepartment = useMemo(() => {
    const result = new Map()
    directives
      .filter((directive) => directive.status === 'pending')
      .forEach((directive) => {
        const current = result.get(directive.target_department_id) || []
        result.set(directive.target_department_id, [...current, directive])
      })
    return result
  }, [directives])

  function openDirective(department, selectedTaskIds = []) {
    if (
      (selectedTaskIds.length === 0 && department.undirected_overdue_count === 0) ||
      !department.manager_name
    ) {
      // Dữ liệu trên card có thể đã cũ nếu một người khác vừa phát chỉ thị.
      // Tải lại trước khi mở form để tránh gửi một yêu cầu chắc chắn bị từ chối.
      void loadOverview()
      return
    }
    setDirectiveDepartment(department)
    setDirectiveForm({ focus: 'overdue', note: '', taskIds: selectedTaskIds })
    setDirectiveError('')
    directiveIdempotencyKeyRef.current = generateIdempotencyKey()
  }

  function handlePortfolioIssue(taskIds) {
    if (!portfolioDepartment || taskIds.length === 0) return
    const department = portfolioDepartment
    closePortfolio()
    openDirective(department, taskIds)
  }

  async function handleIssueDirective(event) {
    event.preventDefault()
    if (!directiveDepartment || directiveSaving) return
    const confirmed = await confirmAction({
      title: 'Xác nhận phát hành chỉ thị công việc',
      description: 'Chỉ thị sẽ được gửi đến Quản lý của phòng ban được chọn.',
      details: [
        `Phòng ban: ${directiveDepartment.department_name}`,
        `Nội dung: ${FOCUS_LABELS[directiveForm.focus] || directiveForm.focus}`,
        `Số công việc chọn: ${directiveForm.taskIds?.length || 0}`,
        `Ghi chú: ${directiveForm.note.trim() || 'Không thêm ghi chú'}`,
      ],
      confirmLabel: 'Xác nhận phát hành',
    })
    if (!confirmed) return
    setDirectiveSaving(true)
    setDirectiveError('')
    try {
      const payload = {
        focus: directiveForm.focus,
        note: directiveForm.note,
      }
      if (directiveForm.taskIds?.length) payload.task_ids = directiveForm.taskIds
      await issueDepartmentTaskDirective(
        directiveDepartment.department_id,
        payload,
        directiveIdempotencyKeyRef.current,
      )
      setDirectiveDepartment(null)
      setSelectedDirectiveTaskIds([])
      directiveIdempotencyKeyRef.current = null
      await loadOverview()
      notifyActionSuccess({
        title: 'Đã phát hành chỉ thị công việc',
        message: `Chỉ thị cho ${directiveDepartment.department_name} đã được gửi thành công.`,
        details: [`Nội dung: ${FOCUS_LABELS[directiveForm.focus] || directiveForm.focus}`],
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể phát hành chỉ thị công việc.'
      setDirectiveError(message)
      notifyActionError({ title: 'Chưa phát hành chỉ thị', message })
      if (requestError.status === 409) {
        // Đồng bộ lại card ngay cả khi tab đang mở bị trễ so với dữ liệu MongoDB.
        await loadOverview()
      }
    } finally {
      setDirectiveSaving(false)
    }
  }

  const chartData = overview?.departments || []

  const closePortfolio = useCallback(() => {
    dismissedDeepLinkRef.current = `${searchParams.get('department_id') || ''}:${searchParams.get('task') || ''}`
    setPortfolioDepartment(null)
    setPortfolio(null)
    setSelectedDirectiveTaskIds([])

    // Deep-link từ notification belt tự mở modal. Xóa các tham số này khi
    // đóng để effect không mở lại modal ngay lập tức.
    const nextParams = new URLSearchParams(searchParams)
    nextParams.delete('task')
    nextParams.delete('department_id')
    setSearchParams(nextParams, { replace: true })
  }, [searchParams, setSearchParams])

  return (
    <MainLayout>
      <FadeIn className="mx-auto max-w-7xl space-y-6">
        <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="!text-caption !font-semibold !uppercase !tracking-wider !text-brand-600">
                Quản trị tiến độ toàn công ty
              </p>
              <h1 className="mt-2 text-slate-900">Công việc & deadline</h1>
              <p className="mt-2 max-w-3xl text-ink-600">
                Theo dõi sức khỏe công việc theo phòng ban và chuyển yêu cầu xử lý đến đúng Quản lý
                phụ trách.
              </p>
            </div>
            <label className="text-sm font-semibold text-slate-700">
              Kỳ thống kê
              <Select
                className="mt-1 min-w-40"
                value={range}
                onChange={(event) => setRange(event.target.value)}
              >
                {Object.entries(RANGE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label} gần nhất
                  </option>
                ))}
              </Select>
            </label>
          </div>

          {error && <p className="mt-5 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
          {isLoading && !overview && (
            <p className="mt-6 rounded-xl bg-slate-50 p-6 text-center text-slate-500">
              Đang tổng hợp dữ liệu công việc...
            </p>
          )}

          {overview && (
            <>
              <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <KpiCard
                  label="Phòng ban đang có việc"
                  value={overview.departments_with_tasks}
                  tone="blue"
                />
                <KpiCard
                  label="Phòng ban cần chú ý"
                  value={overview.departments_need_attention}
                  tone="amber"
                />
                <KpiCard
                  label="Phòng ban có việc quá hạn"
                  value={overview.departments_overdue}
                  tone="red"
                />
                <KpiCard
                  label="Phòng ban có việc sắp đến hạn"
                  value={overview.departments_due_soon}
                  tone="violet"
                />
              </div>
              <p className="mt-3 text-sm text-slate-500">
                Các chỉ số rủi ro phản ánh hiện trạng; kỳ {RANGE_LABELS[range]} chỉ áp dụng cho số
                liệu hoàn thành và biểu đồ xu hướng.
              </p>
            </>
          )}
        </section>

        {overview && (
          <div className="grid gap-6 xl:grid-cols-2">
            <ChartCard
              title="Tình trạng deadline theo phòng ban"
              description="So sánh số công việc đang quá hạn, sắp đến hạn và còn đúng tiến độ giữa các phòng ban."
            >
              {chartData.some((item) => item.open_count > 0) ? (
                <div className="h-80 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 30 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis
                        dataKey="department_code"
                        tick={{ fontSize: 13 }}
                        label={{ value: 'Phòng ban', position: 'insideBottom', offset: -20 }}
                      />
                      <YAxis allowDecimals={false} tick={{ fontSize: 13 }} />
                      <Tooltip />
                      <Legend verticalAlign="top" height={36} />
                      <Bar
                        dataKey="overdue_count"
                        name="Quá hạn"
                        fill="#ef4444"
                        radius={[5, 5, 0, 0]}
                      />
                      <Bar
                        dataKey="due_soon_count"
                        name="Sắp đến hạn"
                        fill="#f59e0b"
                        radius={[5, 5, 0, 0]}
                      />
                      <Bar
                        dataKey={(item) =>
                          Math.max(0, item.open_count - item.overdue_count - item.due_soon_count)
                        }
                        name="Đúng tiến độ"
                        fill="#10b981"
                        radius={[5, 5, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <EmptyState title="Chưa có công việc đang mở trong công ty." />
              )}
            </ChartCard>

            <ChartCard
              title="Xu hướng hoàn thành công việc"
              description={`Số công việc hoàn thành theo tuần trong ${RANGE_LABELS[range]} gần nhất.`}
            >
              <div className="h-80 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={overview.completion_trend}
                    margin={{ top: 8, right: 18, left: 0, bottom: 8 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 13 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 13 }} />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="completed_count"
                      name="Đã hoàn thành"
                      stroke="#2563eb"
                      strokeWidth={3}
                      dot={{ r: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>
          </div>
        )}

        {overview && (
          <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200 sm:p-6">
            <div>
              <h2 className="text-slate-900">Tình hình công việc theo phòng ban</h2>
              <p className="mt-2 text-ink-600">
                Ưu tiên các phòng ban có việc quá hạn; thông tin nhân viên được giữ ở tầng vận hành
                của Quản lý.
              </p>
            </div>

            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              {overview.departments.map((department) => {
                const pending = pendingByDepartment.get(department.department_id) || []
                const hasPendingOverdueDirective = pending.some((item) => item.focus === 'overdue')
                return (
                  <article
                    key={department.department_id}
                    id={`leadership-department-${department.department_id}`}
                    className={`rounded-2xl border p-5 ${department.overdue_count ? 'border-red-200 bg-red-50/30' : 'border-slate-200 bg-white'}`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h3 className="text-lg font-bold text-slate-900">
                          {department.department_name}
                        </h3>
                        <p className="mt-1 text-sm text-slate-500">
                          Mã {department.department_code} ·{' '}
                          {department.manager_name || 'Chưa có Quản lý phụ trách'}
                        </p>
                      </div>
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-sm font-semibold text-slate-700">
                        {department.open_count} việc đang mở
                      </span>
                    </div>

                    <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                      <Metric label="Quá hạn" value={department.overdue_count} tone="red" />
                      <Metric label="Sắp đến hạn" value={department.due_soon_count} tone="amber" />
                      <Metric
                        label="Ưu tiên cao"
                        value={department.high_priority_open_count}
                        tone="violet"
                      />
                      <Metric
                        label={`Hoàn thành ${RANGE_LABELS[range]}`}
                        value={department.completed_in_period_count}
                        tone="green"
                      />
                    </div>

                    <div className="mt-4 flex flex-wrap gap-2 text-sm">
                      <span className="rounded-full bg-blue-50 px-3 py-1 font-semibold text-blue-700">
                        {department.undirected_overdue_count} công việc quá hạn chưa gửi chỉ thị
                      </span>
                      {department.oldest_overdue_date && (
                        <span className="rounded-full bg-red-50 px-3 py-1 font-medium text-red-700">
                          Quá hạn lâu nhất: {formatDate(department.oldest_overdue_date)}
                        </span>
                      )}
                    </div>

                    {pending.length > 0 && (
                      <div className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-800">
                        Đang chờ Quản lý tiếp nhận:{' '}
                        {pending.map((item) => FOCUS_LABELS[item.focus]).join(', ')}
                      </div>
                    )}

                    <div className="mt-5 flex flex-wrap justify-end gap-2 border-t border-slate-200 pt-4">
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => void openPortfolio(department)}
                      >
                        Xem chi tiết
                      </Button>
                      <Button
                        type="button"
                        disabled={
                          department.undirected_overdue_count === 0 || !department.manager_name
                        }
                        onClick={() => void openPortfolio(department, '', 'not_directed')}
                      >
                        {department.undirected_overdue_count === 0
                          ? hasPendingOverdueDirective
                            ? 'Đang chờ Quản lý tiếp nhận'
                            : 'Đã gửi hết công việc quá hạn'
                          : hasPendingOverdueDirective
                            ? 'Bổ sung vào chỉ thị'
                            : 'Ra chỉ thị cho Quản lý'}
                      </Button>
                    </div>
                  </article>
                )
              })}
            </div>
          </section>
        )}
      </FadeIn>

      {portfolioDepartment && (
        <Dialog
          title={`Danh mục công việc · ${portfolioDepartment.department_name}`}
          description="Xem chi tiết công việc theo từng phòng ban."
          className="max-w-5xl"
          onClose={closePortfolio}
        >
          {portfolioLoading && <EmptyState title="Đang tải danh mục công việc..." />}
          {portfolioError && (
            <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{portfolioError}</p>
          )}
          {portfolio && (
            <PortfolioContent
              portfolio={portfolio}
              highlightedTaskId={searchParams.get('task') || ''}
              initialDirectiveFilter={portfolioInitialDirectiveFilter}
              selectedTaskIds={selectedDirectiveTaskIds}
              onToggleTask={(taskId) =>
                setSelectedDirectiveTaskIds((current) =>
                  current.includes(taskId)
                    ? current.filter((item) => item !== taskId)
                    : [...current, taskId],
                )
              }
              onIssueSelected={handlePortfolioIssue}
              onSelectTasks={setSelectedDirectiveTaskIds}
            />
          )}
        </Dialog>
      )}

      {directiveDepartment && (
        <Dialog
          title={`Ra chỉ thị · ${directiveDepartment.department_name}`}
          description={
            directiveForm.taskIds?.length
              ? 'Chỉ thị sẽ bao gồm đúng các công việc bạn đã chọn trong danh mục.'
              : 'Hệ thống sẽ chọn các công việc phù hợp chưa từng được gửi chỉ thị.'
          }
          onClose={() => {
            setDirectiveDepartment(null)
            setSelectedDirectiveTaskIds([])
          }}
        >
          <form className="space-y-4" onSubmit={handleIssueDirective}>
            {directiveError && (
              <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{directiveError}</p>
            )}
            <div className="rounded-lg bg-red-50 p-3 text-sm font-semibold text-red-800">
              Nhóm công việc được phép phát hành chỉ thị: công việc quá hạn chưa gửi chỉ thị.
            </div>
            {directiveForm.taskIds?.length > 0 && (
              <div className="rounded-lg bg-blue-50 p-3 text-sm font-semibold text-blue-800">
                Đã chọn {directiveForm.taskIds.length} công việc quá hạn để đưa vào chỉ thị.
              </div>
            )}
            <label className="block text-sm font-semibold text-slate-700">
              Nội dung chỉ thị
              <Textarea
                className="mt-1 min-h-28"
                maxLength={1000}
                placeholder="Ví dụ: Đề nghị rà soát, phân bổ lại nguồn lực và cập nhật tiến độ trong ngày."
                value={directiveForm.note}
                onChange={(event) =>
                  setDirectiveForm((current) => ({ ...current, note: event.target.value }))
                }
              />
            </label>
            <div className="flex justify-end gap-3 pt-2">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setDirectiveDepartment(null)
                  setSelectedDirectiveTaskIds([])
                }}
              >
                Hủy
              </Button>
              <Button type="submit" loading={directiveSaving} disabled={directiveSaving}>
                {directiveForm.taskIds?.length
                  ? `Gửi chỉ thị cho ${directiveForm.taskIds.length} việc`
                  : 'Gửi chỉ thị'}
              </Button>
            </div>
          </form>
        </Dialog>
      )}
    </MainLayout>
  )
}

function PortfolioContent({
  portfolio,
  highlightedTaskId,
  initialDirectiveFilter = 'all',
  selectedTaskIds = [],
  onToggleTask,
  onIssueSelected,
  onSelectTasks,
}) {
  const [directiveFilter, setDirectiveFilter] = useState(initialDirectiveFilter)
  const selectedSet = new Set(selectedTaskIds)
  const groups = [
    ['Đang quá hạn', portfolio.overdue, 'Không có công việc quá hạn.'],
    ['Sắp đến hạn trong 7 ngày', portfolio.due_soon, 'Không có công việc sắp đến hạn.'],
    ['Ưu tiên cao', portfolio.high_priority, 'Không có công việc ưu tiên cao đang mở.'],
    ['Đang thực hiện đúng tiến độ', portfolio.on_track, 'Không có công việc thuộc nhóm này.'],
    [
      `Đã hoàn thành trong ${RANGE_LABELS[portfolio.range]}`,
      portfolio.completed_in_period,
      'Chưa có công việc hoàn thành trong kỳ.',
    ],
  ]
  const visibleGroups = groups.map(([title, tasks, emptyText]) => [
    title,
    tasks.filter((task) => {
      const isDirected = hasActiveDirective(task)
      return (
        directiveFilter === 'all' ||
        (directiveFilter === 'directed' && isDirected) ||
        (directiveFilter === 'not_directed' && !isDirected)
      )
    }),
    emptyText,
  ])
  const selectableTaskIds = groups
    .flatMap(([, tasks]) => tasks)
    .filter((task) => task.is_overdue && !hasActiveDirective(task))
    .map((task) => task.id)
  const allSelectableTasksSelected =
    selectableTaskIds.length > 0 && selectableTaskIds.every((taskId) => selectedSet.has(taskId))

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3 rounded-xl bg-slate-50 p-3">
        <p className="max-w-2xl text-sm text-slate-600">
          Theo dõi công việc đã được gửi chỉ thị và chọn thêm các việc quá hạn chưa gửi để gom vào
          chỉ thị mới.
        </p>
        <label className="text-sm font-semibold text-slate-700">
          Lọc trạng thái chỉ thị
          <Select
            className="mt-1 min-w-48"
            value={directiveFilter}
            onChange={(event) => setDirectiveFilter(event.target.value)}
          >
            <option value="all">Tất cả công việc</option>
            <option value="not_directed">Chưa ra chỉ thị</option>
            <option value="directed">Đã ra chỉ thị</option>
          </Select>
        </label>
      </div>

      {selectableTaskIds.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3">
          <p className="text-sm text-slate-600">
            Có {selectableTaskIds.length} công việc quá hạn chưa ra chỉ thị.
          </p>
          <Button
            type="button"
            variant="secondary"
            onClick={() => onSelectTasks(allSelectableTasksSelected ? [] : selectableTaskIds)}
          >
            {allSelectableTasksSelected ? 'Bỏ chọn tất cả' : 'Chọn tất cả việc quá hạn'}
          </Button>
        </div>
      )}

      {selectedTaskIds.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-blue-200 bg-blue-50 p-3">
          <p className="text-sm font-semibold text-blue-800">
            Đã chọn {selectedTaskIds.length} công việc quá hạn chưa ra chỉ thị.
          </p>
          <Button type="button" onClick={() => onIssueSelected(selectedTaskIds)}>
            Ra chỉ thị cho {selectedTaskIds.length} việc đã chọn
          </Button>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {visibleGroups.map(([title, tasks, emptyText]) => (
          <section key={title} className="rounded-xl border border-slate-200">
            <h3 className="border-b border-slate-200 px-4 py-3 text-base font-bold text-slate-900">
              {title} ({tasks.length})
            </h3>
            {tasks.length === 0 ? (
              <p className="px-4 py-5 text-sm text-slate-500">{emptyText}</p>
            ) : (
              <div className="divide-y divide-slate-100">
                {tasks.map((task) => (
                  <PortfolioTask
                    key={task.id}
                    task={task}
                    highlightedTaskId={highlightedTaskId}
                    isSelected={selectedSet.has(task.id)}
                    onToggleTask={onToggleTask}
                  />
                ))}
              </div>
            )}
          </section>
        ))}
      </div>
    </div>
  )
}

function PortfolioTask({ task, highlightedTaskId, isSelected, onToggleTask }) {
  const isDirected = hasActiveDirective(task)
  const canSelect = task.is_overdue && !isDirected
  const directiveStatusLabel = getDirectiveStatusLabel(task)

  return (
    <article
      id={`leadership-task-${task.id}`}
      className={`p-4 transition duration-motion-standard ease-motion-standard ${task.id === highlightedTaskId ? 'bg-blue-50 ring-2 ring-inset ring-brand-300' : 'bg-white'}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-semibold text-slate-900">{task.title}</p>
        <span
          className={`rounded-full px-2 py-1 text-xs font-semibold ${isDirected ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}
        >
          {directiveStatusLabel}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-2 text-xs font-semibold">
        <span className={`priority-${task.priority}`}>{PRIORITY_LABELS[task.priority]}</span>
        <span className={task.is_overdue ? 'status-danger' : `task-status-${task.status}`}>
          {task.is_overdue ? 'Quá hạn' : STATUS_LABELS[task.status]}
        </span>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-600">
          Hạn {formatDate(task.due_date)}
        </span>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-600">
          {task.subtask_count} việc con
        </span>
      </div>
      {canSelect && (
        <Button
          type="button"
          variant="secondary"
          className="mt-3"
          onClick={() => onToggleTask(task.id)}
        >
          {isSelected ? 'Bỏ chọn' : 'Thêm vào chỉ thị'}
        </Button>
      )}
    </article>
  )
}

function KpiCard({ label, value, tone }) {
  const tones = {
    blue: 'bg-blue-50 text-blue-700',
    amber: 'bg-amber-50 text-amber-700',
    red: 'bg-red-50 text-red-700',
    violet: 'bg-violet-50 text-violet-700',
  }
  return (
    <div className={`rounded-xl p-5 ${tones[tone]}`}>
      <p className="text-sm font-semibold">{label}</p>
      <p className="mt-2 text-3xl font-bold">{value}</p>
    </div>
  )
}

function Metric({ label, value, tone }) {
  const tones = {
    red: 'bg-red-50 text-red-700',
    amber: 'bg-amber-50 text-amber-700',
    violet: 'bg-violet-50 text-violet-700',
    green: 'bg-emerald-50 text-emerald-700',
  }
  return (
    <div className={`rounded-xl p-3 ${tones[tone]}`}>
      <p className="text-xs font-semibold">{label}</p>
      <p className="mt-1 text-xl font-bold">{value}</p>
    </div>
  )
}

function ChartCard({ title, description, children }) {
  return (
    <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
      <h2 className="text-slate-900">{title}</h2>
      <p className="mt-2 text-base leading-7 text-ink-600">{description}</p>
      <div className="mt-5">{children}</div>
    </section>
  )
}

function formatDate(value) {
  if (!value) return '—'
  const [year, month, day] = String(value).slice(0, 10).split('-').map(Number)
  return new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium' }).format(
    new Date(year, month - 1, day),
  )
}

export default LeadershipTasksOverview
