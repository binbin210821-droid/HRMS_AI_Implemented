import { useCallback, useEffect, useMemo, useState } from 'react'

import { listDepartmentDirectives, listDirectives } from '../coordination/coordinationApi.js'
import { DIRECTIVE_SOURCE_LABELS } from '../coordination/directiveLabels.js'
import { buildCoordinationDirectiveSla, buildLifecycleDirectiveSla } from './managerDirectiveSla.js'
import { listDepartmentTaskDirectives } from '../tasks/tasksApi.js'

const TABS = [
  { key: 'task', label: DIRECTIVE_SOURCE_LABELS.task },
  { key: 'alert', label: DIRECTIVE_SOURCE_LABELS.alert },
  { key: 'coordination', label: DIRECTIVE_SOURCE_LABELS.coordination },
]

function formatHours(value) {
  return value === null || value === undefined ? '—' : `${value.toFixed(1)} giờ`
}

function SortButton({ label, sortKey, sort, onSort }) {
  const isActive = sort.key === sortKey
  return (
    <button
      type="button"
      className="font-semibold text-slate-700 hover:text-brand-700"
      onClick={() => onSort(sortKey)}
    >
      {label} {isActive ? (sort.direction === 'asc' ? '↑' : '↓') : '↕'}
    </button>
  )
}

function sortRows(rows, sort) {
  return [...rows].sort((left, right) => {
    const leftValue = left[sort.key]
    const rightValue = right[sort.key]
    if (leftValue === rightValue) return 0
    if (leftValue === null || leftValue === undefined) return 1
    if (rightValue === null || rightValue === undefined) return -1
    const comparison =
      typeof leftValue === 'string'
        ? leftValue.localeCompare(rightValue, 'vi')
        : leftValue - rightValue
    return sort.direction === 'asc' ? comparison : -comparison
  })
}

function LifecycleTable({ rows, sort, onSort }) {
  const sortedRows = useMemo(() => sortRows(rows, sort), [rows, sort])
  if (sortedRows.length === 0) {
    return <p className="mt-4 text-sm text-slate-500">Chưa có dữ liệu chỉ thị để tổng hợp.</p>
  }

  return (
    <div className="mt-4 overflow-x-auto">
      <table className="min-w-full text-left text-sm">
        <caption className="sr-only">Hiệu quả xử lý chỉ thị theo quản lý</caption>
        <thead className="border-b border-slate-200 text-xs uppercase tracking-wide">
          <tr>
            <th className="px-3 py-2">
              <SortButton label="Quản lý" sortKey="manager_name" sort={sort} onSort={onSort} />
            </th>
            <th className="px-3 py-2">
              <SortButton label="Đang mở" sortKey="open_count" sort={sort} onSort={onSort} />
            </th>
            <th className="px-3 py-2">
              <SortButton
                label="TB tiếp nhận"
                sortKey="average_acknowledgement_hours"
                sort={sort}
                onSort={onSort}
              />
            </th>
            <th className="px-3 py-2">
              <SortButton
                label="TB xử lý"
                sortKey="average_processing_hours"
                sort={sort}
                onSort={onSort}
              />
            </th>
            <th className="px-3 py-2">
              <SortButton
                label="Tỷ lệ làm lại"
                sortKey="revision_rate"
                sort={sort}
                onSort={onSort}
              />
            </th>
            <th className="px-3 py-2">
              <SortButton
                label="Cam kết trễ"
                sortKey="overdue_commitment_count"
                sort={sort}
                onSort={onSort}
              />
            </th>
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((row) => (
            <tr key={row.manager_id} className="border-b border-slate-100 last:border-0">
              <td className="px-3 py-3 font-semibold text-slate-900">{row.manager_name}</td>
              <td className="px-3 py-3 text-slate-700">{row.open_count}</td>
              <td className="px-3 py-3 text-slate-700">
                {formatHours(row.average_acknowledgement_hours)}
              </td>
              <td className="px-3 py-3 text-slate-700">
                {formatHours(row.average_processing_hours)}
              </td>
              <td className="px-3 py-3 text-slate-700">
                {row.revision_rate === null ? '—' : `${row.revision_rate.toFixed(1)}%`}
              </td>
              <td className="px-3 py-3 text-slate-700">{row.overdue_commitment_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CoordinationTable({ result, sort, onSort }) {
  const sortedRows = useMemo(() => sortRows(result.rows, sort), [result.rows, sort])
  return (
    <>
      <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
        Đang chờ xử lý: <strong>{result.pending_count}</strong>
      </p>
      {sortedRows.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">Chưa có yêu cầu điều phối nào được ghi nhận.</p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <caption className="sr-only">Hiệu quả điều phối liên phòng ban theo quản lý</caption>
            <thead className="border-b border-slate-200 text-xs uppercase tracking-wide">
              <tr>
                <th className="px-3 py-2">
                  <SortButton label="Quản lý" sortKey="manager_name" sort={sort} onSort={onSort} />
                </th>
                <th className="px-3 py-2">
                  <SortButton
                    label="Đã hoàn tất"
                    sortKey="fulfilled_count"
                    sort={sort}
                    onSort={onSort}
                  />
                </th>
                <th className="px-3 py-2">
                  <SortButton
                    label="TB hoàn tất"
                    sortKey="average_fulfillment_hours"
                    sort={sort}
                    onSort={onSort}
                  />
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((row) => (
                <tr key={row.manager_id} className="border-b border-slate-100 last:border-0">
                  <td className="px-3 py-3 font-semibold text-slate-900">{row.manager_name}</td>
                  <td className="px-3 py-3 text-slate-700">{row.fulfilled_count}</td>
                  <td className="px-3 py-3 text-slate-700">
                    {formatHours(row.average_fulfillment_hours)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

function ManagerDirectiveSlaCard({ role }) {
  const [activeTab, setActiveTab] = useState('task')
  const [data, setData] = useState({ task: [], alert: [], coordination: [] })
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [sort, setSort] = useState({ key: 'open_count', direction: 'desc' })

  const loadData = useCallback(async () => {
    if (role !== 'leadership') return
    setIsLoading(true)
    setError('')
    const results = await Promise.allSettled([
      listDepartmentTaskDirectives(),
      listDepartmentDirectives(),
      listDirectives(),
    ])
    const nextData = { task: [], alert: [], coordination: [] }
    const failed = []
    results.forEach((result, index) => {
      const key = ['task', 'alert', 'coordination'][index]
      if (result.status === 'fulfilled') nextData[key] = result.value
      else failed.push(TABS[index].label)
    })
    setData(nextData)
    if (failed.length > 0) setError(`Chưa thể tải ${failed.join(', ')}.`)
    setIsLoading(false)
  }, [role])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const lifecycleRows = useMemo(
    () => buildLifecycleDirectiveSla(data[activeTab]),
    [activeTab, data],
  )
  const coordinationResult = useMemo(
    () => buildCoordinationDirectiveSla(data.coordination),
    [data.coordination],
  )

  function handleSort(key) {
    setSort((current) => ({
      key,
      direction: current.key === key && current.direction === 'asc' ? 'desc' : 'asc',
    }))
  }

  if (role !== 'leadership') return null

  return (
    <section className="mt-6 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200 sm:p-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-wide text-brand-700">
          Hiệu quả xử lý chỉ thị
        </p>
        <h2 className="mt-1 text-lg font-bold text-slate-900">Theo dõi theo quản lý</h2>
        <p className="mt-1 text-sm text-slate-600">
          Tổng hợp thời gian tiếp nhận, xử lý, yêu cầu làm lại và cam kết trễ của từng quản lý.
        </p>
      </div>

      <div className="mt-5 flex flex-wrap gap-2" role="tablist" aria-label="Nguồn chỉ thị">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.key}
            className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${
              activeTab === tab.key
                ? 'bg-brand-600 text-white'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
            onClick={() => {
              setActiveTab(tab.key)
              setSort({
                key: tab.key === 'coordination' ? 'fulfilled_count' : 'open_count',
                direction: 'desc',
              })
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {isLoading ? (
        <p className="mt-5 text-sm text-slate-500">Đang tải dữ liệu tổng hợp...</p>
      ) : activeTab === 'coordination' ? (
        <CoordinationTable result={coordinationResult} sort={sort} onSort={handleSort} />
      ) : (
        <LifecycleTable rows={lifecycleRows} sort={sort} onSort={handleSort} />
      )}
    </section>
  )
}

export default ManagerDirectiveSlaCard
