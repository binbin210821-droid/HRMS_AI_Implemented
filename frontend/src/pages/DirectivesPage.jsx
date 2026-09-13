import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useActionFeedback } from '../components/feedback/index.js'
import { FadeIn } from '../components/animations/index.js'
import AttachmentLink from '../components/attachments/AttachmentLink.jsx'
import MainLayout from '../components/layout/MainLayout.jsx'
import { Button, Dialog, Select, Textarea } from '../components/ui/index.js'
import {
  getDepartmentEvaluationAttachmentUrl,
  listDepartmentEvaluations,
} from '../features/departmentEvaluations/departmentEvaluationsApi.js'
import { listAlerts } from '../features/alerts/alertsApi.js'
import {
  acceptDepartmentDirective,
  listDepartmentDirectives,
  listDirectives,
  requestDepartmentDirectiveRevision,
} from '../features/coordination/coordinationApi.js'
import {
  DIRECTIVE_SOURCE_LABELS,
  getDirectiveActionLabel,
  getDirectiveSourceLabel,
  getDirectiveStatusLabel,
} from '../features/coordination/directiveLabels.js'
import {
  acceptDepartmentTaskDirective,
  listDepartmentTaskDirectives,
  listTasks,
  requestTaskDirectiveRevision,
} from '../features/tasks/tasksApi.js'
import { REALTIME_COALESCE_DELAY, useRealtimeUpdates } from '../hooks/useRealtimeUpdates.js'
import { invalidateResource } from '../services/requestCoordinator.js'
import { useAuthStore } from '../stores/authStore.js'
import { generateIdempotencyKey } from '../utils/idempotency.js'

const ALERT_TYPE_LABELS = {
  all: 'Tất cả loại cảnh báo',
  early_warning: 'Dấu hiệu sớm',
  overload: 'Quá tải',
}

const SEVERITY_LABELS = {
  all: 'Tất cả mức độ',
  medium: 'Mức trung bình',
  high: 'Mức cao',
}

const TASK_FOCUS_LABELS = {
  overdue: 'Công việc quá hạn',
  due_soon: 'Sắp đến hạn trong 7 ngày',
  high_priority_open: 'Công việc ưu tiên cao',
  at_risk: 'Tất cả công việc cần chú ý',
}

function DirectivesPage() {
  const role = useAuthStore((state) => state.role)
  const { confirmAction, notifyActionSuccess, notifyActionError } = useActionFeedback()
  const navigate = useNavigate()
  const [alertDirectives, setAlertDirectives] = useState([])
  const [alerts, setAlerts] = useState([])
  const [taskDirectives, setTaskDirectives] = useState([])
  const [tasks, setTasks] = useState([])
  const [coordinationDirectives, setCoordinationDirectives] = useState([])
  const [weeklyEvaluations, setWeeklyEvaluations] = useState([])
  const [errors, setErrors] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [sourceFilter, setSourceFilter] = useState('all')
  // Leadership cần nhìn thấy cả chỉ thị đang chờ Manager tiếp nhận. Nếu mặc định
  // chỉ lọc `submitted`, chỉ thị pending vẫn tải thành công nhưng biến mất khỏi UI.
  const [statusFilter, setStatusFilter] = useState('all')
  const [selectedReview, setSelectedReview] = useState(null)
  const [selectedDirective, setSelectedDirective] = useState(null)
  const [reviewNote, setReviewNote] = useState('')
  const [isReviewSaving, setIsReviewSaving] = useState(false)
  const [reviewError, setReviewError] = useState('')
  const reviewIdempotencyKeyRef = useRef(null)

  const loadDirectives = useCallback(async () => {
    setIsLoading(true)
    const results = await Promise.allSettled([
      listDepartmentDirectives(),
      listDepartmentTaskDirectives(),
      listDirectives(),
      listDepartmentEvaluations('', 1, 12),
      listTasks(),
      listAlerts(undefined, 'all'),
    ])
    const nextErrors = []
    if (results[0].status === 'fulfilled') setAlertDirectives(results[0].value || [])
    else nextErrors.push(DIRECTIVE_SOURCE_LABELS.alert)
    if (results[1].status === 'fulfilled') setTaskDirectives(results[1].value || [])
    else nextErrors.push(DIRECTIVE_SOURCE_LABELS.task)
    if (results[2].status === 'fulfilled') setCoordinationDirectives(results[2].value || [])
    else nextErrors.push(DIRECTIVE_SOURCE_LABELS.coordination)
    if (results[3].status === 'fulfilled') {
      const data = results[3].value
      setWeeklyEvaluations(data?.items || data || [])
    } else nextErrors.push('định hướng tuần')
    if (results[4].status === 'fulfilled') setTasks(results[4].value || [])
    else nextErrors.push('chi tiết công việc')
    if (results[5].status === 'fulfilled') setAlerts(results[5].value || [])
    else nextErrors.push('chi tiết cảnh báo')
    setErrors(nextErrors)
    setIsLoading(false)
  }, [])

  useEffect(() => {
    void loadDirectives()
  }, [loadDirectives])

  const refreshDirectives = useCallback(() => {
    invalidateResource('alerts')
    invalidateResource('tasks')
    return loadDirectives()
  }, [loadDirectives])

  useRealtimeUpdates(
    'department_directives',
    () => {
      void refreshDirectives()
    },
    { coalesceDelay: REALTIME_COALESCE_DELAY },
  )
  useRealtimeUpdates(
    'task_directives',
    () => {
      void refreshDirectives()
    },
    { coalesceDelay: REALTIME_COALESCE_DELAY },
  )
  useRealtimeUpdates(
    'alerts',
    () => {
      void refreshDirectives()
    },
    { coalesceDelay: REALTIME_COALESCE_DELAY },
  )
  useRealtimeUpdates(
    'tasks',
    () => {
      void refreshDirectives()
    },
    { coalesceDelay: REALTIME_COALESCE_DELAY },
  )
  useRealtimeUpdates(
    'department_evaluations',
    () => {
      void refreshDirectives()
    },
    { coalesceDelay: REALTIME_COALESCE_DELAY },
  )

  const taskMap = useMemo(() => Object.fromEntries(tasks.map((task) => [task.id, task])), [tasks])
  const alertMap = useMemo(
    () => Object.fromEntries(alerts.map((alert) => [alert.id, alert])),
    [alerts],
  )

  const directives = useMemo(() => {
    const alertItems = alertDirectives.map((directive) => ({
      ...directive,
      source: 'alert',
      sourceLabel: DIRECTIVE_SOURCE_LABELS.alert,
      normalizedStatus: directive.status,
      departmentName: directive.department_name,
      title: `${ALERT_TYPE_LABELS[directive.selected_alert_type] || 'Nhóm cảnh báo'} · ${SEVERITY_LABELS[directive.selected_severity] || 'Mức cảnh báo'}`,
      countLabel: `${directive.selected_alert_count} cảnh báo`,
      detail: directive.note,
      issuedAt: directive.issued_at,
      relatedAlerts: (directive.alert_ids || [])
        .map((alertId) => alertMap[alertId])
        .filter(Boolean),
    }))
    const taskItems = taskDirectives.map((directive) => ({
      ...directive,
      source: 'task',
      sourceLabel: DIRECTIVE_SOURCE_LABELS.task,
      normalizedStatus: directive.status,
      departmentName: directive.target_department_name,
      title: TASK_FOCUS_LABELS[directive.focus] || 'Nhóm công việc cần chú ý',
      countLabel: `${directive.selected_task_count} công việc`,
      detail: directive.note,
      issuedAt: directive.issued_at,
      relatedTasks: (directive.task_ids || []).map((taskId) => taskMap[taskId]).filter(Boolean),
    }))
    const coordinationItems = coordinationDirectives.map((directive) => ({
      ...directive,
      source: 'coordination',
      sourceLabel: DIRECTIVE_SOURCE_LABELS.coordination,
      normalizedStatus: directive.status === 'fulfilled' ? 'accepted' : directive.status,
      departmentName: directive.target_department_name,
      title: directive.alert_title || 'Điều phối công việc liên phòng ban',
      countLabel: directive.tasks_to_transfer
        ? `${directive.tasks_to_transfer} công việc dự kiến chuyển`
        : 'Chờ Quản lý xác định khối lượng',
      detail: directive.note,
      issuedAt: directive.issued_at,
    }))
    return [...alertItems, ...taskItems, ...coordinationItems].sort((left, right) => {
      if (left.normalizedStatus !== right.normalizedStatus) {
        return left.normalizedStatus === 'pending' ? -1 : 1
      }
      return new Date(right.issuedAt).getTime() - new Date(left.issuedAt).getTime()
    })
  }, [alertDirectives, alertMap, coordinationDirectives, taskDirectives, taskMap])

  const visibleDirectives = useMemo(
    () =>
      directives.filter(
        (directive) =>
          (sourceFilter === 'all' || directive.source === sourceFilter) &&
          (statusFilter === 'all' || directive.normalizedStatus === statusFilter),
      ),
    [directives, sourceFilter, statusFilter],
  )

  const totals = useMemo(
    () => ({
      all: directives.length,
      pending: directives.filter((item) => item.normalizedStatus === 'pending').length,
      acknowledged: directives.filter((item) => item.normalizedStatus === 'acknowledged').length,
      submitted: directives.filter((item) => item.normalizedStatus === 'submitted').length,
      needsRevision: directives.filter((item) => item.normalizedStatus === 'needs_revision').length,
      accepted: directives.filter((item) => item.normalizedStatus === 'accepted').length,
    }),
    [directives],
  )

  const groupedBySource = useMemo(
    () =>
      Object.entries(DIRECTIVE_SOURCE_LABELS)
        .map(([source, label]) => ({
          source,
          label,
          items: visibleDirectives.filter((item) => item.source === source),
        }))
        .filter((group) => group.items.length > 0),
    [visibleDirectives],
  )

  function openDirective(directive) {
    const basePath = role === 'leadership' ? '/leadership' : '/manager'
    const shouldOpenAction = role === 'manager' && directive.normalizedStatus === 'pending'
    if (directive.normalizedStatus === 'accepted') {
      setSelectedDirective(directive)
      return
    }
    if (role === 'leadership' && directive.normalizedStatus === 'submitted') {
      setSelectedReview(directive)
      reviewIdempotencyKeyRef.current = generateIdempotencyKey()
      setReviewNote('')
      setReviewError('')
      return
    }
    if (directive.source === 'task') {
      const params = new URLSearchParams({ department_id: directive.target_department_id })
      if (shouldOpenAction) params.set('task_directive', directive.id)
      else if (directive.task_ids?.[0]) params.set('task', directive.task_ids[0])
      navigate(`${basePath}/tasks?${params.toString()}`)
      return
    }

    const params = new URLSearchParams()
    if (directive.source === 'alert') {
      params.set('department_id', directive.department_id)
      if (shouldOpenAction) params.set('alert_directive', directive.id)
      if (directive.alert_ids?.[0]) params.set('alert', directive.alert_ids[0])
    } else {
      if (shouldOpenAction) params.set('coordination_directive', directive.id)
      if (directive.alert_id) params.set('alert', directive.alert_id)
    }
    navigate(`${basePath}/alerts?${params.toString()}`)
  }

  async function handleReview(action) {
    if (!selectedReview || isReviewSaving) return
    if (action === 'revision' && !reviewNote.trim()) {
      setReviewError('Vui lòng nhập lý do yêu cầu xử lý lại.')
      return
    }
    const isAccepting = action === 'accept'
    const confirmed = await confirmAction({
      title: isAccepting ? 'Xác nhận nghiệm thu chỉ thị' : 'Xác nhận yêu cầu xử lý lại',
      description: isAccepting
        ? 'Chỉ thị sẽ được ghi nhận là đã nghiệm thu.'
        : 'Chỉ thị sẽ được chuyển lại để người phụ trách bổ sung hoặc xử lý lại.',
      details: [
        `Loại chỉ thị: ${selectedReview.sourceLabel}`,
        `Nội dung: ${selectedReview.title}`,
        `Phòng ban: ${selectedReview.departmentName || 'Chưa xác định'}`,
        `Ghi chú: ${reviewNote.trim() || 'Không thêm ghi chú'}`,
      ],
      confirmLabel: isAccepting ? 'Xác nhận nghiệm thu' : 'Yêu cầu xử lý lại',
    })
    if (!confirmed) return
    setIsReviewSaving(true)
    setReviewError('')
    try {
      const payload = { note: reviewNote }
      const updated =
        selectedReview.source === 'task'
          ? action === 'accept'
            ? await acceptDepartmentTaskDirective(
                selectedReview.id,
                payload,
                reviewIdempotencyKeyRef.current,
              )
            : await requestTaskDirectiveRevision(
                selectedReview.id,
                payload,
                reviewIdempotencyKeyRef.current,
              )
          : action === 'accept'
            ? await acceptDepartmentDirective(
                selectedReview.id,
                payload,
                reviewIdempotencyKeyRef.current,
              )
            : await requestDepartmentDirectiveRevision(
                selectedReview.id,
                payload,
                reviewIdempotencyKeyRef.current,
              )
      const setter = selectedReview.source === 'task' ? setTaskDirectives : setAlertDirectives
      setter((current) => current.map((item) => (item.id === selectedReview.id ? updated : item)))
      setSelectedReview(null)
      reviewIdempotencyKeyRef.current = null
      await loadDirectives()
      notifyActionSuccess({
        title: isAccepting ? 'Đã nghiệm thu chỉ thị' : 'Đã yêu cầu xử lý lại',
        message: `${selectedReview.title} đã được cập nhật thành công.`,
        details: [`Phòng ban: ${selectedReview.departmentName || 'Chưa xác định'}`],
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể cập nhật kết quả nghiệm thu.'
      setReviewError(message)
      notifyActionError({ title: 'Chưa cập nhật chỉ thị', message })
    } finally {
      setIsReviewSaving(false)
    }
  }

  return (
    <MainLayout>
      <FadeIn className="mx-auto max-w-7xl">
        <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="!text-caption !font-semibold !uppercase !tracking-wider !text-brand-600">
                Trung tâm chỉ thị
              </p>
              <h1 className="mt-2 text-slate-900">Trung tâm chỉ thị</h1>
              <p className="mt-2 max-w-3xl text-ink-600">
                {role === 'leadership'
                  ? 'Theo dõi tập trung yêu cầu xử lý cảnh báo, giao việc quá hạn và điều phối liên phòng ban.'
                  : 'Tiếp nhận yêu cầu từ Lãnh đạo và chuyển đến đúng màn hình nghiệp vụ để xử lý.'}
              </p>
            </div>
            <Button type="button" variant="secondary" onClick={() => void loadDirectives()}>
              Làm mới
            </Button>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <SummaryCard label="Tổng yêu cầu và điều phối" value={totals.all} tone="blue" />
            <SummaryCard label="Đang chờ xử lý theo loại" value={totals.pending} tone="amber" />
            <SummaryCard
              label="Đã tiếp nhận / nghiệm thu"
              value={directives.filter((item) => item.normalizedStatus !== 'pending').length}
              tone="green"
            />
          </div>

          <div className="mt-6 flex flex-wrap items-end gap-4 rounded-xl bg-slate-50 p-4">
            <SelectFilter
              label="Loại yêu cầu và điều phối"
              value={sourceFilter}
              onChange={setSourceFilter}
            >
              <option value="all">Tất cả nhóm</option>
              {Object.entries(DIRECTIVE_SOURCE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </SelectFilter>
            <div>
              <p className="mb-1 text-sm font-semibold text-slate-700">Trạng thái</p>
              <div className="flex flex-wrap gap-2">
                {[
                  ['pending', `${totals.pending} đang chờ xử lý`],
                  ['acknowledged', `${totals.acknowledged} đang thực hiện`],
                  ['submitted', `${totals.submitted} chờ nghiệm thu`],
                  ['needs_revision', `${totals.needsRevision} cần xử lý lại`],
                  ['accepted', `${totals.accepted} đã nghiệm thu`],
                  ['all', `${totals.all} yêu cầu và điều phối`],
                ].map(([value, label]) => (
                  <Button
                    key={value}
                    type="button"
                    variant="ghost"
                    size="sm"
                    className={`rounded-full border px-3 py-2 text-sm font-semibold shadow-none ${statusFilter === value ? 'border-brand-600 bg-brand-600 text-white hover:bg-brand-700' : 'border-slate-200 bg-white text-slate-600 hover:border-brand-300 hover:bg-white'}`}
                    onClick={() => setStatusFilter(value)}
                  >
                    {label}
                  </Button>
                ))}
              </div>
            </div>
          </div>

          <section className="mt-6 rounded-2xl border border-blue-100 bg-blue-50/50 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Định hướng tuần từ Lãnh đạo</h2>
                <p className="mt-1 text-sm text-slate-600">
                  {role === 'manager'
                    ? 'Tài liệu định hướng và kết quả đánh giá tuần của phòng ban bạn.'
                    : 'Theo dõi các định hướng tuần đã gửi đến từng phòng ban.'}
                </p>
              </div>
              <span className="rounded-full bg-white px-3 py-1 text-sm font-bold text-blue-700 shadow-sm">
                {weeklyEvaluations.length} định hướng
              </span>
            </div>
            {weeklyEvaluations.length ? (
              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                {weeklyEvaluations.slice(0, 8).map((evaluation) => (
                  <WeeklyDirectionCard key={evaluation.id} evaluation={evaluation} />
                ))}
              </div>
            ) : (
              <p className="mt-4 rounded-xl bg-white/80 p-4 text-sm text-slate-500">
                Chưa có tài liệu định hướng tuần nào trong phạm vi này.
              </p>
            )}
          </section>

          {errors.length > 0 && (
            <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
              Chưa thể tải {errors.join(', ')}. Các nhóm còn lại vẫn được hiển thị.
            </p>
          )}

          {isLoading ? (
            <p className="mt-6 rounded-xl bg-slate-50 p-8 text-center text-slate-500">
              Đang tải danh sách yêu cầu và điều phối...
            </p>
          ) : groupedBySource.length === 0 ? (
            <p className="mt-6 rounded-xl bg-emerald-50 p-8 text-center text-emerald-700">
              Không có yêu cầu hoặc điều phối phù hợp với bộ lọc hiện tại.
            </p>
          ) : (
            <div className="mt-6 space-y-7">
              {groupedBySource.map((group) => (
                <section key={group.source}>
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="text-lg font-bold text-slate-900">{group.label}</h2>
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-sm font-semibold text-slate-600">
                      {group.items.length} mục
                    </span>
                  </div>
                  <div className="mt-3 grid gap-3 lg:grid-cols-2">
                    {group.items.map((directive) => (
                      <DirectiveCard
                        key={`${directive.source}-${directive.id}`}
                        directive={directive}
                        role={role}
                        onOpen={() => openDirective(directive)}
                        onReview={() => openDirective(directive)}
                      />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          )}
        </section>
      </FadeIn>

      {selectedReview && (
        <Dialog
          title={`${selectedReview.sourceLabel}: Nghiệm thu`}
          description={`${selectedReview.title} · ${selectedReview.countLabel}`}
          onClose={() => {
            setSelectedReview(null)
            reviewIdempotencyKeyRef.current = null
          }}
        >
          <div className="space-y-4">
            <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-700">
              <p>Phòng ban: {selectedReview.departmentName || 'Phòng ban'}</p>
              <p className="mt-1">Tiến độ: {selectedReview.progress_percent ?? 0}%</p>
              {selectedReview.completion_note && (
                <p className="mt-2">Báo cáo của Quản lý: {selectedReview.completion_note}</p>
              )}
            </div>
            {reviewError && (
              <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{reviewError}</p>
            )}
            <label className="block text-sm font-semibold text-slate-700">
              Ghi chú nghiệm thu hoặc lý do xử lý lại
              <Textarea
                className="mt-1 min-h-28"
                maxLength={1000}
                value={reviewNote}
                onChange={(event) => setReviewNote(event.target.value)}
                placeholder="Nhập nhận xét của Lãnh đạo..."
              />
            </label>
            <div className="flex justify-end gap-3">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setSelectedReview(null)
                  reviewIdempotencyKeyRef.current = null
                }}
              >
                Đóng
              </Button>
              <Button
                type="button"
                variant="secondary"
                className="border-amber-300 text-amber-800 hover:bg-amber-50"
                disabled={isReviewSaving}
                onClick={() => void handleReview('revision')}
              >
                Yêu cầu xử lý lại
              </Button>
              <Button
                type="button"
                loading={isReviewSaving}
                disabled={isReviewSaving}
                onClick={() => void handleReview('accept')}
              >
                Nghiệm thu đạt
              </Button>
            </div>
          </div>
        </Dialog>
      )}

      {selectedDirective && (
        <DirectiveDetailModal
          directive={selectedDirective}
          onClose={() => setSelectedDirective(null)}
        />
      )}
    </MainLayout>
  )
}

function DirectiveCard({ directive, role, onOpen }) {
  const pending = directive.normalizedStatus === 'pending'
  const actionLabel = getDirectiveActionLabel(directive.source, role, directive.normalizedStatus)
  return (
    <article
      className={`rounded-xl border p-4 ${pending ? 'border-amber-200 bg-amber-50/40' : 'border-slate-200 bg-white'}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-brand-700">
            {getDirectiveSourceLabel(directive.source)}
          </p>
          <p className="font-bold text-slate-900">{directive.departmentName || 'Phòng ban'}</p>
          <p className="mt-1 text-sm font-semibold text-slate-700">{directive.title}</p>
        </div>
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-bold ${
            pending || directive.normalizedStatus === 'needs_revision'
              ? 'bg-amber-100 text-amber-800'
              : directive.normalizedStatus === 'submitted'
                ? 'bg-blue-100 text-blue-800'
                : 'bg-emerald-100 text-emerald-800'
          }`}
        >
          {getDirectiveStatusLabel(directive.source, directive.normalizedStatus)}
        </span>
      </div>
      <p className="mt-3 text-sm font-semibold text-brand-700">{directive.countLabel}</p>
      {directive.total_item_count > 0 && (
        <p className="mt-2 text-sm text-slate-600">
          Tiến độ: {directive.completed_item_count || 0}/{directive.total_item_count} mục (
          {directive.progress_percent || 0}%)
        </p>
      )}
      {directive.detail && (
        <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">{directive.detail}</p>
      )}
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
        <span>Phát hành: {formatDateTime(directive.issuedAt)}</span>
        {directive.commitment_date && <span>Cam kết: {formatDate(directive.commitment_date)}</span>}
        {directive.acknowledged_by_name && (
          <span>Tiếp nhận bởi: {directive.acknowledged_by_name}</span>
        )}
        {directive.submitted_at && (
          <span>Gửi nghiệm thu: {formatDateTime(directive.submitted_at)}</span>
        )}
        {directive.accepted_at && <span>Nghiệm thu: {formatDateTime(directive.accepted_at)}</span>}
      </div>
      <div className="mt-4 flex justify-end border-t border-slate-200 pt-3">
        <Button type="button" variant={pending ? 'primary' : 'secondary'} onClick={onOpen}>
          {actionLabel} →
        </Button>
      </div>
    </article>
  )
}

function WeeklyDirectionCard({ evaluation }) {
  return (
    <article className="rounded-xl border border-blue-100 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-bold text-slate-900">{evaluation.department_name}</p>
          <p className="mt-1 text-sm text-slate-600">
            Tuần {formatDate(evaluation.week_start)} – {formatDate(evaluation.week_end)}
          </p>
        </div>
        <span className="rounded-full bg-brand-50 px-3 py-1 text-sm font-black text-brand-700">
          {Number(evaluation.overall_score).toFixed(1)} điểm
        </span>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
        <div className="rounded-lg bg-slate-50 p-2">
          <p className="text-slate-500">Mức hoàn thành yêu cầu</p>
          <p className="mt-1 font-bold text-slate-800">
            {Number(evaluation.directive_execution_score).toFixed(1)}
          </p>
        </div>
        <div className="rounded-lg bg-slate-50 p-2">
          <p className="text-slate-500">Ổn định</p>
          <p className="mt-1 font-bold text-slate-800">
            {Number(evaluation.stability_score).toFixed(1)}
          </p>
        </div>
        <div className="rounded-lg bg-slate-50 p-2">
          <p className="text-slate-500">Đúng hạn</p>
          <p className="mt-1 font-bold text-slate-800">
            {Number(evaluation.timeliness_score).toFixed(1)}
          </p>
        </div>
      </div>
      {evaluation.assessment_note && (
        <p className="mt-3 text-sm leading-6 text-slate-600">{evaluation.assessment_note}</p>
      )}
      <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-3">
        {evaluation.attachments.map((attachment) => (
          <AttachmentLink
            key={attachment.attachment_id}
            attachment={attachment}
            className="rounded-lg bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-100"
            getDownloadUrl={() =>
              getDepartmentEvaluationAttachmentUrl(evaluation.id, attachment.attachment_id)
            }
          />
        ))}
      </div>
    </article>
  )
}

function SummaryCard({ label, value, tone }) {
  const tones = {
    blue: 'bg-blue-50 text-blue-700',
    amber: 'bg-amber-50 text-amber-700',
    green: 'bg-emerald-50 text-emerald-700',
  }
  return (
    <div className={`rounded-xl p-4 ${tones[tone]}`}>
      <p className="text-sm font-semibold">{label}</p>
      <p className="mt-2 text-3xl font-bold">{value}</p>
    </div>
  )
}

function DirectiveDetailModal({ directive, onClose }) {
  const coordination = directive.source === 'coordination'
  const taskDirective = directive.source === 'task'
  return (
    <Dialog
      title="Xem lại chỉ thị đã nghiệm thu"
      description={`${directive.sourceLabel} · ${directive.title}`}
      onClose={onClose}
    >
      <div className="space-y-4">
        <div className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-900">
          <p className="font-bold">
            {getDirectiveStatusLabel(directive.source, directive.normalizedStatus)}
          </p>
          <p className="mt-1">Phòng ban: {directive.departmentName || 'Phòng ban'}</p>
          {coordination && directive.source_department_name && (
            <p className="mt-1">
              Điều phối từ: {directive.source_department_name} → {directive.target_department_name}
            </p>
          )}
          <p className="mt-1">Nội dung: {directive.countLabel}</p>
          {directive.accepted_at && (
            <p className="mt-1">Thời điểm nghiệm thu: {formatDateTime(directive.accepted_at)}</p>
          )}
        </div>

        {directive.total_item_count > 0 && (
          <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-700">
            Tiến độ cuối: {directive.completed_item_count || 0}/{directive.total_item_count} mục (
            {directive.progress_percent || 0}%)
          </p>
        )}

        {taskDirective && (
          <div className="rounded-xl border border-red-100 bg-red-50/60 p-4">
            <p className="font-bold text-slate-900">Công việc quá hạn trong chỉ thị</p>
            {directive.relatedTasks?.length ? (
              <div className="mt-3 space-y-3">
                {directive.relatedTasks.map((task) => (
                  <TaskReviewItem key={task.id} task={task} />
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-slate-600">
                Chưa tải được chi tiết các công việc trong chỉ thị.
              </p>
            )}
          </div>
        )}

        {directive.source === 'alert' && (
          <div className="rounded-xl border border-amber-100 bg-amber-50/60 p-4">
            <p className="font-bold text-slate-900">Cảnh báo trong chỉ thị</p>
            {directive.relatedAlerts?.length ? (
              <div className="mt-3 space-y-3">
                {directive.relatedAlerts.map((alert) => (
                  <AlertReviewItem key={alert.id} alert={alert} />
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-slate-600">
                Chưa tải được chi tiết các cảnh báo trong chỉ thị.
              </p>
            )}
          </div>
        )}

        <div className="space-y-3 text-sm leading-6 text-slate-700">
          {directive.detail && <DetailNote label="Nội dung chỉ thị" value={directive.detail} />}
          {directive.action_note && (
            <DetailNote label="Kế hoạch của Quản lý" value={directive.action_note} />
          )}
          {directive.commitment_date && (
            <DetailNote label="Thời hạn cam kết" value={formatDate(directive.commitment_date)} />
          )}
          {directive.completion_note && (
            <DetailNote label="Báo cáo nghiệm thu của Quản lý" value={directive.completion_note} />
          )}
          {directive.acceptance_note && (
            <DetailNote label="Ghi chú của Lãnh đạo" value={directive.acceptance_note} />
          )}
          {directive.revision_note && (
            <DetailNote label="Yêu cầu xử lý lại trước đó" value={directive.revision_note} />
          )}
        </div>

        <div className="flex justify-end border-t border-slate-200 pt-4">
          <Button type="button" variant="secondary" onClick={onClose}>
            Đóng
          </Button>
        </div>
      </div>
    </Dialog>
  )
}

function DetailNote({ label, value }) {
  return (
    <div className="rounded-xl bg-slate-50 p-3">
      <p className="font-semibold text-slate-800">{label}</p>
      <p className="mt-1 whitespace-pre-wrap">{value}</p>
    </div>
  )
}

function TaskReviewItem({ task }) {
  const overdueDays = getTaskOverdueDays(task)
  const isDone = task.status === 'done'
  return (
    <div className="rounded-lg bg-white p-3 text-sm ring-1 ring-red-100">
      <p className="font-bold text-slate-900">{task.title}</p>
      <p className="mt-1 text-slate-700">Nhân viên: {task.employee_name || 'Chưa xác định'}</p>
      <p className="mt-1 text-slate-600">Hạn xử lý: {formatDate(task.due_date)}</p>
      <p className={`mt-1 font-semibold ${overdueDays > 0 ? 'text-red-700' : 'text-emerald-700'}`}>
        {overdueDays > 0
          ? `Đã quá hạn ${overdueDays} ngày${isDone ? ' khi hoàn tất' : ''}`
          : isDone
            ? 'Đã hoàn thành đúng hạn'
            : 'Chưa quá hạn'}
      </p>
      {isDone && task.completed_at && (
        <p className="mt-1 text-slate-500">Hoàn tất: {formatDateTime(task.completed_at)}</p>
      )}
    </div>
  )
}

function AlertReviewItem({ alert }) {
  const isResolved = alert.status === 'resolved'
  return (
    <div className="rounded-lg bg-white p-3 text-sm ring-1 ring-amber-100">
      <p className="font-bold text-slate-900">{alert.title}</p>
      <p className="mt-1 text-slate-700">Nhân viên: {alert.employee_name || 'Chưa xác định'}</p>
      <p className="mt-1 text-slate-600">
        Loại: {ALERT_TYPE_LABELS[alert.alert_type] || 'Cảnh báo'} · Mức độ:{' '}
        {SEVERITY_LABELS[alert.severity] || 'Chưa xác định'}
      </p>
      <p className="mt-1 text-slate-600">Phát sinh: {formatDateTime(alert.created_at)}</p>
      {alert.detected_dates?.length > 0 && (
        <p className="mt-1 text-slate-600">
          Ngày phát hiện: {alert.detected_dates.map((date) => formatDate(date)).join(', ')}
        </p>
      )}
      {alert.message && <p className="mt-2 text-slate-700">Chi tiết: {alert.message}</p>}
      {alert.suggested_action && (
        <p className="mt-1 text-slate-700">Gợi ý xử lý: {alert.suggested_action}</p>
      )}
      <p className={`mt-1 font-semibold ${isResolved ? 'text-emerald-700' : 'text-amber-700'}`}>
        {isResolved ? 'Đã xử lý' : 'Chưa xử lý'}
      </p>
      {alert.resolution_note && (
        <p className="mt-1 whitespace-pre-wrap text-slate-500">
          Ghi chú xử lý: {alert.resolution_note}
        </p>
      )}
    </div>
  )
}

function getTaskOverdueDays(task) {
  if (!task?.due_date) return 0
  const dueDate = parseDateOnly(task.due_date)
  if (!dueDate) return 0
  const reference =
    task.status === 'done' && task.completed_at ? new Date(task.completed_at) : new Date()
  if (Number.isNaN(reference.getTime())) return 0
  const referenceDate = new Date(reference.getFullYear(), reference.getMonth(), reference.getDate())
  return Math.max(0, Math.floor((referenceDate - dueDate) / 86400000))
}

function parseDateOnly(value) {
  const [year, month, day] = String(value).slice(0, 10).split('-').map(Number)
  if (!year || !month || !day) return null
  return new Date(year, month - 1, day)
}

function SelectFilter({ label, value, onChange, children }) {
  return (
    <label className="min-w-56 text-sm font-semibold text-slate-700">
      {label}
      <Select className="mt-1" value={value} onChange={(event) => onChange(event.target.value)}>
        {children}
      </Select>
    </label>
  )
}

function formatDateTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Không xác định'
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function formatDate(value) {
  if (!value) return '—'
  const [year, month, day] = String(value).slice(0, 10).split('-').map(Number)
  return new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium' }).format(
    new Date(year, month - 1, day),
  )
}

export default DirectivesPage
