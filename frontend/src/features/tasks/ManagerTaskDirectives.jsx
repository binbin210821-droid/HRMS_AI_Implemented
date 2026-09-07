import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import Modal from '../../components/Modal.jsx'
import { useRealtimeUpdates } from '../../hooks/useRealtimeUpdates.js'
import {
  acknowledgeDepartmentTaskDirective,
  listDepartmentTaskDirectives,
  submitDepartmentTaskDirective,
} from './tasksApi.js'
import {
  DIRECTIVE_SOURCE_LABELS,
  getDirectiveStatusLabel,
} from '../coordination/directiveLabels.js'

const FOCUS_LABELS = {
  overdue: 'Công việc quá hạn',
  due_soon: 'Sắp đến hạn trong 7 ngày',
  high_priority_open: 'Công việc ưu tiên cao',
  at_risk: 'Tất cả công việc cần chú ý',
}

function ManagerTaskDirectives({ tasks }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const directiveId = searchParams.get('task_directive')
  const [directives, setDirectives] = useState([])
  const [selected, setSelected] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [form, setForm] = useState({ action_note: '', commitment_date: '', completion_note: '' })
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')

  const loadDirectives = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      setDirectives((await listDepartmentTaskDirectives()) || [])
    } catch (requestError) {
      setError(requestError.message || 'Không thể tải giao việc quá hạn từ Lãnh đạo.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadDirectives()
  }, [loadDirectives])

  useRealtimeUpdates('task_directives', () => {
    void loadDirectives()
  })

  useEffect(() => {
    if (!directiveId || isLoading) return
    const directive = directives.find((item) => item.id === directiveId)
    if (directive?.status !== 'accepted') {
      setSelected(directive)
      if (!isModalOpen) {
        setForm({ action_note: '', commitment_date: '', completion_note: '' })
        setError('')
      }
    } else {
      setSelected(null)
      setIsModalOpen(false)
    }
  }, [directiveId, directives, isLoading, isModalOpen])

  const taskMap = useMemo(() => Object.fromEntries(tasks.map((task) => [task.id, task])), [tasks])
  const displayedDirectives = useMemo(
    () =>
      directives
        .filter((directive) => directive.status !== 'accepted')
        .sort((left, right) => {
          if (left.status !== right.status) return left.status === 'pending' ? -1 : 1
          return new Date(right.issued_at || 0).getTime() - new Date(left.issued_at || 0).getTime()
        }),
    [directives],
  )
  const isSubmission = selected && ['acknowledged', 'needs_revision'].includes(selected.status)

  function openAcknowledge(directive) {
    setSelected(directive)
    setForm({
      action_note: '',
      commitment_date: new Date().toISOString().slice(0, 10),
      completion_note: '',
    })
    setError('')
    setIsModalOpen(true)
  }

  function openSubmit(directive) {
    setSelected(directive)
    setForm({ action_note: '', commitment_date: '', completion_note: '' })
    setError('')
    setIsModalOpen(true)
  }

  async function handleAcknowledge(event) {
    event.preventDefault()
    if (!selected || isSaving) return
    const isSubmission = ['acknowledged', 'needs_revision'].includes(selected.status)
    setIsSaving(true)
    setError('')
    try {
      const updatedDirective = isSubmission
        ? await submitDepartmentTaskDirective(selected.id, {
            completion_note: form.completion_note,
          })
        : await acknowledgeDepartmentTaskDirective(selected.id, {
            action_note: form.action_note,
            commitment_date: form.commitment_date,
          })
      setSelected(
        updatedDirective || {
          ...selected,
          status: isSubmission ? 'submitted' : 'acknowledged',
          ...form,
        },
      )
      setDirectives((current) =>
        current.map((directive) =>
          directive.id === selected.id
            ? updatedDirective || {
                ...directive,
                status: isSubmission ? 'submitted' : 'acknowledged',
                ...form,
              }
            : directive,
        ),
      )
      setIsModalOpen(false)
      await loadDirectives()
    } catch (requestError) {
      setError(
        requestError.message ||
          (['acknowledged', 'needs_revision'].includes(selected.status)
            ? 'Không thể gửi nghiệm thu giao việc quá hạn.'
            : 'Không thể xác nhận giao việc quá hạn.'),
      )
    } finally {
      setIsSaving(false)
    }
  }

  function closeDirective() {
    setSelected(null)
    setIsModalOpen(false)
    const nextParams = new URLSearchParams(searchParams)
    nextParams.delete('task_directive')
    setSearchParams(nextParams, { replace: true })
  }

  if (isLoading) {
    return (
      <div className="mt-6 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">
        Đang kiểm tra giao việc quá hạn từ Lãnh đạo...
      </div>
    )
  }

  return (
    <>
      <section className="mt-6 rounded-2xl border border-blue-200 bg-blue-50/60 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-900">
              {DIRECTIVE_SOURCE_LABELS.task} từ Lãnh đạo
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Theo dõi yêu cầu, kế hoạch đã cam kết và tiến độ các công việc liên quan.
            </p>
          </div>
          <span className="rounded-full bg-white px-3 py-1 text-sm font-bold text-blue-700 shadow-sm">
            {displayedDirectives.length} mục
          </span>
        </div>

        {error && <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        {displayedDirectives.length === 0 ? (
          <p className="mt-4 rounded-xl bg-white/80 p-4 text-sm text-slate-500">
            Hiện chưa có giao việc quá hạn nào từ Lãnh đạo trong phòng ban.
          </p>
        ) : (
          <div className="mt-4 space-y-4">
            {displayedDirectives.map((directive) => (
              <DirectiveProgressCard
                key={directive.id}
                directive={directive}
                tasks={directive.task_ids.map((id) => taskMap[id]).filter(Boolean)}
                isHighlighted={directive.id === directiveId}
                onAcknowledge={openAcknowledge}
                onSubmit={openSubmit}
              />
            ))}
          </div>
        )}
      </section>

      {selected && isModalOpen && (
        <Modal
          title={isSubmission ? 'Gửi nghiệm thu giao việc quá hạn' : 'Tiếp nhận giao việc quá hạn'}
          description={`${FOCUS_LABELS[selected.focus]} · ${selected.selected_task_count} công việc`}
          onClose={() => setIsModalOpen(false)}
        >
          <form className="space-y-4" onSubmit={handleAcknowledge}>
            {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
            {isSubmission ? (
              <label className="block text-sm font-semibold text-slate-700">
                Ghi chú nghiệm thu (tùy chọn)
                <textarea
                  className="form-input mt-1 min-h-28"
                  maxLength={1000}
                  placeholder="Ví dụ: Đã hoàn thành và kiểm tra toàn bộ công việc được giao."
                  value={form.completion_note}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, completion_note: event.target.value }))
                  }
                />
              </label>
            ) : (
              <>
                <label className="block text-sm font-semibold text-slate-700">
                  Hành động dự kiến
                  <textarea
                    className="form-input mt-1 min-h-28"
                    required
                    maxLength={1000}
                    placeholder="Ví dụ: Rà soát tiến độ, ưu tiên việc quá hạn và phân bổ lại nguồn lực."
                    value={form.action_note}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, action_note: event.target.value }))
                    }
                  />
                </label>
                <label className="block text-sm font-semibold text-slate-700">
                  Ngày cam kết xử lý
                  <input
                    className="form-input mt-1"
                    type="date"
                    required
                    min={new Date().toISOString().slice(0, 10)}
                    value={form.commitment_date}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, commitment_date: event.target.value }))
                    }
                  />
                </label>
              </>
            )}
            <div className="flex justify-end gap-3 pt-2">
              <button type="button" className="secondary-button" onClick={closeDirective}>
                Hủy
              </button>
              <button type="submit" className="primary-button" disabled={isSaving}>
                {isSaving ? 'Đang lưu...' : isSubmission ? 'Gửi nghiệm thu' : 'Xác nhận tiếp nhận'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  )
}

function DirectiveProgressCard({ directive, tasks, isHighlighted, onAcknowledge, onSubmit }) {
  const navigate = useNavigate()
  const [isTaskListOpen, setIsTaskListOpen] = useState(false)
  const completedTasks = tasks.filter((task) => task.status === 'done').length
  const totalTasks = directive.task_ids?.length || 0
  const progressPercent = totalTasks ? Math.round((completedTasks / totalTasks) * 100) : 0
  const previewTasks = tasks.slice(0, 5)
  const pendingTasks = tasks.filter((task) => task.status !== 'done')
  const orderedTasks = [...pendingTasks, ...tasks.filter((task) => task.status === 'done')]

  function openTask(task) {
    setIsTaskListOpen(false)
    navigate(`/manager/tasks?task=${encodeURIComponent(task.id)}`)
  }

  function handleTaskListKeyDown(event) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      setIsTaskListOpen((current) => !current)
    }
    if (event.key === 'Escape') setIsTaskListOpen(false)
  }

  function handleTaskListBlur(event) {
    if (!event.currentTarget.contains(event.relatedTarget)) setIsTaskListOpen(false)
  }

  return (
    <article
      id={`task-directive-${directive.id}`}
      className={`rounded-xl bg-white p-4 shadow-sm ring-1 transition ${isHighlighted ? 'ring-brand-400 ring-2' : 'ring-slate-200'}`}
    >
      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-brand-700">
                {DIRECTIVE_SOURCE_LABELS.task}
              </p>
              <p className="font-bold text-slate-900">{FOCUS_LABELS[directive.focus]}</p>
              <p className="mt-1 text-sm text-slate-500">
                {directive.selected_task_count} công việc cần xem xét
              </p>
            </div>
            <span
              className={`rounded-full px-3 py-1 text-xs font-bold ${directive.status === 'pending' ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'}`}
            >
              {getDirectiveStatusLabel('task', directive.status)}
            </span>
          </div>
          {directive.note && (
            <p className="mt-3 rounded-lg bg-slate-50 p-3 text-sm leading-6 text-slate-600">
              {DIRECTIVE_SOURCE_LABELS.task}: {directive.note}
            </p>
          )}
          {directive.action_note && (
            <p className="mt-3 rounded-lg bg-blue-50 p-3 text-sm leading-6 text-blue-900">
              Kế hoạch của Quản lý: {directive.action_note}
            </p>
          )}
          {directive.commitment_date && (
            <p className="mt-3 text-sm font-semibold text-brand-700">
              Cam kết xử lý trước {formatDate(directive.commitment_date)}
            </p>
          )}
          {directive.completion_note && (
            <p className="mt-3 rounded-lg bg-emerald-50 p-3 text-sm leading-6 text-emerald-900">
              Báo cáo nghiệm thu: {directive.completion_note}
            </p>
          )}
          {directive.revision_note && (
            <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm leading-6 text-amber-900">
              Yêu cầu xử lý lại: {directive.revision_note}
            </p>
          )}
          {directive.issued_at && (
            <p className="mt-2 text-xs text-slate-500">
              Phát hành: {formatDateTime(directive.issued_at)}
            </p>
          )}
          {directive.status === 'pending' && (
            <div className="mt-4 flex justify-end">
              <button
                type="button"
                className="primary-button"
                onClick={() => onAcknowledge(directive)}
              >
                Tiếp nhận và lập kế hoạch
              </button>
            </div>
          )}
          {['acknowledged', 'needs_revision'].includes(directive.status) && (
            <div className="mt-4 flex justify-end">
              <button
                type="button"
                className="primary-button"
                disabled={progressPercent < 100}
                title={
                  progressPercent < 100 ? 'Cần hoàn thành toàn bộ công việc trước khi gửi' : ''
                }
                onClick={() => onSubmit(directive)}
              >
                {progressPercent < 100 ? 'Chưa đủ điều kiện nghiệm thu' : 'Gửi nghiệm thu'}
              </button>
            </div>
          )}
        </div>

        <div
          className="group relative"
          onMouseEnter={() => setIsTaskListOpen(true)}
          onMouseLeave={() => setIsTaskListOpen(false)}
          onBlur={handleTaskListBlur}
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-bold text-slate-800">Tiến độ công việc liên quan</p>
              <p className="mt-1 text-xs text-slate-500">
                Di chuột hoặc chọn để xem đầy đủ và mở công việc cần xử lý.
              </p>
            </div>
            <span className="text-sm font-bold text-brand-700">{progressPercent}%</span>
          </div>
          <div className="mt-3 h-3 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-brand-600 transition-all"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <p className="mt-2 text-sm text-slate-600">
            {completedTasks}/{totalTasks} công việc đã hoàn thành
          </p>
          {tasks.length ? (
            <ul className="mt-3 space-y-2 border-t border-slate-100 pt-3 text-sm text-slate-700">
              {previewTasks.map((task) => (
                <li key={task.id} className="flex items-start justify-between gap-3">
                  <span className="min-w-0 truncate font-semibold">{task.title}</span>
                  <span
                    className={
                      task.status === 'done'
                        ? 'shrink-0 text-emerald-700'
                        : task.is_overdue
                          ? 'shrink-0 text-red-700'
                          : 'shrink-0 text-amber-700'
                    }
                  >
                    {task.status === 'done'
                      ? 'Đã xong'
                      : task.is_overdue
                        ? 'Quá hạn'
                        : 'Đang xử lý'}
                  </span>
                </li>
              ))}
              {totalTasks > 5 && (
                <li className="text-slate-500">
                  Và {totalTasks - 5} công việc khác · di chuột để xem đầy đủ
                </li>
              )}
            </ul>
          ) : (
            <p className="mt-3 border-t border-slate-100 pt-3 text-sm text-slate-500">
              Dữ liệu công việc đang được đồng bộ.
            </p>
          )}

          <div
            role="button"
            tabIndex={0}
            aria-expanded={isTaskListOpen}
            aria-label="Xem đầy đủ công việc trong giao việc quá hạn"
            onClick={() => setIsTaskListOpen((current) => !current)}
            onKeyDown={handleTaskListKeyDown}
            className="absolute inset-0 rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
          />

          {isTaskListOpen && (
            <div
              className="absolute inset-x-0 top-full z-30 mt-2 rounded-xl border border-slate-200 bg-white p-3 shadow-xl ring-1 ring-slate-900/5"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-center justify-between gap-3 border-b border-slate-100 pb-2">
                <p className="text-sm font-bold text-slate-900">Danh sách đầy đủ công việc</p>
                <span className="text-xs font-semibold text-slate-500">
                  {pendingTasks.length} việc chưa hoàn tất
                </span>
              </div>
              <div className="mt-2 max-h-72 space-y-1 overflow-y-auto pr-1">
                {orderedTasks.map((task) => {
                  const isDone = task.status === 'done'
                  return (
                    <button
                      key={task.id}
                      type="button"
                      className="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left transition hover:bg-blue-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
                      onClick={() => openTask(task)}
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-semibold text-slate-800">
                          {task.title}
                        </span>
                        <span className="mt-1 block truncate text-xs text-slate-500">
                          Nhân viên: {task.employee_name || 'Chưa xác định'}
                        </span>
                      </span>
                      <span className="shrink-0 text-right text-xs font-bold">
                        <span
                          className={
                            isDone
                              ? 'block text-emerald-700'
                              : task.is_overdue
                                ? 'block text-red-700'
                                : 'block text-amber-700'
                          }
                        >
                          {isDone ? 'Đã xong' : task.is_overdue ? 'Quá hạn' : 'Cần xử lý'}
                        </span>
                        {task.is_overdue && !isDone && (
                          <span className="mt-1 block font-medium text-red-600">
                            Đã trễ hạn {getOverdueDays(task.due_date)} ngày
                          </span>
                        )}
                      </span>
                    </button>
                  )
                })}
              </div>
              <p className="mt-2 border-t border-slate-100 pt-2 text-xs text-slate-500">
                Chọn một công việc để mở trang Công việc và Deadline.
              </p>
            </div>
          )}
        </div>
      </div>
    </article>
  )
}

function formatDate(value) {
  if (!value) return '—'
  const [year, month, day] = String(value).slice(0, 10).split('-').map(Number)
  return new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium' }).format(
    new Date(year, month - 1, day),
  )
}

function getOverdueDays(value, today = new Date()) {
  if (!value) return 0
  const [year, month, day] = String(value).slice(0, 10).split('-').map(Number)
  const dueDate = new Date(year, month - 1, day)
  const currentDate = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  return Math.max(0, Math.floor((currentDate - dueDate) / 86400000))
}

function formatDateTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Không xác định'
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

export default ManagerTaskDirectives
