import { Fragment, useEffect, useState } from 'react'

import { AnimatedTableRows, FadeIn } from '../components/animations/index.js'
import { useActionFeedback } from '../components/feedback/index.js'
import MainLayout from '../components/layout/MainLayout.jsx'
import Modal from '../components/Modal.jsx'
import {
  Button,
  Input,
  StatusBadge,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/index.js'
import {
  createDepartment,
  deleteDepartment,
  listDepartments,
  updateDepartment,
} from '../features/departments/departmentsApi.js'
import {
  createEmployee,
  deleteEmployee,
  listEmployees,
  updateEmployee,
} from '../features/employees/employeesApi.js'

const emptyDepartmentForm = { name: '', code: '', specialty: '', description: '', is_active: true }
const emptyEmployeeForm = {
  employee_code: '',
  full_name: '',
  email: '',
  phone: '',
  position: '',
  department_id: '',
  is_active: true,
}

function DepartmentsPage() {
  const { confirmAction, notifyActionSuccess, notifyActionError } = useActionFeedback()
  const [departments, setDepartments] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(emptyDepartmentForm)
  const [isSaving, setIsSaving] = useState(false)
  const [expandedDepartmentId, setExpandedDepartmentId] = useState(null)
  const [employeesByDepartment, setEmployeesByDepartment] = useState({})
  const [employeeLoadingId, setEmployeeLoadingId] = useState(null)
  const [employeeError, setEmployeeError] = useState('')
  const [employeeModal, setEmployeeModal] = useState(null)
  const [employeeForm, setEmployeeForm] = useState(emptyEmployeeForm)
  const [isEmployeeSaving, setIsEmployeeSaving] = useState(false)

  async function loadDepartments() {
    setIsLoading(true)
    setError('')
    try {
      setDepartments(await listDepartments())
    } catch {
      setError('Không thể tải danh sách phòng ban.')
    } finally {
      setIsLoading(false)
    }
  }

  async function loadEmployees(departmentId) {
    setEmployeeLoadingId(departmentId)
    setEmployeeError('')
    try {
      const data = await listEmployees(departmentId)
      setEmployeesByDepartment((current) => ({ ...current, [departmentId]: data || [] }))
    } catch {
      setEmployeeError('Không thể tải danh sách nhân viên của phòng ban này.')
    } finally {
      setEmployeeLoadingId(null)
    }
  }

  useEffect(() => {
    loadDepartments()
  }, [])

  function openCreate() {
    setForm(emptyDepartmentForm)
    setModal({ mode: 'create' })
  }

  function openEdit(department) {
    setForm({
      name: department.name,
      code: department.code,
      specialty: department.specialty || '',
      description: department.description || '',
      is_active: department.is_active,
    })
    setModal({ mode: 'edit', department })
  }

  async function toggleDepartmentDetails(department) {
    if (expandedDepartmentId === department.id) {
      setExpandedDepartmentId(null)
      return
    }

    setExpandedDepartmentId(department.id)
    if (!Object.prototype.hasOwnProperty.call(employeesByDepartment, department.id)) {
      await loadEmployees(department.id)
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const isCreating = modal.mode === 'create'
    const confirmed = await confirmAction({
      title: isCreating ? 'Xác nhận thêm phòng ban' : 'Xác nhận thay đổi phòng ban',
      description: isCreating
        ? 'Phòng ban sẽ được tạo theo đúng thông tin bên dưới.'
        : 'Thông tin phòng ban sẽ được cập nhật theo nội dung bạn đã chỉnh sửa.',
      details: [
        `Tên phòng ban: ${form.name}`,
        `Mã phòng ban: ${form.code}`,
        `Chuyên môn: ${form.specialty || 'Chưa cập nhật'}`,
        `Trạng thái: ${form.is_active ? 'Đang hoạt động' : 'Tạm dừng'}`,
      ],
      confirmLabel: isCreating ? 'Xác nhận thêm' : 'Xác nhận thay đổi',
    })
    if (!confirmed) return
    setIsSaving(true)
    setError('')
    try {
      const saved = isCreating
        ? await createDepartment(form)
        : await updateDepartment(modal.department.id, form)
      setModal(null)
      await loadDepartments()
      notifyActionSuccess({
        title: isCreating ? 'Đã thêm phòng ban' : 'Đã thay đổi phòng ban',
        message: `Phòng ban “${saved?.name || form.name}” đã được lưu thành công.`,
        details: [`Mã phòng ban: ${saved?.code || form.code}`],
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể lưu phòng ban.'
      setError(message)
      notifyActionError({ title: 'Chưa lưu phòng ban', message })
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDelete(department) {
    const confirmed = await confirmAction({
      title: 'Xác nhận xóa phòng ban',
      description: 'Phòng ban sẽ bị xóa khỏi danh sách quản lý.',
      details: [`Tên phòng ban: ${department.name}`, `Mã phòng ban: ${department.code}`],
      confirmLabel: 'Xóa phòng ban',
      variant: 'danger',
    })
    if (!confirmed) return
    setError('')
    try {
      await deleteDepartment(department.id)
      if (expandedDepartmentId === department.id) setExpandedDepartmentId(null)
      await loadDepartments()
      notifyActionSuccess({
        title: 'Đã xóa phòng ban',
        message: `Phòng ban “${department.name}” đã được xóa thành công.`,
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể xóa phòng ban.'
      setError(message)
      notifyActionError({ title: 'Chưa xóa phòng ban', message })
    }
  }

  function openCreateEmployee(department) {
    setEmployeeForm({ ...emptyEmployeeForm, department_id: department.id })
    setEmployeeModal({ mode: 'create', department })
  }

  function openEditEmployee(employee, department) {
    setEmployeeForm({
      employee_code: employee.employee_code,
      full_name: employee.full_name,
      email: employee.email || '',
      phone: employee.phone || '',
      position: employee.position,
      department_id: department.id,
      is_active: employee.is_active,
    })
    setEmployeeModal({ mode: 'edit', employee, department })
  }

  async function handleEmployeeSubmit(event) {
    event.preventDefault()
    const isCreating = employeeModal.mode === 'create'
    const confirmed = await confirmAction({
      title: isCreating ? 'Xác nhận thêm nhân viên' : 'Xác nhận thay đổi nhân viên',
      description: isCreating
        ? 'Nhân viên sẽ được thêm vào phòng ban theo thông tin bên dưới.'
        : 'Thông tin nhân viên sẽ được cập nhật theo nội dung bạn đã chỉnh sửa.',
      details: [
        `Họ và tên: ${employeeForm.full_name}`,
        `Mã nhân viên: ${employeeForm.employee_code}`,
        `Phòng ban: ${employeeModal.department.name}`,
        `Email: ${employeeForm.email || 'Chưa cập nhật'}`,
        `Số điện thoại: ${employeeForm.phone || 'Chưa cập nhật'}`,
        `Chức danh: ${employeeForm.position}`,
        `Trạng thái: ${employeeForm.is_active ? 'Đang làm việc' : 'Tạm dừng'}`,
      ],
      confirmLabel: isCreating ? 'Xác nhận thêm' : 'Xác nhận thay đổi',
    })
    if (!confirmed) return
    setIsEmployeeSaving(true)
    setEmployeeError('')
    try {
      const saved = isCreating
        ? await createEmployee(employeeForm)
        : await updateEmployee(employeeModal.employee.id, employeeForm)
      setEmployeeModal(null)
      await loadEmployees(employeeModal.department.id)
      notifyActionSuccess({
        title: isCreating ? 'Đã thêm nhân viên' : 'Đã thay đổi thông tin nhân viên',
        message: `Hồ sơ của ${saved?.full_name || employeeForm.full_name} đã được lưu thành công.`,
        details: [
          `Phòng ban: ${employeeModal.department.name}`,
          `Email: ${saved?.email || employeeForm.email || 'Chưa cập nhật'}`,
          `Số điện thoại: ${saved?.phone || employeeForm.phone || 'Chưa cập nhật'}`,
        ],
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể lưu nhân viên.'
      setEmployeeError(message)
      notifyActionError({ title: 'Chưa lưu hồ sơ nhân viên', message })
    } finally {
      setIsEmployeeSaving(false)
    }
  }

  async function handleDeleteEmployee(employee, department) {
    const confirmed = await confirmAction({
      title: 'Xác nhận xóa nhân viên',
      description: 'Hồ sơ nhân viên sẽ bị xóa khỏi phòng ban này.',
      details: [
        `Họ và tên: ${employee.full_name}`,
        `Mã nhân viên: ${employee.employee_code}`,
        `Phòng ban: ${department.name}`,
      ],
      confirmLabel: 'Xóa nhân viên',
      variant: 'danger',
    })
    if (!confirmed) return
    setEmployeeError('')
    try {
      await deleteEmployee(employee.id)
      await loadEmployees(department.id)
      notifyActionSuccess({
        title: 'Đã xóa nhân viên',
        message: `Hồ sơ của ${employee.full_name} đã được xóa thành công.`,
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể xóa nhân viên.'
      setEmployeeError(message)
      notifyActionError({ title: 'Chưa xóa nhân viên', message })
    }
  }

  return (
    <MainLayout>
      <FadeIn className="mx-auto max-w-7xl">
        <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="!text-caption !font-semibold !uppercase !tracking-wider !text-brand-600">
                Dữ liệu nền
              </p>
              <h1 className="mt-2 text-slate-900">Phòng ban & nhân viên</h1>
              <p className="mt-2 text-ink-600">
                Quản lý phòng ban và xem nhân viên theo từng phòng khi cần.
              </p>
            </div>
            <Button type="button" onClick={openCreate}>
              + Thêm phòng ban
            </Button>
          </div>

          {error && <p className="mt-5 rounded-lg bg-red-50 p-3 !text-sm !text-red-700">{error}</p>}
          <div className="mt-6">
            <Table className="min-w-[860px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Mã</TableHead>
                  <TableHead>Tên phòng ban</TableHead>
                  <TableHead>Chuyên môn</TableHead>
                  <TableHead>Mô tả</TableHead>
                  <TableHead>Trạng thái</TableHead>
                  <TableHead>Nhân sự</TableHead>
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
                {!isLoading && departments.length === 0 && (
                  <TableRow>
                    <TableCell colSpan="7" className="py-8 text-center text-slate-500">
                      Chưa có phòng ban.
                    </TableCell>
                  </TableRow>
                )}
                {!isLoading && (
                  <AnimatedTableRows>
                    {departments.map((department) => {
                      const isExpanded = expandedDepartmentId === department.id
                      const employees = employeesByDepartment[department.id] || []
                      return (
                        <Fragment key={department.id}>
                          <TableRow>
                            <TableCell className="font-semibold text-brand-700">
                              {department.code}
                            </TableCell>
                            <TableCell className="font-medium text-slate-900">
                              {department.name}
                            </TableCell>
                            <TableCell>{department.specialty || '—'}</TableCell>
                            <TableCell className="max-w-xs">
                              {department.description || '—'}
                            </TableCell>
                            <TableCell>
                              <StatusBadge
                                status={department.is_active ? 'active' : 'inactive'}
                                label={department.is_active ? 'Đang hoạt động' : 'Tạm dừng'}
                              />
                            </TableCell>
                            <TableCell>
                              <button
                                type="button"
                                className="table-action"
                                onClick={() => toggleDepartmentDetails(department)}
                                aria-expanded={isExpanded}
                              >
                                {isExpanded ? 'Thu gọn' : 'Xem chi tiết'}
                              </button>
                            </TableCell>
                            <TableCell className="text-right">
                              <button
                                type="button"
                                className="table-action"
                                onClick={() => openEdit(department)}
                              >
                                Sửa
                              </button>
                              <button
                                type="button"
                                className="table-action table-action-danger"
                                onClick={() => handleDelete(department)}
                              >
                                Xóa
                              </button>
                            </TableCell>
                          </TableRow>
                          {isExpanded && (
                            <TableRow>
                              <TableCell colSpan="7" className="bg-slate-50 p-0">
                                <DepartmentEmployees
                                  department={department}
                                  employees={employees}
                                  isLoading={employeeLoadingId === department.id}
                                  error={employeeError}
                                  onCreate={() => openCreateEmployee(department)}
                                  onEdit={(employee) => openEditEmployee(employee, department)}
                                  onDelete={(employee) =>
                                    handleDeleteEmployee(employee, department)
                                  }
                                />
                              </TableCell>
                            </TableRow>
                          )}
                        </Fragment>
                      )
                    })}
                  </AnimatedTableRows>
                )}
              </TableBody>
            </Table>
          </div>
        </section>
      </FadeIn>

      {modal && (
        <Modal
          title={modal.mode === 'create' ? 'Thêm phòng ban' : 'Sửa phòng ban'}
          description="Thiết lập thông tin phòng ban và phạm vi quản lý."
          onClose={() => setModal(null)}
        >
          <form className="space-y-4" onSubmit={handleSubmit}>
            <FormField
              label="Tên phòng ban"
              value={form.name}
              onChange={(name) => setForm({ ...form, name })}
              required
            />
            <FormField
              label="Mã phòng ban"
              value={form.code}
              onChange={(code) => setForm({ ...form, code: code.toUpperCase() })}
              required
            />
            <FormField
              label="Chuyên môn"
              value={form.specialty}
              onChange={(specialty) => setForm({ ...form, specialty })}
            />
            <FormField
              label="Mô tả"
              value={form.description}
              onChange={(description) => setForm({ ...form, description })}
            />
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
              />
              Đang hoạt động
            </label>
            <div className="flex justify-end gap-3 pt-3">
              <Button type="button" variant="secondary" onClick={() => setModal(null)}>
                Hủy
              </Button>
              <Button type="submit" disabled={isSaving} loading={isSaving}>
                {isSaving ? 'Đang lưu...' : 'Lưu phòng ban'}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {employeeModal && (
        <Modal
          title={employeeModal.mode === 'create' ? 'Thêm nhân viên' : 'Sửa nhân viên'}
          description={`Nhân viên thuộc phòng ${employeeModal.department.name}.`}
          onClose={() => setEmployeeModal(null)}
        >
          <form className="space-y-4" onSubmit={handleEmployeeSubmit}>
            <FormField
              label="Mã nhân viên"
              value={employeeForm.employee_code}
              onChange={(employee_code) => setEmployeeForm({ ...employeeForm, employee_code })}
              required
            />
            <FormField
              label="Họ và tên"
              value={employeeForm.full_name}
              onChange={(full_name) => setEmployeeForm({ ...employeeForm, full_name })}
              required
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField
                label="Chức danh"
                value={employeeForm.position}
                onChange={(position) => setEmployeeForm({ ...employeeForm, position })}
                required
              />
              <FormField
                label="Số điện thoại"
                value={employeeForm.phone}
                onChange={(phone) => setEmployeeForm({ ...employeeForm, phone })}
              />
            </div>
            <FormField
              label="Email"
              value={employeeForm.email}
              onChange={(email) => setEmployeeForm({ ...employeeForm, email })}
            />
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={employeeForm.is_active}
                onChange={(event) =>
                  setEmployeeForm({ ...employeeForm, is_active: event.target.checked })
                }
              />
              Đang làm việc
            </label>
            <div className="flex justify-end gap-3 pt-3">
              <Button type="button" variant="secondary" onClick={() => setEmployeeModal(null)}>
                Hủy
              </Button>
              <Button type="submit" disabled={isEmployeeSaving} loading={isEmployeeSaving}>
                {isEmployeeSaving ? 'Đang lưu...' : 'Lưu nhân viên'}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </MainLayout>
  )
}

function DepartmentEmployees({
  department,
  employees,
  isLoading,
  error,
  onCreate,
  onEdit,
  onDelete,
}) {
  return (
    <div className="p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-slate-900">Nhân viên phòng {department.name}</h2>
          <p className="mt-1 text-sm text-slate-500">
            Danh sách chỉ hiển thị sau khi bạn mở chi tiết phòng ban.
          </p>
        </div>
        <Button type="button" onClick={onCreate}>
          + Thêm nhân viên
        </Button>
      </div>

      {error && <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {isLoading ? (
        <p className="mt-4 rounded-xl bg-white p-6 text-center text-sm text-slate-500">
          Đang tải nhân viên...
        </p>
      ) : employees.length === 0 ? (
        <p className="mt-4 rounded-xl bg-white p-6 text-center text-sm text-slate-500">
          Chưa có nhân viên trong phòng ban này.
        </p>
      ) : (
        <div className="mt-4">
          <Table className="min-w-[760px]">
            <TableHeader>
              <TableRow>
                <TableHead>Mã nhân viên</TableHead>
                <TableHead>Họ và tên</TableHead>
                <TableHead>Chức danh</TableHead>
                <TableHead>Liên hệ</TableHead>
                <TableHead>Trạng thái</TableHead>
                <TableHead className="text-right">Thao tác</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <AnimatedTableRows>
                {employees.map((employee) => (
                  <TableRow key={employee.id}>
                    <TableCell className="font-semibold text-brand-700">
                      {employee.employee_code}
                    </TableCell>
                    <TableCell className="font-medium text-slate-900">
                      {employee.full_name}
                    </TableCell>
                    <TableCell>{employee.position}</TableCell>
                    <TableCell>
                      <div>{employee.email || 'Chưa cập nhật email'}</div>
                      <div className="mt-1 text-xs text-slate-500">
                        {employee.phone || 'Chưa cập nhật số điện thoại'}
                      </div>
                    </TableCell>
                    <TableCell>
                      <StatusBadge
                        status={employee.is_active ? 'active' : 'inactive'}
                        label={employee.is_active ? 'Đang làm việc' : 'Tạm dừng'}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <button
                        type="button"
                        className="table-action"
                        onClick={() => onEdit(employee)}
                      >
                        Sửa
                      </button>
                      <button
                        type="button"
                        className="table-action table-action-danger"
                        onClick={() => onDelete(employee)}
                      >
                        Xóa
                      </button>
                    </TableCell>
                  </TableRow>
                ))}
              </AnimatedTableRows>
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}

function FormField({ label, value, onChange, required = false }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <Input
        className="mt-1"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required={required}
      />
    </label>
  )
}

export default DepartmentsPage
