import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import Modal from '../../components/Modal.jsx'
import { useActionFeedback } from '../../components/feedback/index.js'
import { REALTIME_COALESCE_DELAY, useRealtimeUpdates } from '../../hooks/useRealtimeUpdates.js'
import { generateIdempotencyKey } from '../../utils/idempotency.js'
import {
  acknowledgeDepartmentDirective,
  fulfillDirective,
  getDirectiveCandidates,
  listDepartmentDirectives,
  listDirectives,
  submitDepartmentDirective,
} from './coordinationApi.js'
import {
  DIRECTIVE_SOURCE_LABELS,
  getDirectiveStatusClass,
  getDirectiveStatusLabel,
} from './directiveLabels.js'

const FILTER_LABELS = {
  all: 'Tất cả',
  early_warning: 'Dấu hiệu sớm',
  overload: 'Quá tải',
  medium: 'Mức trung bình',
  high: 'Mức cao',
}

function ManagerAlertDirectiveAction({ onCompleted, alerts = [] }) {
  const { confirmAction, notifyActionSuccess, notifyActionError } = useActionFeedback()
  const [searchParams, setSearchParams] = useSearchParams()
  const departmentDirectiveId = searchParams.get('alert_directive')
  const coordinationDirectiveId = searchParams.get('coordination_directive')
  const [departmentDirectives, setDepartmentDirectives] = useState([])
  const [directive, setDirective] = useState(null)
  const [candidates, setCandidates] = useState([])
  const [note, setNote] = useState('')
  const [completionNote, setCompletionNote] = useState('')
  const [commitmentDate, setCommitmentDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [candidateId, setCandidateId] = useState('')
  const [tasksToTransfer, setTasksToTransfer] = useState('1')
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [error, setError] = useState('')
  const idempotencyKeyRef = useRef(null)

  const loadDirectives = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const departmentItems = await listDepartmentDirectives()
      const activeDepartmentItems = (departmentItems || []).filter(
        (item) => item.status !== 'accepted',
      )
      setDepartmentDirectives(activeDepartmentItems)
      if (departmentDirectiveId) {
        const selected = activeDepartmentItems.find((item) => item.id === departmentDirectiveId)
        setDirective(selected ? { type: 'department', data: selected } : null)
        setCandidates([])
        setIsModalOpen(Boolean(selected))
        if (selected && !idempotencyKeyRef.current) {
          idempotencyKeyRef.current = generateIdempotencyKey()
        }
      } else if (!coordinationDirectiveId) {
        setDirective(null)
        setIsModalOpen(false)
      }

      if (coordinationDirectiveId) {
        const items = await listDirectives('pending')
        const selected = (items || []).find((item) => item.id === coordinationDirectiveId)
        if (!selected) {
          setDirective(null)
          setCandidates([])
          setIsModalOpen(false)
        } else {
          const candidateData = await getDirectiveCandidates(selected.id)
          setDirective({ type: 'coordination', data: selected })
          setCandidates(candidateData || [])
          setCandidateId(candidateData?.[0]?.employee_id || '')
          setTasksToTransfer(String(selected.tasks_to_transfer || 1))
          setIsModalOpen(true)
          if (!idempotencyKeyRef.current) {
            idempotencyKeyRef.current = generateIdempotencyKey()
          }
        }
      }
    } catch (requestError) {
      setError(requestError.message || 'Không thể tải nội dung yêu cầu hoặc điều phối.')
    } finally {
      setIsLoading(false)
    }
  }, [coordinationDirectiveId, departmentDirectiveId])

  useEffect(() => {
    void loadDirectives()
  }, [loadDirectives])

  useRealtimeUpdates(
    'department_directives',
    () => {
      void loadDirectives()
    },
    { coalesceDelay: REALTIME_COALESCE_DELAY },
  )

  const alertMap = useMemo(
    () => Object.fromEntries(alerts.map((alert) => [alert.id, alert])),
    [alerts],
  )

  function progressFor(item) {
    const ids = item.alert_ids || []
    const relatedAlerts = ids.map((id) => alertMap[id]).filter(Boolean)
    const hasServerProgress = Number(item.total_item_count) > 0
    const total = hasServerProgress
      ? Number(item.total_item_count)
      : ids.length || item.selected_alert_count || 0
    const completed = hasServerProgress
      ? Number(item.completed_item_count || 0)
      : relatedAlerts.length === ids.length
        ? relatedAlerts.filter((alert) => alert.status === 'resolved').length
        : item.completed_item_count || 0
    const percent = hasServerProgress
      ? Number(item.progress_percent || 0)
      : total
        ? Math.round((completed / total) * 100)
        : 0
    return { completed, total, percent }
  }

  function openAcknowledge(item) {
    setDirective({ type: 'department', data: item })
    setNote('')
    setCompletionNote('')
    setCommitmentDate(new Date().toISOString().slice(0, 10))
    setError('')
    idempotencyKeyRef.current = generateIdempotencyKey()
    setIsModalOpen(true)
  }

  function openSubmit(item) {
    setDirective({ type: 'department', data: item })
    setCompletionNote('')
    setError('')
    idempotencyKeyRef.current = generateIdempotencyKey()
    setIsModalOpen(true)
  }

  function closeDirective() {
    setDirective(null)
    setIsModalOpen(false)
    idempotencyKeyRef.current = null
    const nextParams = new URLSearchParams(searchParams)
    nextParams.delete('alert_directive')
    nextParams.delete('coordination_directive')
    setSearchParams(nextParams, { replace: true })
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (!directive || isSaving) return
    const isDepartmentDirective = directive.type === 'department'
    const isSubmission =
      isDepartmentDirective && ['acknowledged', 'needs_revision'].includes(directive.data.status)
    const selectedCandidate = candidates.find((item) => item.employee_id === candidateId)
    const confirmed = await confirmAction({
      title: isSubmission
        ? 'Xác nhận gửi nghiệm thu cảnh báo'
        : isDepartmentDirective
          ? 'Xác nhận tiếp nhận yêu cầu xử lý cảnh báo'
          : 'Xác nhận áp dụng điều phối liên phòng ban',
      description: isSubmission
        ? 'Báo cáo xử lý cảnh báo sẽ được gửi đến Lãnh đạo để nghiệm thu.'
        : isDepartmentDirective
          ? 'Bạn sẽ tiếp nhận yêu cầu và ghi nhận kế hoạch xử lý cho phòng ban.'
          : 'Công việc sẽ được điều phối theo nhân viên và số lượng bạn đã chọn.',
      details: isDepartmentDirective
        ? [
            `Yêu cầu: ${directive.data.title || DIRECTIVE_SOURCE_LABELS.alert}`,
            `Số cảnh báo liên quan: ${directive.data.selected_alert_count || directive.data.alert_ids?.length || 0}`,
            isSubmission
              ? `Nội dung nghiệm thu: ${completionNote.trim() || 'Không thêm ghi chú'}`
              : `Ngày cam kết: ${commitmentDate || 'Chưa xác định'}`,
          ]
        : [
            `Điều phối: ${directive.data.alert_title || DIRECTIVE_SOURCE_LABELS.coordination}`,
            `Nhân viên nhận việc: ${selectedCandidate?.employee_name || 'Chưa xác định'}`,
            `Số công việc chuyển: ${Number(tasksToTransfer) || 1}`,
          ],
      confirmLabel: isSubmission
        ? 'Xác nhận gửi nghiệm thu'
        : isDepartmentDirective
          ? 'Xác nhận tiếp nhận'
          : 'Xác nhận điều phối',
    })
    if (!confirmed) return
    setIsSaving(true)
    setError('')
    try {
      if (directive.type === 'department') {
        if (['acknowledged', 'needs_revision'].includes(directive.data.status)) {
          await submitDepartmentDirective(
            directive.data.id,
            { completion_note: completionNote },
            idempotencyKeyRef.current,
          )
        } else {
          await acknowledgeDepartmentDirective(
            directive.data.id,
            {
              note,
              commitment_date: commitmentDate,
            },
            idempotencyKeyRef.current,
          )
        }
      } else {
        await fulfillDirective(
          directive.data.id,
          {
            target_employee_id: candidateId,
            tasks_to_transfer: Number(tasksToTransfer),
          },
          idempotencyKeyRef.current,
        )
      }
      closeDirective()
      await loadDirectives()
      await onCompleted?.()
      notifyActionSuccess({
        title: isSubmission
          ? 'Đã gửi nghiệm thu cảnh báo'
          : isDepartmentDirective
            ? 'Đã tiếp nhận yêu cầu xử lý cảnh báo'
            : 'Đã áp dụng điều phối liên phòng ban',
        message: isDepartmentDirective
          ? 'Yêu cầu xử lý cảnh báo đã được cập nhật thành công.'
          : `Đã chuyển ${Number(tasksToTransfer) || 1} công việc cho ${selectedCandidate?.employee_name || 'nhân viên đã chọn'}.`,
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể cập nhật yêu cầu hoặc điều phối.'
      setError(message)
      notifyActionError({ title: 'Chưa cập nhật yêu cầu', message })
    } finally {
      setIsSaving(false)
    }
  }

  const showContextBanner = Boolean(departmentDirectiveId || coordinationDirectiveId)

  return (
    <>
      {showContextBanner && (
        <div className="mb-5 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
          <p className="font-bold">Đang mở yêu cầu hoặc điều phối</p>
          <p className="mt-1">
            {isLoading
              ? 'Đang tải nội dung...'
              : directive
                ? `Xem bối cảnh và cập nhật ${directive.type === 'department' ? DIRECTIVE_SOURCE_LABELS.alert.toLowerCase() : DIRECTIVE_SOURCE_LABELS.coordination.toLowerCase()} khi cần.`
                : 'Yêu cầu hoặc điều phối đã được xử lý hoặc không còn thuộc phạm vi của bạn.'}
          </p>
          {error && <p className="mt-2 font-semibold text-red-700">{error}</p>}
        </div>
      )}

      <section className="mt-6 rounded-2xl border border-blue-200 bg-blue-50/60 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-900">
              {DIRECTIVE_SOURCE_LABELS.alert} từ Lãnh đạo
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Theo dõi tiến độ xử lý cảnh báo và gửi nghiệm thu khi đã hoàn tất.
            </p>
          </div>
          <span className="rounded-full bg-white px-3 py-1 text-sm font-bold text-blue-700 shadow-sm">
            {departmentDirectives.length} yêu cầu
          </span>
        </div>

        {error && !showContextBanner && (
          <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>
        )}
        {isLoading ? (
          <p className="mt-4 rounded-xl bg-white/80 p-4 text-sm text-slate-500">
            Đang tải yêu cầu xử lý cảnh báo...
          </p>
        ) : departmentDirectives.length === 0 ? (
          <p className="mt-4 rounded-xl bg-white/80 p-4 text-sm text-slate-500">
            Hiện chưa có yêu cầu xử lý cảnh báo nào từ Lãnh đạo trong phòng ban.
          </p>
        ) : (
          <div className="mt-4 space-y-4">
            {departmentDirectives.map((item) => {
              const progress = progressFor(item)
              const canSubmit = ['acknowledged', 'needs_revision'].includes(item.status)
              return (
                <article
                  key={item.id}
                  className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wide text-brand-700">
                        {DIRECTIVE_SOURCE_LABELS.alert}
                      </p>
                      <p className="font-bold text-slate-900">
                        {FILTER_LABELS[item.selected_alert_type]} ·{' '}
                        {FILTER_LABELS[item.selected_severity]}
                      </p>
                      <p className="mt-1 text-sm text-slate-500">
                        {item.selected_alert_count} cảnh báo được giao xem xét
                      </p>
                    </div>
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-bold ${getDirectiveStatusClass('alert', item.status)}`}
                    >
                      {getDirectiveStatusLabel('alert', item.status)}
                    </span>
                  </div>
                  {item.note && (
                    <p className="mt-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
                      {DIRECTIVE_SOURCE_LABELS.alert}: {item.note}
                    </p>
                  )}
                  {item.commitment_date && (
                    <p className="mt-2 text-sm text-slate-600">
                      Cam kết hoàn thành: {item.commitment_date}
                    </p>
                  )}
                  {item.completion_note && (
                    <p className="mt-3 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-900">
                      Báo cáo nghiệm thu: {item.completion_note}
                    </p>
                  )}
                  {item.revision_note && (
                    <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
                      Yêu cầu xử lý lại: {item.revision_note}
                    </p>
                  )}
                  <div className="mt-4 flex items-center justify-between gap-3 text-sm font-semibold text-slate-700">
                    <span>Tiến độ cảnh báo</span>
                    <span className="text-brand-700">{progress.percent}%</span>
                  </div>
                  <div className="mt-2 h-3 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-brand-600 transition-all duration-motion-standard ease-motion-standard"
                      style={{ width: `${progress.percent}%` }}
                    />
                  </div>
                  <p className="mt-2 text-sm text-slate-600">
                    {progress.completed}/{progress.total} cảnh báo đã xử lý
                  </p>
                  <div className="mt-4 flex justify-end gap-2">
                    {item.status === 'pending' && (
                      <button
                        type="button"
                        className="primary-button"
                        onClick={() => openAcknowledge(item)}
                      >
                        Tiếp nhận yêu cầu xử lý cảnh báo
                      </button>
                    )}
                    {canSubmit && (
                      <button
                        type="button"
                        className="primary-button"
                        disabled={progress.percent < 100}
                        onClick={() => openSubmit(item)}
                        title={
                          progress.percent < 100
                            ? 'Cần xử lý toàn bộ cảnh báo trước khi gửi nghiệm thu'
                            : ''
                        }
                      >
                        {progress.percent < 100 ? 'Chưa đủ điều kiện nghiệm thu' : 'Gửi nghiệm thu'}
                      </button>
                    )}
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </section>

      {directive && isModalOpen && (
        <Modal
          title={
            directive.type === 'department'
              ? ['acknowledged', 'needs_revision'].includes(directive.data.status)
                ? `Gửi nghiệm thu ${DIRECTIVE_SOURCE_LABELS.alert.toLowerCase()}`
                : `Tiếp nhận ${DIRECTIVE_SOURCE_LABELS.alert.toLowerCase()}`
              : `Tiếp nhận ${DIRECTIVE_SOURCE_LABELS.coordination.toLowerCase()}`
          }
          description={
            directive.type === 'department'
              ? `${directive.data.department_name} · ${directive.data.selected_alert_count} cảnh báo`
              : `${directive.data.source_department_name || 'Phòng ban nguồn'} → ${directive.data.target_department_name}`
          }
          onClose={closeDirective}
        >
          <form className="space-y-4" onSubmit={handleSubmit}>
            {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
            {directive.data.note && (
              <p className="rounded-lg bg-slate-50 p-3 text-sm leading-6 text-slate-700">
                {directive.type === 'department'
                  ? DIRECTIVE_SOURCE_LABELS.alert
                  : DIRECTIVE_SOURCE_LABELS.coordination}
                : {directive.data.note}
              </p>
            )}
            {directive.type === 'department' ? (
              ['acknowledged', 'needs_revision'].includes(directive.data.status) ? (
                <label className="block text-sm font-semibold text-slate-700">
                  Ghi chú nghiệm thu (tùy chọn)
                  <textarea
                    className="form-input mt-1 min-h-28"
                    maxLength={1000}
                    value={completionNote}
                    onChange={(event) => setCompletionNote(event.target.value)}
                    placeholder="Ví dụ: Đã xử lý và kiểm tra toàn bộ cảnh báo được giao."
                  />
                </label>
              ) : (
                <>
                  <p className="rounded-lg bg-blue-50 p-3 text-sm text-blue-900">
                    Nhóm {FILTER_LABELS[directive.data.selected_alert_type]} ·{' '}
                    {FILTER_LABELS[directive.data.selected_severity]}.
                  </p>
                  <label className="block text-sm font-semibold text-slate-700">
                    Ghi chú tiếp nhận (tùy chọn)
                    <textarea
                      className="form-input mt-1 min-h-28"
                      maxLength={1000}
                      value={note}
                      onChange={(event) => setNote(event.target.value)}
                      placeholder="Ví dụ: Đã phân công rà soát và sẽ cập nhật kết quả trong ngày."
                    />
                  </label>
                  <label className="block text-sm font-semibold text-slate-700">
                    Ngày cam kết hoàn thành
                    <input
                      className="form-input mt-1"
                      type="date"
                      min={new Date().toISOString().slice(0, 10)}
                      value={commitmentDate}
                      onChange={(event) => setCommitmentDate(event.target.value)}
                      required
                    />
                  </label>
                </>
              )
            ) : (
              <>
                <label className="block text-sm font-semibold text-slate-700">
                  Nhân viên tiếp nhận
                  <select
                    className="form-input mt-1"
                    required
                    value={candidateId}
                    onChange={(event) => setCandidateId(event.target.value)}
                  >
                    <option value="">Chọn nhân viên</option>
                    {candidates.map((candidate) => (
                      <option key={candidate.employee_id} value={candidate.employee_id}>
                        {candidate.employee_name} · {candidate.tasks_completed} công việc · chất
                        lượng {candidate.quality_score}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-sm font-semibold text-slate-700">
                  Số công việc chuyển giao
                  <select
                    className="form-input mt-1"
                    value={tasksToTransfer}
                    onChange={(event) => setTasksToTransfer(event.target.value)}
                  >
                    <option value="1">1 công việc</option>
                    <option value="2">2 công việc</option>
                  </select>
                </label>
                {candidates.length === 0 && (
                  <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
                    Hiện không có nhân viên nào trong phòng còn khả năng nhận việc.
                  </p>
                )}
              </>
            )}
            <div className="flex justify-end gap-3 pt-2">
              <button type="button" className="secondary-button" onClick={closeDirective}>
                Đóng
              </button>
              <button
                type="submit"
                className="primary-button"
                disabled={
                  isSaving ||
                  (directive.type === 'department' &&
                    ['acknowledged', 'needs_revision'].includes(directive.data.status) &&
                    progressFor(directive.data).percent < 100) ||
                  (directive.type === 'coordination' && candidates.length === 0)
                }
              >
                {isSaving
                  ? 'Đang lưu...'
                  : directive.type === 'department' &&
                      ['acknowledged', 'needs_revision'].includes(directive.data.status)
                    ? 'Gửi nghiệm thu'
                    : 'Xác nhận tiếp nhận'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  )
}

export default ManagerAlertDirectiveAction
