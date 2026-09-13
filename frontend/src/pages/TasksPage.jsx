import { Fragment, useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { AnimatedTableRows, FadeIn } from '../components/animations/index.js'
import { useActionFeedback } from '../components/feedback/index.js'
import MainLayout from '../components/layout/MainLayout.jsx'
import Modal from '../components/Modal.jsx'
import { useRealtimeUpdates } from '../hooks/useRealtimeUpdates.js'
import { invalidateResource } from '../services/requestCoordinator.js'
import { listDepartments } from '../features/departments/departmentsApi.js'
import { listEmployees } from '../features/employees/employeesApi.js'
import CalendarView from '../features/tasks/components/CalendarView.jsx'
import AiOverdueTaskProposalCard from '../features/tasks/AiOverdueTaskProposalCard.jsx'
import LeadershipTasksOverview from '../features/tasks/LeadershipTasksOverview.jsx'
import ManagerTaskDirectives from '../features/tasks/ManagerTaskDirectives.jsx'
import { createTask, deleteTask, listTasks, updateTask } from '../features/tasks/tasksApi.js'
import { useAuthStore } from '../stores/authStore.js'
import {
  Button,
  Input,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Textarea,
} from '../components/ui/index.js'

const STATUS_LABELS = {
  todo: 'Chưa bắt đầu',
  in_progress: 'Đang thực hiện',
  done: 'Đã hoàn thành',
}

function getTaskStatusPresentation(task) {
  const isOverdue = task.is_overdue && task.status !== 'done'

  return {
    className: isOverdue ? 'task-status-overdue' : `task-status-${task.status}`,
    label: isOverdue ? 'Quá hạn' : STATUS_LABELS[task.status],
  }
}

const PRIORITY_LABELS = { low: 'Thấp', medium: 'Trung bình', high: 'Cao' }

const emptyForm = {
  title: '',
  description: '',
  employee_id: '',
  due_date: '',
  priority: 'medium',
  status: 'todo',
  estimated_effort_hours: '',
  required_skills: '',
  subtasks: '',
}

function TasksPage() {
  const role = useAuthStore((state) => state.role)
  return role === 'leadership' ? <LeadershipTasksOverview /> : <ManagerTasksPage />
}

function ManagerTasksPage() {
  const { role } = useAuthStore()
  const { confirmAction, notifyActionSuccess, notifyActionError } = useActionFeedback()
  const [searchParams, setSearchParams] = useSearchParams()
  const [tasks, setTasks] = useState([])
  const [employees, setEmployees] = useState([])
  const [departments, setDepartments] = useState([])
  const [filters, setFilters] = useState({
    search: '',
    employeeId: role === 'leadership' ? '' : searchParams.get('employee_id') || '',
    departmentId: role === 'leadership' ? searchParams.get('department_id') || '' : '',
    status: searchParams.get('status') || '',
    deadline: searchParams.get('deadline') || 'all',
  })
  const [form, setForm] = useState(emptyForm)
  const [modal, setModal] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')
  const [viewMode, setViewMode] = useState('list')
  const isLeadership = role === 'leadership'

  useEffect(() => {
    setFilters((current) => ({
      ...current,
      employeeId: role === 'leadership' ? '' : searchParams.get('employee_id') || '',
      departmentId: role === 'leadership' ? searchParams.get('department_id') || '' : '',
      status: searchParams.get('status') || '',
      deadline: searchParams.get('deadline') || 'all',
    }))
  }, [role, searchParams])

  const departmentMap = useMemo(
    () => Object.fromEntries(departments.map((department) => [department.id, department.name])),
    [departments],
  )

  const visibleTasks = useMemo(() => {
    const search = filters.search.trim().toLocaleLowerCase('vi-VN')
    return tasks.filter((task) => {
      const matchesSearch =
        !search ||
        [task.title, task.employee_name, task.employee_code]
          .filter(Boolean)
          .some((value) => value.toLocaleLowerCase('vi-VN').includes(search))
      const matchesEmployee =
        isLeadership || !filters.employeeId || task.employee_id === filters.employeeId
      const matchesDepartment =
        !isLeadership || !filters.departmentId || task.department_id === filters.departmentId
      const matchesStatus = !filters.status || task.status === filters.status
      const matchesDeadline =
        filters.deadline === 'all' ||
        (filters.deadline === 'overdue' && task.is_overdue) ||
        (filters.deadline === 'upcoming' && !task.is_overdue && task.status !== 'done')
      return (
        matchesSearch && matchesEmployee && matchesDepartment && matchesStatus && matchesDeadline
      )
    })
  }, [filters, isLeadership, tasks])

  const summary = useMemo(
    () => ({
      total: tasks.length,
      unfinished: tasks.filter((task) => task.status !== 'done').length,
      overdue: tasks.filter((task) => task.is_overdue).length,
      completed: tasks.filter((task) => task.status === 'done').length,
    }),
    [tasks],
  )

  async function loadData() {
    setIsLoading(true)
    setError('')
    try {
      const [taskData, employeeData, departmentData] = await Promise.all([
        listTasks(),
        listEmployees(),
        listDepartments(),
      ])
      setTasks(taskData)
      setEmployees(employeeData)
      setDepartments(departmentData)
    } catch (requestError) {
      setError(requestError.message || 'Không thể tải danh sách công việc.')
    } finally {
      setIsLoading(false)
    }
  }

  async function refreshTasks() {
    try {
      invalidateResource('tasks')
      setTasks(await listTasks())
    } catch (requestError) {
      setError(requestError.message || 'Không thể cập nhật công việc mới.')
    }
  }

  useRealtimeUpdates('tasks', handleRealtimeTaskChange)

  function handleRealtimeTaskChange(message) {
    const data = message.data || {}
    const taskId = data._id
    if (!taskId) return

    if (message.operation === 'delete') {
      setTasks((currentTasks) => currentTasks.filter((task) => task.id !== taskId))
      void refreshTasks()
      return
    }

    const employee = employees.find((item) => item.id === data.employee_id)
    if (!employee) {
      void refreshTasks()
      return
    }

    const status = data.status || 'todo'
    const task = {
      id: taskId,
      title: data.title || 'Công việc mới',
      description: data.description || null,
      subtasks: data.subtasks || [],
      employee_id: data.employee_id,
      employee_name: employee.full_name,
      employee_code: employee.employee_code,
      department_id: data.department_id || employee.department_id,
      priority: data.priority || 'medium',
      status,
      due_date: toDateOnly(data.due_date),
      is_overdue: status !== 'done' && isPastDate(data.due_date),
      completed_at: data.completed_at || null,
    }
    setTasks((currentTasks) => {
      const exists = currentTasks.some((item) => item.id === task.id)
      return exists
        ? currentTasks.map((item) => (item.id === task.id ? { ...item, ...task } : item))
        : [task, ...currentTasks]
    })
    void refreshTasks()
  }

  useEffect(() => {
    loadData()
  }, [])

  function openCreate(dueDate = '') {
    setForm({ ...emptyForm, employee_id: employees[0]?.id || '', due_date: dueDate })
    setModal({ mode: 'create' })
    setError('')
  }

  const openEdit = useCallback((task) => {
    setForm({
      title: task.title,
      description: task.description || '',
      employee_id: task.employee_id,
      due_date: task.due_date,
      priority: task.priority,
      status: task.status,
      estimated_effort_hours: task.estimated_effort_hours || '',
      required_skills: (task.required_skills || []).join(', '),
      subtasks: (task.subtasks || []).join('\n'),
    })
    setModal({ mode: 'edit', task })
    setError('')
  }, [])

  useEffect(() => {
    const taskId = searchParams.get('task')
    if (isLoading || !taskId) return

    const task = tasks.find((item) => item.id === taskId)
    if (!task) return

    openEdit(task)
    const nextSearchParams = new URLSearchParams(searchParams)
    nextSearchParams.delete('task')
    setSearchParams(nextSearchParams, { replace: true })
  }, [isLoading, openEdit, searchParams, setSearchParams, tasks])

  async function handleSubmit(event) {
    event.preventDefault()
    const payload = {
      ...form,
      estimated_effort_hours: form.estimated_effort_hours
        ? Number(form.estimated_effort_hours)
        : null,
      required_skills: form.required_skills
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
      subtasks: form.subtasks
        .split('\n')
        .map((item) => item.trim())
        .filter(Boolean),
    }
    const isCreating = modal.mode === 'create'
    const employeeName = employees.find((employee) => employee.id === form.employee_id)?.full_name
    const confirmed = await confirmAction({
      title: isCreating ? 'Xác nhận thêm công việc' : 'Xác nhận thay đổi công việc',
      description: isCreating
        ? 'Công việc sẽ được tạo và giao theo đúng thông tin bên dưới.'
        : 'Thông tin công việc sẽ được cập nhật theo nội dung bạn đã chỉnh sửa.',
      details: [
        `Tên công việc: ${payload.title}`,
        `Người phụ trách: ${employeeName || 'Chưa xác định'}`,
        `Hạn hoàn thành: ${payload.due_date || 'Chưa xác định'}`,
        `Trạng thái: ${STATUS_LABELS[payload.status] || payload.status}`,
      ],
      confirmLabel: isCreating ? 'Xác nhận thêm' : 'Xác nhận thay đổi',
    })
    if (!confirmed) return
    setIsSaving(true)
    setError('')
    try {
      const saved = isCreating
        ? await createTask(payload)
        : await updateTask(modal.task.id, payload)
      setModal(null)
      await loadData()
      notifyActionSuccess({
        title: isCreating ? 'Đã thêm công việc' : 'Đã thay đổi công việc',
        message: `Công việc “${saved?.title || payload.title}” đã được lưu thành công.`,
        details: [
          `Người phụ trách: ${saved?.employee_name || employeeName || 'Chưa xác định'}`,
          `Hạn hoàn thành: ${saved?.due_date || payload.due_date || 'Chưa xác định'}`,
        ],
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể lưu công việc.'
      setError(message)
      notifyActionError({ title: 'Chưa lưu công việc', message })
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDelete(task) {
    const confirmed = await confirmAction({
      title: 'Xác nhận xóa công việc',
      description: 'Thao tác này sẽ xóa công việc khỏi danh sách theo dõi.',
      details: [`Công việc: ${task.title}`, `Người phụ trách: ${task.employee_name}`],
      confirmLabel: 'Xóa công việc',
      variant: 'danger',
    })
    if (!confirmed) return
    setError('')
    try {
      await deleteTask(task.id)
      await loadData()
      notifyActionSuccess({
        title: 'Đã xóa công việc',
        message: `Công việc “${task.title}” đã được xóa thành công.`,
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể xóa công việc.'
      setError(message)
      notifyActionError({ title: 'Chưa xóa công việc', message })
    }
  }

  async function handleTaskDateChange(task, dueDate) {
    const confirmed = await confirmAction({
      title: 'Xác nhận thay đổi hạn hoàn thành',
      description: 'Hạn hoàn thành của công việc sẽ được cập nhật theo ngày bạn vừa chọn.',
      details: [
        `Công việc: ${task.title}`,
        `Người phụ trách: ${task.employee_name}`,
        `Hạn cũ: ${formatDate(task.due_date)}`,
        `Hạn mới: ${formatDate(dueDate)}`,
      ],
      confirmLabel: 'Xác nhận đổi hạn',
    })
    if (!confirmed) return
    const previousTasks = tasks
    setTasks((currentTasks) =>
      currentTasks.map((item) =>
        item.id === task.id
          ? {
              ...item,
              due_date: dueDate,
              is_overdue: item.status !== 'done' && isPastDate(dueDate),
            }
          : item,
      ),
    )
    try {
      await updateTask(task.id, { due_date: dueDate })
      await refreshTasks()
      notifyActionSuccess({
        title: 'Đã thay đổi hạn hoàn thành',
        message: `Công việc “${task.title}” đã được cập nhật deadline.`,
        details: [`Hạn mới: ${formatDate(dueDate)}`],
      })
    } catch (requestError) {
      setTasks(previousTasks)
      const message = requestError.message || 'Không thể cập nhật deadline.'
      setError(message)
      notifyActionError({ title: 'Chưa thay đổi deadline', message })
    }
  }

  return (
    <MainLayout>
      <FadeIn className="mx-auto max-w-7xl">
        <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="!text-caption !font-semibold !uppercase !tracking-wider !text-brand-600">
                Theo dõi tiến độ
              </p>
              <h1 className="mt-2 text-slate-900">Công việc & deadline</h1>
              <p className="mt-2 text-ink-600">
                {isLeadership
                  ? 'Theo dõi công việc và hạn hoàn thành của nhân viên trên toàn công ty.'
                  : 'Quản lý công việc của nhân viên trong phòng ban của bạn.'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <div
                className="flex rounded-xl bg-slate-100 p-1"
                role="group"
                aria-label="Chế độ xem công việc"
              >
                <button
                  type="button"
                  className={`rounded-lg px-3 py-2 text-sm font-semibold transition duration-motion-micro ease-motion-standard ${viewMode === 'list' ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}
                  onClick={() => setViewMode('list')}
                >
                  Danh sách
                </button>
                <button
                  type="button"
                  className={`rounded-lg px-3 py-2 text-sm font-semibold transition duration-motion-micro ease-motion-standard ${viewMode === 'calendar' ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}
                  onClick={() => setViewMode('calendar')}
                >
                  Lịch
                </button>
              </div>
              <Button type="button" onClick={() => openCreate()}>
                + Thêm công việc
              </Button>
            </div>
          </div>

          {error && <p className="mt-5 rounded-lg bg-red-50 p-3 !text-sm !text-red-700">{error}</p>}

          <ManagerTaskDirectives tasks={tasks} />

          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <SummaryCard label="Tổng công việc" value={summary.total} tone="blue" />
            <SummaryCard label="Chưa hoàn thành" value={summary.unfinished} tone="amber" />
            <SummaryCard label="Đang quá hạn" value={summary.overdue} tone="red" />
            <SummaryCard label="Đã hoàn thành" value={summary.completed} tone="green" />
          </div>

          <div className="mt-6 grid gap-3 rounded-xl bg-slate-50 p-4 md:grid-cols-[1.5fr_1fr_1fr_1fr]">
            <label className="text-sm font-medium text-slate-700">
              Tìm công việc hoặc nhân viên
              <Input
                className="mt-1"
                placeholder="Nhập từ khóa..."
                value={filters.search}
                onChange={(event) => setFilters({ ...filters, search: event.target.value })}
              />
            </label>
            {isLeadership ? (
              <SelectFilter
                label="Phòng ban"
                value={filters.departmentId}
                onChange={(departmentId) => setFilters({ ...filters, departmentId })}
              >
                <option value="">Tất cả phòng ban</option>
                {departments.map((department) => (
                  <option key={department.id} value={department.id}>
                    {department.name}
                  </option>
                ))}
              </SelectFilter>
            ) : (
              <SelectFilter
                label="Nhân viên"
                value={filters.employeeId}
                onChange={(employeeId) => setFilters({ ...filters, employeeId })}
              >
                <option value="">Tất cả nhân viên</option>
                {employees.map((employee) => (
                  <option key={employee.id} value={employee.id}>
                    {employee.full_name}
                  </option>
                ))}
              </SelectFilter>
            )}
            <SelectFilter
              label="Trạng thái"
              value={filters.status}
              onChange={(status) => setFilters({ ...filters, status })}
            >
              <option value="">Tất cả trạng thái</option>
              {Object.entries(STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </SelectFilter>
            <SelectFilter
              label="Hạn hoàn thành"
              value={filters.deadline}
              onChange={(deadline) => setFilters({ ...filters, deadline })}
            >
              <option value="all">Tất cả thời hạn</option>
              <option value="overdue">Đang quá hạn</option>
              <option value="upcoming">Chưa đến hạn</option>
            </SelectFilter>
          </div>

          {viewMode === 'list' ? (
            <div className="mt-6">
              <Table className="min-w-[1100px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Công việc</TableHead>
                    <TableHead>Người phụ trách</TableHead>
                    <TableHead>Phòng ban</TableHead>
                    <TableHead>Hạn hoàn thành</TableHead>
                    <TableHead>Ưu tiên</TableHead>
                    <TableHead>Trạng thái</TableHead>
                    <TableHead className="text-right">Thao tác</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoading && (
                    <TableRow>
                      <TableCell colSpan="7" className="py-8 text-center text-slate-500">
                        Đang tải...
                      </TableCell>
                    </TableRow>
                  )}
                  {!isLoading && visibleTasks.length === 0 && (
                    <TableRow>
                      <TableCell colSpan="7" className="py-8 text-center text-slate-500">
                        Chưa có công việc phù hợp.
                      </TableCell>
                    </TableRow>
                  )}
                  {!isLoading && (
                    <AnimatedTableRows>
                      {visibleTasks.map((task) => (
                        <Fragment key={task.id}>
                          <TableRow>
                            <TableCell className="max-w-[280px]">
                              <p className="font-semibold text-slate-900">{task.title}</p>
                              {task.description && (
                                <p className="mt-1 line-clamp-2 text-slate-500">
                                  {task.description}
                                </p>
                              )}
                              {task.subtasks?.length > 0 && (
                                <p className="mt-1 text-xs text-slate-400">
                                  {task.subtasks.length} việc con
                                </p>
                              )}
                            </TableCell>
                            <TableCell>
                              <p className="font-medium text-slate-900">{task.employee_name}</p>
                              <p className="text-xs text-slate-500">{task.employee_code}</p>
                            </TableCell>
                            <TableCell>{departmentMap[task.department_id] || '—'}</TableCell>
                            <TableCell>
                              <span
                                className={
                                  task.is_overdue ? 'font-semibold text-red-600' : 'text-slate-600'
                                }
                              >
                                {formatDate(task.due_date)}
                              </span>
                              {task.is_overdue && (
                                <span className="ml-2 status-danger">Quá hạn</span>
                              )}
                            </TableCell>
                            <TableCell>
                              <span className={`priority-${task.priority}`}>
                                {PRIORITY_LABELS[task.priority]}
                              </span>
                            </TableCell>
                            <TableCell>
                              {(() => {
                                const statusPresentation = getTaskStatusPresentation(task)

                                return (
                                  <span className={statusPresentation.className}>
                                    {statusPresentation.label}
                                  </span>
                                )
                              })()}
                            </TableCell>
                            <TableCell className="whitespace-nowrap text-right">
                              <button
                                type="button"
                                className="table-action"
                                onClick={() => openEdit(task)}
                              >
                                Sửa
                              </button>
                              <button
                                type="button"
                                className="table-action table-action-danger"
                                onClick={() => handleDelete(task)}
                              >
                                Xóa
                              </button>
                            </TableCell>
                          </TableRow>
                          {role === 'manager' && task.is_overdue && task.status !== 'done' && (
                            <TableRow>
                              <TableCell colSpan="7" className="pb-3 pt-0">
                                <AiOverdueTaskProposalCard
                                  task={task}
                                  role={role}
                                  employees={employees}
                                  onApplied={loadData}
                                />
                              </TableCell>
                            </TableRow>
                          )}
                        </Fragment>
                      ))}
                    </AnimatedTableRows>
                  )}
                </TableBody>
              </Table>
            </div>
          ) : (
            <CalendarView
              tasks={visibleTasks}
              onTaskClick={openEdit}
              onEmptyDayClick={openCreate}
              onTaskDrop={handleTaskDateChange}
            />
          )}
        </section>
      </FadeIn>

      {modal && (
        <Modal
          title={modal.mode === 'create' ? 'Thêm công việc' : 'Sửa công việc'}
          description="Gán công việc cho đúng nhân viên và theo dõi hạn hoàn thành."
          onClose={() => setModal(null)}
        >
          <form className="space-y-4" onSubmit={handleSubmit}>
            <FormField
              label="Tên công việc"
              value={form.title}
              onChange={(title) => setForm({ ...form, title })}
              required
            />
            <label className="block text-sm font-medium text-slate-700">
              Mô tả
              <Textarea
                className="mt-1 min-h-20"
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
              />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <SelectField
                label="Người phụ trách"
                value={form.employee_id}
                onChange={(employee_id) => setForm({ ...form, employee_id })}
                required
              >
                <option value="">Chọn nhân viên</option>
                {employees.map((employee) => (
                  <option key={employee.id} value={employee.id}>
                    {employee.full_name} ({employee.employee_code})
                  </option>
                ))}
              </SelectField>
              <FormField
                label="Hạn hoàn thành"
                type="date"
                value={form.due_date}
                onChange={(due_date) => setForm({ ...form, due_date })}
                required
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <SelectField
                label="Mức ưu tiên"
                value={form.priority}
                onChange={(priority) => setForm({ ...form, priority })}
              >
                {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </SelectField>
              <SelectField
                label="Trạng thái"
                value={form.status}
                onChange={(status) => setForm({ ...form, status })}
              >
                {Object.entries(STATUS_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </SelectField>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField
                label="Khối lượng ước tính (giờ)"
                type="number"
                value={form.estimated_effort_hours}
                onChange={(estimated_effort_hours) => setForm({ ...form, estimated_effort_hours })}
              />
              <FormField
                label="Kỹ năng cần thiết"
                value={form.required_skills}
                onChange={(required_skills) => setForm({ ...form, required_skills })}
                placeholder="Ví dụ: báo cáo, excel"
              />
            </div>
            <label className="block text-sm font-medium text-slate-700">
              Việc con <span className="font-normal text-slate-400">(mỗi dòng một việc)</span>
              <Textarea
                className="mt-1 min-h-24"
                value={form.subtasks}
                onChange={(event) => setForm({ ...form, subtasks: event.target.value })}
                placeholder="Ví dụ: Kiểm tra tài liệu"
              />
            </label>
            <div className="flex justify-end gap-3 pt-3">
              <Button type="button" variant="secondary" onClick={() => setModal(null)}>
                Hủy
              </Button>
              <Button type="submit" disabled={isSaving || !employees.length} loading={isSaving}>
                {isSaving ? 'Đang lưu...' : 'Lưu công việc'}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </MainLayout>
  )
}

function SummaryCard({ label, value, tone }) {
  const styles = {
    blue: 'bg-blue-50 text-blue-700',
    amber: 'bg-amber-50 text-amber-700',
    red: 'bg-red-50 text-red-700',
    green: 'bg-emerald-50 text-emerald-700',
  }
  return (
    <div className={`rounded-xl p-4 ${styles[tone]}`}>
      <p className="!text-sm font-medium">{label}</p>
      <p className="mt-2 text-2xl font-bold">{value}</p>
    </div>
  )
}

function SelectFilter({ label, value, onChange, children }) {
  return (
    <label className="text-sm font-medium text-slate-700">
      {label}
      <Select className="mt-1" value={value} onChange={(event) => onChange(event.target.value)}>
        {children}
      </Select>
    </label>
  )
}

function SelectField({ label, value, onChange, required = false, children }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <Select
        className="mt-1"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required={required}
      >
        {children}
      </Select>
    </label>
  )
}

function FormField({ label, value, onChange, required = false, type = 'text', placeholder }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <Input
        className="mt-1"
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required={required}
        placeholder={placeholder}
      />
    </label>
  )
}

function formatDate(value) {
  if (!value) return '—'
  const [year, month, day] = value.split('-').map(Number)
  return new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium' }).format(
    new Date(year, month - 1, day),
  )
}

function toDateOnly(value) {
  return value ? String(value).slice(0, 10) : ''
}

function isPastDate(value) {
  const dateValue = toDateOnly(value)
  if (!dateValue) return false
  return dateValue < new Date().toISOString().slice(0, 10)
}

export default TasksPage
