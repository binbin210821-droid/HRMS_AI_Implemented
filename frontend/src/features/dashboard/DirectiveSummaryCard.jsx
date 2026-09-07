import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useRealtimeUpdates } from '../../hooks/useRealtimeUpdates.js'
import {
  listDepartmentDirectives,
  listDirectives,
} from '../coordination/coordinationApi.js'
import {
  DIRECTIVE_SOURCE_LABELS,
  getDirectiveStatusLabel,
} from '../coordination/directiveLabels.js'
import { listDepartmentTaskDirectives } from '../tasks/tasksApi.js'

function DirectiveSummaryCard({ role }) {
  const navigate = useNavigate()
  const [directives, setDirectives] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  const loadDirectives = useCallback(async () => {
    if (role !== 'manager' && role !== 'leadership') return

    setIsLoading(true)
    setError('')
    const results = await Promise.allSettled([
      listDepartmentDirectives(),
      listDepartmentTaskDirectives(),
      listDirectives(),
    ])
    const loadedDirectives = []
    const failedSources = []

    const sourceKeys = ['alert', 'task', 'coordination']
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        loadedDirectives.push(
          ...(Array.isArray(result.value)
            ? result.value.map((directive) => ({ ...directive, source: sourceKeys[index] }))
            : []),
        )
      } else {
        failedSources.push(DIRECTIVE_SOURCE_LABELS[sourceKeys[index]])
      }
    })

    setDirectives(loadedDirectives)
    if (failedSources.length > 0) {
      setError(`Chưa thể tải ${failedSources.join(', ')}.`)
    }
    setIsLoading(false)
  }, [role])

  useEffect(() => {
    void loadDirectives()
  }, [loadDirectives])

  useRealtimeUpdates('department_directives', () => {
    void loadDirectives()
  })
  useRealtimeUpdates('task_directives', () => {
    void loadDirectives()
  })

  const sourceCounts = useMemo(
    () =>
      Object.entries(DIRECTIVE_SOURCE_LABELS).map(([source, label]) => {
        const items = directives.filter((directive) => directive.source === source)
        const statusCounts = items.reduce((counts, directive) => {
          const status = directive.status === 'fulfilled' ? 'accepted' : directive.status
          counts[status] = (counts[status] || 0) + 1
          return counts
        }, {})
        return { source, label, count: items.length, statusCounts }
      }),
    [directives],
  )

  if (role !== 'manager' && role !== 'leadership') return null

  const directivesPath = role === 'leadership' ? '/leadership/directives' : '/manager/directives'

  return (
    <section className="mt-6 rounded-2xl bg-sky-50/70 p-5 ring-1 ring-sky-100 sm:p-6">
      <button
        type="button"
        className="w-full text-left transition hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2"
        aria-label="Mở trang yêu cầu và điều phối"
        onClick={() => navigate(directivesPath)}
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-sky-700">
              Theo dõi yêu cầu và điều phối
            </p>
            <h2 className="mt-1 text-lg font-bold text-slate-900">
              Yêu cầu và điều phối cần theo dõi
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              {role === 'leadership'
                ? 'Theo dõi các yêu cầu đã gửi và tiến độ tiếp nhận, nghiệm thu của các phòng ban.'
                : 'Xem yêu cầu được giao, trạng thái xử lý và việc cần phản hồi.'}
            </p>
          </div>
          <div className="rounded-xl bg-white px-4 py-3 text-right shadow-sm ring-1 ring-sky-100">
            <p className="text-xs font-semibold text-sky-700">Tổng yêu cầu và điều phối</p>
            <p className="mt-1 text-3xl font-bold text-sky-900">
              {isLoading ? '—' : directives.length}
            </p>
          </div>
        </div>

        {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

        <div className="mt-4 grid gap-2 sm:grid-cols-3">
          {sourceCounts.map(({ source, label, count, statusCounts }) => (
            <div
              key={source}
              className="rounded-xl bg-white px-3 py-3 text-sm font-semibold ring-1 ring-sky-100"
            >
              <span className="block text-xs font-bold text-sky-800">{label}</span>
              <span className="mt-1 block text-xl font-bold text-slate-900">
                {isLoading ? '—' : count}
              </span>
              <span className="mt-2 block text-xs font-medium text-slate-600">
                {isLoading
                  ? 'Đang tải...'
                  : count === 0
                    ? 'Chưa có mục nào'
                    : `${getDirectiveStatusLabel(source, 'pending')}: ${statusCounts.pending || 0}`}
              </span>
            </div>
          ))}
        </div>

        <div className="mt-4 flex justify-end border-t border-sky-100 pt-3 text-sm font-semibold text-sky-800">
          Mở trang yêu cầu và điều phối →
        </div>
      </button>
    </section>
  )
}

export default DirectiveSummaryCard
