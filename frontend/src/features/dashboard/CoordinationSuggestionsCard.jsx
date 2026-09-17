import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { FadeIn, StaggerList } from '../../components/animations/index.js'
import { REALTIME_COALESCE_DELAY, useRealtimeUpdates } from '../../hooks/useRealtimeUpdates.js'
import { listCoordinationSuggestions } from '../coordination/coordinationApi.js'
import { DIRECTIVE_SOURCE_LABELS } from '../coordination/directiveLabels.js'
import { formatActiveTaskTitles, formatCandidateWorkload } from '../coordination/workloadLabels.js'

const ALERT_TYPE_LABELS = {
  early_warning: 'Dấu hiệu sớm',
  overload: 'Quá tải',
}

function CoordinationSuggestionsCard({ role }) {
  const navigate = useNavigate()
  const [suggestions, setSuggestions] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  const loadSuggestions = useCallback(async () => {
    if (role !== 'manager') return
    setIsLoading(true)
    setError('')
    try {
      setSuggestions((await listCoordinationSuggestions()) || [])
    } catch {
      setError('Không thể tải gợi ý điều phối lúc này.')
    } finally {
      setIsLoading(false)
    }
  }, [role])

  useEffect(() => {
    void loadSuggestions()
  }, [loadSuggestions])

  useRealtimeUpdates(
    'alerts',
    () => {
      void loadSuggestions()
    },
    { coalesceDelay: REALTIME_COALESCE_DELAY },
  )

  const pendingSuggestions = useMemo(
    () =>
      suggestions
        .filter((suggestion) => !suggestion.applied_plan && suggestion.candidates?.length)
        .slice(0, 5),
    [suggestions],
  )

  if (role !== 'manager') return null

  return (
    <div className="mt-8">
      <FadeIn className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Gợi ý điều phối cần xem xét</h2>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              Các đề xuất dựa trên nhân viên đang quá tải và đồng nghiệp còn khả năng nhận thêm
              việc. {DIRECTIVE_SOURCE_LABELS.coordination} từ Lãnh đạo được quản lý riêng tại trang
              yêu cầu và điều phối.
            </p>
          </div>
          <span className="rounded-full bg-amber-50 px-3 py-1 text-sm font-semibold text-amber-800">
            {pendingSuggestions.length} mục
          </span>
        </div>

        {error ? (
          <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
        ) : isLoading ? (
          <p className="mt-5 rounded-xl bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
            Đang tải gợi ý điều phối...
          </p>
        ) : pendingSuggestions.length === 0 ? (
          <p className="mt-5 rounded-xl bg-emerald-50 px-4 py-6 text-center text-sm text-emerald-700">
            Không có gợi ý điều phối nào đang chờ.
          </p>
        ) : (
          <StaggerList className="mt-5 grid gap-3 lg:grid-cols-2">
            {pendingSuggestions.map((suggestion) => {
              const candidate = suggestion.candidates[0]
              return (
                <article
                  key={suggestion.alert_id}
                  className="rounded-xl border border-slate-200 bg-slate-50/70 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="rounded-full bg-red-50 px-2.5 py-1 text-xs font-bold text-red-700">
                      {ALERT_TYPE_LABELS[suggestion.alert_type] || 'Cần theo dõi'}
                    </span>
                    <span className="text-xs font-medium text-slate-500">
                      {suggestion.source_employee_code}
                    </span>
                  </div>
                  <p className="mt-3 font-bold text-slate-900">{suggestion.source_employee_name}</p>
                  <p className="mt-1 text-sm leading-6 text-slate-600">
                    Có thể phân bớt việc sang {candidate.employee_name} ({candidate.employee_code}),
                    {` ${formatCandidateWorkload(candidate)}`} với chất lượng{' '}
                    {candidate.quality_score} điểm.
                  </p>
                  {formatActiveTaskTitles(candidate) && (
                    <p className="mt-2 text-xs leading-5 text-slate-500">
                      {formatActiveTaskTitles(candidate)}
                    </p>
                  )}
                  <button
                    type="button"
                    className="mt-3 text-sm font-semibold text-brand-700 hover:text-brand-900"
                    onClick={() => navigate(`/manager/alerts?alert=${suggestion.alert_id}`)}
                  >
                    Xem chi tiết →
                  </button>
                </article>
              )
            })}
          </StaggerList>
        )}
      </FadeIn>
    </div>
  )
}

export default CoordinationSuggestionsCard
