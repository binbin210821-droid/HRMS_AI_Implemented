import { useNavigate } from 'react-router-dom'

import { FadeIn, StaggerList } from '../../components/animations/index.js'

const CATEGORY_LABELS = {
  early_warning: 'Dấu hiệu sớm',
  overload: 'Quá tải',
  overdue_task: 'Công việc quá hạn',
}

const CATEGORY_STYLES = {
  early_warning: 'border-amber-200 bg-amber-50 text-amber-800',
  overload: 'border-red-200 bg-red-50 text-red-800',
  overdue_task: 'border-rose-200 bg-rose-50 text-rose-800',
}

function AttentionPanel({ summary, role, error, isLoading = false, variant = 'page' }) {
  const navigate = useNavigate()
  const items = summary?.items || []
  const isPopover = variant === 'popover'
  const isLeadershipPopover = isPopover && role === 'leadership'
  const departmentGroups = isLeadershipPopover
    ? groupAttentionItemsByDepartment(items, summary?.department_details)
    : []
  const overloadedDepartmentCount =
    summary?.overloaded_department_count ??
    departmentGroups.filter((group) => group.overloadCount > 0).length
  const overdueDepartmentCount =
    summary?.overdue_department_count ??
    departmentGroups.filter((group) => group.overdueTaskCount > 0).length

  function openItem(item) {
    if (!item?.id || !item?.source) return

    const params = new URLSearchParams()
    params.set(item.source === 'alert' ? 'alert' : 'task', item.id)

    if (item.source === 'alert') {
      const path = role === 'leadership' ? '/leadership/alerts' : '/manager/alerts'
      params.set('status', 'open')
      if (item.category) params.set('alert_type', item.category)
      if (item.severity) params.set('severity', item.severity)
      if (item.employee_id) params.set('employee_id', item.employee_id)
      if (item.department_id) params.set('department_id', item.department_id)
      navigate(`${path}?${params.toString()}`)
      return
    }

    const path = role === 'leadership' ? '/leadership/tasks' : '/manager/tasks'
    params.set('deadline', 'overdue')
    if (role === 'leadership') {
      if (item.department_id) params.set('department_id', item.department_id)
    } else if (item.employee_id) {
      params.set('employee_id', item.employee_id)
    }
    navigate(`${path}?${params.toString()}`)
  }

  return (
    <FadeIn
      className={
        isPopover
          ? `max-h-[min(32rem,calc(100vh-7rem))] overflow-y-auto rounded-2xl border border-slate-200 p-4 shadow-2xl sm:p-5 ${isLeadershipPopover ? 'bg-slate-50/95' : 'bg-white'}`
          : 'mt-8 rounded-2xl border border-slate-200 bg-slate-50/70 p-5 sm:p-6'
      }
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Việc cần ưu tiên</h2>
          <p className="mt-1 text-sm text-slate-600">
            Các vấn đề nên được xem và xử lý trước để tránh ảnh hưởng tiến độ.
          </p>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <span className="rounded-full bg-white px-3 py-1 text-sm font-semibold text-slate-600 ring-1 ring-slate-200">
            {summary?.total ?? 0} {isLeadershipPopover ? 'hạng mục phòng ban' : 'mục'}
          </span>
          {isLeadershipPopover && (
            <>
              <span className="rounded-full bg-red-50 px-3 py-1 text-sm font-semibold text-red-800 ring-1 ring-red-100">
                {overloadedDepartmentCount} phòng ban quá tải
              </span>
              <span className="rounded-full bg-rose-50 px-3 py-1 text-sm font-semibold text-rose-800 ring-1 ring-rose-100">
                {overdueDepartmentCount} phòng ban có việc quá hạn
              </span>
            </>
          )}
        </div>
      </div>

      {error ? (
        <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
      ) : isLoading ? (
        <p className="mt-5 rounded-xl bg-white px-4 py-6 text-center text-sm text-slate-500 ring-1 ring-slate-200">
          Đang tải danh sách việc cần ưu tiên...
        </p>
      ) : items.length === 0 ? (
        <p className="mt-5 rounded-xl bg-white px-4 py-6 text-center text-sm text-slate-500 ring-1 ring-slate-200">
          Hiện không có việc nào cần theo dõi.
        </p>
      ) : isLeadershipPopover ? (
        <StaggerList className="mt-4 grid gap-3 sm:grid-cols-2">
          {departmentGroups.map((group) => (
            <article
              key={group.id}
              className="rounded-xl border border-slate-200 bg-white p-4 text-left transition duration-motion-standard ease-motion-standard hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-brand-300"
            >
              <div className="flex items-start justify-between gap-3">
                <span className="text-sm font-bold text-slate-800">{group.name}</span>
                <span className="shrink-0 rounded-full bg-brand-50 px-2.5 py-1 text-xs font-bold text-brand-800">
                  {group.totalCount} hạng mục
                </span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-xs font-semibold">
                <span className="rounded-lg bg-amber-50 px-2 py-2 text-amber-800">
                  Sớm: {group.earlyWarningCount}
                </span>
                <span className="rounded-lg bg-red-50 px-2 py-2 text-red-800">
                  Quá tải: {group.overloadCount}
                </span>
                <span className="rounded-lg bg-rose-50 px-2 py-2 text-rose-800">
                  Quá hạn: {group.overdueTaskCount} việc
                </span>
              </div>
              <div className="mt-3 border-t border-slate-100 pt-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Chi tiết theo nhân viên
                </p>
                <div className="mt-2 space-y-2">
                  {group.employees.length === 0 ? (
                    <p className="text-xs text-slate-500">Chưa có chi tiết nhân viên.</p>
                  ) : (
                    group.employees.map((employee) => (
                      <div
                        key={employee.employee_id}
                        className="rounded-lg bg-slate-50 px-3 py-2 text-xs"
                      >
                        <p className="font-semibold text-slate-700">
                          {employee.employee_name}
                          {employee.employee_code ? ` (${employee.employee_code})` : ''}
                        </p>
                        <p className="mt-1 text-slate-500">
                          Sớm {employee.early_warning_count} · Quá tải {employee.overload_count} ·
                          Quá hạn {employee.overdue_task_count} việc
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </div>
              {group.items[0] && (
                <button
                  type="button"
                  className="mt-3 text-xs font-semibold text-brand-700 hover:text-brand-900"
                  onClick={() => openItem(group.items[0])}
                >
                  Xem chi tiết →
                </button>
              )}
            </article>
          ))}
        </StaggerList>
      ) : (
        <StaggerList className={`${isPopover ? 'mt-4' : 'mt-5'} grid gap-3 lg:grid-cols-2`}>
          {items.map((item) => (
            <button
              key={`${item.source}-${item.id}`}
              type="button"
              className={`rounded-xl border p-4 text-left transition duration-motion-standard ease-motion-standard hover:-translate-y-0.5 hover:shadow-md ${CATEGORY_STYLES[item.category] || 'border-slate-200 bg-white text-slate-800'}`}
              onClick={() => openItem(item)}
              aria-label={`Xem và xử lý ${item.title}`}
            >
              <div className="flex items-start justify-between gap-3">
                <span className="rounded-full bg-white/80 px-2.5 py-1 text-xs font-bold">
                  {CATEGORY_LABELS[item.category] || 'Cần theo dõi'}
                </span>
                <span className="text-xs font-semibold opacity-80">
                  {formatAttentionTime(item)}
                </span>
              </div>
              <p className="mt-3 text-sm font-bold">{item.title}</p>
              <p className="mt-1 text-sm opacity-85">{item.employee_name}</p>
              <p className="mt-1 text-xs opacity-75">
                {item.department_name || 'Phòng ban chưa xác định'}
              </p>
              <p className="mt-3 text-xs font-semibold">Xem và xử lý →</p>
            </button>
          ))}
        </StaggerList>
      )}
    </FadeIn>
  )
}

function groupAttentionItemsByDepartment(items, departmentDetails = []) {
  if (departmentDetails.length > 0) {
    return departmentDetails.map((detail) => {
      const matchingItems = items.filter((item) => item.department_id === detail.department_id)
      const firstItem = detail.first_item_id
        ? {
            id: detail.first_item_id,
            source: detail.first_item_source || 'alert',
          }
        : null

      return {
        id: detail.department_id,
        name: detail.department_name || 'Phòng ban chưa xác định',
        items: matchingItems.length > 0 ? matchingItems : firstItem ? [firstItem] : [],
        totalCount:
          Number(detail.early_warning_employee_count > 0) +
          Number(detail.overload_employee_count > 0) +
          Number(detail.overdue_task_count > 0),
        earlyWarningCount: detail.early_warning_employee_count,
        overloadCount: detail.overload_employee_count,
        overdueTaskCount: detail.overdue_task_count,
        employees: detail.employees || [],
      }
    })
  }

  const groups = new Map()

  items.forEach((item) => {
    const departmentId = item.department_id || 'unknown'
    const group = groups.get(departmentId) || {
      id: departmentId,
      name: item.department_name || 'Phòng ban chưa xác định',
      items: [],
      totalCount: 0,
      earlyWarningCount: 0,
      overloadCount: 0,
      overdueTaskCount: 0,
      employees: [],
    }

    group.items.push(item)
    group.totalCount += 1
    if (item.category === 'early_warning') group.earlyWarningCount += 1
    if (item.category === 'overload') group.overloadCount += 1
    if (item.category === 'overdue_task') {
      group.overdueTaskCount += item.overdue_task_count || 1
    }
    groups.set(departmentId, group)
  })

  return [...groups.values()].sort((left, right) => {
    if (right.totalCount !== left.totalCount) return right.totalCount - left.totalCount
    return left.name.localeCompare(right.name, 'vi')
  })
}

function formatAttentionTime(item) {
  if (item.source === 'task') {
    return `Quá ${item.days_overdue || 0} ngày`
  }

  if (!item.created_at) return 'Mới cập nhật'
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(new Date(item.created_at))
}

export default AttentionPanel
