export const ROLE_LABELS = {
  manager: 'Quản lý phòng ban',
  leadership: 'Lãnh đạo',
}

const ROLE_NAVIGATION = {
  manager: [
    { key: 'overview', label: 'Tổng quan', href: '/manager', icon: 'dashboard' },
    {
      key: 'performance',
      label: 'Hiệu suất nhân viên',
      href: '/manager/performance',
      icon: 'performance',
    },
    {
      key: 'alerts',
      label: 'Cảnh báo ngưỡng bất lợi',
      href: '/manager/alerts',
      icon: 'alert',
    },
    {
      key: 'directives',
      label: 'Trung tâm chỉ thị',
      href: '/manager/directives',
      icon: 'directives',
    },
    {
      key: 'employees',
      label: 'Nhân viên phòng ban',
      href: '/manager/employees',
      icon: 'employees',
    },
    { key: 'tasks', label: 'Công việc & deadline', href: '/manager/tasks', icon: 'tasks' },
    { key: 'assistant', label: 'Trợ lý AI', href: '/manager/assistant', icon: 'assistant' },
  ],
  leadership: [
    { key: 'overview', label: 'Tổng quan', href: '/leadership', icon: 'dashboard' },
    {
      key: 'departments',
      label: 'Phòng ban & nhân viên',
      href: '/leadership/departments',
      icon: 'departments',
    },
    {
      key: 'alerts',
      label: 'Cảnh báo ngưỡng toàn công ty',
      href: '/leadership/alerts',
      icon: 'alert',
    },
    {
      key: 'directives',
      label: 'Trung tâm chỉ thị',
      href: '/leadership/directives',
      icon: 'directives',
    },
    {
      key: 'managers',
      label: 'Đánh giá phòng ban',
      href: '/leadership/department-evaluations',
      icon: 'performance',
    },
    { key: 'tasks', label: 'Công việc & deadline', href: '/leadership/tasks', icon: 'tasks' },
    { key: 'assistant', label: 'Trợ lý AI', href: '/leadership/assistant', icon: 'assistant' },
  ],
}

export function getNavigationItems(role) {
  return ROLE_NAVIGATION[role] || []
}
