import { Fragment, useEffect, useState } from 'react'

import { FadeIn } from '../components/animations/index.js'
import MainLayout from '../components/layout/MainLayout.jsx'
import Modal from '../components/Modal.jsx'
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
    setIsSaving(true)
    setError('')
    try {
      if (modal.mode === 'create') await createDepartment(form)
      else await updateDepartment(modal.department.id, form)
      setModal(null)
      await loadDepartments()
    } catch (requestError) {
      setError(requestError.message || 'Không thể lưu phòng ban.')
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDelete(department) {
    if (!window.confirm(`Xóa phòng ban ${department.name}?`)) return
    setError('')
    try {
      await deleteDepartment(department.id)
      if (expandedDepartmentId === department.id) setExpandedDepartmentId(null)
      await loadDepartments()
    } catch (requestError) {
      setError(requestError.message || 'Không thể xóa phòng ban.')
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
    setIsEmployeeSaving(true)
    setEmployeeError('')
    try {
      if (employeeModal.mode === 'create') await createEmployee(employeeForm)
      else await updateEmployee(employeeModal.employee.id, employeeForm)
      setEmployeeModal(null)
      await loadEmployees(employeeModal.department.id)
    } catch (requestError) {
      setEmployeeError(requestError.message || 'Không thể lưu nhân viên.')
    } finally {
      setIsEmployeeSaving(false)
    }
  }

  async function handleDeleteEmployee(employee, department) {
    if (!window.confirm(`Xóa nhân viên ${employee.full_name}?`)) return
    setEmployeeError('')
    try {
      await deleteEmployee(employee.id)
      await loadEmployees(department.id)
    } catch (requestError) {
      setEmployeeError(requestError.message || 'Không thể xóa nhân viên.')
    }
  }

  return (
    <MainLayout>
      <FadeIn className="mx-auto max-w-7xl">
        <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200 sm:p-8">
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
            <button type="button" className="primary-button" onClick={openCreate}>
              + Thêm phòng ban
            </button>
          </div>

          {error && <p className="mt-5 rounded-lg bg-red-50 p-3 !text-sm !text-red-700">{error}</p>}
          <div className="mt-6 overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Mã</th>
                  <th className="px-4 py-3">Tên phòng ban</th>
                  <th className="px-4 py-3">Chuyên môn</th>
                  <th className="px-4 py-3">Mô tả</th>
                  <th className="px-4 py-3">Trạng thái</th>
                  <th className="px-4 py-3">Nhân sự</th>
                  <th className="px-4 py-3 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading && (
                  <tr>
                    <td colSpan="7" className="px-4 py-8 text-center text-slate-500">
                      Đang tải...
                    </td>
                  </tr>
                )}
                {!isLoading && departments.length === 0 && (
                  <tr>
                    <td colSpan="7" className="px-4 py-8 text-center text-slate-500">
                      Chưa có phòng ban.
                    </td>
                  </tr>
                )}
                {!isLoading &&
                  departments.map((department) => {
                    const isExpanded = expandedDepartmentId === department.id
                    const employees = employeesByDepartment[department.id] || []
                    return (
                      <Fragment key={department.id}>
                        <tr className="hover:bg-slate-50">
                          <td className="px-4 py-4 font-semibold text-brand-700">
                            {department.code}
                          </td>
                          <td className="px-4 py-4 font-medium text-slate-900">
                            {department.name}
                          </td>
                          <td className="px-4 py-4 text-slate-600">
                            {department.specialty || '—'}
                          </td>
                          <td className="max-w-xs px-4 py-4 text-slate-600">
                            {department.description || '—'}
                          </td>
                          <td className="px-4 py-4">
                            <span
                              className={department.is_active ? 'status-active' : 'status-inactive'}
                            >
                              {department.is_active ? 'Đang hoạt động' : 'Tạm dừng'}
                            </span>
                          </td>
                          <td className="px-4 py-4">
                            <button
                              type="button"
                              className="table-action"
                              onClick={() => toggleDepartmentDetails(department)}
                              aria-expanded={isExpanded}
                            >
                              {isExpanded ? 'Thu gọn' : 'Xem chi tiết'}
                            </button>
                          </td>
                          <td className="px-4 py-4 text-right">
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
                          </td>
                        </tr>
                        {isExpanded && (
                          <tr>
                            <td colSpan="7" className="bg-slate-50 p-0">
                              <DepartmentEmployees
                                department={department}
                                employees={employees}
                                isLoading={employeeLoadingId === department.id}
                                error={employeeError}
                                onCreate={() => openCreateEmployee(department)}
                                onEdit={(employee) => openEditEmployee(employee, department)}
                                onDelete={(employee) => handleDeleteEmployee(employee, department)}
                              />
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
              </tbody>
            </table>
          </div>
        </section>
      </FadeIn>

      {modal && (
        <Modal
          title={modal.mode === 'create' ? 'Thêm phòng ban' : 'Sửa phòng ban'}
          description="Thông tin này được dùng làm phạm vi quản lý dữ liệu."
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
              <button type="button" className="secondary-button" onClick={() => setModal(null)}>
                Hủy
              </button>
              <button type="submit" className="primary-button" disabled={isSaving}>
                {isSaving ? 'Đang lưu...' : 'Lưu phòng ban'}
              </button>
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
              <button
                type="button"
                className="secondary-button"
                onClick={() => setEmployeeModal(null)}
              >
                Hủy
              </button>
              <button type="submit" className="primary-button" disabled={isEmployeeSaving}>
                {isEmployeeSaving ? 'Đang lưu...' : 'Lưu nhân viên'}
              </button>
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
        <button type="button" className="primary-button" onClick={onCreate}>
          + Thêm nhân viên
        </button>
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
        <div className="mt-4 overflow-x-auto rounded-xl bg-white ring-1 ring-slate-200">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Mã nhân viên</th>
                <th className="px-4 py-3">Họ và tên</th>
                <th className="px-4 py-3">Chức danh</th>
                <th className="px-4 py-3">Liên hệ</th>
                <th className="px-4 py-3">Trạng thái</th>
                <th className="px-4 py-3 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {employees.map((employee) => (
                <tr key={employee.id} className="hover:bg-slate-50">
                  <td className="px-4 py-4 font-semibold text-brand-700">
                    {employee.employee_code}
                  </td>
                  <td className="px-4 py-4 font-medium text-slate-900">{employee.full_name}</td>
                  <td className="px-4 py-4 text-slate-600">{employee.position}</td>
                  <td className="px-4 py-4 text-slate-600">
                    {employee.email || employee.phone || '—'}
                  </td>
                  <td className="px-4 py-4">
                    <span className={employee.is_active ? 'status-active' : 'status-inactive'}>
                      {employee.is_active ? 'Đang làm việc' : 'Tạm dừng'}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-right">
                    <button type="button" className="table-action" onClick={() => onEdit(employee)}>
                      Sửa
                    </button>
                    <button
                      type="button"
                      className="table-action table-action-danger"
                      onClick={() => onDelete(employee)}
                    >
                      Xóa
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function FormField({ label, value, onChange, required = false }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <input
        className="form-input mt-1"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required={required}
      />
    </label>
  )
}

export default DepartmentsPage
