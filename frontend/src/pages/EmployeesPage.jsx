import { useEffect, useMemo, useState } from 'react'

import { FadeIn } from '../components/animations/index.js'
import MainLayout from '../components/layout/MainLayout.jsx'
import Modal from '../components/Modal.jsx'
import { listDepartments } from '../features/departments/departmentsApi.js'
import {
  createEmployee,
  deleteEmployee,
  listEmployees,
  updateEmployee,
} from '../features/employees/employeesApi.js'
import { useAuthStore } from '../stores/authStore.js'

const emptyForm = {
  employee_code: '',
  full_name: '',
  email: '',
  phone: '',
  position: '',
  department_id: '',
  is_active: true,
}

function EmployeesPage() {
  const { role, claims } = useAuthStore()
  const [employees, setEmployees] = useState([])
  const [departments, setDepartments] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [isSaving, setIsSaving] = useState(false)
  const isLeadership = role === 'leadership'

  const departmentMap = useMemo(
    () => Object.fromEntries(departments.map((department) => [department.id, department.name])),
    [departments],
  )

  async function loadData() {
    setIsLoading(true)
    setError('')
    try {
      const [employeeData, departmentData] = await Promise.all([listEmployees(), listDepartments()])
      setEmployees(employeeData)
      setDepartments(departmentData)
    } catch {
      setError('Không thể tải dữ liệu nhân viên.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  function openCreate() {
    setForm({
      ...emptyForm,
      department_id: isLeadership ? departments[0]?.id || '' : claims?.department_id || '',
    })
    setModal({ mode: 'create' })
  }

  function openEdit(employee) {
    setForm({
      employee_code: employee.employee_code,
      full_name: employee.full_name,
      email: employee.email || '',
      phone: employee.phone || '',
      position: employee.position,
      department_id: employee.department_id,
      is_active: employee.is_active,
    })
    setModal({ mode: 'edit', employee })
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setIsSaving(true)
    setError('')
    try {
      if (modal.mode === 'create') await createEmployee(form)
      else await updateEmployee(modal.employee.id, form)
      setModal(null)
      await loadData()
    } catch (requestError) {
      setError(requestError.message || 'Không thể lưu nhân viên.')
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDelete(employee) {
    if (!window.confirm(`Xóa nhân viên ${employee.full_name}?`)) return
    setError('')
    try {
      await deleteEmployee(employee.id)
      await loadData()
    } catch (requestError) {
      setError(requestError.message || 'Không thể xóa nhân viên.')
    }
  }

  return (
    <MainLayout>
      <FadeIn className="mx-auto max-w-7xl">
        <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200 sm:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="!text-caption !font-semibold !uppercase !tracking-wider !text-brand-600">
                Dữ liệu nhân sự
              </p>
              <h1 className="mt-2 text-slate-900">
                {isLeadership ? 'Nhân viên toàn công ty' : 'Nhân viên phòng ban'}
              </h1>
              <p className="mt-2 text-ink-600">
                {isLeadership
                  ? 'Quản lý danh sách nhân sự trên toàn công ty.'
                  : 'Danh sách được giới hạn theo phòng ban của bạn.'}
              </p>
            </div>
            <button type="button" className="primary-button" onClick={openCreate}>
              + Thêm nhân viên
            </button>
          </div>

          {error && <p className="mt-5 rounded-lg bg-red-50 p-3 !text-sm !text-red-700">{error}</p>}
          <div className="mt-6 overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Mã nhân viên</th>
                  <th className="px-4 py-3">Họ và tên</th>
                  <th className="px-4 py-3">Chức danh</th>
                  <th className="px-4 py-3">Phòng ban</th>
                  <th className="px-4 py-3">Liên hệ</th>
                  <th className="px-4 py-3">Trạng thái</th>
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
                {!isLoading && employees.length === 0 && (
                  <tr>
                    <td colSpan="7" className="px-4 py-8 text-center text-slate-500">
                      Chưa có nhân viên.
                    </td>
                  </tr>
                )}
                {!isLoading &&
                  employees.map((employee) => (
                    <tr key={employee.id} className="hover:bg-slate-50">
                      <td className="px-4 py-4 font-semibold text-brand-700">
                        {employee.employee_code}
                      </td>
                      <td className="px-4 py-4 font-medium text-slate-900">{employee.full_name}</td>
                      <td className="px-4 py-4 text-slate-600">{employee.position}</td>
                      <td className="px-4 py-4 text-slate-600">
                        {departmentMap[employee.department_id] || '—'}
                      </td>
                      <td className="px-4 py-4 text-slate-600">
                        {employee.email || employee.phone || '—'}
                      </td>
                      <td className="px-4 py-4">
                        <span className={employee.is_active ? 'status-active' : 'status-inactive'}>
                          {employee.is_active ? 'Đang làm việc' : 'Tạm dừng'}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-right">
                        <button
                          type="button"
                          className="table-action"
                          onClick={() => openEdit(employee)}
                        >
                          Sửa
                        </button>
                        <button
                          type="button"
                          className="table-action table-action-danger"
                          onClick={() => handleDelete(employee)}
                        >
                          Xóa
                        </button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </section>
      </FadeIn>

      {modal && (
        <Modal
          title={modal.mode === 'create' ? 'Thêm nhân viên' : 'Sửa nhân viên'}
          description="Thông tin nhân viên được giới hạn theo quyền truy cập của tài khoản."
          onClose={() => setModal(null)}
        >
          <form className="space-y-4" onSubmit={handleSubmit}>
            <FormField
              label="Mã nhân viên"
              value={form.employee_code}
              onChange={(employee_code) => setForm({ ...form, employee_code })}
              required
            />
            <FormField
              label="Họ và tên"
              value={form.full_name}
              onChange={(full_name) => setForm({ ...form, full_name })}
              required
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField
                label="Chức danh"
                value={form.position}
                onChange={(position) => setForm({ ...form, position })}
                required
              />
              <FormField
                label="Số điện thoại"
                value={form.phone}
                onChange={(phone) => setForm({ ...form, phone })}
              />
            </div>
            <FormField
              label="Email"
              value={form.email}
              onChange={(email) => setForm({ ...form, email })}
            />
            {isLeadership ? (
              <label className="block text-sm font-medium text-slate-700">
                Phòng ban
                <select
                  className="form-input mt-1"
                  value={form.department_id}
                  onChange={(event) => setForm({ ...form, department_id: event.target.value })}
                  required
                >
                  <option value="">Chọn phòng ban</option>
                  {departments.map((department) => (
                    <option key={department.id} value={department.id}>
                      {department.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <p className="rounded-lg bg-slate-50 p-3 !text-sm !text-slate-600">
                Phòng ban: {departmentMap[form.department_id] || 'Chưa xác định'}
              </p>
            )}
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
              />
              Đang làm việc
            </label>
            <div className="flex justify-end gap-3 pt-3">
              <button type="button" className="secondary-button" onClick={() => setModal(null)}>
                Hủy
              </button>
              <button type="submit" className="primary-button" disabled={isSaving}>
                {isSaving ? 'Đang lưu...' : 'Lưu nhân viên'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </MainLayout>
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

export default EmployeesPage
