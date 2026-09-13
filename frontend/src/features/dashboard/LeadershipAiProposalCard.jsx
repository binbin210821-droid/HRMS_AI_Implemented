import { useState } from 'react'
import { AnimatePresence } from 'framer-motion'

import { AiLoadingIndicator, FadeIn, StaggerList } from '../../components/animations/index.js'
import { useActionFeedback } from '../../components/feedback/index.js'
import AiSuggestionToggle from '../ai/AiSuggestionToggle.jsx'
import { getLeadershipActionProposal } from '../ai/aiApi.js'
import {
  makeAiSuggestionKey,
  readAiSuggestion,
  writeAiSuggestion,
} from '../ai/aiSuggestionStorage.js'
import { issueDepartmentDirective } from '../coordination/coordinationApi.js'
import { listDepartments } from '../departments/departmentsApi.js'
import { generateIdempotencyKey } from '../../utils/idempotency.js'

const ALERT_TYPE_LABELS = {
  all: 'Mọi cảnh báo',
  early_warning: 'Dấu hiệu sớm',
  overload: 'Quá tải',
}

const SEVERITY_LABELS = {
  all: 'Mọi mức độ',
  medium: 'Trung bình',
  high: 'Cao',
}

const COORDINATION_ACTION_LABELS = {
  transfer_work: 'Điều phối thêm công việc',
  extend_deadline: 'Gia hạn thời hạn',
  reduce_scope: 'Giảm phạm vi công việc',
  keep_and_extend: 'Giữ phương án hiện tại và gia hạn',
}

const FOLLOW_UP_ACTION_LABELS = {
  request_manager_explanation: 'Yêu cầu Quản lý giải trình',
  monitor_department: 'Theo dõi thêm phòng ban',
  request_manager_re_evaluation: 'Đề xuất đánh giá lại Quản lý',
}

function LeadershipAiProposalCard({ role, onIssued }) {
  const storageKey = makeAiSuggestionKey('leadership-overview-proposal', role || 'unknown')
  const cachedSuggestion = readAiSuggestion(storageKey)
  const [proposal, setProposal] = useState(() => cachedSuggestion?.proposal || null)
  const [departments, setDepartments] = useState(() => cachedSuggestion?.departments || [])
  const [isLoading, setIsLoading] = useState(false)
  const [applyingIndex, setApplyingIndex] = useState(null)
  const [appliedIndexes, setAppliedIndexes] = useState(() => cachedSuggestion?.appliedIndexes || [])
  const [error, setError] = useState('')
  const [isVisible, setIsVisible] = useState(cachedSuggestion?.isVisible ?? true)
  const { confirmAction, notifyActionSuccess, notifyActionError } = useActionFeedback()

  if (role !== 'leadership') return null

  async function handleLoadProposal() {
    if (isLoading) return
    setIsLoading(true)
    setError('')
    try {
      const [result, departmentList] = await Promise.all([
        getLeadershipActionProposal(),
        listDepartments(),
      ])
      setDepartments(departmentList || [])
      const nextProposal = {
        ...result,
        actions: (result.actions || []).map((action) => ({ ...action })),
      }
      setProposal(nextProposal)
      setAppliedIndexes([])
      setIsVisible(true)
      writeAiSuggestion(storageKey, {
        proposal: nextProposal,
        departments: departmentList || [],
        appliedIndexes: [],
        updatedAt: new Date().toISOString(),
        isVisible: true,
      })
    } catch {
      setError('Không thể lấy đề xuất AI lúc này. Bạn có thể phát hành chỉ thị thủ công.')
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
        appliedIndexes,
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
        appliedIndexes,
        isVisible: next,
      })
      return next
    })
  }

  async function handleApply(index, action) {
    if (applyingIndex !== null || appliedIndexes.includes(index)) return
    const departmentName =
      action.department_name ||
      departments.find((department) => department.id === action.department_id)?.name ||
      'Phòng ban đã được kiểm tra quyền'
    const confirmed = await confirmAction({
      title: 'Xác nhận phát hành chỉ thị theo đề xuất AI',
      description: 'Đề xuất chỉ được phát hành sau khi bạn xác nhận thông tin bên dưới.',
      details: [
        `Phòng ban: ${departmentName}`,
        `Loại cảnh báo: ${ALERT_TYPE_LABELS[action.alert_type] || ALERT_TYPE_LABELS.all}`,
        `Mức độ: ${SEVERITY_LABELS[action.severity] || SEVERITY_LABELS.all}`,
        `Ghi chú: ${action.note?.trim() || 'Không thêm ghi chú'}`,
      ],
      confirmLabel: 'Xác nhận phát hành',
    })
    if (!confirmed) return

    setApplyingIndex(index)
    setError('')
    try {
      const created = await issueDepartmentDirective(
        action.department_id,
        {
          alert_type: action.alert_type,
          severity: action.severity,
          note: action.note || null,
        },
        generateIdempotencyKey(),
      )
      setAppliedIndexes((current) => {
        const nextIndexes = [...current, index]
        writeAiSuggestion(storageKey, {
          ...readAiSuggestion(storageKey),
          proposal,
          appliedIndexes: nextIndexes,
          isVisible,
        })
        return nextIndexes
      })
      onIssued?.(created)
      notifyActionSuccess({
        title: 'Đã phát hành chỉ thị phòng ban',
        message: `Chỉ thị cho ${departmentName} đã được ghi nhận.`,
        details: [
          `Loại cảnh báo: ${ALERT_TYPE_LABELS[action.alert_type] || ALERT_TYPE_LABELS.all}`,
          `Mức độ: ${SEVERITY_LABELS[action.severity] || SEVERITY_LABELS.all}`,
        ],
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể phát hành chỉ thị lúc này.'
      setError(message)
      notifyActionError({ title: 'Chưa phát hành chỉ thị', message })
    } finally {
      setApplyingIndex(null)
    }
  }

  return (
    <section className="mt-6 rounded-2xl border border-violet-200 bg-violet-50/70 p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-violet-700">
            Hỗ trợ ra quyết định
          </p>
          <h2 className="mt-1 text-lg font-bold text-violet-950">AI đề xuất cho Lãnh đạo</h2>
          <p className="mt-1 text-sm leading-6 text-violet-900/80">
            Tổng hợp rủi ro theo phòng ban và gợi ý chỉ thị để bạn xem xét trước khi phát hành.
          </p>
        </div>
        {!proposal && !isLoading && (
          <button
            type="button"
            className="secondary-button border-violet-300 text-violet-800 hover:border-violet-500"
            onClick={handleLoadProposal}
          >
            Hỏi AI đề xuất
          </button>
        )}
        {proposal && !isLoading && (
          <AiSuggestionToggle isVisible={isVisible} onToggle={toggleVisibility} />
        )}
      </div>

      <AnimatePresence initial={false} mode="wait">
        {isLoading ? (
          <FadeIn key="loading" className="mt-4">
            <AiLoadingIndicator label="AI đang tổng hợp tình hình các phòng ban…" />
          </FadeIn>
        ) : proposal ? (
          <FadeIn key="proposal" className="mt-4">
            {isVisible ? (
              <>
                <p className="text-base leading-7 text-violet-950">{proposal.summary}</p>
                {proposal.key_findings?.length > 0 && (
                  <div className="mt-4 rounded-xl bg-white/80 p-4 ring-1 ring-violet-100">
                    <p className="text-sm font-semibold text-violet-950">Điểm cần lưu ý</p>
                    <ul className="mt-2 space-y-2 text-sm leading-6 text-slate-700">
                      {proposal.key_findings.map((finding, findingIndex) => (
                        <li key={`${finding.department_id}-${findingIndex}`}>
                          <span className="font-semibold">{finding.title}</span>
                          {finding.evidence?.length > 0 && ` — ${finding.evidence.join('; ')}`}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {proposal.actions?.length ? (
                  <StaggerList className="mt-4 space-y-3">
                    {proposal.actions.map((action, index) => {
                      const applied = appliedIndexes.includes(index)
                      const isDirective = action.type === 'issue_department_directive'
                      const isCoordination = action.type === 'cross_department_coordination'
                      const isThreshold = action.type === 'propose_threshold_config'
                      const isFollowUp = Object.prototype.hasOwnProperty.call(
                        FOLLOW_UP_ACTION_LABELS,
                        action.type,
                      )
                      const departmentName =
                        action.department_name ||
                        departments.find((department) => department.id === action.department_id)
                          ?.name ||
                        (isCoordination ? action.target_department_name : null) ||
                        'Phòng ban đã được kiểm tra quyền'
                      return (
                        <div
                          key={`${action.type}-${index}`}
                          className="rounded-xl bg-white p-4 ring-1 ring-violet-100"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="font-semibold text-slate-900">
                              {isCoordination
                                ? `${action.source_department_name} → ${action.target_department_name}`
                                : departmentName}
                            </p>
                            <span className="rounded-full bg-violet-100 px-2.5 py-1 text-xs font-semibold text-violet-800">
                              Phương án {index + 1}
                            </span>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-slate-700">
                            <span className="font-semibold">Lý do:</span> {action.rationale}
                          </p>
                          {action.evidence?.length > 0 && (
                            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-600">
                              {action.evidence.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          )}
                          {isDirective && (
                            <>
                              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                                <label className="text-sm font-medium text-slate-700">
                                  Loại cảnh báo
                                  <select
                                    className="form-input mt-1"
                                    value={action.alert_type}
                                    onChange={(event) =>
                                      updateAction(index, { alert_type: event.target.value })
                                    }
                                    disabled={applied}
                                  >
                                    {Object.entries(ALERT_TYPE_LABELS).map(([value, label]) => (
                                      <option key={value} value={value}>
                                        {label}
                                      </option>
                                    ))}
                                  </select>
                                </label>
                                <label className="text-sm font-medium text-slate-700">
                                  Mức độ
                                  <select
                                    className="form-input mt-1"
                                    value={action.severity}
                                    onChange={(event) =>
                                      updateAction(index, { severity: event.target.value })
                                    }
                                    disabled={applied}
                                  >
                                    {Object.entries(SEVERITY_LABELS).map(([value, label]) => (
                                      <option key={value} value={value}>
                                        {label}
                                      </option>
                                    ))}
                                  </select>
                                </label>
                              </div>
                              <label className="mt-3 block text-sm font-medium text-slate-700">
                                Ghi chú chỉ thị
                                <textarea
                                  className="form-input mt-1 min-h-20"
                                  value={action.note || ''}
                                  onChange={(event) =>
                                    updateAction(index, { note: event.target.value })
                                  }
                                  disabled={applied}
                                  placeholder="Ví dụ: Rà soát và gửi kế hoạch xử lý trong ngày."
                                />
                              </label>
                              <button
                                type="button"
                                className={
                                  applied
                                    ? 'secondary-button mt-3 text-emerald-700'
                                    : 'primary-button mt-3'
                                }
                                onClick={() => void handleApply(index, action)}
                                disabled={applyingIndex !== null || applied}
                              >
                                {applied
                                  ? 'Đã phát hành'
                                  : applyingIndex === index
                                    ? 'Đang phát hành…'
                                    : 'Xem lại và phát hành'}
                              </button>
                            </>
                          )}
                          {isCoordination && (
                            <div className="mt-3 space-y-2 rounded-lg bg-sky-50 p-3 text-sm text-sky-950">
                              <p>
                                <span className="font-semibold">Phương án:</span>{' '}
                                {COORDINATION_ACTION_LABELS[action.action] ||
                                  'Điều phối liên phòng ban'}
                              </p>
                              <p>
                                <span className="font-semibold">Mức độ phù hợp:</span>{' '}
                                {action.fit_score ?? '—'}/100
                              </p>
                              <p>
                                <span className="font-semibold">Người có thể nhận thêm việc:</span>{' '}
                                {action.available_employee_count ?? '—'}
                              </p>
                              <label className="block text-sm font-medium text-sky-900">
                                Ghi chú bản nháp
                                <textarea
                                  className="form-input mt-1 min-h-16 bg-white"
                                  value={action.note || ''}
                                  onChange={(event) =>
                                    updateAction(index, { note: event.target.value })
                                  }
                                  placeholder="Bổ sung điều kiện hoặc lưu ý khi xem xét."
                                />
                              </label>
                              <p className="text-xs text-sky-800">
                                Đây là bản đề xuất để Lãnh đạo xem xét. Luồng áp dụng điều phối liên
                                phòng ban cần được hoàn thiện và không được tự động thực hiện.
                              </p>
                            </div>
                          )}
                          {isThreshold && (
                            <div className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-950">
                              <div className="grid gap-3 sm:grid-cols-2">
                                <label className="font-medium">
                                  Số ngày liên tiếp
                                  <input
                                    className="form-input mt-1 bg-white"
                                    type="number"
                                    min="3"
                                    max="7"
                                    value={action.consecutive_days}
                                    onChange={(event) =>
                                      updateAction(index, {
                                        consecutive_days: Number(event.target.value),
                                      })
                                    }
                                  />
                                </label>
                                <label className="font-medium">
                                  Mức giảm chất lượng (%)
                                  <input
                                    className="form-input mt-1 bg-white"
                                    type="number"
                                    min="1"
                                    max="100"
                                    value={action.quality_drop_percent}
                                    onChange={(event) =>
                                      updateAction(index, {
                                        quality_drop_percent: Number(event.target.value),
                                      })
                                    }
                                  />
                                </label>
                              </div>
                              <p className="mt-2 text-xs text-amber-800">
                                Đây chỉ là đề xuất cấu hình; việc duyệt vẫn phải thực hiện qua chức
                                năng cấu hình ngưỡng của hệ thống.
                              </p>
                            </div>
                          )}
                          {isFollowUp && (
                            <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
                              <p>
                                <span className="font-semibold">Hành động:</span>{' '}
                                {FOLLOW_UP_ACTION_LABELS[action.type]}
                              </p>
                              {action.monitoring_days && (
                                <p className="mt-1">
                                  <span className="font-semibold">Thời gian theo dõi:</span>{' '}
                                  {action.monitoring_days} ngày
                                </p>
                              )}
                              <label className="mt-2 block font-medium">
                                Ghi chú bản nháp
                                <textarea
                                  className="form-input mt-1 min-h-16 bg-white"
                                  value={action.note || ''}
                                  onChange={(event) =>
                                    updateAction(index, { note: event.target.value })
                                  }
                                  placeholder="Bổ sung yêu cầu hoặc phạm vi theo dõi."
                                />
                              </label>
                              <p className="mt-2 text-xs text-slate-600">
                                Hành động này cần được thực hiện qua quy trình nghiệp vụ tương ứng;
                                AI không tự gửi yêu cầu.
                              </p>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </StaggerList>
                ) : (
                  <p className="mt-3 text-sm text-violet-900">
                    Chưa có đề xuất phù hợp. Bạn có thể xử lý thủ công như bình thường.
                  </p>
                )}
              </>
            ) : (
              <div className="rounded-xl bg-white/70 p-3 text-sm text-violet-900 ring-1 ring-violet-100">
                Gợi ý AI đang tạm ẩn. Bạn có thể hiện lại bằng nút “Hiện gợi ý AI” ở đầu thẻ.
              </div>
            )}
          </FadeIn>
        ) : null}
      </AnimatePresence>

      <AnimatePresence initial={false}>
        {error && (
          <FadeIn key="error" className="mt-3 text-sm text-red-700">
            {error}
          </FadeIn>
        )}
      </AnimatePresence>
    </section>
  )
}

export default LeadershipAiProposalCard
