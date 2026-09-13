import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { AnimatedTableRows, FadeIn } from '../components/animations/index.js'
import { useActionFeedback } from '../components/feedback/index.js'
import AttachmentLink from '../components/attachments/AttachmentLink.jsx'
import { DirectUploadError, uploadFilesDirectly } from '../components/attachments/UploadManager.js'
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
import {
  createDepartmentEvaluation,
  getDepartmentEvaluation,
  getDepartmentEvaluationAttachmentUrl,
  getWeeklyDepartmentReview,
  listDepartmentEvaluations,
  updateDepartmentEvaluation,
} from '../features/departmentEvaluations/departmentEvaluationsApi.js'
import { listDepartments } from '../features/departments/departmentsApi.js'
import { REALTIME_COALESCE_DELAY, useRealtimeUpdates } from '../hooks/useRealtimeUpdates.js'
import { generateIdempotencyKey } from '../utils/idempotency.js'

const STABILITY_LABELS = {
  improving: 'Đang cải thiện',
  stable: 'Ổn định',
  needs_attention: 'Cần chú ý',
  insufficient_data: 'Chưa đủ dữ liệu',
}

const STATUS_LABELS = {
  pending: 'Chờ tiếp nhận',
  acknowledged: 'Đang thực hiện',
  submitted: 'Chờ nghiệm thu',
  accepted: 'Đã nghiệm thu',
  needs_revision: 'Cần xử lý lại',
}

const TIMING_LABELS = {
  on_time: 'Đúng hạn',
  late: 'Hoàn thành trễ',
  overdue: 'Đang quá hạn',
  not_due: 'Chưa đến hạn',
  no_commitment: 'Dữ liệu cũ chưa có mốc cam kết',
}

function defaultWeekStart() {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Ho_Chi_Minh',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      hourCycle: 'h23',
    })
      .formatToParts(new Date())
      .filter(({ type }) => type !== 'literal')
      .map(({ type, value }) => [type, Number(value)]),
  )
  const vietnamToday = new Date(Date.UTC(parts.year, parts.month - 1, parts.day))
  const weekdayFromMonday = (vietnamToday.getUTCDay() + 6) % 7
  vietnamToday.setUTCDate(vietnamToday.getUTCDate() - weekdayFromMonday)
  const isBeforeFridayCutoff = weekdayFromMonday < 4 || (weekdayFromMonday === 4 && parts.hour < 17)
  if (isBeforeFridayCutoff) vietnamToday.setUTCDate(vietnamToday.getUTCDate() - 7)
  return vietnamToday.toISOString().slice(0, 10)
}

function formatDate(value) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('vi-VN').format(new Date(`${value}T00:00:00`))
}

function formatDateTime(value) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone: 'Asia/Ho_Chi_Minh',
  }).format(new Date(value))
}

function formatNumber(value, suffix = '') {
  return value == null ? 'Chưa có dữ liệu' : `${Number(value).toFixed(1)}${suffix}`
}

function formatDelta(value, suffix = '') {
  if (value == null) return 'Chưa đủ dữ liệu đối chiếu'
  const sign = value > 0 ? '+' : ''
  return `${sign}${Number(value).toFixed(1)}${suffix} so với tuần trước`
}

function formatDelay(hours) {
  if (!hours) return ''
  if (hours < 24) return ` · trễ ${hours.toFixed(1)} giờ`
  const days = Math.floor(hours / 24)
  const remaining = Math.round(hours % 24)
  return ` · trễ ${days} ngày${remaining ? ` ${remaining} giờ` : ''}`
}

function DepartmentEvaluationsPage() {
  const { confirmAction, notifyActionSuccess, notifyActionError } = useActionFeedback()
  const [departments, setDepartments] = useState([])
  const [history, setHistory] = useState([])
  const [historyPage, setHistoryPage] = useState(1)
  const [hasMoreHistory, setHasMoreHistory] = useState(false)
  const [isLoadingMoreHistory, setIsLoadingMoreHistory] = useState(false)
  const [selectedHistoryEvaluation, setSelectedHistoryEvaluation] = useState(null)
  const [isHistoryDetailLoading, setIsHistoryDetailLoading] = useState(false)
  const [historyDetailError, setHistoryDetailError] = useState('')
  const [departmentId, setDepartmentId] = useState('')
  const [weekStart, setWeekStart] = useState(defaultWeekStart)
  const [review, setReview] = useState(null)
  const [scores, setScores] = useState({ directive: 80, stability: 80, timeliness: 80 })
  const [assessmentNote, setAssessmentNote] = useState('')
  const [files, setFiles] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [isReviewLoading, setIsReviewLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(null)
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const idempotencyKeyRef = useRef(null)
  const uploadIdempotencyKeysRef = useRef(null)

  const loadBaseData = useCallback(async () => {
    setIsLoading(true)
    try {
      const [departmentData, historyData] = await Promise.all([
        listDepartments(),
        listDepartmentEvaluations(),
      ])
      setDepartments(departmentData || [])
      const historyItems = historyData?.items || historyData || []
      setHistory(historyItems)
      setHistoryPage(historyData?.page || 1)
      setHasMoreHistory(Boolean(historyData?.has_next))
      setDepartmentId((current) => current || departmentData?.[0]?.id || '')
      setError('')
    } catch {
      setError('Không thể tải dữ liệu đánh giá phòng ban.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  async function loadMoreHistory() {
    if (isLoadingMoreHistory || !hasMoreHistory) return
    setIsLoadingMoreHistory(true)
    try {
      const nextPage = historyPage + 1
      const data = await listDepartmentEvaluations('', nextPage, 12)
      setHistory((current) => [...current, ...(data?.items || [])])
      setHistoryPage(data?.page || nextPage)
      setHasMoreHistory(Boolean(data?.has_next))
    } catch (requestError) {
      setError(requestError.message || 'Không thể tải thêm lịch sử đánh giá.')
    } finally {
      setIsLoadingMoreHistory(false)
    }
  }

  async function openHistoryDetail(evaluationId) {
    setIsHistoryDetailLoading(true)
    setHistoryDetailError('')
    try {
      setSelectedHistoryEvaluation(await getDepartmentEvaluation(evaluationId))
    } catch (requestError) {
      setHistoryDetailError(requestError.message || 'Không thể tải chi tiết đánh giá.')
    } finally {
      setIsHistoryDetailLoading(false)
    }
  }

  const loadReview = useCallback(async () => {
    if (!departmentId || !weekStart) return
    setIsReviewLoading(true)
    try {
      const data = await getWeeklyDepartmentReview(departmentId, weekStart)
      setReview(data)
      if (data.existing_evaluation) {
        setScores({
          directive: data.existing_evaluation.directive_execution_score,
          stability: data.existing_evaluation.stability_score,
          timeliness: data.existing_evaluation.timeliness_score,
        })
        setAssessmentNote(data.existing_evaluation.assessment_note || '')
      } else {
        setScores({ directive: 80, stability: 80, timeliness: 80 })
        setAssessmentNote('')
      }
      setFiles([])
      idempotencyKeyRef.current = null
      uploadIdempotencyKeysRef.current = null
      setError('')
    } catch (requestError) {
      setReview(null)
      setError(requestError.message || 'Không thể tải bằng chứng đánh giá tuần.')
    } finally {
      setIsReviewLoading(false)
    }
  }, [departmentId, weekStart])

  useEffect(() => {
    void loadBaseData()
  }, [loadBaseData])

  useEffect(() => {
    void loadReview()
  }, [loadReview])

  useRealtimeUpdates('performance_metrics', () => void loadReview(), {
    coalesceDelay: REALTIME_COALESCE_DELAY,
  })
  useRealtimeUpdates('tasks', () => void loadReview(), {
    coalesceDelay: REALTIME_COALESCE_DELAY,
  })
  useRealtimeUpdates('alerts', () => void loadReview(), {
    coalesceDelay: REALTIME_COALESCE_DELAY,
  })
  useRealtimeUpdates('task_directives', () => void loadReview(), {
    coalesceDelay: REALTIME_COALESCE_DELAY,
  })
  useRealtimeUpdates('department_directives', () => void loadReview(), {
    coalesceDelay: REALTIME_COALESCE_DELAY,
  })
  useRealtimeUpdates(
    'department_evaluations',
    () => {
      void loadReview()
      void loadBaseData()
    },
    { coalesceDelay: REALTIME_COALESCE_DELAY },
  )

  const overallScore = useMemo(
    () =>
      Math.round(
        (Number(scores.directive) * 0.4 +
          Number(scores.stability) * 0.4 +
          Number(scores.timeliness) * 0.2) *
          10,
      ) / 10,
    [scores],
  )

  async function handleSubmit(event) {
    event.preventDefault()
    if (!review || isSaving) return
    const existing = review.existing_evaluation
    if (!existing && files.length === 0) {
      setError('Vui lòng đính kèm ít nhất một tài liệu định hướng tuần mới.')
      return
    }
    const department = departments.find((item) => item.id === departmentId)
    const confirmed = await confirmAction({
      title: existing ? 'Xác nhận thay đổi đánh giá phòng ban' : 'Xác nhận lưu đánh giá phòng ban',
      description: existing
        ? 'Kết quả đánh giá sẽ được cập nhật theo thông tin bạn đã chỉnh sửa.'
        : 'Đánh giá và định hướng tuần sẽ được ghi nhận cho phòng ban này.',
      details: [
        `Phòng ban: ${department?.name || 'Chưa xác định'}`,
        `Tuần đánh giá: ${formatDate(weekStart)}`,
        `Điểm thực hiện chỉ thị: ${scores.directive}/100`,
        `Điểm ổn định: ${scores.stability}/100`,
        `Khả năng hoàn thành đúng hạn: ${scores.timeliness}/100`,
        `Tài liệu đính kèm: ${files.length}`,
      ],
      confirmLabel: existing ? 'Xác nhận thay đổi' : 'Xác nhận lưu đánh giá',
    })
    if (!confirmed) return
    setIsSaving(true)
    setError('')
    setSuccess('')
    idempotencyKeyRef.current ??= generateIdempotencyKey()
    if (files.length && !uploadIdempotencyKeysRef.current) {
      uploadIdempotencyKeysRef.current = files.map(() => ({
        create: generateIdempotencyKey(),
        complete: generateIdempotencyKey(),
      }))
    }
    let submitFiles = files
    let attachmentSessionIds = []
    try {
      if (files.length && import.meta.env.VITE_DIRECT_UPLOAD_ENABLED === 'true') {
        attachmentSessionIds = await uploadFilesDirectly({
          files,
          context: {
            purpose: 'department_evaluation',
            department_id: departmentId,
            week_start: review.week_start,
          },
          idempotencyKeys: uploadIdempotencyKeysRef.current || [],
          onProgress: setUploadProgress,
        })
        submitFiles = []
      }
    } catch (requestError) {
      if (!(requestError instanceof DirectUploadError) || !requestError.fallbackAllowed) {
        setError(requestError.message || 'Không thể tải tài liệu định hướng.')
        notifyActionError({
          title: 'Chưa lưu đánh giá phòng ban',
          message: requestError.message || 'Không thể tải tài liệu định hướng.',
        })
        setIsSaving(false)
        setUploadProgress(null)
        return
      }
      setSuccess(
        'Tải trực tiếp chưa sẵn sàng, đang chuyển sang phương thức tải tệp thông thường...',
      )
      attachmentSessionIds = []
      submitFiles = files
    }
    const payload = {
      directive_execution_score: Number(scores.directive),
      stability_score: Number(scores.stability),
      timeliness_score: Number(scores.timeliness),
      assessment_note: assessmentNote || null,
      attachment_session_ids: attachmentSessionIds,
    }
    try {
      if (existing) {
        await updateDepartmentEvaluation(
          existing.id,
          payload,
          submitFiles,
          idempotencyKeyRef.current,
        )
        setSuccess('Đã cập nhật đánh giá phòng ban.')
        setIsEditModalOpen(false)
      } else {
        await createDepartmentEvaluation(
          { ...payload, department_id: departmentId, week_start: weekStart },
          submitFiles,
          idempotencyKeyRef.current,
        )
        setSuccess('Đã lưu đánh giá và định hướng tuần tiếp theo.')
      }
      await Promise.all([loadReview(), loadBaseData()])
      idempotencyKeyRef.current = null
      uploadIdempotencyKeysRef.current = null
      notifyActionSuccess({
        title: existing ? 'Đã thay đổi đánh giá phòng ban' : 'Đã lưu đánh giá phòng ban',
        message: `Đánh giá phòng ban ${department?.name || 'đã chọn'} cho tuần ${formatDate(weekStart)} đã được ghi nhận.`,
        details: [`Điểm tổng hợp: ${overallScore}/100`],
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể lưu đánh giá phòng ban.'
      setError(message)
      notifyActionError({ title: 'Chưa lưu đánh giá phòng ban', message })
    } finally {
      setIsSaving(false)
      setUploadProgress(null)
    }
  }

  const stability = review?.evidence.stability
  const directives = review?.evidence.directives
  const existing = review?.existing_evaluation
  const canSubmit = Boolean(
    review &&
    review.can_evaluate &&
    !isSaving &&
    (existing || files.length > 0) &&
    Object.values(scores).every(
      (value) =>
        value !== '' &&
        Number.isFinite(Number(value)) &&
        Number(value) >= 0 &&
        Number(value) <= 100,
    ),
  )

  function updateEvaluationScores(nextScores) {
    idempotencyKeyRef.current = null
    setScores(nextScores)
  }

  function updateAssessmentNote(nextNote) {
    idempotencyKeyRef.current = null
    setAssessmentNote(nextNote)
  }

  function updateEvaluationFiles(nextFiles) {
    idempotencyKeyRef.current = null
    uploadIdempotencyKeysRef.current = null
    setFiles(nextFiles)
  }

  return (
    <MainLayout>
      <FadeIn className="mx-auto max-w-7xl">
        <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="!text-caption !font-semibold !uppercase !tracking-wider !text-brand-600">
                Góc nhìn Lãnh đạo
              </p>
              <h1 className="mt-2 text-slate-900">Đánh giá phòng ban theo tuần</h1>
              <p className="mt-2 max-w-3xl text-ink-600">
                Đánh giá dựa trên kết quả thực hiện, độ ổn định và khả năng hoàn thành đúng hạn của
                phòng ban.
              </p>
            </div>
            {review && (
              <span
                className={`rounded-full px-4 py-2 text-sm font-bold ${review.can_evaluate ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-800'}`}
              >
                {review.can_evaluate
                  ? review.evaluation_delay_days
                    ? `Đánh giá trễ ${review.evaluation_delay_days} ngày`
                    : 'Đã đến thời gian đánh giá'
                  : `Mở lúc ${formatDateTime(review.available_from)}`}
              </span>
            )}
          </div>

          <div className="mt-6 grid gap-4 rounded-2xl bg-slate-50 p-4 md:grid-cols-2">
            <label htmlFor="department" className="text-sm font-semibold text-slate-700">
              Phòng ban
              <Select
                id="department"
                className="mt-1"
                value={departmentId}
                onChange={(event) => {
                  idempotencyKeyRef.current = null
                  uploadIdempotencyKeysRef.current = null
                  setDepartmentId(event.target.value)
                }}
                disabled={isLoading}
              >
                {departments.map((department) => (
                  <option key={department.id} value={department.id}>
                    {department.name} ({department.code})
                  </option>
                ))}
              </Select>
            </label>
            <label htmlFor="week-start" className="text-sm font-semibold text-slate-700">
              Thứ Hai bắt đầu tuần
              <Input
                id="week-start"
                className="mt-1"
                type="date"
                value={weekStart}
                onChange={(event) => {
                  idempotencyKeyRef.current = null
                  uploadIdempotencyKeysRef.current = null
                  setWeekStart(event.target.value)
                }}
              />
            </label>
          </div>

          {error && <p className="mt-5 rounded-xl bg-red-50 p-4 text-sm text-red-700">{error}</p>}
          {success && (
            <p className="mt-5 rounded-xl bg-emerald-50 p-4 text-sm text-emerald-700">{success}</p>
          )}
          {uploadProgress && (
            <p className="mt-4 rounded-xl bg-blue-50 p-4 text-sm text-blue-700">
              {uploadProgress.state === 'preparing' && 'Đang chuẩn bị tệp'}
              {uploadProgress.state === 'uploading' && 'Đang tải tệp lên kho lưu trữ'}
              {uploadProgress.state === 'verified' && 'Tệp đã được xác minh'}:{' '}
              {uploadProgress.fileName} ({uploadProgress.index + 1}/{uploadProgress.total})
            </p>
          )}

          {isReviewLoading || isLoading ? (
            <p className="mt-6 rounded-xl bg-slate-50 p-8 text-center text-slate-500">
              Đang tổng hợp dữ liệu đánh giá...
            </p>
          ) : review ? (
            <form className="mt-6 space-y-6" onSubmit={handleSubmit}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-xl font-bold text-slate-900">
                    {review.department_name} · {review.department_code}
                  </h2>
                  <p className="mt-1 text-sm text-slate-600">
                    Tuần {formatDate(review.week_start)} – {formatDate(review.week_end)} · Quản lý:{' '}
                    {review.manager_name || 'Chưa có Quản lý phụ trách'}
                  </p>
                </div>
                {existing && (
                  <span className="rounded-full bg-brand-50 px-3 py-2 text-sm font-bold text-brand-700">
                    Đã đánh giá · {existing.overall_score.toFixed(1)} điểm
                  </span>
                )}
              </div>

              <div className="grid gap-4 lg:grid-cols-3">
                <EvidenceCard
                  title="Kết quả thực hiện chỉ thị"
                  value={directives.total_count}
                  unit="chỉ thị liên quan"
                  detail={`${directives.accepted_count} đã nghiệm thu · ${directives.needs_revision_count} cần xử lý lại`}
                  tone="blue"
                />
                <EvidenceCard
                  title="Tình hình phòng ban"
                  value={STABILITY_LABELS[stability.status]}
                  unit="so với tuần trước"
                  detail={`Hiệu suất ${formatDelta(stability.deltas.performance_score, ' điểm')}`}
                  tone={stability.status === 'needs_attention' ? 'red' : 'green'}
                />
                <EvidenceCard
                  title="Khả năng hoàn thành đúng hạn"
                  value={
                    directives.on_time_rate == null
                      ? 'Chưa đủ dữ liệu'
                      : `${directives.on_time_rate}%`
                  }
                  unit={`${directives.with_commitment_count} chỉ thị có cam kết`}
                  detail={`${directives.late_count} hoàn thành trễ · ${directives.overdue_count} đang quá hạn`}
                  tone="amber"
                />
              </div>

              <section className="rounded-2xl border border-slate-200 p-5">
                <h2 className="text-lg font-bold text-slate-900">Sức khỏe phòng ban</h2>
                <p className="mt-1 text-sm text-slate-600">
                  Các con số hiện tại được đặt cạnh biến động so với tuần làm việc liền trước.
                </p>
                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <MetricTile
                    label="Hiệu suất trung bình"
                    value={formatNumber(stability.current.average_performance_score, ' điểm')}
                    previous={formatNumber(stability.previous.average_performance_score, ' điểm')}
                    delta={formatDelta(stability.deltas.performance_score, ' điểm')}
                  />
                  <MetricTile
                    label="Chất lượng trung bình"
                    value={formatNumber(stability.current.average_quality_score, ' điểm')}
                    previous={formatNumber(stability.previous.average_quality_score, ' điểm')}
                    delta={formatDelta(stability.deltas.quality_score, ' điểm')}
                  />
                  <MetricTile
                    label="Ngày có dữ liệu hiệu suất"
                    value={stability.current.performance_metric_days}
                    previous={stability.previous.performance_metric_days}
                    delta={formatDelta(stability.deltas.performance_metric_days)}
                  />
                  <MetricTile
                    label="Khối lượng hoàn thành ghi nhận"
                    value={stability.current.performance_tasks_completed}
                    previous={stability.previous.performance_tasks_completed}
                    delta={formatDelta(stability.deltas.performance_tasks_completed)}
                  />
                  <MetricTile
                    label="Công việc hoàn thành"
                    value={stability.current.completed_task_count}
                    previous={stability.previous.completed_task_count}
                    delta={formatDelta(stability.deltas.completed_tasks)}
                  />
                  <MetricTile
                    label="Công việc quá hạn"
                    value={stability.current.overdue_task_count}
                    previous={stability.previous.overdue_task_count}
                    delta={formatDelta(stability.deltas.overdue_tasks)}
                  />
                  <MetricTile
                    label="Dấu hiệu sớm phát sinh"
                    value={stability.current.early_warning_count}
                    previous={stability.previous.early_warning_count}
                    delta={formatDelta(stability.deltas.early_warnings)}
                  />
                  <MetricTile
                    label="Cảnh báo quá tải phát sinh"
                    value={stability.current.overload_count}
                    previous={stability.previous.overload_count}
                    delta={formatDelta(stability.deltas.overload_alerts)}
                  />
                  <MetricTile
                    label="Cảnh báo đã xử lý"
                    value={stability.current.resolved_alert_count}
                    previous={stability.previous.resolved_alert_count}
                    delta={formatDelta(stability.deltas.resolved_alerts)}
                  />
                  <MetricTile
                    label="Cảnh báo còn mở"
                    value={stability.current.open_alert_count}
                    previous={stability.previous.open_alert_count}
                    delta={formatDelta(stability.deltas.open_alerts)}
                  />
                </div>
              </section>

              <section className="rounded-2xl border border-slate-200 p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-bold text-slate-900">
                      Tiến độ và thời hạn chỉ thị
                    </h2>
                    <p className="mt-1 text-sm text-slate-600">
                      Độ trễ được tính đến lúc Quản lý gửi nghiệm thu, không tính thời gian chờ Lãnh
                      đạo duyệt.
                    </p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-sm font-bold text-slate-600">
                    {directives.completed_count}/{directives.total_count} hoàn tất
                  </span>
                </div>
                <div className="mt-4 overflow-x-auto">
                  <Table className="min-w-full">
                    <TableHeader>
                      <TableRow className="border-b border-slate-200">
                        <TableHead>Nhóm chỉ thị</TableHead>
                        <TableHead>Trạng thái</TableHead>
                        <TableHead>Tiến độ</TableHead>
                        <TableHead>Ngày phát hành</TableHead>
                        <TableHead>Ngày cam kết</TableHead>
                        <TableHead>Gửi nghiệm thu</TableHead>
                        <TableHead>Kết quả thời hạn</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      <AnimatedTableRows>
                        {directives.items.map((item) => (
                          <TableRow key={`${item.source}-${item.directive_id}`}>
                            <TableCell className="font-semibold text-slate-800">
                              {item.source_label}
                            </TableCell>
                            <TableCell>{STATUS_LABELS[item.status] || item.status}</TableCell>
                            <TableCell>{item.progress_percent}%</TableCell>
                            <TableCell>{formatDateTime(item.issued_at)}</TableCell>
                            <TableCell>{formatDate(item.commitment_date)}</TableCell>
                            <TableCell>{formatDateTime(item.submitted_at)}</TableCell>
                            <TableCell className="font-medium">
                              {TIMING_LABELS[item.timing_status]}
                              {formatDelay(item.delay_hours)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </AnimatedTableRows>
                      {!directives.items.length && (
                        <TableRow>
                          <TableCell colSpan="7" className="py-7 text-center text-slate-500">
                            Không có chỉ thị liên quan trong kỳ này.
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </div>
              </section>

              {existing ? (
                <CompletedEvaluationSummary
                  evaluation={existing}
                  onEdit={() => {
                    setFiles([])
                    idempotencyKeyRef.current = null
                    uploadIdempotencyKeysRef.current = null
                    setIsEditModalOpen(true)
                  }}
                />
              ) : (
                <EvaluationEditor
                  scores={scores}
                  setScores={updateEvaluationScores}
                  assessmentNote={assessmentNote}
                  setAssessmentNote={updateAssessmentNote}
                  files={files}
                  setFiles={updateEvaluationFiles}
                  overallScore={overallScore}
                  canSubmit={canSubmit}
                  isSaving={isSaving}
                />
              )}
            </form>
          ) : null}
        </section>

        <section className="mt-6 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200 sm:p-6">
          <h2 className="text-xl font-bold text-slate-900">Lịch sử đánh giá tuần</h2>
          <div className="mt-5 overflow-x-auto">
            <Table className="min-w-full">
              <TableHeader>
                <TableRow className="border-b border-slate-200">
                  <TableHead>Tuần</TableHead>
                  <TableHead>Phòng ban</TableHead>
                  <TableHead>Điểm tổng</TableHead>
                  <TableHead>Tài liệu định hướng</TableHead>
                  <TableHead>Thời điểm đánh giá</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <AnimatedTableRows>
                  {history.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="px-0 text-left font-semibold text-brand-700 shadow-none hover:bg-transparent hover:text-brand-800 hover:underline"
                          onClick={() => void openHistoryDetail(item.id)}
                        >
                          {formatDate(item.week_start)} – {formatDate(item.week_end)}
                        </Button>
                      </TableCell>
                      <TableCell className="font-semibold">{item.department_name}</TableCell>
                      <TableCell className="font-bold text-brand-700">
                        {item.overall_score.toFixed(1)}
                      </TableCell>
                      <TableCell>
                        {item.attachment_count ?? item.attachments?.length ?? 0} tệp
                      </TableCell>
                      <TableCell>{formatDateTime(item.evaluated_at)}</TableCell>
                    </TableRow>
                  ))}
                </AnimatedTableRows>
                {!history.length && (
                  <TableRow>
                    <TableCell colSpan="5" className="py-8 text-center text-slate-500">
                      Chưa có đánh giá phòng ban theo tuần.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
          {hasMoreHistory && (
            <Button
              type="button"
              variant="secondary"
              className="mt-4"
              onClick={() => void loadMoreHistory()}
              disabled={isLoadingMoreHistory}
            >
              {isLoadingMoreHistory ? 'Đang tải...' : 'Xem thêm lịch sử'}
            </Button>
          )}
        </section>
      </FadeIn>

      {existing && isEditModalOpen && (
        <Dialog
          title={`Thay đổi đánh giá · ${review.department_name}`}
          description={`Tuần ${formatDate(review.week_start)} – ${formatDate(review.week_end)}.`}
          className="max-w-5xl"
          onClose={() => !isSaving && setIsEditModalOpen(false)}
        >
          <form onSubmit={handleSubmit}>
            <EvaluationEditor
              scores={scores}
              setScores={updateEvaluationScores}
              assessmentNote={assessmentNote}
              setAssessmentNote={updateAssessmentNote}
              files={files}
              setFiles={updateEvaluationFiles}
              existing={existing}
              overallScore={overallScore}
              canSubmit={canSubmit}
              isSaving={isSaving}
              submitLabel="Lưu thay đổi"
            />
          </form>
        </Dialog>
      )}

      {(isHistoryDetailLoading || historyDetailError || selectedHistoryEvaluation) && (
        <Dialog
          title={
            selectedHistoryEvaluation
              ? `Chi tiết đánh giá · ${selectedHistoryEvaluation.department_name}`
              : 'Chi tiết đánh giá tuần'
          }
          description="Xem chi tiết minh chứng và kết quả đánh giá của tuần."
          className="max-w-3xl"
          onClose={() => {
            if (!isHistoryDetailLoading) {
              setSelectedHistoryEvaluation(null)
              setHistoryDetailError('')
            }
          }}
        >
          {isHistoryDetailLoading && (
            <p className="rounded-xl bg-slate-50 p-6 text-center text-slate-500">
              Đang tải chi tiết đánh giá...
            </p>
          )}
          {historyDetailError && !isHistoryDetailLoading && (
            <p className="rounded-xl bg-red-50 p-4 text-sm text-red-700">{historyDetailError}</p>
          )}
          {selectedHistoryEvaluation && !isHistoryDetailLoading && (
            <HistoryEvaluationDetail evaluation={selectedHistoryEvaluation} />
          )}
        </Dialog>
      )}
    </MainLayout>
  )
}

function EvidenceCard({ title, value, unit, detail, tone }) {
  const tones = {
    blue: 'border-blue-100 bg-blue-50 text-blue-900',
    green: 'border-emerald-100 bg-emerald-50 text-emerald-900',
    red: 'border-red-100 bg-red-50 text-red-900',
    amber: 'border-amber-100 bg-amber-50 text-amber-900',
  }
  return (
    <article className={`rounded-2xl border p-5 ${tones[tone]}`}>
      <p className="text-sm font-semibold opacity-80">{title}</p>
      <p className="mt-2 text-2xl font-black">{value}</p>
      <p className="mt-1 text-xs font-semibold opacity-70">{unit}</p>
      <p className="mt-3 text-sm opacity-80">{detail}</p>
    </article>
  )
}

function MetricTile({ label, value, previous, delta }) {
  return (
    <div className="rounded-xl bg-slate-50 p-4">
      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-2 text-xl font-black text-slate-900">{value}</p>
      <p className="mt-1 text-xs font-medium text-slate-600">Tuần trước: {previous}</p>
      <p className="mt-1 text-xs text-slate-500">{delta}</p>
    </div>
  )
}

function ScoreInput({ label, value, onChange }) {
  return (
    <label className="rounded-xl bg-slate-50 p-4 text-sm font-semibold text-slate-700">
      {label}
      <Input
        className="mt-2 text-lg font-bold"
        type="number"
        min="0"
        max="100"
        step="0.5"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required
      />
    </label>
  )
}

function EvaluationEditor({
  scores,
  setScores,
  assessmentNote,
  setAssessmentNote,
  files,
  setFiles,
  existing = null,
  overallScore,
  canSubmit,
  isSaving,
  submitLabel = 'Lưu đánh giá tuần',
}) {
  return (
    <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="rounded-2xl border border-slate-200 p-5">
        <h2 className="text-lg font-bold text-slate-900">Chấm điểm và định hướng</h2>
        <p className="mt-1 text-sm text-slate-600">
          Điểm tổng được tính theo trọng số 40% · 40% · 20%.
        </p>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          <ScoreInput
            label="Thực hiện chỉ thị"
            value={scores.directive}
            onChange={(value) => setScores((current) => ({ ...current, directive: value }))}
          />
          <ScoreInput
            label="Ổn định phòng ban"
            value={scores.stability}
            onChange={(value) => setScores((current) => ({ ...current, stability: value }))}
          />
          <ScoreInput
            label="Đúng hạn"
            value={scores.timeliness}
            onChange={(value) => setScores((current) => ({ ...current, timeliness: value }))}
          />
        </div>
        <label className="mt-4 block text-sm font-semibold text-slate-700">
          Nhận xét đánh giá (tùy chọn)
          <Textarea
            className="mt-1"
            maxLength={1000}
            value={assessmentNote}
            onChange={(event) => setAssessmentNote(event.target.value)}
            placeholder="Nhận xét ngắn về kết quả tuần..."
          />
        </label>
        <label
          className="mt-4 block rounded-xl border-2 border-dashed border-brand-200 bg-brand-50/50 p-5 text-center text-sm text-slate-700 transition duration-motion-micro ease-motion-standard hover:border-brand-400"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault()
            setFiles(Array.from(event.dataTransfer.files || []).slice(0, 5))
          }}
        >
          <span className="font-bold text-brand-700">
            {existing
              ? 'Chọn tệp mới để thay tài liệu hiện tại'
              : 'Đính kèm định hướng tuần tiếp theo'}
          </span>
          <span className="mt-1 block text-xs text-slate-500">
            Kéo thả hoặc chọn PDF, Word, Excel, PowerPoint, TXT hoặc ảnh · tối đa 5 tệp, 10 MB/tệp
          </span>
          <input
            className="sr-only"
            type="file"
            multiple
            accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.png,.jpg,.jpeg"
            onChange={(event) => setFiles(Array.from(event.target.files || []).slice(0, 5))}
          />
        </label>
        {files.length > 0 && (
          <ul className="mt-3 space-y-1 text-sm text-slate-600">
            {files.map((file) => (
              <li key={`${file.name}-${file.size}`}>• {file.name}</li>
            ))}
          </ul>
        )}
        {existing?.attachments?.length > 0 && files.length === 0 && (
          <AttachmentLinks evaluationId={evaluation.id} attachments={existing.attachments} />
        )}
      </div>
      <aside className="self-start rounded-2xl bg-gradient-to-br from-brand-600 to-blue-700 p-5 text-white shadow-lg">
        <p className="text-xs font-bold uppercase tracking-widest text-blue-100">
          Điểm tổng dự kiến
        </p>
        <p className="mt-3 text-5xl font-black">{overallScore.toFixed(1)}</p>
        <div className="mt-5 space-y-2 text-sm text-blue-50">
          <p>Thực hiện chỉ thị: {Number(scores.directive).toFixed(1)} × 40%</p>
          <p>Ổn định phòng ban: {Number(scores.stability).toFixed(1)} × 40%</p>
          <p>Đúng hạn: {Number(scores.timeliness).toFixed(1)} × 20%</p>
        </div>
        <Button
          type="submit"
          className="mt-6 w-full rounded-xl bg-white px-4 py-3 font-bold text-brand-700 hover:bg-blue-50"
          loading={isSaving}
          disabled={!canSubmit}
        >
          {isSaving ? 'Đang lưu...' : submitLabel}
        </Button>
      </aside>
    </section>
  )
}

function CompletedEvaluationSummary({ evaluation, onEdit }) {
  return (
    <section className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-emerald-700">
            Đã hoàn tất đánh giá tuần
          </p>
          <p className="mt-2 text-3xl font-black text-slate-900">
            {Number(evaluation.overall_score).toFixed(1)} điểm
          </p>
          <p className="mt-2 text-sm text-slate-600">
            Chỉ thị {evaluation.directive_execution_score} · Ổn định {evaluation.stability_score} ·
            Đúng hạn {evaluation.timeliness_score}
          </p>
          {evaluation.assessment_note && (
            <p className="mt-3 text-sm leading-6 text-slate-700">{evaluation.assessment_note}</p>
          )}
          <AttachmentLinks evaluationId={evaluation.id} attachments={evaluation.attachments} />
        </div>
        <Button type="button" variant="secondary" onClick={onEdit}>
          Thay đổi đánh giá
        </Button>
      </div>
    </section>
  )
}

function HistoryEvaluationDetail({ evaluation }) {
  const indicator = evaluation.evidence_snapshot?.stability
  const directives = evaluation.evidence_snapshot?.directives
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-4">
        <DetailMetric label="Điểm tổng" value={`${Number(evaluation.overall_score).toFixed(1)}`} />
        <DetailMetric
          label="Thực hiện chỉ thị"
          value={`${Number(evaluation.directive_execution_score).toFixed(1)}`}
        />
        <DetailMetric
          label="Ổn định phòng ban"
          value={`${Number(evaluation.stability_score).toFixed(1)}`}
        />
        <DetailMetric
          label="Đúng hạn"
          value={`${Number(evaluation.timeliness_score).toFixed(1)}`}
        />
      </div>
      <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-700">
        <p>
          Kỳ đánh giá: {formatDate(evaluation.week_start)} – {formatDate(evaluation.week_end)}
        </p>
        <p className="mt-1">Đánh giá lúc: {formatDateTime(evaluation.evaluated_at)}</p>
        {evaluation.evaluation_delay_days > 0 && (
          <p className="mt-1 text-amber-700">
            Đánh giá trễ {evaluation.evaluation_delay_days} ngày.
          </p>
        )}
      </div>
      {indicator && directives && (
        <div className="rounded-xl border border-slate-200 p-4 text-sm text-slate-700">
          <h3 className="font-bold text-slate-900">Snapshot bằng chứng</h3>
          <p className="mt-2">
            Hiệu suất trung bình:{' '}
            {formatNumber(indicator.current?.average_performance_score, ' điểm')} · Chất lượng:{' '}
            {formatNumber(indicator.current?.average_quality_score, ' điểm')}
          </p>
          <p className="mt-1">
            Chỉ thị liên quan: {directives.total_count} · Đã nghiệm thu: {directives.accepted_count}{' '}
            · Cần xử lý lại: {directives.needs_revision_count}
          </p>
        </div>
      )}
      {evaluation.assessment_note && (
        <p className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm leading-6 text-slate-700">
          {evaluation.assessment_note}
        </p>
      )}
      <AttachmentLinks evaluationId={evaluation.id} attachments={evaluation.attachments || []} />
    </div>
  )
}

function DetailMetric({ label, value }) {
  return (
    <div className="rounded-xl bg-brand-50 p-3">
      <p className="text-xs font-semibold text-brand-700">{label}</p>
      <p className="mt-1 text-xl font-black text-slate-900">{value}</p>
    </div>
  )
}

function AttachmentLinks({ evaluationId, attachments }) {
  return (
    <ul className="mt-3 space-y-1 text-sm text-slate-600">
      {attachments.map((attachment) => (
        <li key={attachment.attachment_id}>
          •{' '}
          <AttachmentLink
            attachment={attachment}
            getDownloadUrl={() =>
              getDepartmentEvaluationAttachmentUrl(evaluationId, attachment.attachment_id)
            }
          />
        </li>
      ))}
    </ul>
  )
}

export default DepartmentEvaluationsPage
