import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { FadeIn } from '../../components/animations/index.js'
import { useRealtimeUpdates } from '../../hooks/useRealtimeUpdates.js'
import { listAlerts } from '../alerts/alertsApi.js'
import { listDepartmentDirectives } from '../coordination/coordinationApi.js'
import { DIRECTIVE_SOURCE_LABELS } from '../coordination/directiveLabels.js'
import { listDepartments } from '../departments/departmentsApi.js'
import { listDepartmentTaskDirectives, listTasks } from '../tasks/tasksApi.js'
import { useAuthStore } from '../../stores/authStore.js'

function NotificationBell() {
  const navigate = useNavigate()
  const role = useAuthStore((state) => state.role)
  const [alerts, setAlerts] = useState([])
  const [overdueTasks, setOverdueTasks] = useState([])
  const [departments, setDepartments] = useState([])
  const [departmentDirectives, setDepartmentDirectives] = useState([])
  const [departmentTaskDirectives, setDepartmentTaskDirectives] = useState([])
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef(null)
  const departmentsLoadedRef = useRef(false)

  const loadAlerts = useCallback(async () => {
    try {
      const response = await listAlerts('open', 'all')
      setAlerts(Array.isArray(response) ? response : [])
    } catch {
      // Chuông không được làm ảnh hưởng tới phần còn lại của Header khi API tạm lỗi.
    }
  }, [])

  const loadOverdueTasks = useCallback(async () => {
    try {
      const response = await listTasks({ overdueOnly: true })
      setOverdueTasks(Array.isArray(response) ? response : [])
    } catch {
      // Nhóm công việc quá hạn không được làm ảnh hưởng tới Header khi API tạm lỗi.
    }
  }, [])

  const loadDepartments = useCallback(async () => {
    if (departmentsLoadedRef.current) return
    try {
      const response = await listDepartments()
      setDepartments(Array.isArray(response) ? response : [])
      departmentsLoadedRef.current = true
    } catch {
      // Có thể vẫn hiển thị nhóm theo mã phòng ban nếu danh sách tên phòng ban tạm thời lỗi.
    }
  }, [])

  const loadDepartmentDirectives = useCallback(async () => {
    if (role !== 'leadership') return
    try {
      const response = await listDepartmentDirectives()
      setDepartmentDirectives(Array.isArray(response) ? response : [])
    } catch {
      // Không để lỗi theo dõi yêu cầu xử lý cảnh báo làm gián đoạn chuông thông báo.
    }
  }, [role])

  const loadDepartmentTaskDirectives = useCallback(async () => {
    if (role !== 'leadership') return
    try {
      const response = await listDepartmentTaskDirectives()
      setDepartmentTaskDirectives(Array.isArray(response) ? response : [])
    } catch {
      // Không để lỗi theo dõi giao việc quá hạn làm gián đoạn chuông thông báo.
    }
  }, [role])

  useEffect(() => {
    loadAlerts()
    loadOverdueTasks()
  }, [loadAlerts, loadOverdueTasks])

  useEffect(() => {
    if (overdueTasks.length > 0 || (role === 'leadership' && alerts.length > 0)) {
      void loadDepartments()
    }
  }, [alerts.length, loadDepartments, overdueTasks.length, role])

  useEffect(() => {
    if (role === 'leadership') void loadDepartmentDirectives()
  }, [loadDepartmentDirectives, role])

  useEffect(() => {
    if (role === 'leadership') void loadDepartmentTaskDirectives()
  }, [loadDepartmentTaskDirectives, role])

  useRealtimeUpdates('alerts', loadAlerts)
  useRealtimeUpdates('tasks', loadOverdueTasks)
  useRealtimeUpdates('department_directives', loadDepartmentDirectives)
  useRealtimeUpdates('task_directives', loadDepartmentTaskDirectives)

  useEffect(() => {
    function handleOutsideClick(event) {
      if (!containerRef.current?.contains(event.target)) setIsOpen(false)
    }

    document.addEventListener('mousedown', handleOutsideClick)
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [])

  function openAlert(alert) {
    setIsOpen(false)
    const alertsPath = role === 'leadership' ? '/leadership/alerts' : '/manager/alerts'
    const params = new URLSearchParams()
    params.set('alert', alert.id)
    params.set('status', 'open')
    if (alert.alert_type) params.set('alert_type', alert.alert_type)
    if (alert.severity) params.set('severity', alert.severity)
    if (alert.employee_id) params.set('employee_id', alert.employee_id)
    if (alert.department_id) params.set('department_id', alert.department_id)
    navigate(`${alertsPath}?${params.toString()}`)
  }

  function openOverdueTask(taskId, employeeId, departmentId) {
    setIsOpen(false)
    const tasksPath = role === 'leadership' ? '/leadership/tasks' : '/manager/tasks'
    const params = new URLSearchParams()
    if (taskId) params.set('task', taskId)
    params.set('deadline', 'overdue')
    if (role === 'leadership') {
      if (departmentId) params.set('department_id', departmentId)
    } else if (employeeId) {
      params.set('employee_id', employeeId)
    }
    navigate(`${tasksPath}?${params.toString()}`)
  }

  const directedAlertIds = new Set(
    departmentDirectives.flatMap((directive) => directive.alert_ids || []).map(String),
  )
  const directedTaskIds = new Set(
    departmentTaskDirectives.flatMap((directive) => directive.task_ids || []).map(String),
  )
  const thresholdAlerts =
    role === 'leadership'
      ? alerts.filter((alert) => !directedAlertIds.has(String(alert.id)))
      : alerts
  const visibleOverdueTasks =
    role === 'leadership'
      ? overdueTasks.filter((task) => {
          const taskId = task.id || task._id
          return !taskId || !directedTaskIds.has(String(taskId))
        })
      : overdueTasks
  const visibleNotificationCount = thresholdAlerts.length + visibleOverdueTasks.length
  const earlyWarningCount = thresholdAlerts.filter(
    (alert) => alert.alert_type === 'early_warning',
  ).length
  const overloadCount = thresholdAlerts.filter((alert) => alert.alert_type === 'overload').length
  const leadershipAlertGroups = groupOpenAlertsByDepartment(thresholdAlerts, departments)
  const overdueDepartmentGroups = groupOverdueTasks(visibleOverdueTasks, departments)
  const [isReminderVisible, setIsReminderVisible] = useState(false)

  useEffect(() => {
    if (visibleNotificationCount === 0) {
      setIsReminderVisible(false)
      return undefined
    }

    let hideTimer
    const reminderTimer = window.setInterval(() => {
      setIsReminderVisible(true)
      window.clearTimeout(hideTimer)
      hideTimer = window.setTimeout(() => setIsReminderVisible(false), 10000)
    }, 15000)

    return () => {
      window.clearInterval(reminderTimer)
      window.clearTimeout(hideTimer)
    }
  }, [visibleNotificationCount])

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        aria-label={`Thông báo${visibleNotificationCount ? `, ${visibleNotificationCount} cần theo dõi` : ''}`}
        aria-expanded={isOpen}
        className="relative flex h-12 w-12 items-center justify-center rounded-xl text-slate-500 transition hover:bg-slate-100 hover:text-brand-700"
        onClick={() => setIsOpen((current) => !current)}
      >
        <svg
          aria-hidden="true"
          className={`h-6 w-6 ${visibleNotificationCount > 0 ? 'notification-bell-icon' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth="1.8"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9a6 6 0 0 0-12 0v.75a8.967 8.967 0 0 1-2.31 6.022c1.733.64 3.55 1.078 5.454 1.31m5.713 0a24.255 24.255 0 0 1-5.713 0m5.713 0a3 3 0 1 1-5.713 0"
          />
        </svg>
        {visibleNotificationCount > 0 && (
          <span className="absolute -right-1 -top-1 flex min-h-6 min-w-6 items-center justify-center rounded-full bg-amber-500 px-1 text-xs font-bold text-white">
            {visibleNotificationCount > 99 ? '99+' : visibleNotificationCount}
          </span>
        )}
      </button>

      {isReminderVisible && visibleNotificationCount > 0 && !isOpen && (
        <div
          role="status"
          aria-live="polite"
          className="notification-reminder absolute right-0 top-12 z-40 w-[min(24rem,calc(100vw-2rem))] rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 shadow-lg"
        >
          <p className="text-sm font-semibold text-amber-900">Bạn có việc cần xử lý</p>
          <p className="mt-1 text-xs leading-5 text-amber-800">
            Có {thresholdAlerts.length} {DIRECTIVE_SOURCE_LABELS.alert.toLowerCase()} và{' '}
            {visibleOverdueTasks.length} {DIRECTIVE_SOURCE_LABELS.task.toLowerCase()} cần xử lý.
          </p>
        </div>
      )}

      {isOpen && (
        <FadeIn>
          <div className="absolute right-0 top-12 z-50 w-[min(52rem,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
              <div>
                <h2 className="!text-base !font-semibold !text-slate-900">Thông báo</h2>
                <p className="!text-xs !text-slate-500">Các việc cần bạn theo dõi</p>
              </div>
              <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-700">
                {visibleNotificationCount} cần theo dõi
              </span>
            </div>
            <div className="max-h-[32rem] overflow-y-auto p-4">
              {visibleNotificationCount === 0 ? (
                <p className="px-4 py-10 text-center text-sm text-slate-500">
                  Bạn không có thông báo mới.
                </p>
              ) : (
                <div className="grid gap-4 md:grid-cols-2 md:items-stretch">
                  <NotificationSection
                    title={DIRECTIVE_SOURCE_LABELS.alert}
                    count={thresholdAlerts.length}
                    emptyMessage="Không có cảnh báo ngưỡng mới."
                    summary={
                      <div className="flex flex-wrap gap-2 text-[11px] font-semibold">
                        <span className="rounded-full bg-amber-50 px-2 py-1 text-amber-800">
                          Dấu hiệu sớm: {earlyWarningCount}
                        </span>
                        <span className="rounded-full bg-red-50 px-2 py-1 text-red-800">
                          Quá tải: {overloadCount}
                        </span>
                      </div>
                    }
                  >
                    {role === 'leadership'
                      ? leadershipAlertGroups.map((department) => (
                          <button
                            key={department.id}
                            type="button"
                            className="block w-full border-b border-slate-100 px-4 py-3 text-left transition hover:bg-slate-50 last:border-0 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-brand-300"
                            onClick={() => openAlert(department.alerts[0])}
                            aria-label={`Mở cảnh báo phòng ban ${department.name}`}
                            >
                            <p className="text-[11px] font-bold uppercase tracking-wide text-brand-700">
                              {DIRECTIVE_SOURCE_LABELS.alert}
                            </p>
                            <div className="flex items-center justify-between gap-3">
                              <p className="text-sm font-bold text-slate-800">{department.name}</p>
                              <span className="shrink-0 rounded-full bg-amber-50 px-2 py-1 text-[11px] font-bold text-amber-800">
                                {department.totalCount} chưa xử lý
                              </span>
                            </div>
                            <div className="mt-2 flex flex-wrap gap-2 text-[11px] font-semibold">
                              <span className="rounded-full bg-amber-50 px-2 py-1 text-amber-800">
                                Dấu hiệu sớm: {department.earlyWarningCount}
                              </span>
                              <span className="rounded-full bg-red-50 px-2 py-1 text-red-800">
                                Quá tải: {department.overloadCount}
                              </span>
                            </div>
                          </button>
                        ))
                      : alerts.slice(0, 5).map((alert) => (
                          <button
                            key={alert.id}
                            type="button"
                            className="block w-full border-b border-slate-100 px-4 py-3 text-left transition hover:bg-slate-50 last:border-0"
                            onClick={() => openAlert(alert)}
                            aria-label={`Mở cảnh báo ${alert.title}`}
                          >
                            <p className="text-[11px] font-bold uppercase tracking-wide text-brand-700">
                              {DIRECTIVE_SOURCE_LABELS.alert}
                            </p>
                            <p className="text-sm font-semibold text-slate-800">{alert.title}</p>
                            <p className="mt-1 text-xs leading-5 text-slate-600">{alert.message}</p>
                            <p className="mt-1 text-xs font-medium text-brand-700">
                              {alert.employee_name}
                            </p>
                          </button>
                        ))}
                  </NotificationSection>

                  <NotificationSection
                    title={DIRECTIVE_SOURCE_LABELS.task}
                    count={visibleOverdueTasks.length}
                    emptyMessage="Không có công việc quá hạn."
                  >
                    <div className="divide-y divide-slate-100">
                      {overdueDepartmentGroups.map((department) => (
                        <section key={department.id} className="px-4 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <p className="text-[11px] font-bold uppercase tracking-wide text-brand-700">
                                {DIRECTIVE_SOURCE_LABELS.task}
                              </p>
                              <p className="mt-1 text-sm font-bold text-slate-800">
                                {department.name}
                              </p>
                            </div>
                            <span className="shrink-0 rounded-full bg-red-50 px-2 py-1 text-[11px] font-bold text-red-700">
                              {department.taskCount} việc
                            </span>
                          </div>
                          <div className="mt-2 space-y-1.5">
                            {department.employees.map((employee) => (
                              <button
                                key={employee.id}
                                type="button"
                                className="flex w-full items-center justify-between gap-3 rounded-lg px-2 py-2 text-left transition hover:bg-red-50/70 focus:outline-none focus:ring-2 focus:ring-brand-300"
                                onClick={() =>
                                  openOverdueTask(employee.taskId, employee.id, department.id)
                                }
                                aria-label={`Mở công việc quá hạn của ${employee.name}`}
                              >
                                <span className="min-w-0">
                                  <span className="block truncate text-xs font-semibold text-brand-700">
                                    {employee.name}
                                  </span>
                                  {employee.code && (
                                    <span className="mt-0.5 block text-[11px] text-slate-500">
                                      {employee.code}
                                    </span>
                                  )}
                                </span>
                                <span className="shrink-0 text-right">
                                  <span className="block text-xs font-bold text-red-600">
                                    {employee.taskCount} việc quá hạn
                                  </span>
                                  <span className="mt-0.5 block text-[11px] text-slate-500">
                                    Từ {formatNotificationDate(employee.oldestDueDate)}
                                  </span>
                                </span>
                              </button>
                            ))}
                          </div>
                        </section>
                      ))}
                    </div>
                  </NotificationSection>
                </div>
              )}
            </div>
            {thresholdAlerts.length > 5 && (
              <p className="border-t border-slate-100 px-4 py-2 text-center text-xs text-slate-500">
                Hiển thị tối đa 5 yêu cầu xử lý cảnh báo; giao việc quá hạn đã được gom theo phòng
                ban và nhân viên.
              </p>
            )}
          </div>
        </FadeIn>
      )}
    </div>
  )
}

function groupOverdueTasks(tasks, departments) {
  const departmentNames = new Map(
    departments.map((department) => [String(department.id), department.name]),
  )
  const departmentMap = new Map()

  tasks.forEach((task) => {
    const departmentId = task.department_id ? String(task.department_id) : 'unknown'
    const department = departmentMap.get(departmentId) || {
      id: departmentId,
      name:
        task.department_name ||
        departmentNames.get(departmentId) ||
        (departmentId === 'unknown' ? 'Phòng ban chưa xác định' : 'Phòng ban chưa có tên'),
      employees: new Map(),
      taskCount: 0,
    }
    const employeeId = String(
      task.employee_id || task.employee_code || task.employee_name || 'unknown',
    )
    const employee = department.employees.get(employeeId) || {
      id: employeeId,
      name: task.employee_name || 'Nhân viên chưa xác định',
      code: task.employee_code || '',
      taskCount: 0,
      taskId: task.id,
      oldestDueDate: task.due_date,
    }

    employee.taskCount += 1
    if (
      task.due_date &&
      (!employee.oldestDueDate || String(task.due_date) < String(employee.oldestDueDate))
    ) {
      employee.oldestDueDate = task.due_date
      employee.taskId = task.id
    }
    department.employees.set(employeeId, employee)
    department.taskCount += 1
    departmentMap.set(departmentId, department)
  })

  return [...departmentMap.values()]
    .map((department) => ({
      ...department,
      employees: [...department.employees.values()].sort((left, right) =>
        left.name.localeCompare(right.name, 'vi'),
      ),
    }))
    .sort((left, right) => left.name.localeCompare(right.name, 'vi'))
}

function groupOpenAlertsByDepartment(alerts, departments) {
  const departmentDetails = new Map(
    departments.map((department) => [String(department.id), department]),
  )
  const groups = new Map()

  alerts.forEach((alert) => {
    const departmentId = alert.department_id ? String(alert.department_id) : 'unknown'
    const department = departmentDetails.get(departmentId)
    const group = groups.get(departmentId) || {
      id: departmentId,
      name:
        alert.department_name ||
        department?.name ||
        (departmentId === 'unknown' ? 'Phòng ban chưa xác định' : 'Phòng ban chưa có tên'),
      alerts: [],
      totalCount: 0,
      earlyWarningCount: 0,
      overloadCount: 0,
    }

    group.alerts.push(alert)
    group.totalCount += 1
    if (alert.alert_type === 'early_warning') group.earlyWarningCount += 1
    if (alert.alert_type === 'overload') group.overloadCount += 1
    groups.set(departmentId, group)
  })

  return [...groups.values()].sort((left, right) => left.name.localeCompare(right.name, 'vi'))
}

function formatNotificationDate(value) {
  if (!value) return 'chưa rõ ngày'
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('vi-VN').format(date)
}

function NotificationSection({ title, count, emptyMessage, summary, children }) {
  return (
    <section className="flex min-h-[14rem] min-w-0 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-4 py-3">
        <h3 className="text-sm font-bold text-slate-700">{title}</h3>
        <span className="rounded-full bg-white px-2 py-1 text-xs font-semibold text-slate-500">
          {count}
        </span>
      </div>
      {summary && <div className="border-b border-slate-100 px-4 py-2">{summary}</div>}
      {count > 0 ? children : <p className="px-4 py-3 text-xs text-slate-400">{emptyMessage}</p>}
    </section>
  )
}

export default NotificationBell
