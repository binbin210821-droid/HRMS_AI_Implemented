import { useState } from 'react'
import { AnimatePresence } from 'framer-motion'

import { AiLoadingIndicator, FadeIn, StaggerList } from '../../components/animations/index.js'
import { useActionFeedback } from '../../components/feedback/index.js'
import AiSuggestionToggle from '../ai/AiSuggestionToggle.jsx'
import { getOverdueTaskActionProposal } from '../ai/aiApi.js'
import {
  makeAiSuggestionKey,
  readAiSuggestion,
  removeAiSuggestion,
  writeAiSuggestion,
} from '../ai/aiSuggestionStorage.js'
import { updateTask } from './tasksApi.js'

const OPTION_LABELS = {
  keep_and_extend: 'Giữ người phụ trách và gia hạn',
  reassign_and_reset_deadline: 'Đổi người phụ trách và đặt lại hạn',
  reassign_task: 'Đổi người phụ trách và đặt lại hạn',
  reassign_and_extend: 'Đổi người phụ trách và gia hạn',
  manual_review: 'Cần xử lý thủ công',
}

const STATUS_LABELS = {
  todo: 'Chưa bắt đầu',
  in_progress: 'Đang thực hiện',
  done: 'Đã hoàn thành',
}

function getOptions(proposal, task) {
  return (proposal?.options || []).map((option) => ({
    ...option,
    status: task.status,
    due_date: option.due_date || task.due_date,
  }))
}

function AiOverdueTaskProposalCard({ task, role, employees = [], onApplied }) {
  const storageKey = makeAiSuggestionKey('overdue-task-proposal', `${role || 'unknown'}:${task.id}`)
  const cachedSuggestion = readAiSuggestion(storageKey)
  const [proposal, setProposal] = useState(() => cachedSuggestion?.proposal || null)
  const [options, setOptions] = useState(
    () => cachedSuggestion?.options || getOptions(cachedSuggestion?.proposal, task),
  )
  const [isLoading, setIsLoading] = useState(false)
  const [applyingId, setApplyingId] = useState(null)
  const [error, setError] = useState('')
  const [isVisible, setIsVisible] = useState(cachedSuggestion?.isVisible ?? true)
  const { confirmAction, notifyActionSuccess, notifyActionError } = useActionFeedback()

  if (role !== 'manager' || !task.is_overdue || task.status === 'done') return null

  async function handleLoadProposal() {
    setIsLoading(true)
    setError('')
    try {
      const result = await getOverdueTaskActionProposal(task.id)
      const nextOptions = getOptions(result, task)
      setProposal(result)
      setOptions(nextOptions)
      setIsVisible(true)
      writeAiSuggestion(storageKey, {
        proposal: result,
        options: nextOptions,
        updatedAt: new Date().toISOString(),
        isVisible: true,
      })
    } catch (requestError) {
      setError(requestError.message || 'Không thể lấy đề xuất từ AI.')
    } finally {
      setIsLoading(false)
    }
  }

  function updateOption(optionId, values) {
    setOptions((current) => {
      const nextOptions = current.map((option) =>
        option.option_id === optionId ? { ...option, ...values } : option,
      )
      writeAiSuggestion(storageKey, {
        ...readAiSuggestion(storageKey),
        proposal,
        options: nextOptions,
        isVisible,
      })
      return nextOptions
    })
  }

  function toggleVisibility() {
    setIsVisible((current) => {
      const next = !current
      writeAiSuggestion(storageKey, {
        ...readAiSuggestion(storageKey),
        proposal,
        options,
        isVisible: next,
      })
      return next
    })
  }

  async function handleApply(option) {
    if (option.type === 'manual_review') return
    const selectedEmployee = employees.find((employee) => employee.id === option.target_employee_id)
    const confirmed = await confirmAction({
      title: 'Xác nhận áp dụng phương án xử lý quá hạn',
      description: 'Công việc sẽ được cập nhật theo đúng các thông tin bạn đã xem và chỉnh sửa.',
      details: [
        `Công việc: ${task.title}`,
        `Người phụ trách: ${selectedEmployee?.full_name || option.target_employee_name || task.employee_name}`,
        `Hạn hoàn thành mới: ${option.due_date || task.due_date || 'Chưa xác định'}`,
        `Trạng thái sau xử lý: ${STATUS_LABELS[option.status || task.status] || option.status || task.status}`,
      ],
      confirmLabel: 'Xác nhận áp dụng',
    })
    if (!confirmed) return
    const payload = {
      status: option.status || task.status,
      expected_updated_at: task.updated_at,
      planning_version: proposal.plan_version,
    }
    if (option.due_date) payload.due_date = option.due_date
    if (option.type === 'reassign_task' || option.type === 'reassign_and_extend') {
      if (!option.target_employee_id) return
      payload.employee_id = option.target_employee_id
    }

    setApplyingId(option.option_id)
    setError('')
    try {
      await updateTask(task.id, payload)
      removeAiSuggestion(storageKey)
      await onApplied?.()
      notifyActionSuccess({
        title: 'Đã áp dụng phương án xử lý quá hạn',
        message: `Công việc “${task.title}” đã được cập nhật thành công.`,
        details: [
          `Người phụ trách: ${selectedEmployee?.full_name || option.target_employee_name || task.employee_name}`,
          `Hạn mới: ${option.due_date || task.due_date || 'Chưa xác định'}`,
        ],
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể áp dụng thay đổi cho công việc.'
      setError(message)
      notifyActionError({ title: 'Chưa áp dụng thay đổi', message })
    } finally {
      setApplyingId(null)
    }
  }

  return (
    <div className="mt-2 rounded-lg border border-violet-200 bg-violet-50 p-3 text-left">
      <AnimatePresence initial={false} mode="wait">
        {!proposal ? (
          <FadeIn key={isLoading ? 'loading' : 'trigger'}>
            {isLoading ? (
              <AiLoadingIndicator label="AI đang tính phương án…" />
            ) : (
              <button
                type="button"
                className="secondary-button border-violet-300 text-violet-800 hover:border-violet-500"
                onClick={handleLoadProposal}
              >
                Hỏi AI cách xử lý
              </button>
            )}
          </FadeIn>
        ) : (
          <FadeIn key="proposal">
            {isVisible ? (
              <>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-violet-900">
                    Các phương án để bạn xem lại
                  </p>
                  <AiSuggestionToggle isVisible={isVisible} onToggle={toggleVisibility} />
                </div>
                <p className="mt-1 text-lg leading-8 text-violet-900">
                  {proposal.summary || 'Chưa đủ dữ liệu để đề xuất phương án lúc này.'}
                </p>
                {options.length ? (
                  <StaggerList className="mt-3 space-y-3">
                    {options.map((option) => {
                      const isManual = option.type === 'manual_review'
                      const isReassignment =
                        option.type === 'reassign_task' ||
                        option.type === 'reassign_and_reset_deadline' ||
                        option.type === 'reassign_and_extend'
                      return (
                        <div
                          key={option.option_id}
                          className="rounded-lg bg-white p-3 ring-1 ring-violet-100"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="text-sm font-semibold text-slate-900">
                              {OPTION_LABELS[option.type] || 'Phương án xử lý'}
                            </p>
                            <div className="flex gap-2 text-xs">
                              <span className="rounded-full bg-emerald-100 px-2 py-1 text-emerald-800">
                                Mức độ phù hợp: {option.fit_score}/100
                              </span>
                              <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-700">
                                Độ tin cậy: {Math.round(option.confidence * 100)}%
                              </span>
                            </div>
                          </div>
                          <p className="mt-2 text-lg leading-8 text-slate-700">
                            <span className="font-semibold">Lý do:</span> {option.rationale}
                          </p>
                          {option.evidence?.length > 0 && (
                            <ul className="mt-2 list-disc space-y-1 pl-5 text-base leading-7 text-slate-600">
                              {option.evidence.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          )}
                          {!isManual && (
                            <div className="mt-3 grid gap-3 sm:grid-cols-3">
                              <label className="text-sm font-medium text-slate-700">
                                Trạng thái sau xử lý
                                <select
                                  className="form-input mt-1"
                                  value={option.status || task.status}
                                  onChange={(event) =>
                                    updateOption(option.option_id, { status: event.target.value })
                                  }
                                >
                                  <option value="todo">Chưa bắt đầu</option>
                                  <option value="in_progress">Đang thực hiện</option>
                                  <option value="done">Đã hoàn thành</option>
                                </select>
                              </label>
                              <label className="text-sm font-medium text-slate-700">
                                Hạn hoàn thành mới
                                <input
                                  type="date"
                                  className="form-input mt-1"
                                  value={option.due_date || task.due_date}
                                  onChange={(event) =>
                                    updateOption(option.option_id, { due_date: event.target.value })
                                  }
                                />
                              </label>
                              {isReassignment && (
                                <label className="text-sm font-medium text-slate-700">
                                  Người phụ trách
                                  <select
                                    className="form-input mt-1"
                                    value={option.target_employee_id || ''}
                                    onChange={(event) =>
                                      updateOption(option.option_id, {
                                        target_employee_id: event.target.value,
                                        target_employee_name:
                                          employees.find((item) => item.id === event.target.value)
                                            ?.full_name || option.target_employee_name,
                                      })
                                    }
                                  >
                                    {employees.map((employee) => (
                                      <option key={employee.id} value={employee.id}>
                                        {employee.full_name} ({employee.employee_code})
                                      </option>
                                    ))}
                                  </select>
                                </label>
                              )}
                            </div>
                          )}
                          <button
                            type="button"
                            className={isManual ? 'secondary-button mt-3' : 'primary-button mt-3'}
                            onClick={() => handleApply(option)}
                            disabled={isManual || applyingId !== null}
                          >
                            {applyingId === option.option_id
                              ? 'Đang áp dụng...'
                              : isManual
                                ? 'Xử lý thủ công'
                                : 'Áp dụng phương án'}
                          </button>
                        </div>
                      )
                    })}
                  </StaggerList>
                ) : (
                  <p className="mt-3 text-sm text-violet-900">
                    Bạn có thể xử lý thủ công như bình thường.
                  </p>
                )}
              </>
            ) : (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-violet-900">Gợi ý AI đang tạm ẩn.</p>
                <AiSuggestionToggle isVisible={isVisible} onToggle={toggleVisibility} />
              </div>
            )}
          </FadeIn>
        )}
      </AnimatePresence>
      <AnimatePresence initial={false}>
        {error && (
          <FadeIn key="error" className="mt-2 text-sm text-red-700">
            {error}
          </FadeIn>
        )}
      </AnimatePresence>
    </div>
  )
}

export default AiOverdueTaskProposalCard
