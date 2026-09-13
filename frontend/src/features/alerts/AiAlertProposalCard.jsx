import { useState } from 'react'
import { AnimatePresence } from 'framer-motion'

import { AiLoadingIndicator, FadeIn, StaggerList } from '../../components/animations/index.js'
import { useActionFeedback } from '../../components/feedback/index.js'
import AiSuggestionToggle from '../ai/AiSuggestionToggle.jsx'
import { getAlertActionProposal } from '../ai/aiApi.js'
import {
  makeAiSuggestionKey,
  readAiSuggestion,
  removeAiSuggestion,
  writeAiSuggestion,
} from '../ai/aiSuggestionStorage.js'
import { applyCoordination } from '../coordination/coordinationApi.js'
import { resolveAlert } from './alertsApi.js'
import { generateIdempotencyKey } from '../../utils/idempotency.js'

function AiAlertProposalCard({ alert, coordination, role, onResolved, onCoordinationApplied }) {
  const storageKey = makeAiSuggestionKey('alert-proposal', `${role || 'unknown'}:${alert.id}`)
  const cachedSuggestion = readAiSuggestion(storageKey)
  const [proposal, setProposal] = useState(() => cachedSuggestion?.proposal || null)
  const [isLoading, setIsLoading] = useState(false)
  const [applyingIndex, setApplyingIndex] = useState(null)
  const [error, setError] = useState('')
  const [isVisible, setIsVisible] = useState(cachedSuggestion?.isVisible ?? true)
  const { confirmAction, notifyActionSuccess, notifyActionError } = useActionFeedback()

  if (role !== 'manager' || alert.status !== 'open' || coordination?.applied_plan) return null

  async function handleLoadProposal() {
    if (isLoading) return
    setIsLoading(true)
    setError('')
    try {
      const result = await getAlertActionProposal(alert.id)
      const nextProposal = {
        ...result,
        actions: (result.actions || []).map((action) => ({ ...action })),
      }
      setProposal(nextProposal)
      setIsVisible(true)
      writeAiSuggestion(storageKey, {
        proposal: nextProposal,
        updatedAt: new Date().toISOString(),
        isVisible: true,
      })
    } catch {
      setError('Không thể lấy đề xuất AI lúc này. Bạn có thể xử lý thủ công như bình thường.')
    } finally {
      setIsLoading(false)
    }
  }

  function updateAction(index, changes) {
    setProposal((current) => {
      if (!current) return current
      const nextProposal = {
        ...current,
        actions: current.actions.map((action, actionIndex) =>
          actionIndex === index ? { ...action, ...changes } : action,
        ),
      }
      writeAiSuggestion(storageKey, {
        ...readAiSuggestion(storageKey),
        proposal: nextProposal,
        isVisible,
      })
      return nextProposal
    })
  }

  function toggleVisibility() {
    setIsVisible((current) => {
      const next = !current
      writeAiSuggestion(storageKey, {
        ...readAiSuggestion(storageKey),
        proposal,
        isVisible: next,
      })
      return next
    })
  }

  async function handleApply(index, action) {
    if (applyingIndex !== null) return
    const targetCandidate = coordination?.candidates?.find(
      (candidate) => candidate.employee_id === action.target_employee_id,
    )
    const confirmed = await confirmAction({
      title:
        action.type === 'resolve_alert'
          ? 'Xác nhận xử lý cảnh báo theo đề xuất AI'
          : 'Xác nhận điều phối theo đề xuất AI',
      description: 'Đề xuất chỉ được áp dụng sau khi bạn xác nhận thông tin bên dưới.',
      details:
        action.type === 'resolve_alert'
          ? [
              `Cảnh báo: ${alert.title}`,
              `Nhân viên: ${alert.employee_name}`,
              `Ghi chú xử lý: ${action.resolution_note?.trim() || 'Chưa có ghi chú'}`,
            ]
          : [
              `Cảnh báo: ${alert.title}`,
              `Nhân viên nhận việc: ${targetCandidate?.employee_name || 'Nhân viên đã chọn'}`,
              `Số công việc chuyển: ${Number(action.tasks_to_transfer) || 1}`,
              `Ghi chú: ${action.note?.trim() || 'Không thêm ghi chú'}`,
            ],
      confirmLabel: 'Xác nhận áp dụng',
    })
    if (!confirmed) return
    setApplyingIndex(index)
    setError('')
    try {
      if (action.type === 'resolve_alert') {
        const updated = await resolveAlert(alert.id, action.resolution_note)
        removeAiSuggestion(storageKey)
        onResolved?.(updated)
        notifyActionSuccess({
          title: 'Đã áp dụng đề xuất xử lý cảnh báo',
          message: `Cảnh báo của ${updated.employee_name || alert.employee_name} đã được cập nhật.`,
          details: [updated.title || alert.title],
        })
      } else {
        const plan = await applyCoordination(
          alert.id,
          {
            target_employee_id: action.target_employee_id,
            tasks_to_transfer: Number(action.tasks_to_transfer),
            note: action.note || '',
          },
          generateIdempotencyKey(),
        )
        removeAiSuggestion(storageKey)
        onCoordinationApplied?.(plan)
        notifyActionSuccess({
          title: 'Đã áp dụng đề xuất điều phối',
          message: `Đã chuyển ${plan.tasks_to_transfer} công việc cho ${plan.target_employee_name}.`,
          details: [plan.note ? `Ghi chú: ${plan.note}` : 'Không thêm ghi chú'],
        })
      }
    } catch (requestError) {
      const message =
        requestError.message ||
        'Không thể áp dụng đề xuất. Bạn có thể chỉnh sửa hoặc xử lý thủ công.'
      setError(message)
      notifyActionError({ title: 'Chưa áp dụng đề xuất', message })
    } finally {
      setApplyingIndex(null)
    }
  }

  const candidates = coordination?.candidates || []
  const visibleActions = (proposal?.actions || []).filter(
    (action) =>
      action.type !== 'apply_coordination' ||
      candidates.some((candidate) => candidate.employee_id === action.target_employee_id),
  )

  return (
    <div className="mt-4 rounded-lg border border-violet-200 bg-violet-50 p-3">
      <AnimatePresence initial={false} mode="wait">
        {!proposal ? (
          <FadeIn key={isLoading ? 'loading' : 'trigger'}>
            {isLoading ? (
              <AiLoadingIndicator label="AI đang phân tích phương án…" />
            ) : (
              <button
                type="button"
                className="secondary-button border-violet-300 text-violet-800 hover:border-violet-500"
                onClick={handleLoadProposal}
              >
                Hỏi AI đề xuất phương án
              </button>
            )}
          </FadeIn>
        ) : (
          <FadeIn key="proposal">
            {isVisible ? (
              <>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-violet-900">Đề xuất để bạn xem lại</p>
                  <AiSuggestionToggle isVisible={isVisible} onToggle={toggleVisibility} />
                </div>
                <p className="mt-1 text-lg leading-8 text-violet-900">
                  {proposal.summary || 'Chưa đủ dữ liệu để đề xuất phương án lúc này.'}
                </p>
                {visibleActions.length ? (
                  <StaggerList className="mt-3 space-y-3">
                    {visibleActions.map((action) => {
                      const index = proposal.actions.indexOf(action)
                      return (
                        <div
                          key={`${action.type}-${index}`}
                          className="rounded-lg bg-white p-3 ring-1 ring-violet-100"
                        >
                          <p className="text-lg leading-8 text-slate-700">
                            <span className="font-semibold">Lý do:</span> {action.rationale}
                          </p>
                          <div className="mt-2 flex flex-wrap gap-2 text-xs text-violet-800">
                            <span className="rounded-full bg-violet-100 px-2 py-1">
                              Ưu tiên:{' '}
                              {action.priority === 'high'
                                ? 'Cao'
                                : action.priority === 'low'
                                  ? 'Thấp'
                                  : 'Vừa'}
                            </span>
                            {action.data_as_of && (
                              <span className="rounded-full bg-slate-100 px-2 py-1">
                                Dữ liệu đến: {action.data_as_of}
                              </span>
                            )}
                          </div>
                          {action.evidence?.length > 0 && (
                            <div className="mt-2 rounded-md bg-violet-50 text-base leading-7 text-slate-700">
                              <p className="font-semibold">Bằng chứng</p>
                              <ul className="mt-1 list-disc space-y-1 pl-5">
                                {action.evidence.map((item) => (
                                  <li key={item}>{item}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {action.conditions && (
                            <p className="mt-2 text-xs text-slate-600">
                              <span className="font-semibold">Điều kiện áp dụng:</span>{' '}
                              {action.conditions}
                            </p>
                          )}
                          {action.type === 'resolve_alert' ? (
                            <label className="mt-3 block text-sm font-medium text-slate-700">
                              Ghi chú xử lý
                              <textarea
                                className="form-input mt-1 min-h-24"
                                value={action.resolution_note}
                                onChange={(event) =>
                                  updateAction(index, { resolution_note: event.target.value })
                                }
                              />
                            </label>
                          ) : (
                            <>
                              <label className="mt-3 block text-sm font-medium text-slate-700">
                                Nhân viên nhận việc
                                <select
                                  className="form-input mt-1"
                                  value={action.target_employee_id}
                                  onChange={(event) =>
                                    updateAction(index, { target_employee_id: event.target.value })
                                  }
                                >
                                  {candidates.map((candidate) => (
                                    <option
                                      key={candidate.employee_id}
                                      value={candidate.employee_id}
                                    >
                                      {candidate.employee_name} ({candidate.employee_code}) — đang
                                      có {candidate.tasks_completed} công việc
                                    </option>
                                  ))}
                                </select>
                              </label>
                              <label className="mt-3 block text-sm font-medium text-slate-700">
                                Số công việc điều phối
                                <select
                                  className="form-input mt-1"
                                  value={String(action.tasks_to_transfer)}
                                  onChange={(event) =>
                                    updateAction(index, {
                                      tasks_to_transfer: Number(event.target.value),
                                    })
                                  }
                                >
                                  <option value="1">1 công việc</option>
                                  <option value="2">2 công việc</option>
                                </select>
                              </label>
                              <label className="mt-3 block text-sm font-medium text-slate-700">
                                Ghi chú điều phối
                                <textarea
                                  className="form-input mt-1 min-h-20"
                                  value={action.note || ''}
                                  onChange={(event) =>
                                    updateAction(index, { note: event.target.value })
                                  }
                                  placeholder="Ví dụ: Chuyển các việc ưu tiên thấp trong ngày hôm nay."
                                />
                              </label>
                            </>
                          )}
                          <button
                            type="button"
                            className="primary-button mt-3"
                            onClick={() => handleApply(index, action)}
                            disabled={applyingIndex !== null}
                          >
                            {applyingIndex === index ? 'Đang áp dụng...' : 'Áp dụng'}
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

export default AiAlertProposalCard
