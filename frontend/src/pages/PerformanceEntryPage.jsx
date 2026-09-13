import { useEffect, useMemo, useRef, useState } from 'react'

import { AnimatedTableRows, FadeIn } from '../components/animations/index.js'
import { useActionFeedback } from '../components/feedback/index.js'
import AttachmentLink from '../components/attachments/AttachmentLink.jsx'
import MainLayout from '../components/layout/MainLayout.jsx'
import {
  Button,
  Dialog,
  Input,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Textarea,
} from '../components/ui/index.js'
import { listEmployees } from '../features/employees/employeesApi.js'
import {
  calculatePerformanceScore,
  taskVolumeScore,
} from '../features/performance/performanceScore.js'
import {
  getDailyPerformanceReview,
  getDailyReviewAttachmentUrl,
  listPerformance,
  saveDailyPerformanceReview,
  updateDailyPerformanceReview,
} from '../features/performance/performanceApi.js'
import { REALTIME_COALESCE_DELAY, useRealtimeUpdates } from '../hooks/useRealtimeUpdates.js'
import { generateIdempotencyKey } from '../utils/idempotency.js'

const today = businessToday()
const PRIORITY_WEIGHTS = { low: 1, medium: 1.25, high: 1.5 }
const PRIORITY_LABELS = { low: 'Thấp', medium: 'Trung bình', high: 'Cao' }
const STATUS_LABELS = { todo: 'Chưa bắt đầu', in_progress: 'Đang thực hiện', done: 'Đã hoàn thành' }

function businessToday() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Ho_Chi_Minh',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day}`
}

function PerformanceEntryPage() {
  const { confirmAction, notifyActionSuccess, notifyActionError } = useActionFeedback()
  const [employees, setEmployees] = useState([])
  const [metrics, setMetrics] = useState([])
  const [review, setReview] = useState(null)
  const [taskReviews, setTaskReviews] = useState({})
  const [form, setForm] = useState({ employee_id: '', date: today })
  const [isLoading, setIsLoading] = useState(true)
  const [isReviewLoading, setIsReviewLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const reviewRequestIdRef = useRef(0)
  const metricsRequestIdRef = useRef(0)
  const idempotencyKeyRef = useRef(null)

  useEffect(() => {
    async function loadEmployees() {
      try {
        const data = await listEmployees()
        setEmployees(data)
        setForm((current) => ({
          ...current,
          employee_id: current.employee_id || data[0]?.id || '',
        }))
      } catch {
        setError('Không thể tải danh sách nhân viên.')
      } finally {
        setIsLoading(false)
      }
    }
    loadEmployees()
  }, [])

  async function loadReview() {
    const employeeId = form.employee_id
    const reviewDate = form.date
    const requestId = ++reviewRequestIdRef.current
    if (!employeeId || !reviewDate) {
      setIsReviewLoading(false)
      return
    }
    setIsReviewLoading(true)
    setError('')
    try {
      const data = await getDailyPerformanceReview(employeeId, reviewDate)
      if (requestId !== reviewRequestIdRef.current) return
      const tasks = Array.isArray(data?.tasks) ? data.tasks : []
      const normalizedReview = {
        ...data,
        tasks: tasks.map((task) => ({
          ...task,
          attachments: Array.isArray(task.attachments) ? task.attachments : [],
        })),
      }
      setReview(normalizedReview)
      setTaskReviews(
        Object.fromEntries(
          normalizedReview.tasks.map((task) => [
            task.id,
            {
              score: task.score ?? '',
              note: task.note || '',
              missing_reason: task.missing_reason || '',
              change_reason: '',
            },
          ]),
        ),
      )
    } catch (requestError) {
      if (requestId !== reviewRequestIdRef.current) return
      setReview(null)
      setTaskReviews({})
      setError(requestError.message || 'Không thể tải công việc và bằng chứng trong ngày.')
    } finally {
      if (requestId === reviewRequestIdRef.current) setIsReviewLoading(false)
    }
  }

  async function loadMetrics(employeeId = form.employee_id, showError = true) {
    const requestId = ++metricsRequestIdRef.current
    if (!employeeId) {
      setMetrics([])
      return
    }
    try {
      const data = await listPerformance({ employeeId })
      if (requestId === metricsRequestIdRef.current) setMetrics(data)
    } catch {
      if (requestId === metricsRequestIdRef.current && showError) {
        setError('Không thể tải lịch sử hiệu suất.')
      }
    }
  }

  useEffect(() => {
    loadReview()
    loadMetrics(form.employee_id)
  }, [form.employee_id, form.date])

  const isReviewComplete = Boolean(
    review?.tasks.length &&
    review.summary.can_finalize &&
    review.summary.reviewed_task_count === review.tasks.length,
  )

  useRealtimeUpdates('tasks', loadReview, { coalesceDelay: REALTIME_COALESCE_DELAY })
  useRealtimeUpdates('task_execution_reports', loadReview, {
    coalesceDelay: REALTIME_COALESCE_DELAY,
  })
  useRealtimeUpdates(
    'performance_metrics',
    () => {
      loadMetrics(form.employee_id, false)
    },
    { coalesceDelay: REALTIME_COALESCE_DELAY },
  )

  const preview = useMemo(() => {
    const tasks = review?.tasks || []
    const scored = tasks
      .map((task) => ({ task, score: Number(taskReviews[task.id]?.score) }))
      .filter(({ score }) => Number.isFinite(score) && score >= 0 && score <= 100)
    const weightTotal = scored.reduce(
      (total, { task }) => total + (PRIORITY_WEIGHTS[task.priority] || 1.25),
      0,
    )
    const qualityTotal = scored.reduce(
      (total, { task, score }) => total + score * (PRIORITY_WEIGHTS[task.priority] || 1.25),
      0,
    )
    const quality = weightTotal ? qualityTotal / weightTotal : null
    return {
      quality,
      performance:
        quality === null
          ? null
          : calculatePerformanceScore(review.summary.tasks_completed, quality),
      volume: taskVolumeScore(review?.summary.tasks_completed || 0),
      scoredCount: scored.length,
    }
  }, [review, taskReviews])

  function updateForm(event) {
    const { name, value } = event.target
    if (name === 'employee_id' || name === 'date') idempotencyKeyRef.current = null
    setForm((current) => ({ ...current, [name]: value }))
    setReview(null)
    setTaskReviews({})
    setIsEditModalOpen(false)
    setSuccess('')
  }

  function updateTaskReview(taskId, field, value) {
    setTaskReviews((current) => ({ ...current, [taskId]: { ...current[taskId], [field]: value } }))
    setSuccess('')
  }

  function isTaskScoreChanged(task, item) {
    return (
      isEditModalOpen &&
      task.score !== null &&
      task.score !== undefined &&
      item.score !== '' &&
      Number(item.score) !== Number(task.score)
    )
  }

  function openReviewEdit(reviewDate) {
    setError('')
    setSuccess('')
    idempotencyKeyRef.current = null
    if (form.date !== reviewDate) {
      setReview(null)
      setTaskReviews({})
    }
    setForm((current) => ({ ...current, date: reviewDate }))
    setIsEditModalOpen(true)
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const isChangingReview = isEditModalOpen
    if (!review?.tasks.length) {
      setError('Chưa có công việc để nghiệm thu trong ngày này.')
      return
    }
    const taskWithoutChangeReason = isChangingReview
      ? review.tasks.find((task) => {
          const item = taskReviews[task.id] || {}
          return isTaskScoreChanged(task, item) && !item.change_reason?.trim()
        })
      : null
    if (taskWithoutChangeReason) {
      setError(`Vui lòng nhập lý do thay đổi điểm cho "${taskWithoutChangeReason.title}".`)
      return
    }
    const invalidTask = review.tasks.find((task) => {
      const item = taskReviews[task.id] || {}
      return (
        item.score === '' ||
        !Number.isFinite(Number(item.score)) ||
        Number(item.score) < 0 ||
        Number(item.score) > 100 ||
        (!task.attachments.length && !item.missing_reason?.trim())
      )
    })
    if (invalidTask) {
      setError(
        `Vui lòng chấm điểm và bổ sung minh chứng hoặc lý do thiếu minh chứng cho "${invalidTask.title}".`,
      )
      return
    }
    const employee = employees.find((item) => item.id === form.employee_id)
    const confirmed = await confirmAction({
      title: isChangingReview
        ? 'Xác nhận thay đổi điểm nghiệm thu'
        : 'Xác nhận ghi nhận nghiệm thu',
      description: isChangingReview
        ? 'Điểm nghiệm thu sẽ được cập nhật theo các giá trị bạn đã chỉnh sửa.'
        : 'Kết quả nghiệm thu sẽ được ghi nhận cho nhân viên trong ngày đã chọn.',
      details: [
        `Nhân viên: ${employee?.full_name || 'Chưa xác định'}`,
        `Ngày nghiệm thu: ${review.date || form.date}`,
        `Số công việc: ${review.tasks.length}`,
        `Điểm hiệu suất dự kiến: ${preview.performance == null ? 'Chưa đủ dữ liệu' : preview.performance.toFixed(1)}`,
      ],
      confirmLabel: isChangingReview ? 'Xác nhận thay đổi' : 'Xác nhận nghiệm thu',
    })
    if (!confirmed) return
    setError('')
    setSuccess('')
    idempotencyKeyRef.current ??= generateIdempotencyKey()
    setIsSaving(true)
    const employeeId = form.employee_id
    const reviewDate = form.date
    try {
      const payload = {
        employee_id: employeeId,
        date: reviewDate,
        items: review.tasks.map((task) => {
          const item = taskReviews[task.id] || {}
          const scoreChanged = isTaskScoreChanged(task, item)
          return {
            task_id: task.id,
            score: Number(item.score),
            note: item.note?.trim() || null,
            missing_reason: item.missing_reason?.trim() || null,
            change_reason: scoreChanged ? item.change_reason.trim() : null,
          }
        }),
      }
      const saved = isChangingReview
        ? await updateDailyPerformanceReview(payload, idempotencyKeyRef.current)
        : await saveDailyPerformanceReview(payload, idempotencyKeyRef.current)

      // API mutation đã trả về dữ liệu mới, nhưng vẫn tải lại theo đúng nhân viên/ngày
      // trước khi đóng modal để UI luôn phản ánh dữ liệu MongoDB cuối cùng.
      let refreshedReview = saved
      try {
        refreshedReview = await getDailyPerformanceReview(employeeId, reviewDate)
      } catch {
        // Giữ response của mutation nếu request refetch gặp lỗi tạm thời.
      }
      const refreshedTasks = Array.isArray(refreshedReview?.tasks)
        ? refreshedReview.tasks.map((task) => ({
            ...task,
            attachments: Array.isArray(task.attachments) ? task.attachments : [],
          }))
        : []
      const finalReview = { ...refreshedReview, tasks: refreshedTasks }
      setReview(finalReview)
      setTaskReviews(
        Object.fromEntries(
          finalReview.tasks.map((task) => [
            task.id,
            {
              score: task.score ?? '',
              note: task.note || '',
              missing_reason: task.missing_reason || '',
              change_reason: task.change_reason || '',
            },
          ]),
        ),
      )
      idempotencyKeyRef.current = null
      setIsEditModalOpen(false)
      await loadMetrics(employeeId, false)
      setSuccess(
        isChangingReview
          ? `Đã thay đổi điểm nghiệm thu của ${saved.employee.full_name} ngày ${saved.date}.`
          : `Đã nghiệm thu công việc của ${saved.employee.full_name} ngày ${saved.date}.`,
      )
      notifyActionSuccess({
        title: isChangingReview ? 'Đã thay đổi điểm nghiệm thu' : 'Đã ghi nhận nghiệm thu',
        message: isChangingReview
          ? `Điểm nghiệm thu của ${saved.employee.full_name} ngày ${saved.date} đã được cập nhật.`
          : `Kết quả nghiệm thu của ${saved.employee.full_name} ngày ${saved.date} đã được lưu.`,
        details: [`Điểm hiệu suất: ${saved.performance_score ?? preview.performance ?? 'Chưa có'}`],
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể lưu nghiệm thu ngày.'
      setError(message)
      notifyActionError({ title: 'Chưa lưu nghiệm thu', message })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <MainLayout>
      <FadeIn className="mx-auto max-w-7xl">
        <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200 sm:p-6">
          <p className="!text-caption !font-semibold !uppercase !tracking-wider !text-brand-600">
            Hiệu suất hàng ngày
          </p>
          <h1 className="mt-2 text-slate-900">Nghiệm thu bằng chứng công việc</h1>
          <p className="mt-2 text-ink-600">
            Xem kết quả thực tế, minh chứng và chấm điểm từng công việc trước khi ghi nhận hiệu
            suất.
          </p>
          {error && <p className="mt-5 rounded-lg bg-red-50 p-3 !text-sm !text-red-700">{error}</p>}
          {success && (
            <p className="mt-5 rounded-lg bg-emerald-50 p-3 !text-sm !text-emerald-700">
              {success}
            </p>
          )}

          <form className="mt-6" onSubmit={handleSubmit}>
            <div className="grid gap-5 sm:grid-cols-2">
              <label className="block text-sm font-medium text-slate-700">
                Nhân viên
                <Select
                  className="mt-1"
                  name="employee_id"
                  value={form.employee_id}
                  onChange={updateForm}
                  disabled={isLoading}
                  required
                >
                  <option value="">Chọn nhân viên</option>
                  {employees.map((employee) => (
                    <option key={employee.id} value={employee.id}>
                      {employee.full_name} — {employee.position}
                    </option>
                  ))}
                </Select>
              </label>
              <label className="block text-sm font-medium text-slate-700">
                Ngày đánh giá
                <Input
                  className="mt-1"
                  type="date"
                  name="date"
                  value={form.date}
                  onChange={updateForm}
                  required
                />
              </label>
            </div>

            {isReviewLoading && (
              <p className="mt-6 text-sm text-slate-500">Đang tải công việc và minh chứng…</p>
            )}
            {!isReviewLoading && review && !review.tasks.length && (
              <p className="mt-6 rounded-xl bg-slate-50 p-5 text-sm text-slate-600">
                Chưa có công việc hoặc báo cáo thực thi trong ngày này.
              </p>
            )}
            {!isReviewLoading &&
              review?.tasks.length > 0 &&
              (isReviewComplete ? (
                <CompletedReviewSummary review={review} onEdit={() => setIsEditModalOpen(true)} />
              ) : (
                <ReviewTaskFields
                  tasks={review.tasks}
                  taskReviews={taskReviews}
                  employeeId={review.employee.id}
                  reviewDate={review.date}
                  onChange={updateTaskReview}
                  isEditing={false}
                />
              ))}

            {!isReviewComplete && review?.tasks.length > 0 && (
              <div className="mt-6 grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
                <Button
                  type="submit"
                  className="min-h-11 w-full max-w-[260px] self-start px-5 text-base"
                  loading={isSaving}
                  disabled={isSaving || isLoading || isReviewLoading || !review?.tasks.length}
                >
                  Nghiệm thu và lưu điểm ngày
                </Button>
                <ReviewSummary preview={preview} taskCount={review.tasks.length} />
              </div>
            )}
          </form>
        </section>

        <section className="mt-6 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200 sm:p-6">
          <h2 className="text-slate-900">Lịch sử gần đây</h2>
          <p className="mt-2 text-sm text-ink-600">Các lần nghiệm thu của nhân viên đang chọn.</p>
          <div className="mt-5 overflow-x-auto">
            <Table className="min-w-[820px]">
              <TableHeader>
                <TableRow className="border-b border-slate-200">
                  <TableHead>Ngày</TableHead>
                  <TableHead>Đã chấm</TableHead>
                  <TableHead>Minh chứng</TableHead>
                  <TableHead>Chất lượng</TableHead>
                  <TableHead>Điểm hiệu suất</TableHead>
                  <TableHead>Ghi chú</TableHead>
                  <TableHead>Xem lại</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <AnimatedTableRows>
                  {metrics.slice(0, 10).map((metric) => (
                    <TableRow key={metric.id}>
                      <TableCell>{metric.date}</TableCell>
                      <TableCell>
                        {metric.reviewed_task_count || 0}/{metric.total_review_task_count || 0}
                      </TableCell>
                      <TableCell>
                        {metric.evidence_task_count || 0}/{metric.total_review_task_count || 0}
                      </TableCell>
                      <TableCell>{metric.quality_score}</TableCell>
                      <TableCell className="font-semibold text-brand-700">
                        {Number(metric.performance_score).toFixed(1)}
                      </TableCell>
                      <TableCell className="text-slate-600">
                        {metric.note || 'Chưa có ghi chú'}
                      </TableCell>
                      <TableCell>
                        {metric.total_review_task_count > 0 ? (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="px-0 font-medium text-brand-700 underline shadow-none hover:bg-transparent hover:text-brand-800"
                            onClick={() => openReviewEdit(metric.date)}
                          >
                            Thay đổi điểm
                          </Button>
                        ) : (
                          <span
                            className="text-slate-400"
                            title="Bản ghi cũ chưa có dữ liệu đánh giá theo từng công việc"
                          >
                            Không có chi tiết công việc
                          </span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </AnimatedTableRows>
                {!metrics.length && (
                  <TableRow>
                    <TableCell colSpan="7" className="py-8 text-center text-slate-500">
                      Chưa có dữ liệu hiệu suất.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </section>
      </FadeIn>

      {isEditModalOpen && (
        <Dialog
          title={
            review?.employee?.full_name
              ? `Thay đổi điểm nghiệm thu · ${review.employee.full_name}`
              : 'Đang tải dữ liệu đánh giá'
          }
          description={`Chỉnh sửa đánh giá công việc ngày ${review?.date || form.date}.`}
          className="max-w-5xl"
          onClose={() => !isSaving && setIsEditModalOpen(false)}
        >
          {isReviewLoading && (
            <div className="rounded-xl bg-slate-50 p-5 text-sm text-slate-600">
              Đang tải công việc và minh chứng của ngày {form.date}…
            </div>
          )}
          {!isReviewLoading && error && (
            <div className="space-y-4">
              <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>
              <Button type="button" variant="secondary" onClick={() => setIsEditModalOpen(false)}>
                Đóng
              </Button>
            </div>
          )}
          {!isReviewLoading && !error && !review && (
            <div className="space-y-4">
              <p className="rounded-xl bg-slate-50 p-5 text-sm text-slate-600">
                Chưa có dữ liệu đánh giá cho ngày này.
              </p>
              <Button type="button" variant="secondary" onClick={() => setIsEditModalOpen(false)}>
                Đóng
              </Button>
            </div>
          )}
          {!isReviewLoading && review && (
            <form className="space-y-5" onSubmit={handleSubmit}>
              {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
              <ReviewTaskFields
                tasks={review.tasks}
                taskReviews={taskReviews}
                employeeId={review.employee.id}
                reviewDate={review.date}
                onChange={updateTaskReview}
                isEditing
              />
              <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
                <div className="flex items-end justify-end gap-3">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => setIsEditModalOpen(false)}
                    disabled={isSaving}
                  >
                    Hủy
                  </Button>
                  <Button
                    type="submit"
                    className="min-h-11 min-w-48 self-start px-6 text-base"
                    loading={isSaving}
                    disabled={isSaving}
                  >
                    Lưu thay đổi điểm
                  </Button>
                </div>
                <ReviewSummary preview={preview} taskCount={review.tasks.length} />
              </div>
            </form>
          )}
        </Dialog>
      )}
    </MainLayout>
  )
}

function ReviewTaskFields({
  tasks,
  taskReviews,
  employeeId,
  reviewDate,
  onChange,
  isEditing = false,
}) {
  return (
    <div className="mt-6 space-y-4">
      {tasks.map((task) => {
        const item = taskReviews[task.id] || {}
        const hasEvidence = task.attachments.length > 0
        const scoreChanged =
          isEditing &&
          task.score !== null &&
          task.score !== undefined &&
          item.score !== '' &&
          Number(item.score) !== Number(task.score)
        return (
          <article key={task.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">{task.title}</h2>
                <p className="mt-1 text-sm text-slate-600">
                  {task.description || 'Không có mô tả.'}
                </p>
              </div>
              <div className="flex flex-wrap gap-2 text-xs font-medium">
                <span className="rounded-full bg-white px-3 py-1 text-slate-700">
                  {PRIORITY_LABELS[task.priority] || task.priority}
                </span>
                <span className="rounded-full bg-white px-3 py-1 text-slate-700">
                  {STATUS_LABELS[task.status] || task.status}
                </span>
                <span className="rounded-full bg-white px-3 py-1 text-slate-700">
                  Hạn {task.due_date}
                </span>
                <span className="rounded-full bg-white px-3 py-1 text-slate-700">
                  {task.subtask_count} việc con
                </span>
              </div>
            </div>
            <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_260px]">
              <div className="space-y-3 text-sm text-slate-600">
                <p>
                  Kết quả Nhân viên gửi:{' '}
                  <strong className="text-slate-800">
                    {task.result_summary || 'Chưa có báo cáo'}
                  </strong>
                </p>
                <p>
                  Tiến độ báo cáo:{' '}
                  <strong className="text-slate-800">{task.progress_percent}%</strong>
                </p>
                <div>
                  <p className="font-medium text-slate-700">Minh chứng</p>
                  {hasEvidence ? (
                    <ul className="mt-1 list-inside list-disc">
                      {task.attachments.map((attachment) => (
                        <li key={attachment.attachment_id}>
                          <AttachmentLink
                            attachment={attachment}
                            getDownloadUrl={() =>
                              getDailyReviewAttachmentUrl(
                                employeeId,
                                reviewDate,
                                attachment.attachment_id,
                              )
                            }
                          />
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1 text-amber-700">Chưa có tệp minh chứng.</p>
                  )}
                </div>
                {!hasEvidence && (
                  <label className="block font-medium text-slate-700">
                    Lý do thiếu minh chứng <span className="text-red-600">*</span>
                    <Textarea
                      className="mt-1 min-h-20 bg-white font-normal"
                      value={item.missing_reason || ''}
                      onChange={(event) => onChange(task.id, 'missing_reason', event.target.value)}
                      placeholder="Nêu rõ lý do chưa có tệp minh chứng"
                    />
                  </label>
                )}
              </div>
              <div className="space-y-3 rounded-xl bg-white p-4 ring-1 ring-slate-200">
                <label className="block text-sm font-medium text-slate-700">
                  Điểm công việc (0–100)
                  {isEditing && (
                    <span className="ml-2 font-normal text-slate-500">
                      (Điểm hiện tại: {task.score ?? '—'})
                    </span>
                  )}
                  <Input
                    className="mt-1"
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    value={item.score}
                    onChange={(event) => onChange(task.id, 'score', event.target.value)}
                    required
                  />
                </label>
                {isEditing && (
                  <label className="block text-sm font-medium text-slate-700">
                    Lý do thay đổi điểm
                    {scoreChanged && <span className="text-red-600"> *</span>}
                    <Textarea
                      className="mt-1 min-h-20 font-normal"
                      value={item.change_reason || ''}
                      onChange={(event) => onChange(task.id, 'change_reason', event.target.value)}
                      placeholder="Nêu rõ căn cứ thay đổi điểm cho công việc này"
                      required={scoreChanged}
                    />
                    <span className="mt-1 block text-xs font-normal text-slate-500">
                      Bắt buộc khi điểm mới khác điểm đã lưu.
                    </span>
                  </label>
                )}
                <label className="block text-sm font-medium text-slate-700">
                  Nhận xét
                  <Textarea
                    className="mt-1 min-h-20 font-normal"
                    value={item.note || ''}
                    onChange={(event) => onChange(task.id, 'note', event.target.value)}
                    placeholder="Nhận xét ngắn về kết quả"
                  />
                </label>
              </div>
            </div>
          </article>
        )
      })}
    </div>
  )
}

function ReviewSummary({ preview, taskCount }) {
  return (
    <aside className="rounded-2xl border border-brand-100 bg-gradient-to-br from-brand-50 to-white p-4 text-brand-900 shadow-sm">
      <p className="flex items-center gap-2 !text-caption !font-semibold !uppercase !tracking-wider !text-brand-700">
        <span aria-hidden="true" className="text-base">
          ✦
        </span>
        Tổng hợp dự kiến
      </p>
      <p className="mt-2 text-sm">
        Đã chấm: {preview.scoredCount}/{taskCount} công việc
      </p>
      <p className="mt-1 text-2xl font-bold">
        {preview.performance === null ? '—' : preview.performance.toFixed(1)}
      </p>
      <p className="mt-1 text-sm leading-6">
        Chất lượng có trọng số:{' '}
        {preview.quality === null ? '—' : `${preview.quality.toFixed(1)}/100`}
      </p>
      <p className="mt-1 text-sm">Điểm khối lượng: {preview.volume.toFixed(1)}</p>
      <p className="mt-2 border-t border-brand-100 pt-2 text-xs leading-5 text-brand-700">
        Mức ưu tiên cao có trọng số 1,5; trung bình 1,25; thấp 1.
      </p>
    </aside>
  )
}

function CompletedReviewSummary({ review, onEdit }) {
  return (
    <div className="mt-6 rounded-2xl border border-emerald-200 bg-emerald-50/70 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-emerald-700">
            Đã nghiệm thu trong ngày
          </p>
          <h2 className="mt-1 text-xl font-bold text-slate-900">
            Kết quả đánh giá của {review.employee.full_name}
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Đã chấm {review.summary.reviewed_task_count}/{review.tasks.length} công việc và ghi nhận
            một kết quả duy nhất cho ngày {review.date}.
          </p>
        </div>
        <Button type="button" variant="secondary" onClick={onEdit}>
          Thay đổi điểm
        </Button>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <MetricPill label="Điểm chất lượng" value={`${review.summary.quality_score ?? '—'}/100`} />
        <MetricPill label="Điểm hiệu suất" value={review.summary.performance_score ?? '—'} />
        <MetricPill
          label="Công việc hoàn thành"
          value={`${review.summary.tasks_completed}/${review.tasks.length}`}
        />
      </div>
    </div>
  )
}

function MetricPill({ label, value }) {
  return (
    <div className="rounded-xl bg-white px-4 py-3 ring-1 ring-emerald-100">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-bold text-emerald-800">{value}</p>
    </div>
  )
}

export default PerformanceEntryPage
