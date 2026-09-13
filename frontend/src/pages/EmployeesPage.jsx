import { useEffect, useMemo, useState } from 'react'

import { AnimatedTableRows, FadeIn } from '../components/animations/index.js'
import { useActionFeedback } from '../components/feedback/index.js'
import MainLayout from '../components/layout/MainLayout.jsx'
import Modal from '../components/Modal.jsx'
import {
  Button,
  Input,
  Select,
  StatusBadge,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/index.js'
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
  skills: '',
  department_id: '',
  is_active: true,
}

function EmployeesPage() {
  const { role, claims } = useAuthStore()
  const { confirmAction, notifyActionSuccess, notifyActionError } = useActionFeedback()
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
      skills: (employee.skills || []).join(', '),
      department_id: employee.department_id,
      is_active: employee.is_active,
    })
    setModal({ mode: 'edit', employee })
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const payload = {
      ...form,
      skills: form.skills
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
    }
    const isCreating = modal.mode === 'create'
    const departmentName = departmentMap[payload.department_id] || 'Chưa xác định'
    const confirmed = await confirmAction({
      title: isCreating ? 'Xác nhận thêm nhân viên' : 'Xác nhận thay đổi nhân viên',
      description: isCreating
        ? 'Hồ sơ nhân viên sẽ được tạo theo đúng thông tin bên dưới.'
        : 'Thông tin hồ sơ sẽ được cập nhật theo nội dung bạn đã chỉnh sửa.',
      details: [
        `Họ và tên: ${payload.full_name}`,
        `Mã nhân viên: ${payload.employee_code}`,
        `Phòng ban: ${departmentName}`,
        `Email: ${payload.email || 'Chưa cập nhật'}`,
        `Số điện thoại: ${payload.phone || 'Chưa cập nhật'}`,
        `Chức danh: ${payload.position}`,
        `Trạng thái: ${payload.is_active ? 'Đang làm việc' : 'Tạm dừng'}`,
      ],
      confirmLabel: isCreating ? 'Xác nhận thêm' : 'Xác nhận thay đổi',
    })
    if (!confirmed) return
    setIsSaving(true)
    setError('')
    try {
      const saved = isCreating
        ? await createEmployee(payload)
        : await updateEmployee(modal.employee.id, payload)
      setModal(null)
      await loadData()
      notifyActionSuccess({
        title: isCreating ? 'Đã thêm nhân viên' : 'Đã thay đổi thông tin nhân viên',
        message: `Hồ sơ của ${saved?.full_name || payload.full_name} đã được lưu thành công.`,
        details: [
          `Phòng ban: ${departmentMap[saved?.department_id || payload.department_id] || departmentName}`,
          `Email: ${saved?.email || payload.email || 'Chưa cập nhật'}`,
          `Số điện thoại: ${saved?.phone || payload.phone || 'Chưa cập nhật'}`,
        ],
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể lưu nhân viên.'
      setError(message)
      notifyActionError({ title: 'Chưa lưu hồ sơ nhân viên', message })
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDelete(employee) {
    const confirmed = await confirmAction({
      title: 'Xác nhận xóa nhân viên',
      description: 'Hồ sơ nhân viên sẽ bị xóa khỏi danh sách quản lý.',
      details: [
        `Họ và tên: ${employee.full_name}`,
        `Mã nhân viên: ${employee.employee_code}`,
        `Phòng ban: ${departmentMap[employee.department_id] || 'Chưa xác định'}`,
      ],
      confirmLabel: 'Xóa nhân viên',
      variant: 'danger',
    })
    if (!confirmed) return
    setError('')
    try {
      await deleteEmployee(employee.id)
      await loadData()
      notifyActionSuccess({
        title: 'Đã xóa nhân viên',
        message: `Hồ sơ của ${employee.full_name} đã được xóa thành công.`,
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể xóa nhân viên.'
      setError(message)
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
            <Button type="button" onClick={openCreate}>
              + Thêm nhân viên
            </Button>
          </div>

          {error && <p className="mt-5 rounded-lg bg-red-50 p-3 !text-sm !text-red-700">{error}</p>}
          <div className="mt-6">
            <Table className="min-w-[900px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Mã nhân viên</TableHead>
                  <TableHead>Họ và tên</TableHead>
                  <TableHead>Chức danh</TableHead>
                  <TableHead>Phòng ban</TableHead>
                  <TableHead>Liên hệ</TableHead>
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
                {!isLoading && employees.length === 0 && (
                  <TableRow>
                    <TableCell colSpan="7" className="py-8 text-center text-slate-500">
                      Chưa có nhân viên.
                    </TableCell>
                  </TableRow>
                )}
                {!isLoading && (
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
                        <TableCell>{departmentMap[employee.department_id] || '—'}</TableCell>
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
                        </TableCell>
                      </TableRow>
                    ))}
                  </AnimatedTableRows>
                )}
              </TableBody>
            </Table>
          </div>
        </section>
      </FadeIn>

      {modal && (
        <Modal
          title={modal.mode === 'create' ? 'Thêm nhân viên' : 'Sửa nhân viên'}
          description="Cập nhật thông tin hồ sơ nhân viên."
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
            <FormField
              label="Kỹ năng"
              value={form.skills}
              onChange={(skills) => setForm({ ...form, skills })}
              placeholder="Ví dụ: excel, báo cáo, chăm sóc khách hàng"
            />
            {isLeadership ? (
              <label className="block text-sm font-medium text-slate-700">
                Phòng ban
                <Select
                  className="mt-1"
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
                </Select>
              </label>
            ) : (
              <p className="rounded-lg bg-slate-50 p-3 !text-sm !text-slate-600">
                Phòng ban: {departmentMap[form.department_id] || 'Chưa xác định'}
              </p>
            )}
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
              />
              Đang làm việc
            </label>
            <div className="flex justify-end gap-3 pt-3">
              <Button type="button" variant="secondary" onClick={() => setModal(null)}>
                Hủy
              </Button>
              <Button type="submit" disabled={isSaving} loading={isSaving}>
                {isSaving ? 'Đang lưu...' : 'Lưu nhân viên'}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </MainLayout>
  )
}

function FormField({ label, value, onChange, required = false, placeholder }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <Input
        className="mt-1"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required={required}
        placeholder={placeholder}
      />
    </label>
  )
}

export default EmployeesPage
